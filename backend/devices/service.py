"""Store device data (Apple Watch via Shortcut or Health export) with consent checks,
then let the Monitor re-assess the player."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import age_on, has_consent
from devices.apple_health import HealthBatch, estimate_rpe, ln
from domain.enums import ConsentDataType
from domain.models import DeviceToken, HRVRecord, Player, SessionLoad, SleepRecord

SOURCE = "apple_watch"
WINDOW_DAYS = 60  # older data isn't used by the readiness or load models
TOKEN_PREFIX = "ptp_"
MIN_WORKOUT_MINUTES = 10


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_token(db: Session, player: Player, label: str) -> tuple[DeviceToken, str]:
    token = TOKEN_PREFIX + secrets.token_urlsafe(32)
    row = DeviceToken(player_id=player.id, label=label, token_hash=hash_token(token), last_summary={})
    db.add(row)
    db.flush()
    return row, token


def player_for_token(db: Session, token: str) -> tuple[Player, DeviceToken] | None:
    if not token.startswith(TOKEN_PREFIX):
        return None
    row = db.scalars(select(DeviceToken).where(DeviceToken.token_hash == hash_token(token))).first()
    if row is None or row.revoked:
        return None
    return db.get(Player, row.player_id), row


def store(db: Session, player: Player, batch: HealthBatch, today: date) -> dict:
    """Upsert the batch. Returns what was stored and what was skipped (and why)."""
    since = today - timedelta(days=WINDOW_DAYS)
    out = {"hrv_days": 0, "sleep_nights": 0, "workouts": 0, "skipped": []}

    if batch.hrv_sdnn:
        if not has_consent(db, player, ConsentDataType.HRV, today):
            out["skipped"].append("heart-rate variability: no consent")
        else:
            for d, sdnn in batch.hrv_sdnn.items():
                if not since <= d <= today:
                    continue
                rec = db.scalars(
                    select(HRVRecord).where(HRVRecord.player_id == player.id, HRVRecord.day == d, HRVRecord.source == SOURCE)
                ).first()
                if rec is None:
                    rec = HRVRecord(player_id=player.id, day=d, source=SOURCE, metric="sdnn", ln_rmssd=ln(sdnn))
                    db.add(rec)
                rec.ln_rmssd, rec.metric = ln(sdnn), "sdnn"
                out["hrv_days"] += 1

    if batch.sleep_hours:
        if not has_consent(db, player, ConsentDataType.SLEEP, today):
            out["skipped"].append("sleep: no consent")
        else:
            for d, hours in batch.sleep_hours.items():
                if not since <= d <= today or hours <= 0:
                    continue
                rec = db.scalars(select(SleepRecord).where(SleepRecord.player_id == player.id, SleepRecord.night_of == d)).first()
                if rec is None:
                    db.add(SleepRecord(player_id=player.id, night_of=d, hours=hours, source=SOURCE))
                else:  # the watch measures; it replaces a typed-in estimate
                    rec.hours, rec.source = hours, SOURCE
                out["sleep_nights"] += 1

    if batch.workouts:
        if not has_consent(db, player, ConsentDataType.WELLNESS, today):
            out["skipped"].append("workouts: no consent")
        else:
            already = {
                sl.day
                for sl in db.scalars(
                    select(SessionLoad).where(SessionLoad.player_id == player.id, SessionLoad.day >= since, SessionLoad.source.is_(None))
                )
            }
            known = {
                e
                for e in db.scalars(
                    select(SessionLoad.external_id).where(SessionLoad.player_id == player.id, SessionLoad.external_id.is_not(None))
                )
            }
            age = age_on(player.birth_date, today)
            doubles = 0
            for w in batch.workouts:
                d = w.start.date()
                if not since <= d <= today or w.minutes < MIN_WORKOUT_MINUTES or w.id[:120] in known:
                    continue
                if d in already:  # the club, the coach or the player already logged that day
                    doubles += 1
                    continue
                rpe = estimate_rpe(w, age)
                minutes = round(w.minutes)
                db.add(
                    SessionLoad(
                        player_id=player.id, day=d, rpe=rpe, minutes=minutes, load_au=rpe * minutes, source=SOURCE, external_id=w.id[:120]
                    )
                )
                known.add(w.id[:120])
                out["workouts"] += 1
            if doubles:
                out["skipped"].append(f"{doubles} workout(s) on days that were already logged")
    db.flush()
    return out


def after_import(db: Session, player: Player, today: date, summary: dict) -> None:
    """New recovery data for last night: the Monitor re-assesses today (it may re-plan)."""
    from api.services import agent_runner

    if summary["hrv_days"] or summary["sleep_nights"] or summary["workouts"]:
        agent_runner.run_player(db, player, today, "device")


def mark_used(row: DeviceToken, summary: dict) -> None:
    row.last_used_at = datetime.now(UTC)
    row.last_summary = summary
