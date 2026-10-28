"""FastAPI app: routers, CORS, startup, scheduler (nightly agents at 23:00, email retries
every minute, training weeks extended on Sundays; see api/jobs.py)."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from api import clock, jobs
from api.db import SessionLocal, get_db, init_db
from api.deps import CurrentUser, require
from api.routers import account, admin, auth, coach, devices, finance, guardian, physio, player, pro, schedule, team
from api.settings import settings
from domain.enums import Role

log = logging.getLogger("pathtopro")


def nightly_job() -> None:
    jobs.nightly()


_data_state = {"status": "ready"}


def _autoseed() -> None:
    """Demo deployments: load the synthetic season into an empty database, in the
    background so the server answers health checks while it runs."""
    if not settings.autoseed:
        return
    from domain.models import Player

    with SessionLocal() as db:
        if db.scalars(select(Player.id).limit(1)).first() is not None:
            return

    def run() -> None:
        from api.services.seed import seed

        _data_state["status"] = "seeding"
        try:
            with SessionLocal() as db:
                log.info("seeded the synthetic demo season: %s", seed(db))
            _data_state["status"] = "ready"
        except Exception:
            log.exception("demo seeding failed")
            _data_state["status"] = "error"

    import threading

    _data_state["status"] = "seeding"
    threading.Thread(target=run, name="autoseed", daemon=True).start()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _autoseed()
    jobs.ensure_admin()
    jobs.load_state()
    if settings.env == "production" and settings.mail == "log":
        log.warning("PATHTOPRO_SMTP_HOST is not set: emails (safety alerts, password resets) are only logged")
    scheduler = None
    if settings.scheduler:
        from apscheduler.schedulers.background import BackgroundScheduler

        scheduler = BackgroundScheduler()
        scheduler.add_job(nightly_job, "cron", hour=23, minute=0, id="nightly")
        scheduler.add_job(jobs.deliver, "interval", minutes=1, id="mail")
        scheduler.add_job(jobs.extend_schedules, "cron", day_of_week="sun", hour=22, id="schedule")
        scheduler.add_job(jobs.remind, "cron", minute=0, id="remind")
        scheduler.start()
    yield
    if scheduler:
        scheduler.shutdown(wait=False)


app = FastAPI(title="PathToPro API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
for r in (
    auth.router,
    player.router,
    coach.router,
    schedule.router,
    team.router,
    account.router,
    admin.router,
    pro.router,
    physio.router,
    guardian.router,
    devices.router,
    finance.router,
):
    app.include_router(r)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "today": clock.today().isoformat(), "data": _data_state["status"]}


@app.post("/api/demo/seed")
def demo_seed(players: int = 25, db: Session = Depends(get_db)) -> dict:
    """Reset the database to the synthetic demo season. Development only."""
    if settings.env == "production":
        raise HTTPException(403, "Disabled in production")
    from api.services.seed import seed

    return seed(db, n_players=players)


@app.post("/api/admin/nightly")
def admin_nightly(_: CurrentUser = Depends(require(Role.ADMIN))) -> dict:
    nightly_job()
    return {"ok": True}


# --------------------------------------------------------------------------- website (single-container deploy)

if settings.static_dir and Path(settings.static_dir, "index.html").exists():
    _static = Path(settings.static_dir).resolve()

    @app.get("/{path:path}", include_in_schema=False)
    def website(path: str):
        """Serve the built React app; unknown paths get index.html (client-side routing)."""
        if path.startswith("api/"):
            raise HTTPException(404, "Not found")
        target = (_static / path).resolve()
        if path and target.is_file() and _static in target.parents:
            headers = {"Cache-Control": "public, max-age=31536000, immutable"} if path.startswith("assets/") else {}
            return FileResponse(target, headers=headers)
        return FileResponse(_static / "index.html", headers={"Cache-Control": "no-cache"})
