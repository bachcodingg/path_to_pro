"""FastAPI app: routers, CORS, startup, nightly scheduler (APScheduler, 23:00)."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import date

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from api import clock
from api.db import SessionLocal, get_db, init_db
from api.deps import CurrentUser, require
from api.routers import auth, coach, guardian, physio, player
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


def _load_today() -> None:
    with SessionLocal() as db:
        row = db.get(AppSetting, "today")
        if row and settings.demo_today is None:
            clock.set_today(date.fromisoformat(row.value))


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
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
for r in (auth.router, player.router, coach.router, physio.router, guardian.router):
    app.include_router(r)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "today": clock.today().isoformat()}


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
