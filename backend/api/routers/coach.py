"""Coach view (desktop-first): squad heatmap, approval inbox, line-up readiness,
player profile and the agent log."""

from __future__ import annotations

import csv
import io
from datetime import date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from api import clock
from api.db import get_db
from api.deps import CurrentUser, age_on, audit, player_in_scope, require, staff_of
from api.routers.player import player_card, roadmap_view
from api.services import agent_runner, calibration, views
from domain.enums import AgentName, ProposalStatus, Role
from domain.models import (
    AgentRun,
    Anthropometrics,
    Approval,
    DailyStatus,
    Escalation,
    Match,
    Player,
    PlayerNote,
    Proposal,
    StaffMember,
    StaffRating,
    WeeklyPlan,
)

router = APIRouter(prefix="/api/coach", tags=["coach"])
STAFF = (Role.COACH, Role.PHYSIO)


def _squad_players(db: Session, user: CurrentUser) -> list[Player]:
    staff = staff_of(user, db)
    q = select(Player).order_by(Player.display_name)
    if staff.squad_id:
        q = q.where(Player.squad_id == staff.squad_id)
    return list(db.scalars(q))


# --------------------------------------------------------------------------- heatmap


@router.get("/heatmap")
def heatmap(
    days: int = Query(14, ge=7, le=28),
    age_group: str | None = None,
    flag: str | None = None,
    user: CurrentUser = Depends(require(*STAFF)),
    db: Session = Depends(get_db),
) -> dict:
    today = clock.today()
    dates = [today - timedelta(days=days - 1 - i) for i in range(days)]
    rows = []
    for p in _squad_players(db, user):
        age = age_on(p.birth_date, today)
        group = f"U{int(age) + 1}"
        if age_group and group != age_group:
            continue
        sts = {
            s.day: s
            for s in db.scalars(
                select(DailyStatus).where(DailyStatus.player_id == p.id, DailyStatus.day >= dates[0], DailyStatus.day <= today)
            )
        }
        last = views.latest_status(db, p.id, today)
        flags = {f["kind"] for f in (last.flags if last else [])}
        if flag and flag not in flags:
            continue
        rows.append(
            {
                "id": p.id,
                "name": p.display_name,
                "age": round(age, 1),
                "age_group": group,
                "phv": bool(last and last.in_phv_window),
                "load_flag": "load_spike" in flags,
                "flags": sorted(flags),
                "cells": [
                    {
                        "date": d.isoformat(),
                        "score": sts[d].readiness if d in sts else None,
                        "band": sts[d].band if d in sts else None,
                    }
                    for d in dates
                ],
            }
        )
    audit(db, user, "read", "daily_status", None, view="heatmap", players=len(rows))
    db.commit()
    return {"dates": [d.isoformat() for d in dates], "today": today.isoformat(), "players": rows}


# --------------------------------------------------------------------------- approval inbox


def _proposal_json(db: Session, p: Proposal) -> dict:
    player = db.get(Player, p.player_id)
    plan = db.get(WeeklyPlan, p.proposed_plan_id) if p.proposed_plan_id else None
    out = {
        "id": p.id,
        "player": {"id": player.id, "name": player.display_name},
        "kind": p.kind,
        "reason": p.reason,
        "chips": p.data_chips,
        "policy_rule": p.policy_rule,
        "status": p.status.value,
        "created_at": p.created_at.isoformat(),
        "payload": p.payload,
        "current": [],
        "proposed": [],
        "explanation_player": plan.explanation_player if plan else None,
        "solver_status": plan.solver_status if plan else None,
    }
    if plan:
        items = sorted(plan.items, key=lambda i: i.day)
        start, n = items[0].day, len(items)
        out["proposed"] = [
            views.day_json(
                agent_runner.PlanDay(day=(i.day - start).days, date=i.day, kind=i.kind, rpe=i.target_rpe, minutes=i.minutes)
            )
            for i in items
        ]
        out["current"] = [views.day_json(d) for d in agent_runner.plan_days(db, player, start, n)]
    return out


@router.get("/inbox")
def inbox(user: CurrentUser = Depends(require(*STAFF)), db: Session = Depends(get_db)) -> list[dict]:
    ids = {p.id for p in _squad_players(db, user)}
    props = db.scalars(
        select(Proposal).where(Proposal.status == ProposalStatus.PENDING).order_by(Proposal.created_at)
    ).all()
    out = [_proposal_json(db, p) for p in props if p.player_id in ids]
    audit(db, user, "read", "proposal", None, view="inbox", n=len(out))
    db.commit()
    return out


class Decision(BaseModel):
    action: Literal["approve", "edit", "reject"]
    edits: list[dict] = Field(default_factory=list, description="[{day: ISO date, kind?, rpe?}] for action=edit")
    note: str | None = Field(default=None, max_length=500)


@router.post("/proposals/{proposal_id}/decision")
def decide(
    proposal_id: str, body: Decision, user: CurrentUser = Depends(require(Role.COACH)), db: Session = Depends(get_db)
) -> dict:
    prop = db.get(Proposal, proposal_id)
    if prop is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proposal not found")
    player_in_scope(prop.player_id, user, db)
    try:
        agent_runner.decide_proposal(db, prop, staff_of(user, db), body.action, body.edits, body.note)
    except agent_runner.EditRejected as e:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from e
    audit(db, user, body.action, "proposal", prop.id, player=prop.player_id)
    db.commit()
    return {"id": prop.id, "status": prop.status.value}


# --------------------------------------------------------------------------- tactics board


@router.get("/lineup")
def lineup(user: CurrentUser = Depends(require(*STAFF)), db: Session = Depends(get_db)) -> dict:
    today = clock.today()
    players = _squad_players(db, user)
    match = db.scalars(
        select(Match)
        .where(Match.kickoff >= datetime.combine(today, datetime.min.time()))
        .order_by(Match.kickoff)
        .limit(1)
    ).first()
    out = []
    for p in players:
        st = views.latest_status(db, p.id, today)
        out.append(
            {
                "id": p.id,
                "name": p.display_name,
                "readiness": st.readiness if st else None,
                "band": st.band if st else None,
                "flags": [f["detail"] for f in (st.flags if st else [])],
                "phv": bool(st and st.in_phv_window),
            }
        )
    out.sort(key=lambda r: -(r["readiness"] or 0))
    audit(db, user, "read", "daily_status", None, view="lineup")
    db.commit()
    return {
        "match": None
        if match is None
        else {"date": match.kickoff.date().isoformat(), "kickoff": match.kickoff.isoformat(), "opponent": match.opponent,
              "competition": match.competition},
        "players": out,
    }


# --------------------------------------------------------------------------- player profile


@router.get("/players/{player_id}")
def profile(player_id: str, user: CurrentUser = Depends(require(*STAFF)), db: Session = Depends(get_db)) -> dict:
    p = player_in_scope(player_id, user, db)
    today = clock.today()
    start = today - timedelta(days=55)
    loads = views.daily_loads(db, p.id, start, today)
    sts = {s.day: s for s in db.scalars(select(DailyStatus).where(DailyStatus.player_id == p.id, DailyStatus.day >= start))}
    series = []
    for i in range(56):
        d = start + timedelta(days=i)
        st = sts.get(d)
        series.append(
            {
                "date": d.isoformat(),
                "load": round(loads.get(d, 0.0)),
                "readiness": st.readiness if st else None,
                "acwr": st.acwr if st else None,
            }
        )
    growth = [
        {"date": a.day.isoformat(), "height_cm": a.height_cm}
        for a in db.scalars(select(Anthropometrics).where(Anthropometrics.player_id == p.id).order_by(Anthropometrics.day))
    ]
    changes = []
    for pr in db.scalars(
        select(Proposal)
        .where(Proposal.player_id == p.id, Proposal.status != ProposalStatus.SUPERSEDED)
        .order_by(Proposal.created_at.desc())
        .limit(20)
    ):
        appr = db.scalars(select(Approval).where(Approval.proposal_id == pr.id)).first()
        changes.append(
            {
                "date": pr.created_at.date().isoformat(),
                "kind": pr.kind,
                "status": pr.status.value,
                "reason": pr.reason,
                "approver": db.get(StaffMember, appr.approver_id).name if appr else None,
            }
        )
    escalations = [
        {"date": e.created_at.date().isoformat(), "kind": e.kind, "acknowledged": e.acknowledged_at is not None}
        for e in db.scalars(select(Escalation).where(Escalation.player_id == p.id).order_by(Escalation.created_at.desc()))
    ]
    notes = [
        {"date": n.day.isoformat(), "text": n.text, "author": db.get(StaffMember, n.author_id).name}
        for n in db.scalars(select(PlayerNote).where(PlayerNote.player_id == p.id).order_by(PlayerNote.day.desc()))
    ]
    audit(db, user, "read", "player_profile", p.id)
    db.commit()
    return {
        "player": {"id": p.id, "name": p.display_name, "age": round(age_on(p.birth_date, today), 1)},
        "status": views.status_json(views.latest_status(db, p.id, today)),
        "series": series,
        "growth": growth,
        "card": player_card(db, p, today),
        "roadmap": roadmap_view(db, p, today),
        "changes": changes,
        "escalations": escalations,
        "notes": notes,
        "week": views.week_days(db, p, views.week_start(today)),
    }


class Note(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


@router.post("/players/{player_id}/notes")
def add_note(
    player_id: str, body: Note, user: CurrentUser = Depends(require(*STAFF)), db: Session = Depends(get_db)
) -> dict:
    p = player_in_scope(player_id, user, db)
    n = PlayerNote(player_id=p.id, author_id=staff_of(user, db).id, day=clock.today(), text=body.text)
    db.add(n)
    audit(db, user, "create", "player_note", p.id)
    db.commit()
    return {"id": n.id}


# --------------------------------------------------------------------------- agent log ("match commentary")


def _commentary(run: AgentRun, player: Player | None) -> str:
    who = player.display_name if player else "squad"
    out = run.output or {}
    flags = ", ".join(f["detail"] for f in run.flags or []) or "no flags"
    if run.agent == AgentName.MONITOR:
        return f"Monitor checked {who}: {flags}. No change needed."
    if run.agent == AgentName.COORDINATOR and out.get("decision") == "escalate":
        return f"Safety flag for {who} ({flags}). Escalated to staff; agents took no action."
    if run.agent == AgentName.DEVELOPMENT_COACH:
        goals = ", ".join(views.kpi_label(g) for g in out.get("goals", [])) or "none"
        return f"Development Coach set goals for {who}: {goals}; picked {len(out.get('drills', []))} drills."
    decision = out.get("decision")
    if decision:
        return (
            f"Planner re-planned {who}'s week ({flags}). Solver {out.get('status')}, load {out.get('weekly_load')} AU. "
            f"Coordinator: {decision.replace('_', ' ')}."
        )
    return f"Planner built {who}'s week: solver {out.get('status')}, load {out.get('weekly_load')} AU ({flags})."


def _log_rows(db: Session, user: CurrentUser, agent: str | None, player: str | None, decision: str | None, limit: int):
    ids = {p.id: p for p in _squad_players(db, user)}
    q = select(AgentRun).order_by(AgentRun.started_at.desc())
    if agent:
        q = q.where(AgentRun.agent == AgentName(agent))
    if player:
        q = q.where(AgentRun.player_id == player)
    rows = []
    for r in db.scalars(q.limit(limit * 4)):
        if r.player_id and r.player_id not in ids:
            continue
        dec = (r.output or {}).get("decision", "plan" if r.agent == AgentName.PLANNER else "none")
        if decision and dec != decision:
            continue
        p = ids.get(r.player_id)
        rows.append(
            {
                "id": r.id,
                "at": r.started_at.isoformat(),
                "agent": r.agent.value,
                "trigger": r.trigger,
                "player": None if p is None else {"id": p.id, "name": p.display_name},
                "decision": dec,
                "text": _commentary(r, p),
                "flags": r.flags,
                "inputs": r.inputs,
                "constraints": r.constraints,
                "fallback": r.used_fallback,
            }
        )
        if len(rows) >= limit:
            break
    return rows


@router.get("/agent-log")
def agent_log(
    agent: str | None = None,
    player: str | None = None,
    decision: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
    user: CurrentUser = Depends(require(*STAFF)),
    db: Session = Depends(get_db),
) -> list[dict]:
    rows = _log_rows(db, user, agent, player, decision, limit)
    audit(db, user, "read", "agent_run", None, n=len(rows))
    db.commit()
    return rows


@router.get("/agent-log.csv")
def agent_log_csv(
    agent: str | None = None,
    player: str | None = None,
    decision: str | None = None,
    user: CurrentUser = Depends(require(*STAFF)),
    db: Session = Depends(get_db),
):
    rows = _log_rows(db, user, agent, player, decision, 1000)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["time", "agent", "trigger", "player", "decision", "fallback", "commentary"])
    for r in rows:
        w.writerow([r["at"], r["agent"], r["trigger"], (r["player"] or {}).get("name", ""), r["decision"], r["fallback"], r["text"]])
    audit(db, user, "export", "agent_run", None, n=len(rows))
    db.commit()
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=agent-log.csv"}
    )


@router.post("/run-nightly")
def run_nightly(user: CurrentUser = Depends(require(Role.COACH)), db: Session = Depends(get_db)) -> dict:
    staff = staff_of(user, db)
    out = agent_runner.run_squad(db, staff.squad_id, clock.today(), "manual")
    audit(db, user, "run", "agent_run", None, **out)
    db.commit()
    return out


# --------------------------------------------------------------------------- staff ratings + calibration


class Rating(BaseModel):
    band: Literal["green", "amber", "red"]
    day: date | None = None


@router.post("/players/{player_id}/rating")
def rate_player(
    player_id: str, body: Rating, user: CurrentUser = Depends(require(*STAFF)), db: Session = Depends(get_db)
) -> dict:
    """Staff's own judgement of how ready a player looks (used to calibrate the score)."""
    p = player_in_scope(player_id, user, db)
    staff = staff_of(user, db)
    day = body.day or clock.today()
    if day > clock.today():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Cannot rate a future day")
    row = db.scalars(
        select(StaffRating).where(StaffRating.player_id == p.id, StaffRating.staff_id == staff.id, StaffRating.day == day)
    ).first()
    if row is None:
        row = StaffRating(player_id=p.id, staff_id=staff.id, day=day, band=body.band)
        db.add(row)
    else:
        row.band = body.band
    audit(db, user, "create", "staff_rating", p.id, day=day.isoformat())
    db.commit()
    return {"player_id": p.id, "day": day.isoformat(), "band": body.band}


@router.get("/calibration")
def calibration_report(user: CurrentUser = Depends(require(*STAFF)), db: Session = Depends(get_db)) -> dict:
    out = calibration.report(db, staff_of(user, db).squad_id)
    audit(db, user, "read", "staff_rating", None, view="calibration", n=out["n"])
    db.commit()
    return out


class Weights(BaseModel):
    weights: dict[str, float] | None = Field(default=None, description="null resets to the default weights")


@router.post("/calibration/apply")
def calibration_apply(body: Weights, user: CurrentUser = Depends(require(Role.COACH)), db: Session = Depends(get_db)) -> dict:
    """A coach reviews the suggestion and applies it (or resets). Takes effect for new scores."""
    try:
        calibration.apply(db, body.weights)
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from e
    audit(db, user, "update", "readiness_weights", None, weights=body.weights)
    db.commit()
    return calibration.report(db, staff_of(user, db).squad_id)
