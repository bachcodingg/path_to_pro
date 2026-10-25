"""Guardian view: weekly summary, consent switches per data type, data export and delete."""

from __future__ import annotations

import statistics
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from api import clock
from api.db import get_db
from api.deps import CurrentUser, age_on, audit, has_consent, player_in_scope, require
from api.routers.player import roadmap_view
from api.services import views
from domain.enums import ConsentDataType, Role
from domain.models import (
    Anthropometrics,
    DailyStatus,
    GuardianAlert,
    HRVRecord,
    Player,
    SessionLoad,
    SleepRecord,
    TestResult,
    WellnessCheckin,
    player_guardians,
)
from domain.models import ConsentRecord as Consent

router = APIRouter(prefix="/api/guardian", tags=["guardian"])

CONSENT_TEXT = {
    ConsentDataType.WELLNESS: "Morning check-in (sleep quality, fatigue, stress, soreness, mood)",
    ConsentDataType.SLEEP: "Sleep duration",
    ConsentDataType.HRV: "Heart-rate variability from a wearable",
    ConsentDataType.ANTHROPOMETRICS: "Height, sitting height and weight (growth tracking)",
    ConsentDataType.TEST_RESULTS: "Fitness test results",
}


@router.get("/children")
def children(user: CurrentUser = Depends(require(Role.GUARDIAN)), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.execute(
        select(Player).join(player_guardians).where(player_guardians.c.guardian_id == user.account.guardian_id)
    ).scalars()
    today = clock.today()
    return [{"id": p.id, "name": p.display_name, "age": round(age_on(p.birth_date, today), 1)} for p in rows]


@router.get("/children/{player_id}/summary")
def summary(player_id: str, user: CurrentUser = Depends(require(Role.GUARDIAN)), db: Session = Depends(get_db)) -> dict:
    p = player_in_scope(player_id, user, db)
    today = clock.today()
    start = views.week_start(today)
    loads = views.daily_loads(db, p.id, start, today)
    sleeps = [
        s.hours
        for s in db.scalars(select(SleepRecord).where(SleepRecord.player_id == p.id, SleepRecord.night_of >= start - timedelta(days=7)))
    ]
    rm = roadmap_view(db, p, today)
    alerts = db.scalars(
        select(GuardianAlert)
        .where(
            GuardianAlert.player_id == p.id,
            GuardianAlert.guardian_id == user.account.guardian_id,
            GuardianAlert.seen_at.is_(None),
        )
        .order_by(GuardianAlert.created_at.desc())
    )
    audit(db, user, "read", "weekly_summary", p.id)
    db.commit()
    return {
        "name": p.display_name,
        "week_start": start.isoformat(),
        "sessions_done": sum(1 for v in loads.values() if v > 0),
        "avg_sleep_h": None if not sleeps else round(statistics.fmean(sleeps), 1),
        "goals": [{"label": g["label"], "progress": g["progress"]} for g in rm["goals"] if g["status"] == "active"],
        "streak": rm["streak"],
        # Safety flags with no staff to take them (self-guided players): the parent is told.
        "alerts": [
            {"id": a.id, "kind": a.kind, "text": ALERT_TEXT.get(a.kind, a.kind), "created_at": a.created_at.isoformat()}
            for a in alerts
        ],
    }


ALERT_TEXT = {
    "pain_report": "reported pain in this morning's check-in. The next two days are now rest only. "
    "Please check in with them, and see a doctor or physio if it lasts or gets worse.",
    "red_mood": "had a really low mood in this morning's check-in. The plan is now easy for two days. "
    "Please find a moment to talk today.",
    "missed_checkins": "hasn't checked in for a few days and their readiness looks low. Please check how they are.",
}


@router.post("/children/{player_id}/alerts/{alert_id}/seen")
def alert_seen(
    player_id: str, alert_id: str, user: CurrentUser = Depends(require(Role.GUARDIAN)), db: Session = Depends(get_db)
) -> dict:
    p = player_in_scope(player_id, user, db)
    a = db.get(GuardianAlert, alert_id)
    if a is None or a.player_id != p.id or a.guardian_id != user.account.guardian_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found")
    a.seen_at = datetime.now(UTC)
    audit(db, user, "acknowledge", "guardian_alert", a.id, player=p.id)
    db.commit()
    return {"id": a.id, "seen_at": a.seen_at.isoformat()}


@router.get("/children/{player_id}/consent")
def get_consent(player_id: str, user: CurrentUser = Depends(require(Role.GUARDIAN)), db: Session = Depends(get_db)) -> dict:
    p = player_in_scope(player_id, user, db)
    today = clock.today()
    return {
        "age": round(age_on(p.birth_date, today), 1),
        "items": [
            {"data_type": dt.value, "text": CONSENT_TEXT[dt], "granted": has_consent(db, p, dt, today)}
            for dt in ConsentDataType
        ],
    }


class ConsentChange(BaseModel):
    data_type: ConsentDataType
    granted: bool


@router.put("/children/{player_id}/consent")
def set_consent(
    player_id: str, body: ConsentChange, user: CurrentUser = Depends(require(Role.GUARDIAN)), db: Session = Depends(get_db)
) -> dict:
    p = player_in_scope(player_id, user, db)
    db.add(
        Consent(
            player_id=p.id,
            guardian_id=user.account.guardian_id,
            data_type=body.data_type,
            granted=body.granted,
            recorded_at=datetime.now(UTC),
        )
    )
    audit(db, user, "consent", "consent_record", p.id, data_type=body.data_type.value, granted=body.granted)
    db.commit()
    return get_consent(player_id, user, db)


@router.get("/children/{player_id}/export")
def export(player_id: str, user: CurrentUser = Depends(require(Role.GUARDIAN)), db: Session = Depends(get_db)):
    """All stored data about the player, as JSON (GDPR Art. 15/20)."""
    p = player_in_scope(player_id, user, db)

    def rows(model, *cols):
        return [
            {c: (v.isoformat() if hasattr(v, "isoformat") else v) for c in cols for v in [getattr(r, c)]}
            for r in db.scalars(select(model).where(model.player_id == p.id))
        ]

    data = {
        "player": {"name": p.display_name, "birth_date": p.birth_date.isoformat()},
        "session_loads": rows(SessionLoad, "day", "rpe", "minutes", "load_au"),
        "wellness_checkins": rows(WellnessCheckin, "day", "sleep_quality", "fatigue", "stress", "soreness", "mood_red", "pain_reported"),
        "sleep": rows(SleepRecord, "night_of", "hours"),
        "hrv": rows(HRVRecord, "day", "ln_rmssd"),
        "anthropometrics": rows(Anthropometrics, "day", "height_cm", "sitting_height_cm", "weight_kg"),
        "tests": rows(TestResult, "day", "test", "value"),
        "consents": rows(Consent, "data_type", "granted", "recorded_at"),
        "guardian_alerts": rows(GuardianAlert, "kind", "created_at", "seen_at"),
    }
    audit(db, user, "export", "player", p.id)
    db.commit()
    return JSONResponse(data, headers={"Content-Disposition": f"attachment; filename=pathtopro-{p.id[:8]}.json"})


@router.delete("/children/{player_id}/data")
def delete_data(player_id: str, user: CurrentUser = Depends(require(Role.GUARDIAN)), db: Session = Depends(get_db)) -> dict:
    """Deletes all health data about the player (GDPR Art. 17). The account remains."""
    p = player_in_scope(player_id, user, db)
    counts = {}
    for model in (SessionLoad, WellnessCheckin, SleepRecord, HRVRecord, Anthropometrics, TestResult, DailyStatus, GuardianAlert):
        counts[model.__tablename__] = db.execute(delete(model).where(model.player_id == p.id)).rowcount
    audit(db, user, "delete", "player_health_data", p.id, **counts)
    db.commit()
    if not any(counts.values()):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No health data stored")
    return {"deleted": counts}
