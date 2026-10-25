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
import os
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
    LedgerEntry,
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
ADMIN_EMAIL = "admin@demo.pathtopro"
TODAY_WEEK, TODAY_WEEKDAY = 12, 3  # Thursday of week 12
STATUS_DAYS = 56  # Monitor history computed at seed time (heatmap uses 14, calibration all)
FIRST_NAMES = [
    "Leo", "Noah", "Elias", "Finn", "Jonas", "Luca", "Ben", "Paul", "Felix", "Emil", "Anton", "Theo", "Jakob",
    "Max", "Leon", "Henry", "Oskar", "Matteo", "David", "Samuel", "Julian", "Moritz", "Nico", "Tim", "Jan",
]  # fmt: skip
# A realistic squad spread: 2 goalkeepers, 5 centre-backs, 4 full-backs, 6 midfielders, 4 wingers, 4 strikers
POSITIONS = [
    "goalkeeper", "centre_back", "full_back", "midfielder", "winger", "striker", "centre_back", "midfielder",
    "full_back", "midfielder", "winger", "striker", "centre_back", "midfielder", "striker", "goalkeeper",
    "full_back", "midfielder", "winger", "centre_back", "striker", "midfielder", "full_back", "winger", "centre_back",
]  # fmt: skip
AMATEUR_EMAIL = "amateur@demo.pathtopro"
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

    squad = Squad(name="PathToPro Academy U13-U18", age_group="U13-U18", club="PathToPro FC")
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
        ]
    )
    # Admin sees every player, so it never gets the published demo password: it exists only
    # when the operator sets its password explicitly.
    admin_pw = os.environ.get("PATHTOPRO_ADMIN_PASSWORD")
    if admin_pw:
        db.add(UserAccount(email=ADMIN_EMAIL, password_hash=hash_password(admin_pw), role=Role.ADMIN))
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
            position=POSITIONS[i % len(POSITIONS)],
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

    dual_email = _teams_and_careers(db, res, players, squad, pw, today)
    story_ids = _story(db, players, yesterday) if story else {}
    story_ids["dual_email"] = dual_email
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
    _amateur(db, pw, today, week_start)
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
        "amateur_email": AMATEUR_EMAIL,
        "dual_email": DUAL_EMAIL,
        "men_coach_email": MEN_COACH_EMAIL,
    }


DUAL_EMAIL = "dual@demo.pathtopro"
FORMATION = {"gk": 1, "def": 4, "mid": 3, "fwd": 3}  # 4-3-3
GROUP_OF = {"goalkeeper": "gk", "centre_back": "def", "full_back": "def", "midfielder": "mid", "winger": "fwd", "striker": "fwd"}


def pick_xi(rows: list[tuple[str, str, float]]) -> set[str]:
    """Starting XI for a 4-3-3 from (player id, position, minutes): per position group the
    players with most minutes; open slots (no player of that group) go to the next most
    minutes. Everyone else came off the bench."""
    chosen: list[str] = []
    ordered = sorted(rows, key=lambda r: -r[2])
    for g, n in FORMATION.items():
        chosen += [pid for pid, pos, _ in ordered if GROUP_OF.get(pos, "mid") == g][:n]
    for pid, _, _ in ordered:
        if len(chosen) >= 11:
            break
        if pid not in chosen:
            chosen.append(pid)
    return set(chosen[:11])
MEN_SQUAD = [
    ("Ville K.", "goalkeeper"), ("Aleksi P.", "goalkeeper"), ("Juho M.", "centre_back"), ("Tuomas R.", "centre_back"),
    ("Eero S.", "centre_back"), ("Lauri H.", "full_back"), ("Joonas V.", "full_back"), ("Arttu L.", "full_back"),
    ("Mikael N.", "midfielder"), ("Santeri J.", "midfielder"), ("Otto K.", "midfielder"), ("Roope A.", "midfielder"),
    ("Veeti T.", "winger"), ("Niko E.", "winger"), ("Aatu P.", "striker"), ("Kasper O.", "striker"),
]  # fmt: skip
MEN_COACH_EMAIL = "mencoach@demo.pathtopro"
RATED_WEEKS = 26  # the whole season so far: enough matches for rating trends


def _teams_and_careers(db: Session, res, players: dict[str, Player], academy: Squad, pw: str, today: date) -> str:
    """Men's team with dual-registered U18s, match ratings for recent games, past seasons.

    The club's men's team (Kakkonen) plays on Sundays, so dual players this weekend have
    the youth match on Saturday and the men's match on Sunday: rule H8 shares their minutes.
    """
    import random

    from domain.models import Appearance, CareerSeason, Registration
    from performance import competitions
    from performance import service as perf

    yesterday = today - timedelta(days=1)
    men = Squad(name="PathToPro FC Men", age_group="SEN", competition="fi_kakkonen", club="PathToPro FC")
    db.add(men)
    db.flush()
    men_coach = StaffMember(name="Mikko Laine", email=MEN_COACH_EMAIL, role=Role.COACH, squad_id=men.id)
    db.add(men_coach)
    db.flush()
    db.add(UserAccount(email=MEN_COACH_EMAIL, password_hash=pw, role=Role.COACH, staff_id=men_coach.id))

    first = date.fromisoformat(res.fixtures[0]["date"])
    sunday = first + timedelta(days=(6 - first.weekday()) % 7)
    men_matches: dict[date, Match] = {}
    k = 0
    while sunday <= today + timedelta(days=14):
        m = Match(squad_id=men.id, kickoff=_at(sunday, 14), opponent=f"FC Opponent {k + 1}", competition="Kakkonen")
        db.add(m)
        men_matches[sunday] = m
        sunday += timedelta(weeks=1)
        k += 1
    db.flush()

    # Dual registration: the three oldest players still under 18
    plist = sorted(players.values(), key=lambda p: p.birth_date)
    dual = [p for p in plist if agent_runner.age_on(p.birth_date, today) < 18][:3]
    for p in dual:
        db.add(Registration(player_id=p.id, squad_id=men.id, season=perf.season_of(today)))
    db.flush()
    # An extra demo login for the first dual player (their own pNN login still works)
    db.add(UserAccount(email=DUAL_EMAIL, password_hash=pw, role=Role.PLAYER, player_id=dual[0].id))

    academy_matches = {
        m.kickoff.date(): m for m in db.scalars(select(Match).where(Match.squad_id == academy.id, Match.kickoff < _at(today, 0)))
    }
    first_rated = today - timedelta(weeks=RATED_WEEKS)

    def form(p: Player, d: date) -> float:
        """Synthetic form curve: most players improve a little over the season, some dip;
        the first dual-registered player clearly improves (demo of the progress line)."""
        slope = 0.08 if p is dual[0] else random.Random(f"form{p.email}").uniform(-0.01, 0.025)
        return max(0.6, 1 + slope * ((d - first_rated).days / 7 - RATED_WEEKS / 2))

    def outcome(d: date, team: str) -> tuple[str, int]:
        r = random.Random(f"{team}{d}")
        return r.choice(["win", "win", "draw", "loss"]), r.choice([0, 0, 1, 1, 2, 3])

    # Academy matches: stats and ratings from the simulated minutes; some match diaries.
    # The 11 players with the most minutes in a match started it.
    starters: dict[str, set[str]] = {}
    by_date: dict[str, list] = {}
    for s in res.sessions:
        if s["kind"] == "match" and s["minutes"] > 0:
            by_date.setdefault(s["date"], []).append(s)
    for d_, rows in by_date.items():
        starters[d_] = pick_xi([(r["player_id"], players[r["player_id"]].position, r["minutes"]) for r in rows])
    for s in res.sessions:
        d = date.fromisoformat(s["date"])
        if s["kind"] != "match" or d < first_rated or d > yesterday or d not in academy_matches or s["minutes"] <= 0:
            continue
        p = players[s["player_id"]]
        rng = random.Random(f"{p.email}{d}")
        minutes = int(s["minutes"])
        result, conceded = outcome(d, "academy")
        a = perf.appearance(db, p, academy_matches[d])
        started = s["player_id"] in starters.get(s["date"], set())
        stats = perf.synthetic_stats(rng, p.position, minutes, result, conceded, form(p, d))
        perf.apply_stats(a, minutes, started, p.position, stats)
        if rng.random() < 0.6 and a.rating is not None:
            a.self_rating = max(1, min(10, round(a.rating + rng.choice([-1, 0, 0, 1]))))
            a.self_rpe, a.diary_at = 7, _at(d, 20)

    # Men's matches for dual players before this week: off the bench after a youth match
    # the day before, otherwise longer
    for p in dual:
        for d, m in men_matches.items():
            if d < first_rated or d > yesterday:
                continue
            rng = random.Random(f"men{p.email}{d}")
            if rng.random() < 0.35:
                continue
            minutes = 30 if (d - timedelta(days=1)) in academy_matches else rng.choice([60, 75, 90])
            result, conceded = outcome(d, "men")
            a = perf.appearance(db, p, m)
            perf.apply_stats(a, minutes, minutes >= 60, p.position, perf.synthetic_stats(rng, p.position, minutes, result, conceded, form(p, d)))
            db.add(SessionLoad(player_id=p.id, match_id=m.id, day=d, rpe=7, minutes=minutes, load_au=7 * minutes))

    # The rest of the men's squad (adults, synthetic, no logins and no health data): they
    # complete each men's match to 11 starters and 3 substitutes around the dual players.
    men_squad = []
    for i, (name, pos) in enumerate(MEN_SQUAD):
        mp = Player(
            squad_id=men.id,
            display_name=name,
            birth_date=today - timedelta(days=round((21 + i % 9) * 365.25)),
            sex="male",
            position=pos,
            exam_dates=[],
            preferred_days=[],
        )
        db.add(mp)
        men_squad.append(mp)
    db.flush()
    for d, m in men_matches.items():
        if d < first_rated or d > yesterday:
            continue
        rng = random.Random(f"menxi{d}")
        result, conceded = outcome(d, "men")
        played = {a.player_id: a for a in db.scalars(select(Appearance).where(Appearance.match_id == m.id))}
        open_slots = dict(FORMATION)
        for a in played.values():
            if a.started:
                g = GROUP_OF[a.position or "midfielder"]
                open_slots[g] = max(0, open_slots[g] - 1)
        pool = list(men_squad)
        rng.shuffle(pool)
        starters_men = []
        for g, n in open_slots.items():
            starters_men += [mp for mp in pool if GROUP_OF[mp.position] == g][:n]
        bench = [mp for mp in pool if mp not in starters_men and mp.position != "goalkeeper"][:3]
        for mp in [*starters_men, *bench]:
            start_ = mp in starters_men
            minutes = rng.choice([90, 90, 90, 80, 70]) if start_ else rng.choice([10, 20, 25, 30])
            a = perf.appearance(db, mp, m)
            perf.apply_stats(a, minutes, start_, mp.position, perf.synthetic_stats(rng, mp.position, minutes, result, conceded))

    # Past seasons on everyone's football CV. The first dual player has a real journey
    # through clubs (synthetic): grassroots, a bigger youth club, the academy, and a
    # season with a men's team in Kolmonen alongside the U17s.
    year = today.year
    journey = [
        (6, "FC Lahti", "U12", "fi_u12_regional", 18, 15, 9, 6),
        (5, "FC Lahti", "U13", "fi_u13_regional", 20, 18, 11, 7),
        (4, "FC Honka", "U14", "fi_u14_regional", 22, 17, 8, 5),
        (3, "FC Honka", "U15", "fi_u15_national", 21, 14, 5, 4),
        (2, "PathToPro FC", "U17", "fi_u17_national", 19, 13, 4, 3),
        (1, "PathToPro FC", "U17", "fi_u17_national", 16, 12, 3, 5),
        (1, "HooGee", "Men", "fi_kolmonen", 9, 3, 1, 1),
    ]
    for back, club, team, comp, apps, starts, goals, assists in journey:
        db.add(
            CareerSeason(
                player_id=dual[0].id,
                season=str(year - back),
                club=club,
                team=team,
                competition=comp,
                apps=apps,
                starts=starts,
                minutes=starts * 75 + (apps - starts) * 25,
                goals=goals,
                assists=assists,
                avg_rating=round(6.6 + 0.08 * (6 - back), 2),
            )
        )
    for p in players.values():
        if p is dual[0]:
            continue
        rng = random.Random(f"cv{p.email}")
        for back in (2, 1):
            age = agent_runner.age_on(p.birth_date, date(year - back, 7, 1))
            if age < 12:
                continue
            comp = competitions.academy_competition(age)
            apps = rng.randint(14, 24)
            starts = rng.randint(apps // 2, apps)
            db.add(
                CareerSeason(
                    player_id=p.id,
                    season=str(year - back),
                    club="PathToPro FC",
                    team=f"{competitions.label(comp).split()[0]} academy",
                    competition=comp,
                    apps=apps,
                    starts=starts,
                    minutes=starts * rng.randint(60, 85) + (apps - starts) * 20,
                    goals=rng.randint(0, 8 if p.position in ("striker", "winger") else 3),
                    assists=rng.randint(0, 6),
                    avg_rating=round(rng.uniform(6.4, 7.4), 2),
                )
            )
    db.flush()
    _finances(db, academy, men, men_coach, list(players.values()), dual, first, today)
    return DUAL_EMAIL


def _finances(db: Session, academy: Squad, men: Squad, men_coach: StaffMember, players: list[Player], dual: list[Player], first: date, today: date) -> None:
    """A season of synthetic club money: academy fees, semi-pro contracts with bonuses for
    the dual players, staff pay, pitch hire, referees, sponsors and gate money."""
    from domain.models import Contract, RecurringItem
    from finance import service as fin

    start = first.replace(day=1)
    coach = db.scalars(select(StaffMember).where(StaffMember.email == "coach@demo.pathtopro")).first()
    physio = db.scalars(select(StaffMember).where(StaffMember.email == "physio@demo.pathtopro")).first()
    for p in players:
        fee = 12000 if agent_runner.age_on(p.birth_date, today) < 16 else 15000
        db.add(Contract(player_id=p.id, squad_id=academy.id, kind="academy_fee", title="Academy fee", direction="income",
                        amount_cents=fee, period="month", starts_on=start))  # fmt: skip
    for p in dual:
        db.add(
            Contract(
                player_id=p.id,
                squad_id=men.id,
                kind="semi_pro",
                title="Semi-pro contract (men's team)",
                direction="expense",
                amount_cents=35000,
                period="month",
                bonus={"appearance": 5000, "goal": 10000, "assist": 5000, "win": 7500, "clean_sheet": 5000, "title": 100000},
                starts_on=start,
            )
        )
    db.add_all(
        [
            Contract(staff_id=coach.id, squad_id=academy.id, kind="staff_salary", title="Head coach", direction="expense",
                     amount_cents=220000, starts_on=start),
            Contract(staff_id=physio.id, squad_id=academy.id, kind="staff_salary", title="Physio (part-time)", direction="expense",
                     amount_cents=160000, starts_on=start),
            Contract(staff_id=men_coach.id, squad_id=men.id, kind="coach_fee", title="Men's team coach", direction="expense",
                     amount_cents=90000, starts_on=start),
            RecurringItem(squad_id=academy.id, name="Pitch hire per training session", category="field_rental", direction="expense",
                          amount_cents=8500, period="session"),
            RecurringItem(squad_id=academy.id, name="Away match travel", category="travel", direction="expense",
                          amount_cents=40000, period="month"),
            RecurringItem(squad_id=academy.id, name="Training equipment", category="equipment", direction="expense",
                          amount_cents=30000, period="month"),
            RecurringItem(squad_id=academy.id, name="Academy sponsor", category="sponsorship", direction="income",
                          amount_cents=200000, period="month"),
            RecurringItem(squad_id=men.id, name="Pitch hire per match", category="field_rental", direction="expense",
                          amount_cents=12000, period="match"),
            RecurringItem(squad_id=men.id, name="Referee fees per match", category="referee", direction="expense",
                          amount_cents=9000, period="match"),
            RecurringItem(squad_id=men.id, name="Gate money per match", category="ticketing", direction="income",
                          amount_cents=45000, period="match"),
            RecurringItem(squad_id=men.id, name="Shirt sponsor", category="sponsorship", direction="income",
                          amount_cents=120000, period="month"),
        ]
    )  # fmt: skip
    db.flush()
    this_month = today.replace(day=1)
    m = start
    while m <= this_month:
        fin.run_month(db, m, paid=m < this_month)
        m = fin.next_month(m)
    # Three families are a month behind with the academy fee
    last = fin.next_month(this_month - timedelta(days=1)) - timedelta(days=1)
    late = db.scalars(
        select(LedgerEntry).where(LedgerEntry.category == "academy_fee", LedgerEntry.day == last.replace(day=1)).order_by(LedgerEntry.description).limit(3)
    ).all()
    for e in late:
        e.status = "due"
    for match in db.scalars(select(Match).where(Match.squad_id == men.id, Match.kickoff < _at(today, 0))):
        fin.match_bonuses(db, match, paid=match.kickoff.date() < this_month)
    db.flush()


def _amateur(db: Session, pw: str, today: date, week_start: date) -> None:
    """A self-guided demo player one benchmark away from levelling up.

    Maya (17) plays for her local club (training Tue and Thu, matches on Saturday), is on
    level 2 and meets 3 of the 6 level-3 benchmarks. Logging a wall-pass test of 18 or
    more completes the checklist and levels her up.
    """
    from pathway import service as pathway

    player, prof = pathway.create_player(
        db,
        name="Maya R.",
        email=AMATEUR_EMAIL,
        birth_date=today - timedelta(days=round(17.4 * 365.25)),
        sex="female",
        position="striker",
        level=2,
        goal="first_team",
        equipment="home",
        team_days=[1, 3],
        match_day=5,
        today=today,
    )
    prof.level_since = today - timedelta(days=60)
    pathway.sync_fixtures(db, player, prof, today - timedelta(days=35))
    db.add(UserAccount(email=AMATEUR_EMAIL, password_hash=pw, role=Role.PLAYER, player_id=player.id))
    tested = today - timedelta(days=12)
    for test, value in {
        "sprint_30m": 5.05, "yoyo_ir1": 600, "standing_long_jump": 172, "juggling": 65, "wall_pass_30s": 16, "weak_foot_10": 4,
    }.items():  # fmt: skip
        db.add(TestResult(player_id=player.id, day=tested, test=test, value=value))
    # Four weeks of logged training: club nights, a solo session, Saturday matches
    for k in range(28, 0, -1):
        d = today - timedelta(days=k)
        wd = d.weekday()
        if wd in (1, 3):
            rpe, minutes = 6, 90
        elif wd == 5:
            rpe, minutes = 8, 70
        elif wd == 6 and k % 14 < 7:
            rpe, minutes = 5, 45
        else:
            continue
        db.add(SessionLoad(player_id=player.id, day=d, rpe=rpe, minutes=minutes, load_au=rpe * minutes))
    for k in range(10, 0, -1):
        d = today - timedelta(days=k)
        db.add(SleepRecord(player_id=player.id, night_of=d, hours=8.1 + (k % 3) * 0.3, source="manual"))
        db.add(
            WellnessCheckin(
                player_id=player.id, day=d, sleep_quality=2, fatigue=3, stress=2, soreness=3, submitted_at=_at(d, 8), duration_s=20
            )
        )
    db.flush()
    agent_runner.run_player(db, player, week_start - timedelta(days=1), "weekly")
    d = week_start
    while d < today:
        agent_runner.run_player(db, player, d, "nightly")
        d += timedelta(days=1)
    db.flush()


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
