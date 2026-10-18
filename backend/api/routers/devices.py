"""Apple Watch / Apple Health: device tokens, the Shortcut ingest endpoint, export upload."""

from __future__ import annotations

import tempfile
from datetime import timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, File, Header, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from api import clock
from api.db import get_db
from api.deps import CurrentUser, audit, has_consent, require
from devices import service
from devices.apple_health import ExportError, HealthPayload, open_export, parse_export
from domain.enums import ConsentDataType, Role
from domain.models import DeviceToken, HRVRecord, Player, SleepRecord

router = APIRouter(tags=["devices"])
MAX_UPLOAD = 400 * 1024**2  # Health exports of a few years are 50-300 MB zipped
MAX_TOKENS = 5


def _me(user: CurrentUser, db: Session) -> Player:
    if user.account.player_id is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Player accounts only")
    return db.get(Player, user.account.player_id)


def _view(db: Session, p: Player, request: Request) -> dict:
    today = clock.today()
    tokens = db.scalars(
        select(DeviceToken).where(DeviceToken.player_id == p.id, DeviceToken.revoked.is_(False)).order_by(DeviceToken.created_at)
    ).all()
    last_hrv = db.scalars(
        select(HRVRecord).where(HRVRecord.player_id == p.id, HRVRecord.source == service.SOURCE).order_by(HRVRecord.day.desc()).limit(1)
    ).first()
    last_sleep = db.scalars(
        select(SleepRecord).where(SleepRecord.player_id == p.id, SleepRecord.source == service.SOURCE).order_by(SleepRecord.night_of.desc()).limit(1)
    ).first()
    return {
        "ingest_url": str(request.base_url).rstrip("/") + "/api/ingest/apple-health",
        "tokens": [
            {
                "id": t.id,
                "label": t.label,
                "created_at": t.created_at.isoformat(),
                "last_used_at": t.last_used_at.isoformat() if t.last_used_at else None,
                "last_summary": t.last_summary or {},
            }
            for t in tokens
        ],
        "consent": {k.value: has_consent(db, p, k, today) for k in (ConsentDataType.HRV, ConsentDataType.SLEEP, ConsentDataType.WELLNESS)},
        "latest": {
            "hrv_day": last_hrv.day.isoformat() if last_hrv else None,
            "sleep_night": last_sleep.night_of.isoformat() if last_sleep else None,
            "sleep_hours": last_sleep.hours if last_sleep else None,
        },
        "window_days": service.WINDOW_DAYS,
    }


@router.get("/api/me/devices")
def devices(request: Request, user: CurrentUser = Depends(require(Role.PLAYER)), db: Session = Depends(get_db)) -> dict:
    p = _me(user, db)
    out = _view(db, p, request)
    audit(db, user, "read", "device_token", p.id)
    db.commit()
    return out


class NewDevice(BaseModel):
    label: str = Field(default="Apple Watch", min_length=1, max_length=60)


@router.post("/api/me/devices", status_code=201)
def add_device(body: NewDevice, request: Request, user: CurrentUser = Depends(require(Role.PLAYER)), db: Session = Depends(get_db)) -> dict:
    """A write-only token for the iPhone Shortcut. Shown once; only its hash is stored."""
    p = _me(user, db)
    active = db.scalars(select(DeviceToken.id).where(DeviceToken.player_id == p.id, DeviceToken.revoked.is_(False))).all()
    if len(active) >= MAX_TOKENS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"At most {MAX_TOKENS} connected devices: remove one first")
    row, token = service.new_token(db, p, body.label.strip())
    audit(db, user, "create", "device_token", p.id)
    db.commit()
    return {**_view(db, p, request), "new_token": {"id": row.id, "token": token}}


@router.delete("/api/me/devices/{token_id}")
def remove_device(token_id: str, request: Request, user: CurrentUser = Depends(require(Role.PLAYER)), db: Session = Depends(get_db)) -> dict:
    p = _me(user, db)
    row = db.get(DeviceToken, token_id)
    if row is None or row.player_id != p.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Device not found")
    row.revoked = True
    audit(db, user, "delete", "device_token", p.id)
    db.commit()
    return _view(db, p, request)


@router.post("/api/ingest/apple-health")
def ingest(body: HealthPayload, authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> dict:
    """Called by the player's iPhone Shortcut with a device token (not a login)."""
    token = (authorization or "").removeprefix("Bearer ").strip()
    found = service.player_for_token(db, token) if token else None
    if found is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown or revoked device token")
    p, row = found
    today = clock.today()
    try:
        batch = body.to_batch()
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Bad date in workouts: {e}") from e
    summary = service.store(db, p, batch, today)
    service.mark_used(row, summary)
    audit(db, None, "create", "device_import", p.id, device=row.id, **{k: v for k, v in summary.items() if k != "skipped"})
    service.after_import(db, p, today, summary)
    db.commit()
    return {"ok": True, **summary}


@router.post("/api/me/health/import")
def import_export(
    file: UploadFile = File(...), user: CurrentUser = Depends(require(Role.PLAYER)), db: Session = Depends(get_db)
) -> dict:
    """Upload the Health app's 'Export All Health Data' (export.zip). Only the last
    60 days of HRV, sleep and workouts are read; the file itself is not kept."""
    p = _me(user, db)
    today = clock.today()
    with tempfile.TemporaryDirectory(prefix="pathtopro-health-") as tmp:
        path = Path(tmp) / "upload"
        size = 0
        with path.open("wb") as out:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD:
                    raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "File too large (max 400 MB)")
                out.write(chunk)
        try:
            with open_export(path) as src:
                batch = parse_export(src, today - timedelta(days=service.WINDOW_DAYS))
        except ExportError as e:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from e
        except Exception as e:  # malformed XML, forbidden DTD entities, bad zip
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Could not read this file as an Apple Health export") from e
    summary = service.store(db, p, batch, today)
    audit(db, user, "create", "device_import", p.id, kind="health_export", **{k: v for k, v in summary.items() if k != "skipped"})
    service.after_import(db, p, today, summary)
    db.commit()
    return {"ok": True, **summary}

