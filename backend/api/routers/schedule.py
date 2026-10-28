"""Coach: the team's training week and its fixtures, the two inputs every plan is built on.
Changes reach the players' plans at the next agent run (nightly, or "Run agents now")."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from api import clock
from api.db import get_db
from api.deps import CurrentUser, audit, require, staff_of
from api.services import schedule
from domain.enums import Role, SessionType
from domain.models import Appearance, Match, SessionLoad, Squad
from domain.models import Session as TeamSession
from planner.schema import RPE_RANGE, SESSION_MINUTES

router = APIRouter(prefix="/api/coach", tags=["schedule"])

STAFF = (Role.COACH, Role.PHYSIO)


def _squad(user: CurrentUser, db: Session) -> Squad:
    staff = staff_of(user, db)
    if staff.squad_id is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You are not on a team yet: ask your club administrator")
    return db.get(Squad, staff.squad_id)


def _fixture(m: Match) -> dict:
    return {
        "id": m.id,
        "kickoff": m.kickoff.replace(tzinfo=None).isoformat(timespec="minutes"),
        "opponent": m.opponent,
        "competition": m.competition,
        "is_evening": m.is_evening,
    }


@router.get("/schedule")
def get_schedule(user: CurrentUser = Depends(require(*STAFF)), db: Session = Depends(get_db)) -> dict:
    squad = _squad(user, db)
    today = clock.today()
    since = datetime.combine(today - timedelta(days=14), time(0), tzinfo=UTC)
    fixtures = db.scalars(select(Match).where(Match.squad_id == squad.id, Match.kickoff >= since).order_by(Match.kickoff))
    sessions = db.scalars(
        select(TeamSession)
        .where(TeamSession.squad_id == squad.id, TeamSession.player_id.is_(None), TeamSession.day >= today)
        .order_by(TeamSession.day)
        .limit(14)
    )
    return {
        "team": squad.name,
        "today": today.isoformat(),
        "weeks_ahead": schedule.WEEKS_AHEAD,
        "training_week": squad.training_week or schedule.suggest_week(db, squad, today),
        "saved": bool(squad.training_week),
        "kinds": [
            {"kind": k.value, "minutes": SESSION_MINUTES[k], "rpe_min": RPE_RANGE[k][0], "rpe_max": RPE_RANGE[k][1]}
            for k in schedule.TRAINING_KINDS
        ],
        "fixtures": [_fixture(m) for m in fixtures],
        "next_sessions": [
            {"day": s.day.isoformat(), "kind": s.kind.value, "minutes": s.planned_minutes, "rpe": s.planned_rpe} for s in sessions
        ],
    }


class Slot(BaseModel):
    weekday: int = Field(ge=0, le=6)
    kind: SessionType
    minutes: int = Field(ge=20, le=150)
    rpe: int = Field(ge=1, le=10)

    @model_validator(mode="after")
    def _in_range(self) -> Slot:
        if self.kind not in schedule.TRAINING_KINDS:
            raise ValueError(f"{self.kind.value} is not a training session")
        lo, hi = RPE_RANGE[self.kind]
        if not lo <= self.rpe <= hi:
            raise ValueError(f"A {self.kind.value} session is RPE {lo}-{hi}")
        return self


class Week(BaseModel):
    days: list[Slot] = Field(max_length=6)

    @field_validator("days")
    @classmethod
    def _rest_day(cls, v: list[Slot]) -> list[Slot]:
        if len({d.weekday for d in v}) != len(v):
            raise ValueError("One session per weekday")
        return v


@router.put("/schedule/week")
def set_week(body: Week, user: CurrentUser = Depends(require(Role.COACH)), db: Session = Depends(get_db)) -> dict:
    squad = _squad(user, db)
    week = [{"weekday": d.weekday, "kind": d.kind.value, "minutes": d.minutes, "rpe": d.rpe} for d in body.days]
    out = schedule.replace_week(db, squad, week, clock.today())
    audit(db, user, "update", "training_week", squad.id, days=len(week), **out)
    db.commit()
    return {**out, **get_schedule(user, db)}


class FixtureIn(BaseModel):
    opponent: str = Field(min_length=2, max_length=100)
    kickoff: datetime
    competition: str | None = Field(default=None, max_length=100)


@router.post("/fixtures", status_code=201)
def add_fixture(body: FixtureIn, user: CurrentUser = Depends(require(Role.COACH)), db: Session = Depends(get_db)) -> dict:
    squad = _squad(user, db)
    # Kick-off is club-local time; stored like the rest of the schedule (naive clock as UTC)
    kickoff = body.kickoff.replace(tzinfo=UTC)
    if kickoff.date() < clock.today():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Kick-off is in the past")
    if db.scalars(
        select(Match.id).where(
            Match.squad_id == squad.id,
            Match.kickoff >= datetime.combine(kickoff.date(), time(0), tzinfo=UTC),
            Match.kickoff < datetime.combine(kickoff.date() + timedelta(days=1), time(0), tzinfo=UTC),
        )
    ).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "The team already plays that day")
    m = Match(
        squad_id=squad.id,
        kickoff=kickoff,
        opponent=body.opponent.strip(),
        competition=(body.competition or "").strip() or None,
        is_evening=kickoff.hour >= 17,
    )
    db.add(m)
    # Match day replaces that day's team training (unless someone already logged it)
    logged = select(SessionLoad.session_id).where(SessionLoad.session_id.is_not(None))
    for s in db.scalars(
        select(TeamSession).where(
            TeamSession.squad_id == squad.id, TeamSession.player_id.is_(None), TeamSession.day == kickoff.date(), TeamSession.id.not_in(logged)
        )
    ):
        db.delete(s)
    db.flush()
    audit(db, user, "create", "match", m.id, opponent=m.opponent, day=kickoff.date().isoformat())
    db.commit()
    return _fixture(m)


@router.delete("/fixtures/{match_id}")
def delete_fixture(match_id: str, user: CurrentUser = Depends(require(Role.COACH)), db: Session = Depends(get_db)) -> dict:
    squad = _squad(user, db)
    m = db.get(Match, match_id)
    if m is None or m.squad_id != squad.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fixture not found")
    played = db.scalars(select(SessionLoad.id).where(SessionLoad.match_id == m.id)).first() or db.scalars(
        select(Appearance.id).where(Appearance.match_id == m.id, Appearance.minutes > 0)
    ).first()
    if played or m.kickoff.date() < clock.today():
        raise HTTPException(status.HTTP_409_CONFLICT, "This match has been played: it stays on record")
    db.delete(m)
    # The day is free again: the training week fills it if it is a training day
    schedule.generate(db, squad, m.kickoff.date(), m.kickoff.date() + timedelta(days=1))
    audit(db, user, "delete", "match", match_id)
    db.commit()
    return {"deleted": match_id}
