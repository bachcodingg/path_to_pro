"""Daily check-in reminders, opt-in per player at the hour they chose (club's local time).

Sent only to players who haven't checked in today and whose check-in may be stored (a
parent's consent under 16): push to their phone if they turned it on, else email if their
address is confirmed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from api import clock
from api.deps import has_consent
from api.services import notify, push
from api.settings import settings
from domain.enums import ConsentDataType
from domain.models import Player, PushSubscription, UserAccount, WellnessCheckin


def local_hour(now: datetime | None = None) -> int:
    return (now or datetime.now(UTC)).astimezone(ZoneInfo(settings.timezone)).hour


def send_due(db: Session, now: datetime | None = None) -> int:
    hour, today = local_hour(now), clock.today()
    sent = 0
    for acc in db.scalars(
        select(UserAccount).where(UserAccount.reminder_hour == hour, UserAccount.active.is_(True), UserAccount.player_id.is_not(None))
    ):
        player = db.get(Player, acc.player_id)
        if db.scalars(select(WellnessCheckin.id).where(WellnessCheckin.player_id == player.id, WellnessCheckin.day == today)).first():
            continue
        if not has_consent(db, player, ConsentDataType.WELLNESS, today):
            continue
        first = player.display_name.split()[0]
        if db.scalars(select(PushSubscription.id).where(PushSubscription.account_id == acc.id)).first():
            push.queue(db, [acc.id], "Morning check-in", f"30 seconds, {first}: how did you sleep?", "/player/checkin")
        elif acc.email_verified_at is not None:
            notify.queue(
                db,
                acc.email,
                "reminder",
                "Your PathToPro check-in",
                f"Morning {first},\n\n30 seconds: how did you sleep, and how do you feel? Your plan for today "
                f"follows your answers.\n\n{notify.link('/player/checkin')}\n\n"
                f"(You chose this reminder; switch it off in your account settings: {notify.link('/account')})",
            )
        else:
            continue
        sent += 1
    return sent
