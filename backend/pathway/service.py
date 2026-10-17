"""Database side of the self-guided pathway: sign-up, the player's own club week,
levels, and the content of each solo session.

Self-guided players have no staff. They get the same planner and safety rules as
academy players; re-plans (which can only make a week easier) are applied
automatically, and safety flags show advice in the app instead of going to a physio.
"""

from __future__ import annotations

import secrets
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from agents.rules import DevGoal
from api.deps import age_on, audit
from domain.enums import Pathway, SessionType
from domain.models import AmateurProfile, Match, Player, SessionLoad, Squad
from pathway import levels

FIXTURE_WEEKS = 10


def is_amateur(player: Player) -> bool:
    return player.pathway == Pathway.AMATEUR.value


def profile(db: Session, player: Player) -> AmateurProfile | None:
    return db.get(AmateurProfile, player.id) if is_amateur(player) else None


def invite_code() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I
    return "".join(secrets.choice(alphabet) for _ in range(8))


def new_squad(db: Session, name: str) -> Squad:
    squad = Squad(name=f"Self-guided: {name}", age_group="SELF")
    db.add(squad)
    db.flush()
    return squad


# --------------------------------------------------------------------------- the player's own club week


def sync_fixtures(db: Session, player: Player, prof: AmateurProfile, today: date) -> None:
    """Weekly club match on the player's match day for the next weeks; future matches on
    other weekdays (from an old setting) are removed."""
    start = datetime.combine(today, time(0), tzinfo=UTC)
    existing = list(db.scalars(select(Match).where(Match.squad_id == player.squad_id, Match.kickoff >= start)))
    keep = set()
    for m in existing:
        if prof.match_day is None or m.kickoff.date().weekday() != prof.match_day:
            db.delete(m)
        else:
            keep.add(m.kickoff.date())
    if prof.match_day is None:
        return
    first = today + timedelta(days=(prof.match_day - today.weekday()) % 7)
    for k in range(FIXTURE_WEEKS):
        d = first + timedelta(weeks=k)
        if d not in keep:
            db.add(
                Match(
                    squad_id=player.squad_id,
                    kickoff=datetime.combine(d, time(11), tzinfo=UTC),
                    opponent="Club match",
                    competition="League",
                    is_evening=False,
                )
            )


def planner_overrides(prof: AmateurProfile, start: date, n: int) -> dict:
    lvl = levels.config()["levels"][prof.level]
    return {
        "club_weekly_load": float(lvl["weekly_load"]),
        "min_training_sessions": max(1, round(lvl["min_sessions"] * n / 7)),
        "team_days": sorted({(wd - start.weekday()) % 7 for wd in prof.team_days} & set(range(n))),
    }


def preseason_load(prof: AmateurProfile) -> float:
    return levels.config()["levels"][prof.level]["weekly_load"] / 7


# --------------------------------------------------------------------------- levels


def latest_results(db: Session, player: Player) -> dict[str, float]:
    from api.services.agent_runner import latest_tests

    return {k: v for k, v in latest_tests(db, player).items() if k in levels.tests()}


def sessions_28d(db: Session, player: Player, today: date) -> int:
    """Training sessions and matches logged in the last 4 weeks."""
    return len(
        db.scalars(
            select(SessionLoad.id).where(
                SessionLoad.player_id == player.id, SessionLoad.day > today - timedelta(days=28), SessionLoad.day <= today
            )
        ).all()
    )


def assessment(db: Session, player: Player, prof: AmateurProfile, today: date) -> dict:
    return levels.assess(
        latest_results(db, player),
        age_on(player.birth_date, today),
        player.sex,
        prof.level,
        sessions_28d(db, player, today),
    )


def evaluate(db: Session, player: Player, prof: AmateurProfile, today: date) -> dict:
    """Assess and level up (one level at a time) when the checklist is complete."""
    a = assessment(db, player, prof, today)
    if a["ready_to_level_up"]:
        prof.level += 1
        prof.level_since = today
        audit(db, None, "level_up", "amateur_profile", player.id, level=prof.level)
        db.flush()
        a = assessment(db, player, prof, today)
        a["levelled_up"] = True
    return a


def goals(db: Session, player: Player, prof: AmateurProfile, today: date) -> list[DevGoal]:
    """The planner's development goals: the level's gym sessions plus one session a week
    for each focus area."""
    focus = assessment(db, player, prof, today)["focus"]
    out = {kpi: 1 for kpi in levels.focus_kpis(focus)}
    gym = levels.config()["levels"][prof.level]["gym_per_week"]
    out["cmj"] = max(out.get("cmj", 0), gym)  # gym sessions (strength) for the level
    return [DevGoal(kpi, n) for kpi, n in out.items()]


# --------------------------------------------------------------------------- session content


def session_content(kind: str, team_day: bool, focus: list[str]) -> dict | None:
    """What a self-guided player actually does in a planned session (gym days come from
    gym/programme.py)."""
    k = SessionType(kind)
    if k in (SessionType.REST, SessionType.MATCH, SessionType.STRENGTH):
        return None
    if team_day and k in (SessionType.TECHNICAL, SessionType.TACTICAL):
        return {
            "title": "Club training",
            "items": [{"name": "Train with your team", "minutes": None, "how": "Tell your coach how you feel if your battery is amber or red."}],
        }
    if k == SessionType.RECOVERY:
        return {
            "title": "Recovery",
            "items": [
                {"name": "Easy jog or bike", "minutes": 15, "how": "Conversation pace."},
                {"name": "Mobility flow", "minutes": 15, "how": "Hips, hamstrings, calves: 60 s each position."},
            ],
        }
    if k == SessionType.SPEED:
        return {"title": "Speed", "items": levels.solo_drills("sprint_30m") + levels.solo_drills("general")[:1]}
    if k == SessionType.TACTICAL:
        return {"title": "Fitness with the ball", "items": levels.solo_drills("yoyo_ir1") + levels.solo_drills("general")[1:]}
    technical = [f for f in focus if levels.tests()[f]["kind"] == "technical"]
    items = levels.solo_drills(technical[0] if technical else None)[:2] + levels.solo_drills("general")[:1]
    return {"title": "Ball skills", "items": items}


# --------------------------------------------------------------------------- sign-up


def create_player(
    db: Session,
    *,
    name: str,
    email: str,
    birth_date: date,
    sex: str,
    position: str,
    level: int,
    goal: str,
    equipment: str,
    team_days: list[int],
    match_day: int | None,
    today: date,
) -> tuple[Player, AmateurProfile]:
    squad = new_squad(db, name)
    player = Player(
        squad_id=squad.id,
        display_name=name,
        email=email,
        birth_date=birth_date,
        sex=sex,
        position=position,
        pathway=Pathway.AMATEUR.value,
        preferred_days=[],
        exam_dates=[],
    )
    db.add(player)
    db.flush()
    prof = AmateurProfile(
        player_id=player.id,
        level=level,
        level_since=today,
        goal=goal,
        equipment=equipment,
        team_days=sorted(set(team_days)),
        match_day=match_day,
    )
    db.add(prof)
    db.flush()
    sync_fixtures(db, player, prof, today)
    return player, prof


def replan_from(db: Session, player: Player, day: date, trigger: str) -> None:
    """Re-plan the rest of the week from `day` (after a settings change or at sign-up)."""
    from api.services import agent_runner
    from domain.models import WeeklyPlan

    for p in db.scalars(select(WeeklyPlan).where(WeeklyPlan.player_id == player.id, WeeklyPlan.status == "active")):
        for it in list(p.items):
            if it.day >= day:
                p.items.remove(it)
        if not p.items:
            p.status = "superseded"
    db.flush()
    agent_runner.run_player(db, player, day - timedelta(days=1), trigger)


def ensure_week(db: Session, player: Player, start: date, today: date) -> None:
    """Self-guided players have no nightly staff run: plan a week the first time it's
    viewed (from today for the current week)."""
    from api.services import agent_runner

    if not is_amateur(player) or start + timedelta(days=6) < today:
        return
    first = max(start, today)
    if agent_runner.has_active_plan(db, player, first) and agent_runner.plan_covers(db, player, first, start + timedelta(days=7)):
        return
    prof = profile(db, player)
    if prof is not None:
        sync_fixtures(db, player, prof, today)
    agent_runner.run_player(db, player, first - timedelta(days=1), "weekly")
    db.flush()

