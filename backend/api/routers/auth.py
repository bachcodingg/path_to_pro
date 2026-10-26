from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from api import clock
from api.db import get_db
from api.deps import CurrentUser, age_on, audit, current_user
from api.security import create_token, hash_password, verify_password
from api.settings import settings
from domain.enums import Position, Role
from domain.models import Guardian, Player, StaffMember, UserAccount
from pathway import service as pathway

router = APIRouter(prefix="/api/auth", tags=["auth"])

MIN_AGE = 13


class Login(BaseModel):
    email: str
    password: str


def _profile(db: Session, acc: UserAccount) -> dict:
    name = "Admin"
    extra: dict = {"pathway": None, "position": None}
    if acc.player_id:
        p = db.get(Player, acc.player_id)
        name = p.display_name
        extra = {"pathway": p.pathway, "position": p.position}
    elif acc.guardian_id:
        name = db.get(Guardian, acc.guardian_id).name
    elif acc.staff_id:
        name = db.get(StaffMember, acc.staff_id).name
    return {"id": acc.id, "email": acc.email, "role": acc.role.value, "name": name, "player_id": acc.player_id, **extra}


# Failed sign-ins per email within a sliding window (in memory: one API process).
MAX_FAILED_LOGINS = 10
FAILED_LOGIN_WINDOW_S = 15 * 60
_failed: dict[str, deque[float]] = defaultdict(deque)
_failed_lock = threading.Lock()


def _recent_failures(email: str, now: float) -> deque[float]:
    q = _failed[email]
    while q and q[0] < now - FAILED_LOGIN_WINDOW_S:
        q.popleft()
    return q


@router.post("/login")
def login(body: Login, db: Session = Depends(get_db)) -> dict:
    email = body.email.strip().lower()
    now = time.monotonic()
    with _failed_lock:
        if len(_recent_failures(email, now)) >= MAX_FAILED_LOGINS:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts. Try again in 15 minutes")
    acc = db.scalars(select(UserAccount).where(UserAccount.email == email)).first()
    if acc is None or not acc.active or not verify_password(body.password, acc.password_hash):
        with _failed_lock:
            _recent_failures(email, now).append(now)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password")
    with _failed_lock:
        _failed.pop(email, None)
    audit(db, CurrentUser(acc, acc.role), "login", "user_account", acc.id)
    db.commit()
    return {"token": create_token(acc.id, acc.role.value), "user": _profile(db, acc)}


@router.get("/me")
def me(user: CurrentUser = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return _profile(db, user.account)


# --------------------------------------------------------------------------- self sign-up (self-guided pathway)


def _email(v: str) -> str:
    v = v.strip().lower()
    if "@" not in v or "." not in v.split("@")[-1] or len(v) > 200:
        raise ValueError("Enter a valid email address")
    return v


class Register(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    email: str
    password: str = Field(min_length=8, max_length=200)
    birth_date: date
    sex: Literal["male", "female", "other"] = "male"
    position: Position = Position.MIDFIELDER
    level: int = Field(default=1, ge=1, le=4, description="self-estimate; level 5 is earned with tests")
    goal: Literal["next_level", "first_team", "trial", "fitness"] = "next_level"
    equipment: Literal["none", "home", "gym"] = "none"
    team_days: list[int] = Field(default_factory=list, max_length=5)
    match_day: int | None = Field(default=None, ge=0, le=6)
    guardian_email: str | None = None
    accept_terms: bool = False

    @field_validator("email")
    @classmethod
    def _check_email(cls, v: str) -> str:
        return _email(v)

    @field_validator("team_days")
    @classmethod
    def _days(cls, v: list[int]) -> list[int]:
        if any(not 0 <= d <= 6 for d in v):
            raise ValueError("team_days are weekdays 0-6")
        return sorted(set(v))


def _taken(db: Session, email: str) -> bool:
    return (
        db.scalars(select(UserAccount.id).where(UserAccount.email == email)).first() is not None
        or db.scalars(select(Player.id).where(Player.email == email)).first() is not None
    )


@router.post("/register", status_code=201)
def register(body: Register, db: Session = Depends(get_db)) -> dict:
    """Create a self-guided player account. Under the age of digital consent a parent
    must link with the invite code before check-ins and tests are stored."""
    if not settings.registration:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Sign-up is closed on this server")
    if not body.accept_terms:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Please accept the terms and privacy notice")
    today = clock.today()
    age = age_on(body.birth_date, today)
    if age < MIN_AGE or age > 80:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"PathToPro is for players aged {MIN_AGE} and over")
    minor = age < settings.digital_consent_age
    guardian_email = _email(body.guardian_email) if body.guardian_email else None
    if minor and not guardian_email:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Players under 16 need a parent's email")
    if guardian_email == body.email:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Use a different email for your parent")
    if _taken(db, body.email):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")

    player, _ = pathway.create_player(
        db,
        name=body.name.strip(),
        email=body.email,
        birth_date=body.birth_date,
        sex=body.sex,
        position=body.position.value,
        level=body.level,
        goal=body.goal,
        equipment=body.equipment,
        team_days=body.team_days,
        match_day=body.match_day,
        today=today,
    )
    acc = UserAccount(email=body.email, password_hash=hash_password(body.password), role=Role.PLAYER, player_id=player.id)
    db.add(acc)
    invite = None
    if guardian_email:
        g = db.scalars(select(Guardian).where(Guardian.email == guardian_email)).first()
        if g is None:
            g = Guardian(name="Parent", email=guardian_email, invite_code=pathway.invite_code())
            db.add(g)
        player.guardians.append(g)
        invite = g.invite_code
    db.flush()
    pathway.replan_from(db, player, today, "signup")
    audit(db, CurrentUser(acc, acc.role), "create", "user_account", acc.id, pathway="amateur", minor=minor)
    db.commit()
    return {"token": create_token(acc.id, acc.role.value), "user": _profile(db, acc), "guardian_invite": invite}


class RegisterGuardian(BaseModel):
    invite_code: str = Field(min_length=6, max_length=20)
    name: str = Field(min_length=2, max_length=60)
    password: str = Field(min_length=8, max_length=200)


@router.post("/register/guardian", status_code=201)
def register_guardian(body: RegisterGuardian, db: Session = Depends(get_db)) -> dict:
    """A parent joins with the code their child got at sign-up, then grants consent per data type."""
    if not settings.registration:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Sign-up is closed on this server")
    g = db.scalars(select(Guardian).where(Guardian.invite_code == body.invite_code.strip().upper())).first()
    if g is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invite code not found")
    if db.scalars(select(UserAccount.id).where(UserAccount.email == g.email)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "This parent already has an account: sign in instead")
    g.name, g.invite_code = body.name.strip(), None
    acc = UserAccount(email=g.email, password_hash=hash_password(body.password), role=Role.GUARDIAN, guardian_id=g.id)
    db.add(acc)
    db.flush()
    audit(db, CurrentUser(acc, acc.role), "create", "user_account", acc.id, role="guardian")
    db.commit()
    return {"token": create_token(acc.id, acc.role.value), "user": _profile(db, acc)}
