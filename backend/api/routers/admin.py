"""Club administrator: teams, staff and academy players. One deployment is one club.

Staff and players are invited by email and choose their own password; a player under
the age of digital consent also gets a parent invitation, and nothing about their health
is stored until that parent agrees (api.deps.has_consent).
"""

from __future__ import annotations

import csv
import io
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api import clock
from api.db import get_db
from api.deps import CurrentUser, age_on, audit, require
from api.routers.auth import MIN_AGE, _email, _taken
from api.services import accounts
from api.settings import settings
from domain.enums import Pathway, Position, Role
from domain.models import AuthToken, Guardian, Player, Squad, StaffMember, UserAccount
from pathway import service as pathway

router = APIRouter(prefix="/api/admin", tags=["admin"])

ADMIN = require(Role.ADMIN)
CLUB_TEAMS = Squad.age_group != "SELF"  # self-guided players each have a squad of their own


def _club(db: Session) -> str:
    return db.scalars(select(Squad.club).where(CLUB_TEAMS, Squad.club.is_not(None))).first() or "Your club"


def _invite_pending(db: Session, acc: UserAccount | None) -> bool:
    return acc is not None and acc.password_hash == accounts.UNUSABLE_PASSWORD


@router.get("/overview")
def overview(user: CurrentUser = Depends(ADMIN), db: Session = Depends(get_db)) -> dict:
    today = clock.today()
    squads = list(db.scalars(select(Squad).where(CLUB_TEAMS).order_by(Squad.name)))
    counts = dict(
        db.execute(select(Player.squad_id, func.count()).where(Player.pathway == Pathway.ACADEMY.value).group_by(Player.squad_id)).all()
    )
    staff_rows = []
    for s in db.scalars(select(StaffMember).order_by(StaffMember.name)):
        acc = db.scalars(select(UserAccount).where(UserAccount.staff_id == s.id)).first()
        staff_rows.append(
            {
                "id": s.id,
                "account_id": acc.id if acc else None,
                "name": s.name,
                "email": s.email,
                "role": s.role.value,
                "squad_id": s.squad_id,
                "invite_pending": _invite_pending(db, acc),
                "active": bool(acc and acc.active),
                "mfa": bool(acc and acc.mfa_enabled_at),
            }
        )
    players = []
    for p in db.scalars(select(Player).where(Player.pathway == Pathway.ACADEMY.value).order_by(Player.display_name)):
        acc = db.scalars(select(UserAccount).where(UserAccount.player_id == p.id)).first()
        minor = age_on(p.birth_date, today) < settings.digital_consent_age
        parent_joined = any(g.invite_code is None for g in p.guardians)
        players.append(
            {
                "id": p.id,
                "account_id": acc.id if acc else None,
                "name": p.display_name,
                "email": p.email,
                "squad_id": p.squad_id,
                "position": p.position,
                "age": round(age_on(p.birth_date, today), 1),
                "invite_pending": _invite_pending(db, acc),
                "needs_parent": minor and not parent_joined,
            }
        )
    audit(db, user, "read", "club_overview", None)
    db.commit()
    return {
        "club": _club(db),
        "email_mode": settings.mail,
        "squads": [
            {
                "id": s.id,
                "name": s.name,
                "age_group": s.age_group,
                "competition": s.competition,
                "players": counts.get(s.id, 0),
                "has_training_week": bool(s.training_week),
            }
            for s in squads
        ],
        "staff": staff_rows,
        "players": players,
    }


# --------------------------------------------------------------------------- teams


class SquadIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    age_group: str = Field(min_length=2, max_length=10, description="U13 ... U19, or SEN")
    club: str | None = Field(default=None, max_length=100)

    @field_validator("age_group")
    @classmethod
    def _age_group(cls, v: str) -> str:
        v = v.strip().upper()
        if v == "SELF":
            raise ValueError("SELF is reserved for self-guided players")
        return v


@router.post("/squads", status_code=201)
def create_squad(body: SquadIn, user: CurrentUser = Depends(ADMIN), db: Session = Depends(get_db)) -> dict:
    squad = Squad(name=body.name.strip(), age_group=body.age_group, club=(body.club or "").strip() or _club(db))
    db.add(squad)
    db.flush()
    audit(db, user, "create", "squad", squad.id, name=squad.name)
    db.commit()
    return {"id": squad.id, "name": squad.name, "age_group": squad.age_group, "club": squad.club}


@router.patch("/squads/{squad_id}")
def rename_squad(squad_id: str, body: SquadIn, user: CurrentUser = Depends(ADMIN), db: Session = Depends(get_db)) -> dict:
    squad = _team(db, squad_id)
    squad.name, squad.age_group = body.name.strip(), body.age_group
    if body.club:
        squad.club = body.club.strip()
    audit(db, user, "update", "squad", squad.id, name=squad.name)
    db.commit()
    return {"id": squad.id, "name": squad.name, "age_group": squad.age_group, "club": squad.club}


def _team(db: Session, squad_id: str | None) -> Squad:
    squad = db.get(Squad, squad_id) if squad_id else None
    if squad is None or squad.age_group == "SELF":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not found")
    return squad


# --------------------------------------------------------------------------- staff


class StaffIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: str
    role: Literal["coach", "physio"]
    squad_id: str

    @field_validator("email")
    @classmethod
    def _check_email(cls, v: str) -> str:
        return _email(v)


@router.post("/staff", status_code=201)
def invite_staff(body: StaffIn, user: CurrentUser = Depends(ADMIN), db: Session = Depends(get_db)) -> dict:
    squad = _team(db, body.squad_id)
    if _taken(db, body.email) or db.scalars(select(StaffMember.id).where(StaffMember.email == body.email)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    role = Role(body.role)
    staff = StaffMember(name=body.name.strip(), email=body.email, role=role, squad_id=squad.id)
    db.add(staff)
    db.flush()
    acc = UserAccount(email=body.email, password_hash=accounts.UNUSABLE_PASSWORD, role=role, staff_id=staff.id)
    db.add(acc)
    db.flush()
    accounts.send_invite(db, acc, squad.club or _club(db), squad.name)
    audit(db, user, "invite", "staff_member", staff.id, role=role.value, squad=squad.id)
    db.commit()
    return {"id": staff.id, "account_id": acc.id, "name": staff.name, "email": staff.email, "role": role.value, "squad_id": squad.id}


class StaffChange(BaseModel):
    squad_id: str | None = None
    active: bool | None = None
    reset_mfa: bool = False  # lost phone: two-step sign-in off, they set it up again


@router.patch("/staff/{staff_id}")
def change_staff(staff_id: str, body: StaffChange, user: CurrentUser = Depends(ADMIN), db: Session = Depends(get_db)) -> dict:
    """Move to another team, or switch the account off when someone leaves the club (their
    approvals and notes stay on record). A switched-off account is signed out at once."""
    staff = db.get(StaffMember, staff_id)
    if staff is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Staff member not found")
    if body.squad_id is not None:
        staff.squad_id = _team(db, body.squad_id).id
    acc = db.scalars(select(UserAccount).where(UserAccount.staff_id == staff.id)).first()
    if body.active is not None and acc is not None:
        acc.active = body.active
        acc.token_version = (acc.token_version or 0) + 1
    if body.reset_mfa and acc is not None:
        acc.mfa_secret = acc.mfa_enabled_at = acc.mfa_recovery = None
    audit(db, user, "update", "staff_member", staff.id, squad=staff.squad_id, active=body.active, reset_mfa=body.reset_mfa)
    db.commit()
    return {"id": staff.id, "squad_id": staff.squad_id, "active": bool(acc and acc.active)}


# --------------------------------------------------------------------------- academy players


class PlayerIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    birth_date: date
    sex: Literal["male", "female"] = "male"
    position: Position = Position.MIDFIELDER
    email: str | None = None
    guardian_email: str | None = None

    @field_validator("email", "guardian_email", mode="before")
    @classmethod
    def _optional_email(cls, v: str | None) -> str | None:
        return _email(v) if v and str(v).strip() else None


def _add_player(db: Session, body: PlayerIn, squad: Squad, user: CurrentUser) -> dict:
    """Validate and add one academy player (shared by the form and the CSV import)."""
    today = clock.today()
    age = age_on(body.birth_date, today)
    if not MIN_AGE <= age < 40:
        raise ValueError(f"Players are {MIN_AGE} or older")
    minor = age < settings.digital_consent_age
    if minor and not body.guardian_email:
        raise ValueError(f"Under {settings.digital_consent_age} a parent's email is needed for consent")
    if body.email and body.email == body.guardian_email:
        raise ValueError("The player's and the parent's email must differ")
    if body.email and (_taken(db, body.email) or db.scalars(select(StaffMember.id).where(StaffMember.email == body.email)).first()):
        raise ValueError(f"{body.email} already has an account")
    # The squad's physio (or coach) is the named adult for red check-ins
    contact = db.scalars(
        select(StaffMember).where(StaffMember.squad_id == squad.id).order_by((StaffMember.role == Role.PHYSIO).desc())
    ).first()
    player = Player(
        squad_id=squad.id,
        display_name=body.name.strip(),
        email=body.email,
        birth_date=body.birth_date,
        sex=body.sex,
        position=body.position.value,
        pathway=Pathway.ACADEMY.value,
        escalation_contact_id=contact.id if contact else None,
    )
    db.add(player)
    db.flush()
    acc = None
    if body.email:
        acc = UserAccount(email=body.email, password_hash=accounts.UNUSABLE_PASSWORD, role=Role.PLAYER, player_id=player.id)
        db.add(acc)
        db.flush()
        accounts.send_invite(db, acc, squad.club or _club(db), squad.name)
    if body.guardian_email:
        g = db.scalars(select(Guardian).where(Guardian.email == body.guardian_email)).first()
        if g is None:
            g = Guardian(name="Parent", email=body.guardian_email, invite_code=pathway.invite_code())
            db.add(g)
        player.guardians.append(g)
        db.flush()
        if g.invite_code:  # parent not signed up yet
            accounts.send_guardian_invite(db, g, player.display_name, squad.club or _club(db))
    audit(db, user, "create", "player", player.id, squad=squad.id, minor=minor, invited=bool(acc))
    return {"id": player.id, "name": player.display_name, "invited": bool(acc), "parent_invited": bool(body.guardian_email)}


@router.post("/squads/{squad_id}/players", status_code=201)
def add_player(squad_id: str, body: PlayerIn, user: CurrentUser = Depends(ADMIN), db: Session = Depends(get_db)) -> dict:
    squad = _team(db, squad_id)
    try:
        out = _add_player(db, body, squad, user)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from e
    db.commit()
    return out


CSV_COLUMNS = ("name", "birth_date", "sex", "position", "email", "guardian_email")
MAX_IMPORT_ROWS = 200


@router.post("/squads/{squad_id}/players/import")
async def import_players(
    squad_id: str,
    file: UploadFile = File(...),
    dry_run: bool = Form(True),
    user: CurrentUser = Depends(ADMIN),
    db: Session = Depends(get_db),
) -> dict:
    """CSV with a header row: name, birth_date (YYYY-MM-DD), sex, position, email,
    guardian_email. A dry run checks every row and saves nothing; a real run saves only
    if every row is valid, so a file is never half imported."""
    squad = _team(db, squad_id)
    raw = await file.read(512 * 1024 + 1)
    if len(raw) > 512 * 1024:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "The file is larger than 512 KB")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Save the file as CSV (UTF-8)") from e
    first = text.splitlines()[0] if text else ""
    # Spreadsheets in German locales save with semicolons
    delimiter = ";" if first.count(";") > first.count(",") else "\t" if "\t" in first else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    header = [h.strip().lower() for h in reader.fieldnames or []]
    missing = [c for c in ("name", "birth_date") if c not in header]
    if missing:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Missing column(s): {', '.join(missing)}")
    rows, errors = [], []
    for line, row in enumerate(reader, start=2):
        if line - 1 > MAX_IMPORT_ROWS:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"At most {MAX_IMPORT_ROWS} players per file")
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        if not any(row.values()):
            continue
        # A row is checked completely before anything is written, so a bad row leaves no trace;
        # earlier rows are flushed, so an email used twice in the file is caught too
        try:
            rows.append({"line": line, **_add_player(db, PlayerIn(**{c: row[c] for c in CSV_COLUMNS if row.get(c)}), squad, user)})
        except ValidationError as e:
            first_error = e.errors()[0]
            errors.append({"line": line, "error": f"{'.'.join(str(x) for x in first_error['loc'])}: {first_error['msg']}"})
        except ValueError as e:
            errors.append({"line": line, "error": str(e)})
    if dry_run or errors:
        db.rollback()  # nothing saved, no invitation sent
    else:
        audit(db, user, "import", "player", None, squad=squad.id, n=len(rows))
        db.commit()
    return {"dry_run": dry_run, "saved": not dry_run and not errors, "valid": len(rows), "errors": errors, "rows": rows}


class PlayerChange(BaseModel):
    squad_id: str | None = None
    position: Position | None = None


@router.patch("/players/{player_id}")
def change_player(player_id: str, body: PlayerChange, user: CurrentUser = Depends(ADMIN), db: Session = Depends(get_db)) -> dict:
    p = db.get(Player, player_id)
    if p is None or p.pathway != Pathway.ACADEMY.value:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Player not found")
    if body.squad_id:
        p.squad_id = _team(db, body.squad_id).id
    if body.position:
        p.position = body.position.value
    audit(db, user, "update", "player", p.id, squad=p.squad_id, position=p.position)
    db.commit()
    return {"id": p.id, "squad_id": p.squad_id, "position": p.position}


@router.delete("/players/{player_id}")
def delete_player(player_id: str, user: CurrentUser = Depends(ADMIN), db: Session = Depends(get_db)) -> dict:
    """The player leaves the club, or asks for erasure (GDPR Art. 17): everything stored
    about them is deleted. Parents' accounts stay (they may have other children)."""
    p = db.get(Player, player_id)
    if p is None or p.pathway != Pathway.ACADEMY.value:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Player not found")
    accounts.delete_player(db, p)
    audit(db, user, "delete", "player", player_id)
    db.commit()
    return {"deleted": player_id}


# --------------------------------------------------------------------------- invitations


@router.post("/accounts/{account_id}/resend-invite", status_code=202)
def resend_invite(account_id: str, user: CurrentUser = Depends(ADMIN), db: Session = Depends(get_db)) -> dict:
    acc = db.get(UserAccount, account_id)
    if acc is None or not _invite_pending(db, acc):
        raise HTTPException(status.HTTP_409_CONFLICT, "This person has already set a password")
    squad_id = db.get(StaffMember, acc.staff_id).squad_id if acc.staff_id else db.get(Player, acc.player_id).squad_id
    squad = db.get(Squad, squad_id) if squad_id else None
    accounts.send_invite(db, acc, (squad and squad.club) or _club(db), squad.name if squad else "the club")
    audit(db, user, "invite", "user_account", acc.id, resend=True)
    db.commit()
    return {"ok": True}


@router.get("/invites")
def open_invites(user: CurrentUser = Depends(ADMIN), db: Session = Depends(get_db)) -> list[dict]:
    """Invitation links that are still unused, newest first (no link itself: only a hash is stored)."""
    rows = db.execute(
        select(AuthToken, UserAccount)
        .join(UserAccount, UserAccount.id == AuthToken.account_id)
        .where(AuthToken.purpose == "invite", AuthToken.used_at.is_(None))
        .order_by(AuthToken.created_at.desc())
    ).all()
    return [{"email": a.email, "role": a.role.value, "sent": t.created_at.isoformat(), "expires": t.expires_at.isoformat()} for t, a in rows]
