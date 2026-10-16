"""Loads a simulated season into the database for the demo. All data is synthetic.

'Today' is fixed inside the season (default: Thursday of week 12). Records up to
yesterday are loaded, the agents are run nightly through the current week so plans
and proposals exist, and a short demo story is set up:
  - one player in the growth window slept < 6 h for 3 nights after a midweek cup
    match: the nightly run proposes a lighter week (coach inbox)
  - one player reported pain yesterday: it sits in the physio queue
"""

from __future__ import annotations

import copy
import logging
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from agents.monitor import assess
from analytics.readiness import set_active_weights
from api.clock import set_today
from api.security import hash_password
from api.services import agent_runner
from domain.enums import ConsentDataType, ProposalStatus, Role, SessionType
from domain.models import (
    Anthropometrics,
    AppSetting,
    Base,
    ConsentRecord,
    Drill,
    Guardian,
    HRVRecord,
    Match,
    Player,
    Proposal,
    SessionLoad,
    SleepRecord,
    Squad,
    StaffMember,
    StaffRating,
    TestResult,
    UserAccount,
    WellnessCheckin,
)
from domain.models import Session as TeamSession
from simulator.policies import BASELINE_TEMPLATE
from simulator.season import SeasonSimulator, load_config

log = logging.getLogger(__name__)

DEMO_PASSWORD = "demo1234"
TODAY_WEEK, TODAY_WEEKDAY = 12, 3  # Thursday of week 12
STATUS_DAYS = 56  # Monitor history computed at seed time (heatmap uses 14, calibration all)
FIRST_NAMES = [
    "Leo", "Noah", "Elias", "Finn", "Jonas", "Luca", "Ben", "Paul", "Felix", "Emil", "Anton", "Theo", "Jakob",
    "Max", "Leon", "Henry", "Oskar", "Matteo", "David", "Samuel", "Julian", "Moritz", "Nico", "Tim", "Jan",
]  # fmt: skip
TEMPLATE_RPE = {SessionType.TECHNICAL: 5, SessionType.STRENGTH: 6, SessionType.TACTICAL: 6, SessionType.SPEED: 6}
TEMPLATE_MIN = {SessionType.TECHNICAL: 75, SessionType.STRENGTH: 60, SessionType.TACTICAL: 80, SessionType.SPEED: 50}


def demo_today(cfg: dict | None = None) -> date:
    cfg = cfg or load_config()
    start = cfg["start_date"] if isinstance(cfg["start_date"], date) else date.fromisoformat(str(cfg["start_date"]))
    return start + timedelta(days=7 * TODAY_WEEK + TODAY_WEEKDAY)


def _at(d: date, hour: int) -> datetime:
    return datetime.combine(d, time(hour, 0), tzinfo=UTC)


def seed(db: Session, n_players: int = 25, story: bool = True) -> dict:
    cfg = load_config()
    cfg["n_players"] = n_players
    cfg["weeks"] = TODAY_WEEK + 2
    today = demo_today(cfg)
    yesterday = today - timedelta(days=1)
    res = SeasonSimulator(copy.deepcopy(cfg)).run()

    for table in reversed(Base.metadata.sorted_tables):
        db.execute(delete(table))
    db.flush()

    squad = Squad(name="PathToPro Academy U13-U18", age_group="U13-U18")
    db.add(squad)
    db.flush()
    coach = StaffMember(name="Alex Weber", email="coach@demo.pathtopro", role=Role.COACH, squad_id=squad.id)
    physio = StaffMember(name="Sam Okafor", email="physio@demo.pathtopro", role=Role.PHYSIO, squad_id=squad.id)
    db.add_all([coach, physio])
    db.flush()
    pw = hash_password(DEMO_PASSWORD)
    db.add_all(
        [
            UserAccount(email=coach.email, password_hash=pw, role=Role.COACH, staff_id=coach.id),
            UserAccount(email=physio.email, password_hash=pw, role=Role.PHYSIO, staff_id=physio.id),
            UserAccount(email="admin@demo.pathtopro", password_hash=pw, role=Role.ADMIN),
        ]
    )
    for d in agent_runner_drills():
        db.add(d)

    start = date.fromisoformat(res.fixtures[0]["date"])
    exam_dates = [f["date"] for f in res.fixtures if f["exam"]]
    players: dict[str, Player] = {}
    for i, p in enumerate(res.players):
        birth = start - timedelta(days=round(p["age_at_start"] * 365.25))
        name = f"{FIRST_NAMES[i % len(FIRST_NAMES)]} {chr(65 + (i * 7) % 26)}."
        pl = Player(
            squad_id=squad.id,
            display_name=name,
            email=f"p{i + 1:02d}@demo.pathtopro",
            birth_date=birth,
            sex="male",
            exam_dates=exam_dates,
            escalation_contact_id=physio.id,
        )
        db.add(pl)
        db.flush()
        players[p["player_id"]] = pl
        g = Guardian(name=f"Guardian of {name}", email=f"guardian{i + 1:02d}@demo.pathtopro")
        pl.guardians.append(g)
        db.flush()
        db.add(UserAccount(email=pl.email, password_hash=pw, role=Role.PLAYER, player_id=pl.id))
        db.add(UserAccount(email=g.email, password_hash=pw, role=Role.GUARDIAN, guardian_id=g.id))
        if agent_runner.age_on(birth, today) < 16:
            for dt in ConsentDataType:
                db.add(
                    ConsentRecord(player_id=pl.id, guardian_id=g.id, data_type=dt, granted=True, recorded_at=_at(start, 9))
                )

    # Fixtures and the team's weekly template for the whole loaded period
    for f in res.fixtures:
        d = date.fromisoformat(f["date"])
        if f["match"]:
            db.add(
                Match(
                    squad_id=squad.id,
                    kickoff=_at(d, 19 if f["evening_match"] else 15),
                    opponent=f"Opponent {f['week'] + 1}",
                    competition="Cup" if f["evening_match"] else "League",
                    is_evening=f["evening_match"],
                )
            )
        elif f["weekday"] in BASELINE_TEMPLATE:
            kind = BASELINE_TEMPLATE[f["weekday"]]
            db.add(
                TeamSession(
                    squad_id=squad.id, day=d, kind=kind, planned_rpe=TEMPLATE_RPE[kind], planned_minutes=TEMPLATE_MIN[kind]
                )
            )

    # Records up to yesterday
    for s in res.sessions:
        d = date.fromisoformat(s["date"])
        if d <= yesterday:
            db.add(
                SessionLoad(
                    player_id=players[s["player_id"]].id, day=d, rpe=s["rpe"], minutes=s["minutes"], load_au=s["load"]
                )
            )
    for c in res.checkins:
        d = date.fromisoformat(c["date"])
        if d > yesterday:
            continue
        pid = players[c["player_id"]].id
        db.add(SleepRecord(player_id=pid, night_of=d, hours=c["sleep_hours"], source="wearable"))
        db.add(HRVRecord(player_id=pid, day=d, ln_rmssd=c["ln_rmssd"], source="wearable"))
        if c["completed"]:
            db.add(
                WellnessCheckin(
                    player_id=pid,
                    day=d,
                    sleep_quality=c["sleep_quality"],
                    fatigue=c["fatigue"],
                    stress=c["stress"],
                    soreness=c["soreness"],
                    mood_red=False,  # historical red check-ins were handled at the time
                    pain_reported=False,
                    submitted_at=_at(d, 7),
                    duration_s=18.0,
                )
            )
    for a in res.anthropometrics:
        d = date.fromisoformat(a["date"])
        if d <= yesterday:
            db.add(
                Anthropometrics(
                    player_id=players[a["player_id"]].id,
                    day=d,
                    height_cm=a["height_cm"],
                    sitting_height_cm=a["sitting_height_cm"],
                    weight_kg=a["weight_kg"],
                )
            )
    for t in res.tests:
        d = date.fromisoformat(t["date"])
        if d <= yesterday:
            db.add(TestResult(player_id=players[t["player_id"]].id, day=d, test=t["test"], value=t["value"]))
    db.flush()

    story_ids = _story(db, players, yesterday) if story else {}
    story_player = next((p for p in players.values() if p.display_name == story_ids.get("tired_player")), None)

    # Synthetic staff ratings (coach and physio) for the last STATUS_DAYS, for calibration
    first_status = today - timedelta(days=STATUS_DAYS)
    for c in res.checkins:
        d = date.fromisoformat(c["date"])
        if c["staff_rating"] and first_status <= d <= yesterday:
            rater = coach if d.toordinal() % 2 else physio
            db.add(StaffRating(player_id=players[c["player_id"]].id, staff_id=rater.id, day=d, band=c["staff_rating"]))

    # Monitor history (heatmap, calibration), then the nightly agents through this week
    set_active_weights(None)
    week_start = today - timedelta(days=TODAY_WEEKDAY)
    for p in players.values():
        for k in range(STATUS_DAYS, 0, -1):
            d = today - timedelta(days=k)
            if d < week_start - timedelta(days=1):
                agent_runner.save_status(db, p, d, assess(agent_runner.load_history(db, p, d)))
    db.flush()
    d = week_start - timedelta(days=1)
    while d <= yesterday:
        if story and d == yesterday:
            _heavy_session(db, story_player, today)
        for p in players.values():
            agent_runner.run_player(db, p, d, "nightly")
        db.flush()
        d += timedelta(days=1)

    # Development Coach after the last test day; most goals approved, a few left in the inbox
    for i, p in enumerate(players.values()):
        prop = agent_runner.run_dev_coach(db, p, yesterday - timedelta(days=3), "test_day")
        db.flush()
        if prop is not None and i % 6 != 0:
            agent_runner.decide_proposal(db, prop, coach, "approve", note="seeded")
    db.merge(AppSetting(key="today", value=today.isoformat()))
    db.commit()
    set_today(today)
    pending = db.scalars(select(Proposal).where(Proposal.status == ProposalStatus.PENDING)).all()
    return {
        "today": today.isoformat(),
        "players": len(players),
        "pending_proposals": len(pending),
        "story": story_ids,
        "password": DEMO_PASSWORD,
    }


def _story(db: Session, players: dict[str, Player], yesterday: date) -> dict:
    """Demo story on two players (synthetic data edits)."""
    plist = list(players.values())
    # The player closest to PHV by estimate gets the "tired after the cup match" story.
    best, best_off = plist[0], 99.0
    for p in plist:
        a = assess(agent_runner.load_history(db, p, yesterday))
        if a.growth is not None and abs(a.growth.maturity_offset) < best_off:
            best, best_off = p, abs(a.growth.maturity_offset)
    tired = best
    for k, hours in zip(range(2, -1, -1), (5.6, 5.4, 5.5)):
        d = yesterday - timedelta(days=k)
        rec = db.scalars(select(SleepRecord).where(SleepRecord.player_id == tired.id, SleepRecord.night_of == d)).first()
        if rec:
            rec.hours = hours
    hrv = db.scalars(select(HRVRecord).where(HRVRecord.player_id == tired.id, HRVRecord.day == yesterday)).first()
    if hrv:
        hrv.ln_rmssd = hrv.ln_rmssd - 0.35
    # Extra load: an evening cup match two days ago plus a hard session yesterday.
    db.add(SessionLoad(player_id=tired.id, day=yesterday - timedelta(days=1), rpe=9, minutes=95, load_au=855))
    db.add(SessionLoad(player_id=tired.id, day=yesterday, rpe=8, minutes=90, load_au=720))

    pain = plist[1] if plist[1] is not tired else plist[2]
    chk = db.scalars(
        select(WellnessCheckin).where(WellnessCheckin.player_id == pain.id, WellnessCheckin.day == yesterday)
    ).first()
    if chk is None:
        chk = WellnessCheckin(
            player_id=pain.id, day=yesterday, sleep_quality=3, fatigue=4, stress=3, soreness=6, submitted_at=_at(yesterday, 7)
        )
        db.add(chk)
    chk.pain_reported, chk.soreness = True, 6
    db.flush()
    return {"tired_player": tired.display_name, "tired_email": tired.email, "pain_player": pain.display_name}


def _heavy_session(db: Session, player: Player | None, day: date) -> None:
    """Demo story: the team plan has a heavy gym session for the tired player tomorrow.

    With his flags (short sleep, low HRV, load spike, growth zone) any re-plan lowers it by
    more than 1 RPE or swaps it, so the change always needs the coach. This keeps the demo
    the same on every platform instead of depending on near-equal solver optima.
    """
    from domain.models import PlanItem, WeeklyPlan

    if player is None:
        return
    item = db.scalars(
        select(PlanItem)
        .join(WeeklyPlan)
        .where(WeeklyPlan.player_id == player.id, WeeklyPlan.status == "active", PlanItem.day == day)
    ).first()
    if item is not None and item.kind != SessionType.MATCH:
        item.kind, item.target_rpe, item.minutes = SessionType.STRENGTH, 8, 60
        db.flush()


def agent_runner_drills() -> list[Drill]:
    from agents.dev_coach import load_drills

    return [
        Drill(
            id=d.id,
            name=d.name,
            kpi=d.kpi,
            session_type=SessionType(d.session),
            description=d.description,
            typical_rpe=d.rpe,
            minutes=d.minutes,
            plyometric=d.plyometric,
            min_age=d.min_age,
        )
        for d in load_drills()
    ]
