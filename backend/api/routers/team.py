"""Team life around the plan: who can make the next sessions and matches, and the coach's
announcements. Academy teams only (a self-guided player has no team to answer to)."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from api import clock
from api.db import get_db
from api.deps import CurrentUser, audit, require, staff_of
from api.services import agent_runner, push
from domain.enums import Pathway, Role
from domain.models import Announcement, Availability, Match, Player, Registration, Squad, StaffMember, UserAccount
from domain.models import Session as TeamSession

router = APIRouter(prefix="/api/team", tags=["team"])

AHEAD_DAYS = 21
REASONS = {"school": "School or exams", "family": "Family", "travel": "Travel", "other": "Other"}


def _events(db: Session, squad_ids: list[str], primary: str | None) -> list[dict]:
    """Team sessions (primary team) and matches (every team) from today on."""
    today = clock.today()
    end = today + timedelta(days=AHEAD_DAYS)
    out = []
    if primary:
        for s in db.scalars(
            select(TeamSession).where(
                TeamSession.squad_id == primary, TeamSession.player_id.is_(None), TeamSession.day >= today, TeamSession.day < end
            )
        ):
            out.append({"key": f"session:{s.id}", "kind": "session", "day": s.day.isoformat(), "time": None, "title": f"Training: {s.kind.value}", "squad_id": primary})
    for m in db.scalars(
        select(Match).where(
            Match.squad_id.in_(squad_ids),
            Match.kickoff >= datetime.combine(today, time(0), tzinfo=UTC),
            Match.kickoff < datetime.combine(end, time(0), tzinfo=UTC),
        )
    ):
        out.append(
            {
                "key": f"match:{m.id}",
                "kind": "match",
                "day": m.kickoff.date().isoformat(),
                "time": m.kickoff.strftime("%H:%M"),
                "title": f"Match vs {m.opponent}",
                "squad_id": m.squad_id,
            }
        )
    return sorted(out, key=lambda e: (e["day"], e["time"] or ""))


def _academy_player(user: CurrentUser, db: Session) -> Player:
    p = db.get(Player, user.account.player_id)
    if p.pathway != Pathway.ACADEMY.value:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Availability is for academy teams")
    return p


@router.get("/events")
def events(user: CurrentUser = Depends(require(Role.PLAYER, Role.COACH, Role.PHYSIO)), db: Session = Depends(get_db)) -> dict:
    if user.role == Role.PLAYER:
        p = db.get(Player, user.account.player_id)
        if p.pathway != Pathway.ACADEMY.value:
            return {"events": [], "reasons": REASONS, "team": None}
        evs = _events(db, agent_runner.team_ids(db, p), p.squad_id)
        mine = {a.event_key: a for a in db.scalars(select(Availability).where(Availability.player_id == p.id))}
        for e in evs:
            a = mine.get(e["key"])
            e["available"], e["reason"] = (a.available, a.reason) if a else (None, None)
        return {"events": evs, "reasons": REASONS, "team": db.get(Squad, p.squad_id).name}

    staff = staff_of(user, db)
    if staff.squad_id is None:
        return {"events": [], "reasons": REASONS, "team": None}
    evs = _events(db, [staff.squad_id], staff.squad_id)
    squad_players = {p.id: p.display_name for p in db.scalars(select(Player).where(Player.squad_id == staff.squad_id))}
    dual = {
        p.id: p.display_name
        for p in db.scalars(select(Player).join(Registration, Registration.player_id == Player.id).where(Registration.squad_id == staff.squad_id))
    }
    answers: dict[str, list[Availability]] = {}
    for a in db.scalars(select(Availability).where(Availability.event_key.in_([e["key"] for e in evs]))):
        answers.setdefault(a.event_key, []).append(a)
    for e in evs:
        roster = {**squad_players, **dual} if e["kind"] == "match" else squad_players
        got = [a for a in answers.get(e["key"], []) if a.player_id in roster]
        e["available"] = sum(a.available for a in got)
        e["unavailable"] = [{"name": roster[a.player_id], "reason": REASONS.get(a.reason or "", "")} for a in got if not a.available]
        e["no_answer"] = len(roster) - len(got)
    return {"events": evs, "reasons": REASONS, "team": db.get(Squad, staff.squad_id).name}


class Answer(BaseModel):
    event: str = Field(pattern=r"^(match|session):[0-9a-f-]{36}$")
    available: bool
    reason: Literal["school", "family", "travel", "other"] | None = None


@router.put("/availability")
def answer(body: Answer, user: CurrentUser = Depends(require(Role.PLAYER)), db: Session = Depends(get_db)) -> dict:
    p = _academy_player(user, db)
    known = {e["key"] for e in _events(db, agent_runner.team_ids(db, p), p.squad_id)}
    if body.event not in known:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not one of your team's upcoming events")
    kind, ident = body.event.split(":", 1)
    a = db.scalars(select(Availability).where(Availability.player_id == p.id, Availability.event_key == body.event)).first()
    if a is None:
        a = Availability(player_id=p.id, event_key=body.event, match_id=ident if kind == "match" else None, session_id=ident if kind == "session" else None)
        db.add(a)
    a.available, a.reason, a.updated_at = body.available, None if body.available else body.reason, datetime.now(UTC)
    audit(db, user, "update", "availability", p.id, event=body.event, available=body.available)
    db.commit()
    return {"event": body.event, "available": a.available, "reason": a.reason}


# --------------------------------------------------------------------------- announcements


def _announcement(db: Session, a: Announcement) -> dict:
    author = db.get(StaffMember, a.author_id)
    created = a.created_at if a.created_at.tzinfo else a.created_at.replace(tzinfo=UTC)  # SQLite drops the zone
    return {"id": a.id, "text": a.text, "author": author.name if author else "", "created_at": created.isoformat(), "squad_id": a.squad_id}


@router.get("/announcements")
def announcements(user: CurrentUser = Depends(require(Role.PLAYER, Role.COACH, Role.PHYSIO)), db: Session = Depends(get_db)) -> list[dict]:
    if user.role == Role.PLAYER:
        p = db.get(Player, user.account.player_id)
        squads, since, limit = agent_runner.team_ids(db, p), datetime.now(UTC) - timedelta(days=14), 5
    else:
        staff = staff_of(user, db)
        squads, since, limit = [staff.squad_id] if staff.squad_id else [], datetime.now(UTC) - timedelta(days=60), 30
    rows = db.scalars(
        select(Announcement)
        .where(Announcement.squad_id.in_(squads), Announcement.created_at >= since)
        .order_by(Announcement.created_at.desc())
        .limit(limit)
    )
    return [_announcement(db, a) for a in rows]


class AnnouncementIn(BaseModel):
    text: str = Field(min_length=2, max_length=1000)


@router.post("/announcements", status_code=201)
def announce(body: AnnouncementIn, user: CurrentUser = Depends(require(Role.COACH)), db: Session = Depends(get_db)) -> dict:
    staff = staff_of(user, db)
    if staff.squad_id is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You are not on a team yet")
    a = Announcement(squad_id=staff.squad_id, author_id=staff.id, text=body.text.strip(), created_at=datetime.now(UTC))
    db.add(a)
    db.flush()
    players = select(Player.id).where(Player.squad_id == staff.squad_id)
    accounts = list(db.scalars(select(UserAccount.id).where(UserAccount.player_id.in_(players), UserAccount.active.is_(True))))
    text = a.text if len(a.text) <= 120 else a.text[:117] + "..."
    push.queue(db, accounts, f"{staff.name.split()[0]}: team news", text, "/player")
    audit(db, user, "create", "announcement", a.id, squad=staff.squad_id)
    db.commit()
    return _announcement(db, a)


@router.delete("/announcements/{announcement_id}")
def remove_announcement(announcement_id: str, user: CurrentUser = Depends(require(Role.COACH)), db: Session = Depends(get_db)) -> dict:
    staff = staff_of(user, db)
    a = db.get(Announcement, announcement_id)
    if a is None or a.squad_id != staff.squad_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Announcement not found")
    db.delete(a)
    audit(db, user, "delete", "announcement", announcement_id)
    db.commit()
    return {"deleted": announcement_id}
