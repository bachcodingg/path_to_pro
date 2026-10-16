"""Physio view: escalation queue (oldest first) and the squad's PHV list."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from api import clock
from api.db import get_db
from api.deps import CurrentUser, age_on, audit, player_in_scope, require, staff_of
from api.services import views
from domain.enums import Role
from domain.models import Escalation, Player

router = APIRouter(prefix="/api/physio", tags=["physio"])

KIND_TEXT = {
    "pain_report": "Pain reported",
    "red_mood": "Red mood check-in",
    "missed_checkins": "Missed check-ins with red readiness",
}


@router.get("/queue")
def queue(user: CurrentUser = Depends(require(Role.PHYSIO, Role.COACH)), db: Session = Depends(get_db)) -> list[dict]:
    staff = staff_of(user, db)
    now = datetime.now(UTC)
    out = []
    for e in db.scalars(
        select(Escalation).where(Escalation.acknowledged_at.is_(None)).order_by(Escalation.created_at)
    ):
        p = db.get(Player, e.player_id)
        if staff.squad_id and p.squad_id != staff.squad_id:
            continue
        created = e.created_at if e.created_at.tzinfo else e.created_at.replace(tzinfo=UTC)
        notified = e.notified_at if e.notified_at is None or e.notified_at.tzinfo else e.notified_at.replace(tzinfo=UTC)
        st = views.latest_status(db, p.id, clock.today())
        out.append(
            {
                "id": e.id,
                "player": {"id": p.id, "name": p.display_name},
                "kind": e.kind,
                "text": KIND_TEXT.get(e.kind, e.kind),
                "created_at": created.isoformat(),
                "age_minutes": round((now - created).total_seconds() / 60),
                "notified_after_s": None if notified is None else round((notified - created).total_seconds(), 3),
                "readiness": views.status_json(st),
            }
        )
    audit(db, user, "read", "escalation", None, n=len(out))
    db.commit()
    return out


@router.post("/escalations/{escalation_id}/ack")
def acknowledge(
    escalation_id: str, user: CurrentUser = Depends(require(Role.PHYSIO, Role.COACH)), db: Session = Depends(get_db)
) -> dict:
    e = db.get(Escalation, escalation_id)
    if e is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Escalation not found")
    player_in_scope(e.player_id, user, db)
    e.acknowledged_at = datetime.now(UTC)
    audit(db, user, "acknowledge", "escalation", e.id, player=e.player_id)
    db.commit()
    return {"id": e.id, "acknowledged_at": e.acknowledged_at.isoformat()}


@router.get("/phv")
def phv_list(user: CurrentUser = Depends(require(Role.PHYSIO, Role.COACH)), db: Session = Depends(get_db)) -> list[dict]:
    staff = staff_of(user, db)
    today = clock.today()
    out = []
    for p in db.scalars(select(Player).where(Player.squad_id == staff.squad_id).order_by(Player.display_name)):
        st = views.latest_status(db, p.id, today)
        if st and st.maturity_offset is not None and abs(st.maturity_offset) <= 1.5:
            out.append(
                {
                    "id": p.id,
                    "name": p.display_name,
                    "age": round(age_on(p.birth_date, today), 1),
                    "maturity_offset": st.maturity_offset,
                    "in_window": st.in_phv_window,
                }
            )
    out.sort(key=lambda r: abs(r["maturity_offset"]))
    audit(db, user, "read", "daily_status", None, view="phv")
    db.commit()
    return out
