"""Email outbox: queue in the request's transaction, send after the commit, retry later.

`queue()` adds a Notification row and arranges for `deliver_pending()` to run once the
session commits, so nothing is sent for work that was rolled back. The scheduler calls
`deliver_pending()` every minute to retry failures (python -m api.jobs deliver does the
same from a cron job).
"""

from __future__ import annotations

import logging
import smtplib
import ssl
import threading
from datetime import UTC, datetime
from email.message import EmailMessage

from sqlalchemy import event, select
from sqlalchemy.orm import Session

from api.settings import settings
from domain.models import Notification

log = logging.getLogger("pathtopro.mail")

MAX_ATTEMPTS = 5

# PATHTOPRO_MAIL=memory (tests): every sent email lands here
SENT: list[dict] = []

_deliver_lock = threading.Lock()


def link(path: str) -> str:
    return f"{settings.public_url}{path}"


def queue(db: Session, to: str, kind: str, subject: str, body: str, escalation_id: str | None = None) -> Notification:
    n = Notification(to_email=to, kind=kind, subject=subject, body=body, escalation_id=escalation_id, created_at=_now())
    db.add(n)
    if not db.info.get("mail_hook"):
        db.info["mail_hook"] = True
        event.listen(db, "after_commit", _after_commit, once=True)
    return n


def _after_commit(db: Session) -> None:
    db.info.pop("mail_hook", None)
    if settings.mail == "smtp":
        # Don't hold the request on the mail server
        threading.Thread(target=deliver_pending, name="mail", daemon=True).start()
    else:
        deliver_pending()


def _now() -> datetime:
    return datetime.now(UTC)


def _send(n: Notification) -> None:
    if settings.mail == "memory":
        SENT.append({"to": n.to_email, "kind": n.kind, "subject": n.subject, "body": n.body})
        return
    if settings.mail == "log":
        log.info("email to %s: %s\n%s", n.to_email, n.subject, n.body)
        return
    msg = EmailMessage()
    msg["From"] = settings.mail_from
    msg["To"] = n.to_email
    msg["Subject"] = n.subject
    msg.set_content(n.body)
    if settings.smtp_tls == "ssl":
        smtp = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=ssl.create_default_context(), timeout=20)
    else:
        smtp = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20)
    with smtp:
        if settings.smtp_tls == "starttls":
            smtp.starttls(context=ssl.create_default_context())
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password or "")
        smtp.send_message(msg)


def deliver_pending(limit: int = 50) -> int:
    """Send queued emails, oldest first. Returns how many were sent."""
    from api.db import SessionLocal

    sent = 0
    with _deliver_lock, SessionLocal() as db:
        rows = db.scalars(
            select(Notification)
            .where(Notification.sent_at.is_(None), Notification.attempts < MAX_ATTEMPTS)
            .order_by(Notification.created_at)
            .limit(limit)
        ).all()
        for n in rows:
            n.attempts += 1
            try:
                _send(n)
            except Exception as e:  # noqa: BLE001 - any mail failure is retried later
                n.error = f"{type(e).__name__}: {e}"[:500]
                log.warning("email %s to %s failed (attempt %d): %s", n.id, n.to_email, n.attempts, n.error)
            else:
                n.sent_at, n.error = _now(), None
                sent += 1
            db.commit()
    return sent
