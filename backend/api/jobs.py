"""Background jobs, runnable from a cron job instead of the in-process scheduler.

    python -m api.jobs nightly     # Monitor + Planner for every squad (23:00)
    python -m api.jobs deliver     # send queued emails, retrying failures (every minute)
    python -m api.jobs schedule    # extend every team's training week 8 weeks ahead (weekly)
    python -m api.jobs remind      # check-in reminders due this hour (hourly, on the hour)
    python -m api.jobs vapid       # print a new key pair for web push (once, at setup)

With more than one API instance, set PATHTOPRO_SCHEDULER=off and run these from a single
cron job, so the nightly run doesn't happen once per instance.
"""

from __future__ import annotations

import logging
import sys

from sqlalchemy import select

from api import clock
from api.db import SessionLocal, init_db
from api.settings import settings

log = logging.getLogger("pathtopro")


def load_state() -> None:
    """The demo's fixed 'today' and any readiness weights a coach applied."""
    from datetime import date

    from api.services.calibration import load_saved
    from domain.models import AppSetting

    with SessionLocal() as db:
        row = db.get(AppSetting, "today")
        if row and settings.demo_today is None:
            clock.set_today(date.fromisoformat(row.value))
        load_saved(db)


def ensure_admin() -> bool:
    """Real deployments: the club administrator from PATHTOPRO_ADMIN_EMAIL and
    PATHTOPRO_ADMIN_PASSWORD, created once if no account has that email."""
    import os

    from api.security import hash_password
    from domain.enums import Role
    from domain.models import UserAccount

    email, password = settings.admin_email, os.environ.get("PATHTOPRO_ADMIN_PASSWORD")
    if not email or not password or settings.autoseed:
        return False  # demo deployments: the seed owns the accounts
    email = email.strip().lower()
    with SessionLocal() as db:
        if db.scalars(select(UserAccount.id).where(UserAccount.email == email)).first():
            return False
        db.add(UserAccount(email=email, password_hash=hash_password(password), role=Role.ADMIN))
        db.commit()
    log.info("created the administrator account %s", email)
    return True


def nightly() -> dict:
    from agents.llm import default_backend
    from api.services.agent_runner import run_squad
    from domain.models import Squad

    out = {}
    with SessionLocal() as db:
        for squad in db.scalars(select(Squad)):
            out[squad.name] = run_squad(db, squad.id, clock.today(), "nightly", default_backend())
            log.info("nightly run for %s: %s", squad.name, out[squad.name])
    return out


def deliver() -> int:
    from api.services.notify import deliver_pending

    return deliver_pending()


def extend_schedules() -> int:
    from api.services.schedule import extend_all

    with SessionLocal() as db:
        n = extend_all(db, clock.today())
        db.commit()
    return n


def remind() -> int:
    from api.services.reminders import send_due

    with SessionLocal() as db:
        n = send_due(db)
        db.commit()
    return n


def vapid() -> str:
    """A new web-push key pair, as environment lines to copy into the deployment."""
    import base64

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    def b64(raw: bytes) -> str:
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    key = ec.generate_private_key(ec.SECP256R1())
    private = key.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    public = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return f"PATHTOPRO_VAPID_PUBLIC_KEY={b64(public)}\nPATHTOPRO_VAPID_PRIVATE_KEY={b64(private)}"


JOBS = {"nightly": nightly, "deliver": deliver, "schedule": extend_schedules, "remind": remind, "vapid": vapid}


def main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] not in JOBS:
        print(f"usage: python -m api.jobs {{{'|'.join(JOBS)}}}", file=sys.stderr)
        return 2
    logging.basicConfig(level=logging.INFO)
    if argv[0] == "vapid":
        print(vapid())
        return 0
    init_db()
    load_state()
    print(JOBS[argv[0]]())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
