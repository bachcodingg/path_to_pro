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
from api.services import agent_runner, views
from domain.enums import ConsentDataType, ProposalStatus, Role, SessionType
from domain.models import (
    Anthropometrics,
    Drill,
    IDPGoal,
    Player,
    Proposal,
    SleepRecord,
    TaskCompletion,
    TestResult,
    WellnessCheckin,
)

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


def today_view(p: Player, user: CurrentUser, db: Session) -> dict:
    today = clock.today()
    st = views.status(db, p.id, today)
    shown = st or views.latest_status(db, p.id, today)
    plan = agent_runner.plan_days(db, p, today, 1)[0]
    flags = {f["kind"] for f in (shown.flags if shown else [])}
    done = {
        t.task for t in db.scalars(select(TaskCompletion).where(TaskCompletion.player_id == p.id, TaskCompletion.day == today))
    }
    days = views.checkin_days(db, p.id)
    audit(db, user, "read", "daily_status", p.id, view="today")
    return {
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
    this = views.week_days(db, p, start)
    last = views.week_days(db, p, start - timedelta(weeks=1))
    actual = views.daily_loads(db, p.id, start - timedelta(weeks=1), start + timedelta(days=6))
    for d in this + last:
        d["actual_load"] = actual.get(date.fromisoformat(d["date"]))
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
