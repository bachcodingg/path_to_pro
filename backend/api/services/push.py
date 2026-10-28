"""Web push to the installed app or browser (PWA), next to email.

Push is a quicker nudge, not the record: safety alerts always go by email as well (the
outbox retries those). `queue()` collects pushes in the session and sends them after the
commit, best effort; subscriptions the push service reports as gone are removed.
"""

from __future__ import annotations

import json
import logging
import threading

from sqlalchemy import delete, event, select
from sqlalchemy.orm import Session

from api.settings import settings
from domain.models import PushSubscription

log = logging.getLogger("pathtopro.push")

# PATHTOPRO_MAIL=memory (tests): pushes land here instead of a push service
SENT: list[dict] = []


def enabled() -> bool:
    return bool(settings.vapid_public_key and settings.vapid_private_key) or settings.mail == "memory"


def queue(db: Session, account_ids: list[str], title: str, body: str, url: str) -> None:
    if not enabled() or not account_ids:
        return
    pending = db.info.setdefault("pushes", [])
    pending.append({"accounts": list(account_ids), "title": title, "body": body, "url": url})
    if not db.info.get("push_hook"):
        db.info["push_hook"] = True
        event.listen(db, "after_commit", _after_commit, once=True)
        event.listen(db, "after_rollback", _after_rollback, once=True)


def _after_rollback(db: Session) -> None:
    db.info.pop("pushes", None)
    db.info.pop("push_hook", None)


def _after_commit(db: Session) -> None:
    pending = db.info.pop("pushes", [])
    db.info.pop("push_hook", None)
    if not pending:
        return
    if settings.mail == "memory":
        deliver(pending)
    else:
        threading.Thread(target=deliver, args=(pending,), name="push", daemon=True).start()


def _send(sub: PushSubscription, payload: str) -> int | None:
    """Status code of a failed send (404/410: the subscription is gone), None if sent."""
    if settings.mail == "memory":
        SENT.append({"account": sub.account_id, **json.loads(payload)})
        return None
    from pywebpush import WebPushException, webpush

    try:
        webpush(
            subscription_info={"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh, "auth": sub.auth}},
            data=payload,
            vapid_private_key=settings.vapid_private_key,
            vapid_claims={"sub": settings.vapid_subject},
            ttl=12 * 3600,
            timeout=10,
        )
    except WebPushException as e:
        return getattr(e.response, "status_code", None) or 500
    return None


def deliver(pending: list[dict]) -> int:
    from api.db import SessionLocal

    sent = 0
    with SessionLocal() as db:
        gone = []
        for p in pending:
            payload = json.dumps({"title": p["title"], "body": p["body"], "url": p["url"]})
            for sub in db.scalars(select(PushSubscription).where(PushSubscription.account_id.in_(p["accounts"]))):
                try:
                    status = _send(sub, payload)
                except Exception as e:  # noqa: BLE001 - push is best effort; email carries what matters
                    log.warning("push to %s failed: %s", sub.account_id, e)
                    continue
                if status in (404, 410):
                    gone.append(sub.id)
                elif status is None:
                    sent += 1
                else:
                    log.warning("push to %s failed with HTTP %s", sub.account_id, status)
        if gone:
            db.execute(delete(PushSubscription).where(PushSubscription.id.in_(gone)))
            db.commit()
    return sent
