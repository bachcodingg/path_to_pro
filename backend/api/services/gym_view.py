"""Gym programmes for a player's planned strength sessions (gym/programme.py + stored data)."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from api.deps import age_on
from api.services import agent_runner, views
from domain.enums import SessionType
from domain.models import Player
from gym.programme import GymContext, build, positions
from pathway import service as pathway
from planner.schema import PlanDay


def maturity(offset: float | None) -> str | None:
    if offset is None:
        return None
    return "pre_phv" if offset < -1 else "post_phv" if offset > 1 else "circa_phv"


def context(db: Session, p: Player, d: PlanDay, today: date) -> GymContext:
    st = views.latest_status(db, p.id, today)
    prof = pathway.profile(db, p)
    matches = agent_runner.match_days(db, p, d.date + timedelta(days=1), 7)
    nxt = min(matches) if matches else None
    return GymContext(
        position=p.position or "midfielder",
        age=age_on(p.birth_date, d.date),
        maturity=maturity(st.maturity_offset if st else None),
        in_phv_window=bool(st and st.in_phv_window),
        # Today's colour only applies to today; later days are planned for a normal day.
        band=st.band if st is not None and st.day == today and d.date == today else None,
        planned_rpe=d.rpe or 5,
        days_to_match=None if nxt is None else (nxt - d.date).days,
        equipment=prof.equipment if prof else "gym",
        level=prof.level if prof else None,
        day=d.date,
    )


def programme(db: Session, p: Player, d: PlanDay, today: date) -> dict | None:
    if d.kind != SessionType.STRENGTH:
        return None
    return build(context(db, p, d, today)).to_json()


def week(db: Session, p: Player, start: date, today: date) -> dict:
    days = agent_runner.plan_days(db, p, start, 7)
    sessions = [
        {"session": views.day_json(d), "programme": programme(db, p, d, today)}
        for d in days
        if d.kind == SessionType.STRENGTH
    ]
    optional = None
    if not sessions:
        # No gym day this week: offer a short session to do on any easy day.
        # Prefer an easy day that isn't the day before a match (that would be activation only).
        match_dates = {d.date for d in days if d.kind == SessionType.MATCH}
        easy = [d for d in days if d.kind in (SessionType.REST, SessionType.RECOVERY) and d.date >= today]
        free = next(
            (d for d in easy if d.date + timedelta(days=1) not in match_dates and d.date + timedelta(days=2) not in match_dates),
            next((d for d in easy if d.date + timedelta(days=1) not in match_dates), easy[0] if easy else days[0]),
        )
        pd = PlanDay(day=free.day, date=free.date, kind=SessionType.STRENGTH, rpe=4, minutes=30)
        optional = build(context(db, p, pd, today)).to_json()
    pos = positions()
    prof = pathway.profile(db, p)
    key = p.position if p.position in pos else "midfielder"
    return {
        "start": start.isoformat(),
        "position": key,
        "position_label": pos[key]["label"],
        "focus": pos[key]["focus"],
        "equipment": prof.equipment if prof else "gym",
        "sessions": sessions,
        "optional": optional,
        "positions": [{"id": k, **v} for k, v in pos.items()],
    }
