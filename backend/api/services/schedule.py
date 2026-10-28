"""A team's training week: the coach sets it once, team sessions are generated from it
for the next weeks (never on a match day), and the Sunday job keeps the horizon full."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from domain.enums import SessionType
from domain.models import Match, SessionLoad, Squad
from domain.models import Session as TeamSession
from planner.schema import RPE_RANGE, SESSION_MINUTES

WEEKS_AHEAD = 8
TRAINING_KINDS = (SessionType.RECOVERY, SessionType.TECHNICAL, SessionType.TACTICAL, SessionType.STRENGTH, SessionType.SPEED)


def _match_days(db: Session, squad_id: str, start: date, end: date) -> set[date]:
    return {
        m.kickoff.date()
        for m in db.scalars(
            select(Match).where(
                Match.squad_id == squad_id,
                Match.kickoff >= datetime.combine(start, time(0), tzinfo=UTC),
                Match.kickoff < datetime.combine(end, time(0), tzinfo=UTC),
            )
        )
    }


def generate(db: Session, squad: Squad, start: date, end: date) -> int:
    """Team sessions from the training week for [start, end), skipping days that already
    have a team session or a match. Returns how many were added."""
    week = {d["weekday"]: d for d in squad.training_week or []}
    if not week:
        return 0
    have = set(
        db.scalars(
            select(TeamSession.day).where(
                TeamSession.squad_id == squad.id, TeamSession.player_id.is_(None), TeamSession.day >= start, TeamSession.day < end
            )
        )
    )
    matches = _match_days(db, squad.id, start, end)
    added = 0
    d = start
    while d < end:
        slot = week.get(d.weekday())
        if slot and d not in have and d not in matches:
            db.add(
                TeamSession(
                    squad_id=squad.id, day=d, kind=SessionType(slot["kind"]), planned_rpe=slot["rpe"], planned_minutes=slot["minutes"]
                )
            )
            added += 1
        d += timedelta(days=1)
    return added


def replace_week(db: Session, squad: Squad, week: list[dict], today: date) -> dict:
    """New training week from today on: future team sessions nobody has logged against
    are replaced; past ones (and their loads) stay as they were."""
    squad.training_week = sorted(week, key=lambda d: d["weekday"])
    logged = select(SessionLoad.session_id).where(SessionLoad.session_id.is_not(None))
    removed = db.execute(
        delete(TeamSession).where(
            TeamSession.squad_id == squad.id,
            TeamSession.player_id.is_(None),
            TeamSession.day >= today,
            TeamSession.id.not_in(logged),
        )
    ).rowcount
    db.flush()
    added = generate(db, squad, today, today + timedelta(weeks=WEEKS_AHEAD))
    return {"removed": removed, "added": added}


def extend_all(db: Session, today: date) -> int:
    return sum(
        generate(db, squad, today, today + timedelta(weeks=WEEKS_AHEAD))
        for squad in db.scalars(select(Squad))
        if squad.training_week
    )


def suggest_week(db: Session, squad: Squad, today: date) -> list[dict]:
    """No training week saved yet (a team set up before the Schedule page): the pattern of
    the team sessions already planned, so saving the page doesn't silently drop them."""
    by_day: dict[int, list[TeamSession]] = {}
    for s in db.scalars(
        select(TeamSession).where(
            TeamSession.squad_id == squad.id,
            TeamSession.player_id.is_(None),
            TeamSession.day >= today,
            TeamSession.day < today + timedelta(days=28),
        )
    ):
        if s.kind in TRAINING_KINDS:
            by_day.setdefault(s.day.weekday(), []).append(s)
    week = []
    for weekday, rows in sorted(by_day.items()):
        kind = max(sorted({r.kind for r in rows}, key=lambda k: k.value), key=lambda k: sum(r.kind == k for r in rows))
        first = next(r for r in rows if r.kind == kind)
        lo, hi = RPE_RANGE[kind]
        week.append(
            {
                "weekday": weekday,
                "kind": kind.value,
                "minutes": int(first.planned_minutes or SESSION_MINUTES[kind]),
                "rpe": min(max(round(first.planned_rpe or lo), lo), hi),
            }
        )
    return week
