"""Readiness weight calibration from staff ratings stored in the database."""

from __future__ import annotations

import json
from dataclasses import asdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from analytics.calibration import KEYS, MIN_SAMPLES, MIN_WEIGHT, RatedDay, fit_weights
from analytics.readiness import Band, active_config, set_active_weights
from domain.models import AppSetting, DailyStatus, Player, StaffRating

SETTING_KEY = "readiness_weights"


def rated_days(db: Session, squad_id: str | None) -> list[RatedDay]:
    q = select(StaffRating, DailyStatus).join(
        DailyStatus, (DailyStatus.player_id == StaffRating.player_id) & (DailyStatus.day == StaffRating.day)
    )
    if squad_id:
        q = q.join(Player, Player.id == StaffRating.player_id).where(Player.squad_id == squad_id)
    out = []
    for rating, status in db.execute(q):
        if status.components:
            out.append(RatedDay(rating.player_id, dict(status.components), Band(rating.band)))
    return out


def report(db: Session, squad_id: str | None) -> dict:
    cfg = active_config()
    samples = rated_days(db, squad_id)
    cal = fit_weights(samples, cfg)
    return {
        "n": len(samples),
        "min_samples": MIN_SAMPLES,
        "enough_data": cal.enough_data,
        "current": {k: round(cfg.weights[k], 2) for k in KEYS},
        "suggested": {k: round(cal.weights[k], 2) for k in KEYS},
        "before": asdict(cal.before),
        "after": asdict(cal.after),
        "cv_before": cal.cv_before,
        "cv_after": cal.cv_after,
        "hysteresis": {"up": cfg.hysteresis_up, "down": cfg.hysteresis_down},
    }


def validate(weights: dict[str, float]) -> dict[str, float]:
    if set(weights) != set(KEYS):
        raise ValueError(f"weights must have exactly {', '.join(KEYS)}")
    if any(w < MIN_WEIGHT - 1e-9 for w in weights.values()):
        raise ValueError(f"every weight must be at least {MIN_WEIGHT}")
    if abs(sum(weights.values()) - 1) > 1e-6:
        raise ValueError("weights must add up to 1")
    return {k: float(weights[k]) for k in KEYS}


def apply(db: Session, weights: dict[str, float] | None) -> None:
    """Persist and activate weights (None resets to the YAML defaults)."""
    row = db.get(AppSetting, SETTING_KEY)
    if weights is None:
        if row:
            db.delete(row)
    else:
        db.merge(AppSetting(key=SETTING_KEY, value=json.dumps(validate(weights))))
    set_active_weights(weights)


def load_saved(db: Session) -> None:
    row = db.get(AppSetting, SETTING_KEY)
    set_active_weights(json.loads(row.value) if row else None)
