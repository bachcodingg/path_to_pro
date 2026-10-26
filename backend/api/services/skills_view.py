"""Today's ball-skills session (skills/programme.py) from the player's plan, readiness and
growth status, and the whole drill library for browsing other positions."""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from api.services import agent_runner, views
from domain.models import Player
from pathway import service as pathway
from skills.programme import SkillsContext, build, library, positions


def context(db: Session, p: Player, today: date) -> SkillsContext:
    st = views.latest_status(db, p.id, today)
    plan = agent_runner.plan_days(db, p, today, 1)
    matches = agent_runner.match_days(db, p, today, 7)
    nxt = min(matches) if matches else None
    return SkillsContext(
        position=p.position or "midfielder",
        in_phv_window=bool(st and st.in_phv_window),
        band=st.band if st is not None and st.day == today else None,
        day_kind=plan[0].kind.value if plan else None,
        days_to_match=None if nxt is None else (nxt - today).days,
        # Academy players train with teammates; self-guided players may be on their own
        partner=pathway.profile(db, p) is None,
        day=today,
    )


def today_view(db: Session, p: Player, today: date) -> dict:
    drills, _, _ = library()
    ctx = context(db, p, today)
    return {
        "date": today.isoformat(),
        "position": ctx.position if ctx.position in positions() else "midfielder",
        "session": build(ctx).to_json(),
        "positions": [{"id": k, "label": v["label"], "focus": v["focus"]} for k, v in positions().items()],
        "drills": [d.to_json() for d in drills.values()],
    }
