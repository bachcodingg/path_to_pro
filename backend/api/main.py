"""FastAPI app: routers, CORS, startup, nightly scheduler (APScheduler, 23:00)."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from api import clock
from api.db import SessionLocal, get_db, init_db
from api.deps import CurrentUser, require
from api.routers import auth, coach, devices, finance, guardian, physio, player
from api.settings import settings
from domain.enums import Role
from domain.models import AppSetting, Squad

log = logging.getLogger("pathtopro")


def nightly_job() -> None:
    from agents.llm import default_backend
    from api.services.agent_runner import run_squad

    with SessionLocal() as db:
        for squad in db.scalars(select(Squad)):
            out = run_squad(db, squad.id, clock.today(), "nightly", default_backend())
            log.info("nightly run for %s: %s", squad.name, out)


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


def _load_today() -> None:
    from api.services.calibration import load_saved

    with SessionLocal() as db:
        row = db.get(AppSetting, "today")
        if row and settings.demo_today is None:
            clock.set_today(date.fromisoformat(row.value))
        load_saved(db)  # calibrated readiness weights, if a coach applied them


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _autoseed()
    _load_today()
    scheduler = None
    if settings.scheduler:
        from apscheduler.schedulers.background import BackgroundScheduler

        scheduler = BackgroundScheduler()
        scheduler.add_job(nightly_job, "cron", hour=23, minute=0, id="nightly")
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
for r in (auth.router, player.router, coach.router, physio.router, guardian.router, devices.router, finance.router):
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
