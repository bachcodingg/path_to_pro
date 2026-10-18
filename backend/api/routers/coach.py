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
from api.services import agent_runner, calibration, gym_view, squad_week, views
from domain.enums import AgentName, Position, ProposalStatus, Role, SessionType
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
from performance import service as performance

router = APIRouter(prefix="/api/coach", tags=["coach"])
STAFF = (Role.COACH, Role.PHYSIO)


def _squad_players(db: Session, user: CurrentUser) -> list[Player]:
    """The staff member's squad, including players dual-registered with it."""
    from domain.models import Registration

    staff = staff_of(user, db)
    q = select(Player).order_by(Player.display_name)
    if staff.squad_id:
        dual = select(Registration.player_id).where(Registration.squad_id == staff.squad_id)
        q = q.where((Player.squad_id == staff.squad_id) | Player.id.in_(dual))
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
        "teams": [t["team"] for t in performance.registrations(db, player, clock.today())],
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
    player = player_in_scope(prop.player_id, user, db)
    staff = staff_of(user, db)
    if staff.squad_id and staff.squad_id != player.squad_id:
        # Dual registration: both coaches see it, the primary team's coach decides.
        raise HTTPException(status.HTTP_403_FORBIDDEN, "The player's primary team coach decides")
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
    gym = gym_view.week(db, p, views.week_start(today), today)
    audit(db, user, "read", "player_profile", p.id)
    db.commit()
    return {
        "player": {"id": p.id, "name": p.display_name, "age": round(age_on(p.birth_date, today), 1), "position": p.position},
        "positions": gym["positions"],
        "gym": gym["sessions"][0]["programme"] if gym["sessions"] else gym["optional"],
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
    if run.trigger == "team_session":
        return f"Team session for {who}: {(run.output or {}).get('status')} ({', '.join((run.output or {}).get('reasons') or []) or 'as planned'})."
    if run.trigger == "coach_instruction":
        return (
            f"Coach instruction for {who}: \"{(run.inputs or {}).get('instruction', '')}\". "
            f"Planner rebuilt the week: solver {out.get('status')}, load {out.get('weekly_load')} AU."
        )
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
    force: bool = Field(default=False, description="apply although the held-out gain is within the noise")


@router.post("/calibration/apply")
def calibration_apply(body: Weights, user: CurrentUser = Depends(require(Role.COACH)), db: Session = Depends(get_db)) -> dict:
    """A coach reviews the suggestion and applies it (or resets). Takes effect for new scores.

    The suggested weights are refused unless they beat the current ones on held-out
    players by more than the noise (or the coach explicitly forces it)."""
    if body.weights is not None and not body.force:
        rep = calibration.report(db, staff_of(user, db).squad_id)
        if body.weights == rep["suggested"] and not rep["recommended"]:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "The suggested weights don't beat the current ones on players they weren't fitted on by more than "
                "the noise. Collect more ratings first.",
            )
    try:
        calibration.apply(db, body.weights)
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from e
    audit(db, user, "update", "readiness_weights", None, weights=body.weights)
    db.commit()
    return calibration.report(db, staff_of(user, db).squad_id)


# --------------------------------------------------------------------------- position + coach instructions


class PositionBody(BaseModel):
    position: Position


@router.put("/players/{player_id}/position")
def set_position(
    player_id: str, body: PositionBody, user: CurrentUser = Depends(require(*STAFF)), db: Session = Depends(get_db)
) -> dict:
    """The position picks the position block of the player's gym programme."""
    p = player_in_scope(player_id, user, db)
    p.position = body.position.value
    audit(db, user, "update", "player", p.id, position=p.position)
    db.commit()
    today = clock.today()
    gym = gym_view.week(db, p, views.week_start(today), today)
    return {"position": p.position, "gym": gym["sessions"][0]["programme"] if gym["sessions"] else gym["optional"]}


class Instruction(BaseModel):
    text: str = Field(min_length=3, max_length=300)
    apply: bool = False


@router.post("/players/{player_id}/instruction")
def instruction(
    player_id: str, body: Instruction, user: CurrentUser = Depends(require(Role.COACH)), db: Session = Depends(get_db)
) -> dict:
    """A coach's note in plain words becomes planner constraints for the rest of the week.

    Without `apply` it is a preview (current vs proposed week). With `apply` the new week
    is activated, logged as an agent run and shown to the player as a why-card.
    """
    from agents.instruction import InstructionRefused, parse
    from agents.llm import default_backend
    from agents.monitor import assess
    from agents.rules import DevGoal, default_constraints
    from planner.model import hard_violations, plan_week

    p = player_in_scope(player_id, user, db)
    today = clock.today()
    start, n = today, agent_runner.days_left_in_week(today)
    current = agent_runner.plan_days(db, p, start, n)
    counts: dict[SessionType, int] = {}
    for d in current:
        counts[d.kind] = counts.get(d.kind, 0) + 1
    try:
        parsed = parse(body.text, start, n, default_backend(), counts)
    except InstructionRefused as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from e

    a = assess(agent_runner.load_history(db, p, today))
    inp = agent_runner.planner_input(db, p, start, n).model_copy(
        update={
            "acwr": a.acwr,
            "chronic_daily_load": a.chronic_daily_load or 300.0,
            "acute_daily_load": a.acute_daily_load if a.chronic_daily_load else None,
            "in_phv_window": bool(a.growth and a.growth.in_phv_window),
        }
    )
    from planner.schema import MinSessions

    if not any(isinstance(c, MinSessions) for c in parsed.constraints.soft) and parsed.constraints.load_factor <= 1.0:
        # The coach only asked for less: no day may get harder than it is now.
        inp = inp.model_copy(update={"rpe_ceiling": [d.rpe for d in current]})
    goals = [DevGoal(g.kpi, g.sessions_per_week) for g in agent_runner.active_goals(db, p, start)]
    base = default_constraints(a.planning_flags, goals, inp)
    cs = parsed.constraints.model_copy(update={"soft": (parsed.constraints.soft + base.soft)[:12]})
    result = plan_week(inp, cs)
    out = {
        "constraints": parsed.summary,
        "source": parsed.source,
        "status": result.status,
        "dropped": result.dropped,
        "hard_violations": hard_violations(result, inp),
        "current": [views.day_json(d) for d in current],
        "proposed": [views.day_json(d) for d in result.days],
        "applied": False,
    }
    if not body.apply:
        db.commit()
        return out

    from domain.models import Approval

    staff = staff_of(user, db)
    run = AgentRun(
        agent=AgentName.PLANNER,
        trigger="coach_instruction",
        player_id=p.id,
        inputs={"instruction": body.text, "day": today.isoformat()},
        flags=[{"kind": f.kind.value, "detail": f.detail} for f in a.flags],
        constraints=cs.model_dump(mode="json"),
        output={"status": result.status, "weekly_load": result.weekly_load, "decision": "coach_instruction", "dropped": result.dropped},
        used_fallback=parsed.source == "rules",
        llm_valid_first_try=None if parsed.source == "rules" else parsed.source == "llm",
    )
    db.add(run)
    db.flush()
    plan = agent_runner._plan_from(
        result.days,
        p,
        run,
        "draft",
        solver_status=result.status,
        explanation_player=(
            f'Your coach adjusted your week: "{body.text.strip()}". '
            "The safety rules (rest day, easy day before matches, growth-zone limits) still apply. "
            "Ask your coach if you have questions."
        ),
        reason_coach=f"Coach instruction: {body.text.strip()}"[:300],
    )
    db.add(plan)
    agent_runner.activate(db, plan, p)
    changed = [d.date.isoformat() for d, c in zip(result.days, current) if (d.kind, d.rpe) != (c.kind, c.rpe)]
    prop = Proposal(
        agent_run_id=run.id,
        player_id=p.id,
        kind="coach_instruction",
        payload={"changed_days": changed, "instruction": body.text},
        proposed_plan_id=plan.id,
        reason=f"Coach instruction: {body.text.strip()}"[:300],
        data_chips=parsed.summary[:4],
        policy_rule="coach instruction: applied by the coach",
        status=ProposalStatus.APPROVED,
    )
    db.add(prop)
    db.flush()
    db.add(Approval(proposal_id=prop.id, approver_id=staff.id, action="approve", note=body.text[:500]))
    db.add(PlayerNote(player_id=p.id, author_id=staff.id, day=today, text=f"Plan instruction: {body.text.strip()}"))
    audit(db, user, "approve", "proposal", prop.id, player=p.id, instruction=True)
    db.commit()
    return {**out, "applied": True}


# --------------------------------------------------------------------------- training pitch (squad week)


@router.get("/squad-week")
def get_squad_week(offset: int = 0, user: CurrentUser = Depends(require(*STAFF)), db: Session = Depends(get_db)) -> dict:
    today = clock.today()
    start = views.week_start(today) + timedelta(weeks=max(0, min(1, offset)))
    out = squad_week.squad_week(db, _squad_players(db, user), start, today)
    audit(db, user, "read", "weekly_plan", None, view="squad_week")
    db.commit()
    return out


class TeamSession(BaseModel):
    day: date
    kind: SessionType
    rpe: int = Field(ge=0, le=10)
    minutes: int | None = Field(default=None, ge=15, le=150)
    player_ids: list[str] | None = None
    apply: bool = False


@router.post("/squad-week/session")
def team_session(body: TeamSession, user: CurrentUser = Depends(require(Role.COACH)), db: Session = Depends(get_db)) -> dict:
    """Place one team session on a day for the squad. Each player gets it as planned, or
    the nearest safe version when it would break a hard rule for them."""
    from planner.schema import RPE_RANGE

    today = clock.today()
    if body.day < today:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Plan today or a later day")
    lo, hi = RPE_RANGE[body.kind]
    if not lo <= body.rpe <= hi or body.kind == SessionType.MATCH:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"{body.kind.value} sessions use effort {lo}-{hi}")
    staff = staff_of(user, db)
    players = [p for p in _squad_players(db, user) if body.player_ids is None or p.id in body.player_ids]
    # The primary team's coach plans the player's week
    players = [p for p in players if not staff.squad_id or p.squad_id == staff.squad_id]
    label = f"{views.SESSION_LABEL[body.kind].lower()} (effort {body.rpe})"
    results = [squad_week.place(db, p, body.day, body.kind, body.rpe, body.minutes, today) for p in players]
    if body.apply:
        by_id = {p.id: p for p in players}
        for r in results:
            squad_week.apply(db, by_id[r["player"]["id"]], r, staff, label)
        audit(db, user, "approve", "team_session", None, day=body.day.isoformat(), kind=body.kind.value, players=len(results))
    db.commit()
    counts: dict[str, int] = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    return {"day": body.day.isoformat(), "label": label, "counts": counts, "players": results, "applied": body.apply}


# --------------------------------------------------------------------------- match ratings


def _team_matches(db: Session, user: CurrentUser) -> list[Match]:
    staff = staff_of(user, db)
    today = clock.today()
    q = select(Match).where(
        Match.kickoff < datetime.combine(today + timedelta(days=1), datetime.min.time()),
        Match.kickoff >= datetime.combine(today - timedelta(days=42), datetime.min.time()),
    )
    if staff.squad_id:
        q = q.where(Match.squad_id == staff.squad_id)
    return list(db.scalars(q.order_by(Match.kickoff.desc())))


@router.get("/matches")
def matches(user: CurrentUser = Depends(require(*STAFF)), db: Session = Depends(get_db)) -> list[dict]:
    from domain.models import Appearance, Squad

    out = []
    for m in _team_matches(db, user):
        apps = list(db.scalars(select(Appearance).where(Appearance.match_id == m.id, Appearance.minutes > 0)))
        rated = [a.rating for a in apps if a.rating is not None and a.rating_source == "stats"]
        best = max(apps, key=lambda a: a.rating or 0, default=None)
        squad = db.get(Squad, m.squad_id)
        out.append(
            {
                "id": m.id,
                "date": m.kickoff.date().isoformat(),
                "opponent": m.opponent,
                "team": squad.name if squad else "",
                "competition": m.competition,
                "players": len(apps),
                "rated": len(rated),
                "avg_rating": round(sum(rated) / len(rated), 2) if rated else None,
                "best": None if best is None or best.rating is None else {"name": db.get(Player, best.player_id).display_name, "rating": best.rating},
            }
        )
    db.commit()
    return out


@router.get("/matches/{match_id}")
def match_report(match_id: str, user: CurrentUser = Depends(require(*STAFF)), db: Session = Depends(get_db)) -> dict:
    from domain.models import Squad
    from performance.rating import STAT_KEYS, band

    m = db.get(Match, match_id)
    if m is None or m.id not in {x.id for x in _team_matches(db, user)}:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Match not found")
    rows = []
    for p in _squad_players(db, user):
        if not performance.is_registered(db, p, m.squad_id):
            continue
        a = performance.appearance(db, p, m, create=False)
        rows.append(
            {
                "player": {"id": p.id, "name": p.display_name, "position": p.position},
                "minutes": a.minutes if a else 0,
                "started": a.started if a else False,
                "position": (a.position if a else None) or p.position,
                "stats": (a.stats if a else {}) or {},
                "rating": a.rating if a else None,
                "rating_band": band(a.rating if a else None),
                "rating_source": a.rating_source if a else None,
                "breakdown": (a.breakdown if a else []) or [],
                "self_rating": a.self_rating if a else None,
            }
        )
    rows.sort(key=lambda r: (-(r["minutes"] or 0), r["player"]["name"]))
    squad = db.get(Squad, m.squad_id)
    audit(db, user, "read", "appearance", m.id)
    db.commit()
    return {
        "match": {"id": m.id, "date": m.kickoff.date().isoformat(), "opponent": m.opponent, "team": squad.name if squad else "", "competition": m.competition},
        "stat_keys": STAT_KEYS,
        "players": rows,
    }


class PlayerStats(BaseModel):
    player_id: str
    minutes: int = Field(ge=0, le=130)
    started: bool = False
    position: Position | None = None
    stats: dict[str, float | int | str | None] = Field(default_factory=dict)


class MatchStats(BaseModel):
    players: list[PlayerStats] = Field(max_length=40)


@router.put("/matches/{match_id}/ratings")
def save_ratings(match_id: str, body: MatchStats, user: CurrentUser = Depends(require(Role.COACH)), db: Session = Depends(get_db)) -> dict:
    """Coach (or data-provider) match stats; ratings are computed with a breakdown."""
    from performance.rating import STAT_KEYS

    m = db.get(Match, match_id)
    if m is None or m.id not in {x.id for x in _team_matches(db, user)}:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Match not found")
    allowed = {p.id: p for p in _squad_players(db, user) if performance.is_registered(db, p, m.squad_id)}
    for row in body.players:
        p = allowed.get(row.player_id)
        if p is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not a player of this team")
        unknown = set(row.stats) - set(STAT_KEYS)
        if unknown:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Unknown stats: {', '.join(sorted(unknown))}")
        if row.stats.get("result") not in (None, "win", "draw", "loss"):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "result is win, draw or loss")
        if any(isinstance(v, (int, float)) and v < 0 for v in row.stats.values()):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Stats can't be negative")
        a = performance.appearance(db, p, m)
        performance.apply_stats(a, row.minutes, row.started, row.position.value if row.position else None, row.stats)
    audit(db, user, "update", "appearance", m.id, players=len(body.players))
    db.commit()
    return match_report(match_id, user, db)


class Preview(BaseModel):
    position: Position | None = None
    minutes: int = Field(ge=0, le=130)
    stats: dict[str, float | int | str | None] = Field(default_factory=dict)


@router.post("/ratings/preview")
def rating_preview(body: Preview, _: CurrentUser = Depends(require(*STAFF))) -> dict:
    from performance.rating import band, rate

    r = rate(body.position.value if body.position else None, body.minutes, body.stats)
    return {**r.to_json(), "rating_band": band(r.value)}
