"""Player view (mobile-first PWA): check-in, Today, My week, Growth zone, Player card, Road to Pro."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from analytics.maturation import maturity_offset
from analytics.norms import NormTable
from api import clock
from api.db import get_db
from api.deps import CurrentUser, age_on, audit, has_consent, require
from api.services import agent_runner, gym_view, views
from domain.enums import ConsentDataType, Position, ProposalStatus, Role, SessionType
from domain.models import (
    AmateurProfile,
    Anthropometrics,
    Drill,
    IDPGoal,
    Player,
    Proposal,
    SessionLoad,
    SleepRecord,
    TaskCompletion,
    TestResult,
    WellnessCheckin,
)
from pathway import levels
from pathway import service as pathway
from performance import service as performance

router = APIRouter(prefix="/api/me", tags=["player"])
NORMS = NormTable.load()


def _me(user: CurrentUser, db: Session) -> Player:
    if user.account.player_id is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Player accounts only")
    return db.get(Player, user.account.player_id)


# --------------------------------------------------------------------------- check-in


class CheckIn(BaseModel):
    sleep_quality: int = Field(ge=1, le=7, description="1 = very good ... 7 = very bad")
    fatigue: int = Field(ge=1, le=7)
    stress: int = Field(ge=1, le=7)
    soreness: int = Field(ge=1, le=7)
    mood: Literal["green", "amber", "red"] = "green"
    pain: bool = False
    sleep_hours: float | None = Field(default=None, ge=0, le=16)
    duration_s: float | None = Field(default=None, ge=0, le=3600)


@router.post("/checkin")
def checkin(body: CheckIn, user: CurrentUser = Depends(require(Role.PLAYER)), db: Session = Depends(get_db)) -> dict:
    p = _me(user, db)
    today = clock.today()
    if not has_consent(db, p, ConsentDataType.WELLNESS, today):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Wellness check-ins need consent from your guardian")
    chk = db.scalars(select(WellnessCheckin).where(WellnessCheckin.player_id == p.id, WellnessCheckin.day == today)).first()
    if chk is None:
        chk = WellnessCheckin(player_id=p.id, day=today)
        db.add(chk)
    chk.sleep_quality, chk.fatigue, chk.stress, chk.soreness = (
        body.sleep_quality,
        body.fatigue,
        body.stress,
        body.soreness,
    )
    chk.mood_red, chk.pain_reported = body.mood == "red", body.pain
    chk.submitted_at, chk.duration_s = datetime.now(UTC), body.duration_s
    if body.sleep_hours is not None and has_consent(db, p, ConsentDataType.SLEEP, today):
        rec = db.scalars(select(SleepRecord).where(SleepRecord.player_id == p.id, SleepRecord.night_of == today)).first()
        if rec is None:
            db.add(SleepRecord(player_id=p.id, night_of=today, hours=body.sleep_hours, source="manual"))
        else:
            rec.hours = body.sleep_hours
    db.flush()
    audit(db, user, "create", "wellness_checkin", chk.id)
    # The Monitor runs on every check-in; red check-ins and pain go straight to a named adult.
    result = agent_runner.run_player(db, p, today, "checkin")
    db.commit()
    return {"escalated": result["escalations"] > 0, "today": today_view(p, user, db)}


# --------------------------------------------------------------------------- Today


TASKS = {
    "sleep": "Lights out by 22:00 (9 h sleep)",
    "hydrate": "Drink 2 litres of water",
    "mobility": "10 min mobility routine",
    "recovery": "Foam roll legs for 8 minutes",
    "breathing": "5 min breathing before bed",
}


def _tasks_for(band: str | None, flags: set[str]) -> list[str]:
    out = ["sleep", "hydrate"]
    if band in ("amber", "red") or "short_sleep" in flags:
        out.append("breathing")
    if band == "red" or "load_spike" in flags:
        out.append("recovery")
    out.append("mobility")
    return out


SAFETY_ADVICE = {
    "pain_report": "You reported pain. Don't train through it today. Tell a parent or your club coach, and see a doctor or physio if it's still there tomorrow or gets worse.",
    "red_mood": "Thanks for being honest. Talk to someone you trust today: a parent, a coach or a friend. If you ever feel unsafe, call your local emergency number.",
    "missed_checkins": "We haven't heard from you for a few days and your battery is low. Take it easy and check in when you can.",
}


def today_view(p: Player, user: CurrentUser, db: Session) -> dict:
    today = clock.today()
    prof = pathway.profile(db, p)
    if prof is not None:
        pathway.ensure_week(db, p, views.week_start(today), today)
    st = views.status(db, p.id, today)
    shown = st or views.latest_status(db, p.id, today)
    plan = agent_runner.plan_days(db, p, today, 1)[0]
    flags = {f["kind"] for f in (shown.flags if shown else [])}
    done = {
        t.task for t in db.scalars(select(TaskCompletion).where(TaskCompletion.player_id == p.id, TaskCompletion.day == today))
    }
    days = views.checkin_days(db, p.id)
    audit(db, user, "read", "daily_status", p.id, view="today")
    extra: dict = {
        "gym": gym_view.programme(db, p, plan, today),
        "pathway": None,
        "safety": [],
        "logged": [],
        "diary_due": performance.diary_due(db, p, today),
    }
    if prof is not None:
        a = pathway.assessment(db, p, prof, today)
        extra["pathway"] = {
            "level": a["level"],
            "name": a["name"],
            "next": a["next"],
            "consistency": a["consistency"],
            "focus": [levels.tests()[f]["label"] for f in a["focus"]],
        }
        extra["content"] = pathway.session_content(plan.kind.value, today.weekday() in prof.team_days, a["focus"])
        if st is not None:
            extra["safety"] = [SAFETY_ADVICE[f["kind"]] for f in st.flags if f["kind"] in SAFETY_ADVICE]
        extra["logged"] = [
            {"minutes": sl.minutes, "rpe": sl.rpe, "load": sl.load_au}
            for sl in db.scalars(select(SessionLoad).where(SessionLoad.player_id == p.id, SessionLoad.day == today))
        ]
        extra["consent"] = {
            "wellness": has_consent(db, p, ConsentDataType.WELLNESS, today),
            "test_results": has_consent(db, p, ConsentDataType.TEST_RESULTS, today),
        }
    return {
        **extra,
        "date": today.isoformat(),
        "name": p.display_name,
        "checked_in": today in days,
        "readiness": views.status_json(shown) if shown else None,
        "readiness_is_today": st is not None,
        "flags": [{"kind": k, "text": views.FLAG_PLAYER_TEXT[k]} for k in flags if k in views.FLAG_PLAYER_TEXT],
        "session": views.day_json(plan),
        "tasks": [{"id": t, "label": TASKS[t], "done": t in done} for t in _tasks_for(shown.band if shown else None, flags)],
        "why": views.why_cards(db, p),
        "streak": views.streak(days, today),
    }


@router.get("/today")
def today(user: CurrentUser = Depends(require(Role.PLAYER)), db: Session = Depends(get_db)) -> dict:
    out = today_view(_me(user, db), user, db)
    db.commit()
    return out


@router.post("/tasks/{task}/toggle")
def toggle_task(task: str, user: CurrentUser = Depends(require(Role.PLAYER)), db: Session = Depends(get_db)) -> dict:
    if task not in TASKS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown task")
    p, today = _me(user, db), clock.today()
    t = db.scalars(
        select(TaskCompletion).where(
            TaskCompletion.player_id == p.id, TaskCompletion.day == today, TaskCompletion.task == task
        )
    ).first()
    if t:
        db.delete(t)
    else:
        db.add(TaskCompletion(player_id=p.id, day=today, task=task))
    db.commit()
    return {"task": task, "done": t is None}


# --------------------------------------------------------------------------- My week


@router.get("/week")
def week(offset: int = 0, user: CurrentUser = Depends(require(Role.PLAYER)), db: Session = Depends(get_db)) -> dict:
    p = _me(user, db)
    start = views.week_start(clock.today()) + timedelta(weeks=offset)
    prof = pathway.profile(db, p)
    if prof is not None:
        pathway.ensure_week(db, p, start, clock.today())
    this = views.week_days(db, p, start)
    last = views.week_days(db, p, start - timedelta(weeks=1))
    actual = views.daily_loads(db, p.id, start - timedelta(weeks=1), start + timedelta(days=6))
    for d in this + last:
        d["actual_load"] = actual.get(date.fromisoformat(d["date"]))
    if prof is not None:
        focus = pathway.assessment(db, p, prof, clock.today())["focus"]
        for d in this:
            team = date.fromisoformat(d["date"]).weekday() in prof.team_days
            d["team_day"] = team
            d["content"] = pathway.session_content(d["kind"], team, focus)
    audit(db, user, "read", "weekly_plan", p.id)
    db.commit()
    return {"start": start.isoformat(), "today": clock.today().isoformat(), "days": this, "last_week": last}


# --------------------------------------------------------------------------- Growth zone


class Measurement(BaseModel):
    height_cm: float = Field(ge=120, le=220)
    sitting_height_cm: float = Field(ge=60, le=120)
    weight_kg: float = Field(ge=25, le=130)


@router.get("/growth")
def growth(user: CurrentUser = Depends(require(Role.PLAYER)), db: Session = Depends(get_db)) -> dict:
    p = _me(user, db)
    today = clock.today()
    if not has_consent(db, p, ConsentDataType.ANTHROPOMETRICS, today):
        return {"consent": False, "measurements": []}
    rows = db.scalars(select(Anthropometrics).where(Anthropometrics.player_id == p.id).order_by(Anthropometrics.day)).all()
    pts = []
    for a in rows:
        age = age_on(p.birth_date, a.day)
        mo = maturity_offset(age, a.height_cm, a.sitting_height_cm, a.weight_kg)
        pts.append(
            {
                "date": a.day.isoformat(),
                "age": round(age, 2),
                "height_cm": a.height_cm,
                "sitting_height_cm": a.sitting_height_cm,
                "weight_kg": a.weight_kg,
                "maturity_offset": round(mo, 2),
            }
        )
    latest = pts[-1] if pts else None
    phv_age = None if latest is None else round(latest["age"] - latest["maturity_offset"], 2)
    st = views.latest_status(db, p.id, today)
    audit(db, user, "read", "anthropometrics", p.id)
    db.commit()
    return {
        "consent": True,
        "measurements": pts,
        "phv_age": phv_age,
        "phv_window": None if phv_age is None else [round(phv_age - 1, 2), round(phv_age + 1, 2)],
        "in_phv_window": bool(st and st.in_phv_window),
        "age_now": round(age_on(p.birth_date, today), 2),
        "next_measurement_due": None if latest is None else (date.fromisoformat(latest["date"]) + timedelta(days=28)).isoformat(),
    }


@router.post("/growth")
def add_measurement(
    body: Measurement, user: CurrentUser = Depends(require(Role.PLAYER)), db: Session = Depends(get_db)
) -> dict:
    p = _me(user, db)
    today = clock.today()
    if not has_consent(db, p, ConsentDataType.ANTHROPOMETRICS, today):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Growth tracking needs consent from your guardian")
    if body.sitting_height_cm >= body.height_cm:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Sitting height must be less than standing height")
    db.add(Anthropometrics(player_id=p.id, day=today, **body.model_dump()))
    audit(db, user, "create", "anthropometrics", p.id)
    db.commit()
    return growth(user, db)


# --------------------------------------------------------------------------- Player card


@router.get("/card")
def card(user: CurrentUser = Depends(require(Role.PLAYER)), db: Session = Depends(get_db)) -> dict:
    p = _me(user, db)
    out = player_card(db, p, clock.today())
    audit(db, user, "read", "test_results", p.id)
    db.commit()
    return out


def player_card(db: Session, p: Player, today: date) -> dict:
    from analytics.maturation import MaturityStatus

    st = views.latest_status(db, p.id, today)
    mo = st.maturity_offset if st else None
    status_ = (
        MaturityStatus.CIRCA_PHV
        if mo is None
        else MaturityStatus.PRE_PHV
        if mo < -1
        else MaturityStatus.POST_PHV
        if mo > 1
        else MaturityStatus.CIRCA_PHV
    )
    tests = db.scalars(select(TestResult).where(TestResult.player_id == p.id).order_by(TestResult.day)).all()
    history: dict[str, list] = {}
    for t in tests:
        history.setdefault(t.test, []).append({"date": t.day.isoformat(), "value": t.value})
    drills = _suggested_drills(db, p)
    attrs = []
    groups = {"speed": ["sprint_10m", "sprint_30m"], "power": ["cmj"], "endurance": ["yoyo_ir1"]}
    for attr, kpis in groups.items():
        for kpi in kpis:
            if kpi not in history:
                continue
            value = history[kpi][-1]["value"]
            attrs.append(
                {
                    "attribute": attr,
                    "kpi": kpi,
                    "label": views.kpi_label(kpi),
                    "unit": views.UNITS[kpi],
                    "value": value,
                    "bio_percentile": round(NORMS.bio_banded_percentile(kpi, value, status_)),
                    "age_percentile": round(NORMS.age_percentile(kpi, value, age_on(p.birth_date, today))),
                    "history": history[kpi],
                    "drills": [d for d in drills if d["kpi"] == kpi],
                }
            )
    return {"name": p.display_name, "maturity_status": status_.value, "attributes": attrs}


def _suggested_drills(db: Session, p: Player) -> list[dict]:
    prop = db.scalars(
        select(Proposal)
        .where(
            Proposal.player_id == p.id,
            Proposal.kind == "drill_suggestion",
            Proposal.status == ProposalStatus.AUTO_APPLIED,
        )
        .order_by(Proposal.created_at.desc())
        .limit(1)
    ).first()
    if prop is None:
        return []
    out = []
    for did in prop.payload.get("drills", []):
        d = db.get(Drill, did)
        if d:
            out.append(
                {"id": d.id, "name": d.name, "kpi": d.kpi, "minutes": d.minutes, "rpe": d.typical_rpe, "description": d.description}
            )
    return out


# --------------------------------------------------------------------------- Road to Pro


@router.get("/roadmap")
def roadmap(user: CurrentUser = Depends(require(Role.PLAYER)), db: Session = Depends(get_db)) -> dict:
    p = _me(user, db)
    out = roadmap_view(db, p, clock.today())
    audit(db, user, "read", "idp_goals", p.id)
    db.commit()
    return out


def roadmap_view(db: Session, p: Player, today: date) -> dict:
    goals = db.scalars(select(IDPGoal).where(IDPGoal.player_id == p.id).order_by(IDPGoal.starts_on)).all()
    latest = agent_runner.latest_tests(db, p)
    lower_better = {"sprint_10m", "sprint_30m"}
    items = []
    for g in goals:
        cur = latest.get(g.kpi, g.baseline_value)
        span = g.target_value - g.baseline_value
        progress = 0.0 if span == 0 else max(0.0, min(1.0, (cur - g.baseline_value) / span))
        items.append(
            {
                "id": g.id,
                "kpi": g.kpi,
                "label": views.kpi_label(g.kpi),
                "unit": views.UNITS.get(g.kpi, ""),
                "baseline": g.baseline_value,
                "target": g.target_value,
                "current": cur,
                "lower_is_better": g.kpi in lower_better,
                "starts_on": g.starts_on.isoformat(),
                "ends_on": g.ends_on.isoformat(),
                "sessions_per_week": g.sessions_per_week,
                "progress": round(progress, 2),
                "status": g.status,
            }
        )
    test_days = sorted({t.day for t in db.scalars(select(TestResult).where(TestResult.player_id == p.id))})
    next_test = (test_days[-1] + timedelta(days=28)) if test_days else today + timedelta(days=7)
    checkpoints = [{"date": d.isoformat(), "done": True} for d in test_days] + [
        {"date": next_test.isoformat(), "done": False}
    ]
    days = views.checkin_days(db, p.id)
    met = sum(1 for g in goals if g.status == "met")
    return {
        "goals": items,
        "checkpoints": checkpoints,
        "badges": views.badges(len(days), met),
        "streak": views.streak(days, today),
        "session_types": [t.value for t in SessionType],
    }


# --------------------------------------------------------------------------- Gym


@router.get("/gym")
def gym(offset: int = 0, user: CurrentUser = Depends(require(Role.PLAYER)), db: Session = Depends(get_db)) -> dict:
    """This week's gym sessions: the shared part for every player plus the position block."""
    p = _me(user, db)
    today = clock.today()
    start = views.week_start(today) + timedelta(weeks=max(-1, min(1, offset)))
    pathway.ensure_week(db, p, start, today)
    out = gym_view.week(db, p, start, today)
    audit(db, user, "read", "weekly_plan", p.id, view="gym")
    db.commit()
    return out


class PositionBody(BaseModel):
    position: Position


@router.put("/position")
def set_position(body: PositionBody, user: CurrentUser = Depends(require(Role.PLAYER)), db: Session = Depends(get_db)) -> dict:
    """Self-guided players set their own position (academy positions are set by staff)."""
    p = _me(user, db)
    if not pathway.is_amateur(p):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your coach sets your position")
    p.position = body.position.value
    audit(db, user, "update", "player", p.id, position=p.position)
    db.commit()
    return {"position": p.position}


# --------------------------------------------------------------------------- Self-guided pathway


def _amateur(user: CurrentUser, db: Session) -> tuple[Player, AmateurProfile]:
    p = _me(user, db)
    prof = pathway.profile(db, p)
    if prof is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "For self-guided players: your academy plans your development")
    return p, prof


def pathway_view(db: Session, p: Player, prof: AmateurProfile, today: date, a: dict | None = None) -> dict:
    a = a or pathway.assessment(db, p, prof, today)
    age = age_on(p.birth_date, today)
    pending = [g.invite_code for g in p.guardians if g.invite_code]
    return {
        "profile": {
            "level": prof.level,
            "level_since": prof.level_since.isoformat(),
            "goal": prof.goal,
            "goal_label": levels.config()["goals"].get(prof.goal, prof.goal),
            "equipment": prof.equipment,
            "team_days": prof.team_days,
            "match_day": prof.match_day,
            "position": p.position,
        },
        "assessment": a,
        "ladder": levels.ladder(age, p.sex),
        "goals": levels.config()["goals"],
        "can_store_tests": has_consent(db, p, ConsentDataType.TEST_RESULTS, today),
        "guardian_invite": pending[0] if pending else None,
        "history": [
            {"test": t.test, "date": t.day.isoformat(), "value": t.value}
            for t in db.scalars(select(TestResult).where(TestResult.player_id == p.id).order_by(TestResult.day))
            if t.test in levels.tests()
        ],
        "note": "Benchmarks are placeholder values for a demo, adjusted for age and sex. They are not validated norms.",
    }


@router.get("/pathway")
def get_pathway(user: CurrentUser = Depends(require(Role.PLAYER)), db: Session = Depends(get_db)) -> dict:
    p, prof = _amateur(user, db)
    out = pathway_view(db, p, prof, clock.today())
    audit(db, user, "read", "test_results", p.id, view="pathway")
    db.commit()
    return out


class PathwayProfile(BaseModel):
    goal: Literal["next_level", "first_team", "trial", "fitness"] | None = None
    equipment: Literal["none", "home", "gym"] | None = None
    team_days: list[int] | None = Field(default=None, max_length=5)
    match_day: int | None = Field(default=None, ge=-1, le=6, description="-1 = no regular match")
    position: Position | None = None


@router.put("/pathway/profile")
def update_pathway(body: PathwayProfile, user: CurrentUser = Depends(require(Role.PLAYER)), db: Session = Depends(get_db)) -> dict:
    p, prof = _amateur(user, db)
    today = clock.today()
    schedule = False
    if body.goal:
        prof.goal = body.goal
    if body.equipment:
        prof.equipment = body.equipment
    if body.position:
        p.position = body.position.value
    if body.team_days is not None:
        if any(not 0 <= d <= 6 for d in body.team_days):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "team_days are weekdays 0-6")
        prof.team_days, schedule = sorted(set(body.team_days)), True
    if body.match_day is not None:
        prof.match_day, schedule = (None if body.match_day < 0 else body.match_day), True
    db.flush()
    if schedule:
        pathway.sync_fixtures(db, p, prof, today)
        db.flush()
        pathway.replan_from(db, p, today, "settings")
    audit(db, user, "update", "amateur_profile", p.id)
    db.commit()
    return pathway_view(db, p, prof, today)


TEST_RANGE = {
    "sprint_30m": (3.5, 9.0),
    "yoyo_ir1": (40, 4000),
    "standing_long_jump": (80, 350),
    "juggling": (0, 10000),
    "wall_pass_30s": (0, 60),
    "weak_foot_10": (0, 10),
}


class TestEntry(BaseModel):
    __test__ = False  # not a pytest class
    test: str
    value: float


@router.post("/pathway/tests")
def add_test(body: TestEntry, user: CurrentUser = Depends(require(Role.PLAYER)), db: Session = Depends(get_db)) -> dict:
    p, prof = _amateur(user, db)
    today = clock.today()
    if body.test not in TEST_RANGE:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown test")
    lo, hi = TEST_RANGE[body.test]
    if not lo <= body.value <= hi:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Value must be between {lo} and {hi}")
    if not has_consent(db, p, ConsentDataType.TEST_RESULTS, today):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Test results need consent from your parent")
    db.add(TestResult(player_id=p.id, day=today, test=body.test, value=body.value))
    db.flush()
    a = pathway.evaluate(db, p, prof, today)
    audit(db, user, "create", "test_results", p.id, test=body.test)
    if a.get("levelled_up"):
        pathway.replan_from(db, p, today + timedelta(days=1), "level_up")
    db.commit()
    return {**pathway_view(db, p, prof, today, a), "levelled_up": bool(a.get("levelled_up"))}


class LoggedSession(BaseModel):
    kind: SessionType
    minutes: int = Field(ge=5, le=180)
    rpe: int = Field(ge=1, le=10)
    day: date | None = None


@router.post("/log")
def log_session(body: LoggedSession, user: CurrentUser = Depends(require(Role.PLAYER)), db: Session = Depends(get_db)) -> dict:
    """Self-guided players log what they actually did (session RPE x minutes = load)."""
    p, prof = _amateur(user, db)
    today = clock.today()
    day = body.day or today
    if day > today or day < today - timedelta(days=7):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Log sessions from the last 7 days")
    if body.kind == SessionType.REST:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Nothing to log on a rest day")
    if not has_consent(db, p, ConsentDataType.WELLNESS, today):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Logging training needs consent from your parent")
    db.add(SessionLoad(player_id=p.id, day=day, rpe=body.rpe, minutes=body.minutes, load_au=body.rpe * body.minutes))
    db.flush()
    a = pathway.evaluate(db, p, prof, today)
    audit(db, user, "create", "session_load", p.id)
    db.commit()
    return {"today": today_view(p, user, db), "levelled_up": bool(a.get("levelled_up"))}


# --------------------------------------------------------------------------- Career and match diary


@router.get("/career")
def career(user: CurrentUser = Depends(require(Role.PLAYER)), db: Session = Depends(get_db)) -> dict:
    p = _me(user, db)
    out = performance.career_view(db, p, clock.today())
    audit(db, user, "read", "appearance", p.id, view="career")
    db.commit()
    return out


class PastSeason(BaseModel):
    season: str = Field(pattern=r"^(19|20)\d\d$")
    club: str = Field(min_length=1, max_length=100)
    team: str = Field(min_length=1, max_length=100)
    competition: str
    apps: int = Field(default=0, ge=0, le=80)
    starts: int = Field(default=0, ge=0, le=80)
    minutes: int = Field(default=0, ge=0, le=7200)
    goals: int = Field(default=0, ge=0, le=150)
    assists: int = Field(default=0, ge=0, le=150)
    avg_rating: float | None = Field(default=None, ge=3, le=10)


@router.post("/career/seasons", status_code=201)
def add_season(body: PastSeason, user: CurrentUser = Depends(require(Role.PLAYER)), db: Session = Depends(get_db)) -> dict:
    from domain.models import CareerSeason
    from performance import competitions

    p = _me(user, db)
    if competitions.get(body.competition) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown competition")
    if int(body.season) > clock.today().year:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Add past seasons only")
    if body.starts > body.apps:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Starts can't be more than appearances")
    db.add(CareerSeason(player_id=p.id, **body.model_dump()))
    audit(db, user, "create", "career_season", p.id)
    db.commit()
    return performance.career_view(db, p, clock.today())


@router.delete("/career/seasons/{season_id}")
def delete_season(season_id: str, user: CurrentUser = Depends(require(Role.PLAYER)), db: Session = Depends(get_db)) -> dict:
    from domain.models import CareerSeason

    p = _me(user, db)
    row = db.get(CareerSeason, season_id)
    if row is None or row.player_id != p.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Season not found")
    db.delete(row)
    audit(db, user, "delete", "career_season", p.id)
    db.commit()
    return performance.career_view(db, p, clock.today())


class Diary(BaseModel):
    minutes: int = Field(ge=0, le=130)
    position: Position | None = None
    goals: int = Field(default=0, ge=0, le=10)
    assists: int = Field(default=0, ge=0, le=10)
    self_rating: int = Field(ge=1, le=10)
    rpe: int = Field(default=7, ge=1, le=10)


@router.post("/matches/{match_id}/diary")
def match_diary(match_id: str, body: Diary, user: CurrentUser = Depends(require(Role.PLAYER)), db: Session = Depends(get_db)) -> dict:
    """After the final whistle: minutes, position, goals, assists, self-rating and effort."""
    from domain.models import Match

    p = _me(user, db)
    m = db.get(Match, match_id)
    today = clock.today()
    if m is None or not performance.is_registered(db, p, m.squad_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Match not found")
    if m.kickoff.date() > today:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The match hasn't been played yet")
    if not has_consent(db, p, ConsentDataType.WELLNESS, today):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "The match diary needs consent from your parent")
    performance.apply_diary(
        db, p, m, body.minutes, body.position.value if body.position else None, body.goals, body.assists, body.self_rating, body.rpe
    )
    audit(db, user, "create", "appearance", p.id, diary=True)
    db.commit()
    return performance.career_view(db, p, today)


@router.get("/matches/{match_id}")
def match_lineup(match_id: str, user: CurrentUser = Depends(require(Role.PLAYER)), db: Session = Depends(get_db)) -> dict:
    """The line-up and ratings of a match the player's team played (like a ratings app).
    Teammates' own self-ratings stay private."""
    from domain.models import Match, Squad

    p = _me(user, db)
    m = db.get(Match, match_id)
    if m is None or not performance.is_registered(db, p, m.squad_id) or m.kickoff.date() > clock.today():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Match not found")
    rows = performance.match_rows(db, m, performance.team_players(db, m.squad_id))
    for r in rows:
        if r["player"]["id"] != p.id:
            r["self_rating"] = None
    squad = db.get(Squad, m.squad_id)
    audit(db, user, "read", "appearance", m.id)
    db.commit()
    return {
        "match": {"id": m.id, "date": m.kickoff.date().isoformat(), "opponent": m.opponent, "team": squad.name if squad else "", "competition": m.competition},
        "players": rows,
        "me": p.id,
    }
