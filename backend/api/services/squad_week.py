"""Training pitch: the coach plans one team session for the whole squad; each player
gets it, or the nearest safe version of it when it would break a hard rule for them
(growth zone, day before a match, exam, load cap, rest day, red battery today)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy.orm import Session

from api.services import agent_runner, views
from domain.enums import AgentName, ProposalStatus, SessionType
from domain.models import AgentRun, Approval, Player, Proposal, StaffMember
from planner.model import hard_violations
from planner.schema import RPE_RANGE, SESSION_MINUTES, PlanDay, PlanResult

REASONS = {
    "H2": "needs a rest day this week",
    "H3": "day before a match: effort at most 4",
    "H4": "growth zone: speed work at most effort 6",
    "H5": "load cap after a spike",
    "H6": "exam evening: no session",
    "H7": "effort outside the session's range",
    "H8": "too many match minutes on back-to-back days",
}


def _now() -> datetime:
    return datetime.now(UTC)


def _input(db: Session, p: Player, start: date):
    st = views.latest_status(db, p.id, start + timedelta(days=6))
    inp = agent_runner.planner_input(db, p, start, 7)
    return inp.model_copy(update={"acwr": st.acwr if st else None, "in_phv_window": bool(st and st.in_phv_window)})


def squad_week(db: Session, players: list[Player], start: date, today: date) -> dict:
    rows = []
    for p in players:
        st = views.latest_status(db, p.id, today)
        matches = agent_runner.match_days(db, p, start, 7)
        days = []
        for d in agent_runner.plan_days(db, p, start, 7):
            j = views.day_json(d)
            m = matches.get(d.date)
            if m is not None:
                j["team_match"] = m.squad_id != p.squad_id
            days.append(j)
        rows.append(
            {
                "id": p.id,
                "name": p.display_name,
                "position": p.position,
                "phv": bool(st and st.in_phv_window),
                "band": st.band if st else None,
                "dual": len(agent_runner.team_ids(db, p)) > 1,
                "days": days,
            }
        )
    return {"start": start.isoformat(), "today": today.isoformat(), "dates": [(start + timedelta(days=i)).isoformat() for i in range(7)], "players": rows}


def _candidates(kind: SessionType, rpe: int) -> list[tuple[SessionType, int]]:
    lo, _ = RPE_RANGE[kind]
    out = [(kind, r) for r in range(rpe, lo - 1, -1)]
    out += [(SessionType.RECOVERY, 3), (SessionType.RECOVERY, 2), (SessionType.REST, 0)]
    return out


def place(db: Session, p: Player, day: date, kind: SessionType, rpe: int, minutes: int | None, today: date) -> dict:
    """What this player would do if the team session goes on `day`."""
    start = views.week_start(day)
    week = agent_runner.plan_days(db, p, start, 7)
    i = (day - start).days
    current = week[i]
    base = {"player": {"id": p.id, "name": p.display_name}, "current": views.day_json(current)}
    if current.kind == SessionType.MATCH:
        return {**base, "status": "match", "proposed": views.day_json(current), "reasons": ["match day"]}
    inp = _input(db, p, start)
    before = set(hard_violations(PlanResult(player_id=p.id, days=week, status="feasible"), inp))
    st = views.latest_status(db, p.id, today)
    red_today = day == today and st is not None and st.day == today and st.band == "red"
    first_reasons: list[str] = []
    for k, r in _candidates(kind, rpe):
        if red_today and r > 4:
            first_reasons = first_reasons or ["red battery today: effort at most 4"]
            continue
        mins = 0 if k == SessionType.REST else (minutes if k == kind and minutes else SESSION_MINUTES[k])
        days = [*week]
        days[i] = PlanDay(day=i, date=day, kind=k, rpe=r, minutes=mins)
        new = set(hard_violations(PlanResult(player_id=p.id, days=days, status="feasible"), inp)) - before
        if not new:
            status = "ok" if (k, r) == (kind, rpe) else "adjusted"
            return {**base, "status": status, "proposed": views.day_json(days[i]), "reasons": first_reasons}
        if not first_reasons:
            first_reasons = sorted({REASONS.get(v[:2], v) for v in new})
    return {**base, "status": "unchanged", "proposed": views.day_json(current), "reasons": first_reasons}


def apply(db: Session, p: Player, result: dict, staff: StaffMember, label: str) -> None:
    """Write the player's new day into an active plan, log it, and show a why-card."""
    if result["status"] not in ("ok", "adjusted"):
        return
    pr = result["proposed"]
    day = date.fromisoformat(pr["date"])
    start = views.week_start(day)
    week = agent_runner.plan_days(db, p, day, (start + timedelta(days=7) - day).days)
    week[0] = PlanDay(day=0, date=day, kind=SessionType(pr["kind"]), rpe=pr["rpe"], minutes=pr["minutes"])
    run = AgentRun(
        agent=AgentName.PLANNER,
        trigger="team_session",
        player_id=p.id,
        started_at=_now(),
        finished_at=_now(),
        inputs={"day": day.isoformat(), "team_session": label},
        output={"decision": "team_session", "status": result["status"], "reasons": result["reasons"]},
    )
    db.add(run)
    db.flush()
    weekday = day.strftime("%A")
    text = f"Your coach planned a team {label} session on {weekday}."
    if result["status"] == "adjusted":
        text += f" For you it's {pr['label'].lower()} at effort {pr['rpe']} because: {', '.join(result['reasons'])}."
    plan = agent_runner._plan_from(week, p, run, "draft", solver_status="coach", explanation_player=text, reason_coach=f"Team session: {label}")
    db.add(plan)
    agent_runner.activate(db, plan, p)
    prop = Proposal(
        agent_run_id=run.id,
        player_id=p.id,
        kind="team_session",
        payload={"changed_days": [day.isoformat()]},
        proposed_plan_id=plan.id,
        reason=f"Team session on {weekday}: {label}" + (" (adjusted)" if result["status"] == "adjusted" else ""),
        data_chips=result["reasons"][:3],
        policy_rule="team session planned by the coach; hard rules checked per player",
        status=ProposalStatus.APPROVED,
    )
    db.add(prop)
    db.flush()
    db.add(Approval(proposal_id=prop.id, approver_id=staff.id, action="approve", note=label))
