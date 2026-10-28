"""Per-account connections: check-in reminders, web push on this device, calendar feed."""

from __future__ import annotations

import hashlib
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from api import clock
from api.db import get_db
from api.deps import CurrentUser, audit, current_user
from api.services import calendar, notify, push
from api.settings import settings
from domain.enums import Role
from domain.models import CalendarFeed, PushSubscription, UserAccount

router = APIRouter(tags=["account"])


@router.get("/api/account/notifications")
def settings_view(user: CurrentUser = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    acc = user.account
    return {
        "reminder_hour": acc.reminder_hour,
        "reminders_available": acc.role == Role.PLAYER,
        "timezone": settings.timezone,
        "push_public_key": settings.vapid_public_key if push.enabled() else None,
        "push_devices": len(db.scalars(select(PushSubscription.id).where(PushSubscription.account_id == acc.id)).all()),
        "calendar": db.scalars(select(CalendarFeed.id).where(CalendarFeed.account_id == acc.id)).first() is not None,
        "calendar_available": acc.role in (Role.PLAYER, Role.COACH, Role.PHYSIO),
    }


class Reminder(BaseModel):
    hour: int | None = Field(default=None, ge=5, le=22, description="local hour; None turns reminders off")


@router.put("/api/account/reminder")
def set_reminder(body: Reminder, user: CurrentUser = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    if user.role != Role.PLAYER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Check-in reminders are for players")
    user.account.reminder_hour = body.hour
    audit(db, user, "update", "reminder", user.id, hour=body.hour)
    db.commit()
    return settings_view(user, db)


class PushKeys(BaseModel):
    p256dh: str = Field(max_length=200)
    auth: str = Field(max_length=100)


class PushIn(BaseModel):
    endpoint: str = Field(min_length=10, max_length=1000)
    keys: PushKeys


@router.post("/api/account/push", status_code=201)
def subscribe(body: PushIn, user: CurrentUser = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    if not push.enabled():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Notifications are not set up on this server")
    if not body.endpoint.startswith("https://"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Not a push service address")
    sub = db.scalars(select(PushSubscription).where(PushSubscription.endpoint == body.endpoint)).first()
    if sub is None:
        sub = PushSubscription(endpoint=body.endpoint, account_id=user.id, p256dh=body.keys.p256dh, auth=body.keys.auth)
        db.add(sub)
    else:  # the same browser, maybe now signed in as someone else
        sub.account_id, sub.p256dh, sub.auth = user.id, body.keys.p256dh, body.keys.auth
    db.commit()
    return {"ok": True}


class PushOut(BaseModel):
    endpoint: str = Field(max_length=1000)


@router.post("/api/account/push/remove")
def unsubscribe(body: PushOut, user: CurrentUser = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    db.execute(delete(PushSubscription).where(PushSubscription.endpoint == body.endpoint, PushSubscription.account_id == user.id))
    db.commit()
    return {"ok": True}


@router.post("/api/account/push/test", status_code=202)
def test_push(user: CurrentUser = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    push.queue(db, [user.id], "PathToPro notifications are on", "This is how alerts and reminders will reach you.", "/account")
    db.commit()
    return {"ok": True}


# --------------------------------------------------------------------------- calendar feed


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


@router.post("/api/account/calendar", status_code=201)
def new_calendar(user: CurrentUser = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """A new secret calendar address; the old one (if any) stops working. Shown once."""
    if user.role not in (Role.PLAYER, Role.COACH, Role.PHYSIO):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Calendars are for players and staff")
    db.execute(delete(CalendarFeed).where(CalendarFeed.account_id == user.id))
    raw = secrets.token_urlsafe(24)
    db.add(CalendarFeed(account_id=user.id, token_hash=_hash(raw)))
    audit(db, user, "create", "calendar_feed", user.id)
    db.commit()
    url = notify.link(f"/api/calendar/{raw}.ics")
    return {"url": url, "webcal": url.replace("https://", "webcal://", 1).replace("http://", "webcal://", 1)}


@router.delete("/api/account/calendar")
def remove_calendar(user: CurrentUser = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    db.execute(delete(CalendarFeed).where(CalendarFeed.account_id == user.id))
    audit(db, user, "delete", "calendar_feed", user.id)
    db.commit()
    return {"ok": True}


@router.get("/api/calendar/{token}.ics", include_in_schema=False)
def calendar_feed(token: str, db: Session = Depends(get_db)) -> Response:
    feed = db.scalars(select(CalendarFeed).where(CalendarFeed.token_hash == _hash(token))).first()
    acc = db.get(UserAccount, feed.account_id) if feed else None
    if acc is None or not acc.active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return Response(
        calendar.feed(db, acc, clock.today()),
        media_type="text/calendar; charset=utf-8",
        headers={"Cache-Control": "private, max-age=900"},
    )
