"""Connects the agents to the database: builds their inputs from stored records and
persists what they decide (AgentRun, DailyStatus, WeeklyPlan, Proposal, Escalation)."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from agents import dev_coach
from agents.coordinator import ActionKind, Decision, decide
from agents.coordinator import Proposal as PolicyProposal
from agents.llm import LLMBackend
from agents.monitor import Measurements, PlayerHistory, assess
from agents.orchestrator import PROTECT_DAYS, CycleResult, diff, protective_plan, run_cycle
from agents.rules import DevGoal
from analytics.maturation import MaturityStatus
from api.deps import age_on, audit, has_consent
from domain.enums import AgentName, ConsentDataType, ProposalStatus, Role, SessionType
from domain.models import (
    AgentRun,
    Anthropometrics,
    DailyStatus,
    Drill,
    Escalation,
    GuardianAlert,
    HRVRecord,
    IDPGoal,
    Match,
    PlanItem,
    Player,
    Proposal,
    SessionLoad,
    SleepRecord,
    StaffMember,
    TestResult,
    WeeklyPlan,
    WellnessCheckin,
)
from domain.models import (
    Session as TeamSession,
)
from pathway import service as pathway_service
from planner.model import hard_violations
from planner.schema import SESSION_MINUTES, PlanDay, PlannerInput, PlanResult

HISTORY_DAYS = 56
PRESEASON_DAILY_LOAD = 300.0


def _now() -> datetime:
    return datetime.now(UTC)


# --------------------------------------------------------------------------- inputs


def load_history(db: Session, player: Player, day: date) -> PlayerHistory:
    start = day - timedelta(days=HISTORY_DAYS - 1)
    loads = defaultdict(float)
    for sl in db.scalars(
        select(SessionLoad).where(SessionLoad.player_id == player.id, SessionLoad.day >= start, SessionLoad.day <= day)
    ):
        loads[sl.day] += sl.load_au
    first = min(loads) if loads else day
    days = [first + timedelta(days=i) for i in range((day - first).days + 1)]
    daily = [loads.get(d, 0.0) for d in days]
    preseason = PRESEASON_DAILY_LOAD
    prof = pathway_service.profile(db, player)
    if prof is not None:
        # Self-guided players log their own sessions. With nothing logged for two weeks
        # their fitness is unknown, so start from the level's normal week (not from zero).
        preseason = pathway_service.preseason_load(prof)
        if not any(d > day - timedelta(days=14) for d in loads):
            daily = []

    sleep, hrv, hooper, mood, pain, meas = [], [], None, False, False, None
    if has_consent(db, player, ConsentDataType.SLEEP, day):
        sleep = [
            s.hours
            for s in db.scalars(
                select(SleepRecord)
                .where(SleepRecord.player_id == player.id, SleepRecord.night_of <= day, SleepRecord.night_of > day - timedelta(days=7))
                .order_by(SleepRecord.night_of)
            )
        ]
    if has_consent(db, player, ConsentDataType.HRV, day):
        rows = list(
            db.scalars(
                select(HRVRecord)
                .where(HRVRecord.player_id == player.id, HRVRecord.day <= day, HRVRecord.day > day - timedelta(days=8))
                .order_by(HRVRecord.day)
            )
        )
        # One metric only (RMSSD from a strap, SDNN from Apple Watch): the latest one decides,
        # and the baseline is built from the same metric, never a mix.
        metric = (rows[-1].metric or "rmssd") if rows else "rmssd"
        hrv = [h.ln_rmssd for h in rows if (h.metric or "rmssd") == metric]
    missed = 0
    if has_consent(db, player, ConsentDataType.WELLNESS, day):
        recent = {
            c.day: c
            for c in db.scalars(
                select(WellnessCheckin).where(
                    WellnessCheckin.player_id == player.id,
                    WellnessCheckin.day <= day,
                    WellnessCheckin.day > day - timedelta(days=14),
                )
            )
        }
        today = recent.get(day)
        if today is not None:
            hooper = (today.sleep_quality, today.fatigue, today.stress, today.soreness)
            mood, pain = today.mood_red, today.pain_reported
        d = day
        while d not in recent and d > day - timedelta(days=14) and prof is None:  # no staff to alert
            missed += 1
            d -= timedelta(days=1)
    if has_consent(db, player, ConsentDataType.ANTHROPOMETRICS, day):
        a = db.scalars(
            select(Anthropometrics)
            .where(Anthropometrics.player_id == player.id, Anthropometrics.day <= day)
            .order_by(Anthropometrics.day.desc())
            .limit(1)
        ).first()
        if a is not None:
            meas = Measurements(age_on(player.birth_date, a.day), a.height_cm, a.sitting_height_cm, a.weight_kg)
    return PlayerHistory(
        player_id=player.id,
        day=day,
        daily_loads=daily,
        sleep_hours=sleep,
        ln_rmssd=hrv,
        hooper_today=hooper,
        mood_red=mood,
        pain_reported=pain,
        missed_checkins_in_row=missed,
        measurements=meas,
        preseason_daily_load=preseason if len(daily) < 28 else None,
        previous_band=_previous_band(db, player, day),
    )


def _previous_band(db: Session, player: Player, day: date):
    from analytics.readiness import Band

    prev = db.scalars(
        select(DailyStatus)
        .where(DailyStatus.player_id == player.id, DailyStatus.day < day)
        .order_by(DailyStatus.day.desc())
        .limit(1)
    ).first()
    return Band(prev.band) if prev and prev.band and (day - prev.day).days <= 3 else None


def team_ids(db: Session, player: Player) -> list[str]:
    """The player's primary team first, then teams from dual registrations."""
    from domain.models import Registration

    extra = [r.squad_id for r in db.scalars(select(Registration).where(Registration.player_id == player.id))]
    return [player.squad_id, *[s for s in extra if s != player.squad_id]]


def match_days(db: Session, player: Player, start: date, n: int = 7) -> dict[date, Match]:
    """Fixtures of every team the player is registered with. Two matches on one day:
    the primary team's match counts (the player can't play both)."""
    end = start + timedelta(days=n)
    teams = team_ids(db, player)
    out: dict[date, Match] = {}
    for m in db.scalars(
        select(Match)
        .where(
            Match.squad_id.in_(teams),
            Match.kickoff >= datetime.combine(start, datetime.min.time()),
            Match.kickoff < datetime.combine(end, datetime.min.time()),
        )
        .order_by(Match.kickoff)
    ):
        d = m.kickoff.date()
        if d not in out or teams.index(m.squad_id) < teams.index(out[d].squad_id):
            out[d] = m
    return out


def active_goals(db: Session, player: Player, day: date) -> list[IDPGoal]:
    return list(
        db.scalars(
            select(IDPGoal).where(
                IDPGoal.player_id == player.id,
                IDPGoal.status == "active",
                IDPGoal.starts_on <= day,
                IDPGoal.ends_on >= day,
            )
        )
    )


def plan_days(db: Session, player: Player, start: date, n: int = 7) -> list[PlanDay]:
    """The player's current plan for [start, start+n): active plan items, else the squad's
    team sessions, with fixtures always on match days."""
    items: dict[date, PlanItem] = {}
    for plan in db.scalars(
        select(WeeklyPlan)
        .where(WeeklyPlan.player_id == player.id, WeeklyPlan.status == "active")
        .order_by(WeeklyPlan.starts_on)
    ):
        for it in plan.items:
            if start <= it.day < start + timedelta(days=n):
                items[it.day] = it
    team = {
        s.day: s
        for s in db.scalars(
            select(TeamSession).where(
                TeamSession.squad_id == player.squad_id, TeamSession.day >= start, TeamSession.day < start + timedelta(days=n)
            )
        )
    }
    matches = match_days(db, player, start, n)
    out = []
    for i in range(n):
        d = start + timedelta(days=i)
        if d in matches:
            minutes = items[d].minutes if d in items and items[d].kind == SessionType.MATCH else 90
            out.append(PlanDay(day=i, date=d, kind=SessionType.MATCH, rpe=8, minutes=minutes))
        elif d in items:
            it = items[d]
            out.append(PlanDay(day=i, date=d, kind=it.kind, rpe=it.target_rpe, minutes=it.minutes))
        elif d in team:
            t = team[d]
            out.append(
                PlanDay(
                    day=i, date=d, kind=t.kind, rpe=round(t.planned_rpe or 5), minutes=t.planned_minutes or SESSION_MINUTES[t.kind]
                )
            )
        else:
            out.append(PlanDay(day=i, date=d, kind=SessionType.REST, rpe=0, minutes=0))
    # Not planned yet (e.g. next week): show back-to-back matches within H8 already,
    # the second team's match taking what's left of the 90 minutes.
    if age_on(player.birth_date, start) < 18:
        for a, b in zip(out, out[1:]):
            if a.kind == b.kind == SessionType.MATCH and a.date not in items and b.date not in items and a.minutes + b.minutes > 90:
                second = b if matches[b.date].squad_id != player.squad_id else a
                second.minutes = max(0, 90 - (a.minutes if second is b else b.minutes))
    return out


def has_active_plan(db: Session, player: Player, start: date) -> bool:
    return (
        db.scalars(
            select(PlanItem.id)
            .join(WeeklyPlan)
            .where(
                WeeklyPlan.player_id == player.id,
                WeeklyPlan.status == "active",
                PlanItem.day >= start,
                PlanItem.day < start + timedelta(days=7),
            )
            .limit(1)
        ).first()
        is not None
    )


def planner_input(db: Session, player: Player, start: date, n: int = 7) -> PlannerInput:
    matches = match_days(db, player, start, n)
    exams = {date.fromisoformat(x) for x in (player.exam_dates or [])}
    extra = {}
    prof = pathway_service.profile(db, player)
    if prof is not None:
        extra = pathway_service.planner_overrides(prof, start, n)
    return PlannerInput(
        player_id=player.id,
        start=start,
        days=n,
        under_18=age_on(player.birth_date, start) < 18,
        match_priority={(d - start).days: 2 if m.squad_id == player.squad_id else 1 for d, m in matches.items()},
        match_days=sorted((d - start).days for d in matches),
        exam_days=sorted((d - start).days for d in exams if 0 <= (d - start).days < n),
        preferred_days=player.preferred_days or [],
        min_training_sessions=max(1, round(3 * n / 7)),
    ).model_copy(update=extra)


def plan_covers(db: Session, player: Player, start: date, end: date) -> bool:
    """Every day in [start, end) has an active plan item."""
    days = {
        it.day
        for it in db.scalars(
            select(PlanItem)
            .join(WeeklyPlan)
            .where(WeeklyPlan.player_id == player.id, WeeklyPlan.status == "active", PlanItem.day >= start, PlanItem.day < end)
        )
    }
    return all(start + timedelta(days=i) in days for i in range((end - start).days))


REPLAN_FLAGS = {"short_sleep", "low_hrv", "readiness_red", "load_spike"}


def days_left_in_week(start: date) -> int:
    return 7 - start.weekday()  # plans run Monday-Sunday


# --------------------------------------------------------------------------- outputs


def save_status(db: Session, player: Player, day: date, a) -> DailyStatus:
    st = db.scalars(select(DailyStatus).where(DailyStatus.player_id == player.id, DailyStatus.day == day)).first()
    if st is None:
        st = DailyStatus(player_id=player.id, day=day)
        db.add(st)
    st.readiness = None if a.readiness is None else round(a.readiness.score, 1)
    st.band = None if a.readiness is None else a.readiness.band.value
    st.acwr = None if a.acwr is None else round(a.acwr, 3)
    st.in_phv_window = bool(a.growth and a.growth.in_phv_window)
    st.maturity_offset = None if a.growth is None else round(a.growth.maturity_offset, 2)
    st.flags = [{"kind": f.kind.value, "detail": f.detail} for f in a.flags]
    st.chips = list(a.chips)
    st.components = {} if a.readiness is None else {k: round(v, 2) for k, v in a.readiness.components.items()}
    return st


def _plan_from(result_days: list[PlanDay], player: Player, run: AgentRun, status: str, **kw) -> WeeklyPlan:
    plan = WeeklyPlan(player_id=player.id, starts_on=result_days[0].date, agent_run_id=run.id, status=status, **kw)
    for d in result_days:
        plan.items.append(PlanItem(day=d.date, kind=d.kind, target_rpe=d.rpe, minutes=d.minutes))
    return plan


def _supersede_active(db: Session, player: Player, start: date, end: date, keep: WeeklyPlan) -> None:
    for p in db.scalars(select(WeeklyPlan).where(WeeklyPlan.player_id == player.id, WeeklyPlan.status == "active")):
        if p.id != keep.id and p.starts_on < end and p.starts_on + timedelta(days=7) > start:
            # Keep days before the new plan's start; the new plan owns the rest.
            for it in list(p.items):
                if it.day >= start:
                    p.items.remove(it)
            if not p.items:
                p.status = "superseded"


def activate(db: Session, plan: WeeklyPlan, player: Player) -> None:
    plan.status = "active"
    db.flush()
    _supersede_active(db, player, plan.starts_on, plan.starts_on + timedelta(days=7), plan)


def escalation_contact(db: Session, player: Player) -> StaffMember | None:
    if player.escalation_contact_id:
        return db.get(StaffMember, player.escalation_contact_id)
    return db.scalars(
        select(StaffMember).where(StaffMember.squad_id == player.squad_id, StaffMember.role == Role.PHYSIO)
    ).first() or db.scalars(select(StaffMember).where(StaffMember.squad_id == player.squad_id)).first()


def _escalate(db: Session, player: Player, cycle: CycleResult, run: AgentRun, day: date) -> list[Escalation]:
    staff = escalation_contact(db, player)
    out = []
    open_kinds = {
        e.kind
        for e in db.scalars(
            select(Escalation).where(Escalation.player_id == player.id, Escalation.acknowledged_at.is_(None))
        )
    }
    for f in cycle.assessment.safety_flags:
        if staff is None:
            break  # no staff: _alert_guardians and _protect take over
        if f.kind.value in open_kinds:
            continue
        esc = Escalation(player_id=player.id, kind=f.kind.value, staff_id=staff.id, created_at=_now())
        db.add(esc)
        # In-app notification: the escalation lands in the staff member's queue now.
        esc.notified_at = _now()
        out.append(esc)
        audit(db, None, "escalate", "escalation", None, player=player.id, kind=f.kind.value, staff=staff.id, run=run.id)
    return out


def _alert_guardians(db: Session, player: Player, cycle: CycleResult) -> list[GuardianAlert]:
    """No staff to escalate to (self-guided player): each linked parent is the named adult."""
    out = []
    for g in player.guardians:
        open_kinds = {
            a.kind
            for a in db.scalars(
                select(GuardianAlert).where(
                    GuardianAlert.player_id == player.id, GuardianAlert.guardian_id == g.id, GuardianAlert.seen_at.is_(None)
                )
            )
        }
        for f in cycle.assessment.safety_flags:
            if f.kind.value in open_kinds:
                continue
            alert = GuardianAlert(player_id=player.id, guardian_id=g.id, kind=f.kind.value, created_at=_now())
            db.add(alert)
            out.append(alert)
            audit(db, None, "alert_guardian", "guardian_alert", None, player=player.id, kind=f.kind.value, guardian=g.id)
    return out


def _protect(
    db: Session, player: Player, cycle: CycleResult, run: AgentRun, inp: PlannerInput, current: list[PlanDay] | None
) -> bool:
    """No staff can take over, so "no agent action" would leave a hard session in place after
    a pain report. Instead the next days become rest or recovery (rules only, never harder
    than the current plan) and the player sees a why-card. Returns True if the plan changed."""
    result = protective_plan(inp, cycle.assessment, current)
    run.output["protective_plan"] = {
        "status": result.status,
        "weekly_load": result.weekly_load,
        "hard_violations": hard_violations(result, inp),
    }
    if current is not None and diff(current, result.days).is_empty:
        return False
    kinds = ", ".join(sorted(f.kind.value.replace("_", " ") for f in cycle.assessment.safety_flags))
    plan = _plan_from(
        result.days,
        player,
        run,
        "draft",
        solver_status=result.status,
        explanation_player=(
            "You told us something that matters more than training. The next two days are rest or easy "
            "recovery only. Talk to a parent or another adult you trust, and see a doctor or physio if it's pain."
        ),
        reason_coach=f"Safety flag ({kinds}) with no staff to decide: protective plan",
    )
    db.add(plan)
    db.flush()
    d = diff(current, result.days) if current is not None else None
    db.add(
        Proposal(
            agent_run_id=run.id,
            player_id=player.id,
            kind=ActionKind.LOAD_CUT.value,
            payload={
                "rpe_delta": 0 if d is None else d.max_rpe_delta,
                "load_change_pct": 0.0 if d is None else round(d.load_change_pct, 1),
                "changed_days": [] if d is None else [(inp.start + timedelta(days=x)).isoformat() for x in d.changed_days],
            },
            proposed_plan_id=plan.id,
            reason=f"Safety flag ({kinds}): the next {PROTECT_DAYS} days are rest or recovery only",
            data_chips=cycle.assessment.chips,
            policy_rule="safety flag with no staff: protective plan (rest or recovery only), applied automatically",
            status=ProposalStatus.AUTO_APPLIED,
        )
    )
    activate(db, plan, player)
    return True


def _proposal_status(decision: Decision) -> ProposalStatus:
    return {
        Decision.AUTO_APPLY: ProposalStatus.AUTO_APPLIED,
        Decision.AUTO_APPLY_NOTIFY_COACH: ProposalStatus.AUTO_APPLIED,
        Decision.COACH_APPROVAL: ProposalStatus.PENDING,
        Decision.ESCALATE: ProposalStatus.ESCALATED,
    }[decision]


def run_player(db: Session, player: Player, day: date, trigger: str, llm: LLMBackend | None = None) -> dict:
    """Monitor, then (if needed) Planner + Coordinator for the rest of the week after `day`.

    The Planner runs when the week has no plan yet (normally Sunday night: that plan is
    activated and logged), or when the Monitor raises a new recovery/load flag: the rest
    of the week is then re-planned, never harder than the current plan, and the change
    goes through the Coordinator's policy table. Safety flags always escalate.
    """
    history = load_history(db, player, day)
    start = day + timedelta(days=1)
    n = days_left_in_week(start)
    a0 = assess(history)
    prev = db.scalars(
        select(DailyStatus).where(DailyStatus.player_id == player.id, DailyStatus.day == day - timedelta(days=1))
    ).first()
    prev_flags = {f["kind"] for f in (prev.flags if prev else [])}
    new_flags = {f.kind.value for f in a0.planning_flags} & REPLAN_FLAGS - prev_flags
    planned = has_active_plan(db, player, start)
    if not a0.safety_flags and planned and not new_flags:
        save_status(db, player, day, a0)
        db.add(
            AgentRun(
                agent=AgentName.MONITOR,
                trigger=trigger,
                player_id=player.id,
                started_at=_now(),
                finished_at=_now(),
                flags=[{"kind": f.kind.value, "detail": f.detail} for f in a0.flags],
                output={"decision": "no change"},
            )
        )
        return {"player_id": player.id, "escalations": 0, "proposal": None}

    inp = planner_input(db, player, start, n)
    goals = [DevGoal(g.kpi, g.sessions_per_week) for g in active_goals(db, player, start)]
    self_guided = pathway_service.profile(db, player)
    if self_guided is not None:
        goals = pathway_service.goals(db, player, self_guided, day)
    current = None
    if planned:
        current = plan_days(db, player, start, n)
        inp = inp.model_copy(update={"rpe_ceiling": [d.rpe for d in current]})
    run = AgentRun(agent=AgentName.PLANNER, trigger=trigger, player_id=player.id, started_at=_now())
    db.add(run)
    db.flush()
    cycle = run_cycle(history, inp, goals, current, llm)
    a = cycle.assessment
    save_status(db, player, day, a)
    run.flags = [{"kind": f.kind.value, "detail": f.detail} for f in a.flags]
    run.inputs = {
        "day": day.isoformat(),
        "readiness": None if a.readiness is None else round(a.readiness.score, 1),
        "acwr": None if a.acwr is None else round(a.acwr, 2),
        "match_days": inp.match_days,
        "exam_days": inp.exam_days,
        "goals": [g.kpi for g in goals],
    }
    summary: dict = {"player_id": player.id, "escalations": 0, "proposal": None}

    if cycle.escalate:
        run.agent = AgentName.COORDINATOR
        run.output = {"decision": "escalate", "rule": cycle.ruling.rule}
        if escalation_contact(db, player) is not None:
            summary["escalations"] = len(_escalate(db, player, cycle, run, day))
            summary["notified"] = "staff"
        else:
            alerts = _alert_guardians(db, player, cycle)
            summary["escalations"] = len(alerts)
            summary["notified"] = "guardian" if player.guardians else None
            summary["protected"] = _protect(db, player, cycle, run, inp, current)
    elif cycle.outcome is not None:
        out = cycle.outcome
        run.constraints = out.constraints.model_dump(mode="json")
        run.llm_valid_first_try = None if out.constraint_source == "rules" else out.constraint_source == "llm"
        run.used_fallback = out.constraint_source == "rules"
        run.output = {
            "status": out.result.status,
            "weekly_load": out.result.weekly_load,
            "cap": out.result.weekly_load_cap,
            "dropped": out.result.dropped,
            "hard_violations": out.hard_violations,
            "notes": cycle.notes,
        }
        if cycle.proposal is not None:
            plan = _plan_from(
                out.result.days,
                player,
                run,
                "draft",
                solver_status=out.result.status,
                explanation_player=out.explanation_player,
                reason_coach=out.reason_coach,
            )
            db.add(plan)
            db.flush()
            for old in db.scalars(
                select(Proposal).where(Proposal.player_id == player.id, Proposal.status == ProposalStatus.PENDING)
            ):
                old.status = ProposalStatus.SUPERSEDED
            prop = Proposal(
                agent_run_id=run.id,
                player_id=player.id,
                kind=cycle.proposal.kind.value,
                payload={
                    "rpe_delta": cycle.proposal.rpe_delta,
                    "load_change_pct": round(cycle.diff.load_change_pct, 1),
                    "changed_days": [(start + timedelta(days=d)).isoformat() for d in cycle.diff.changed_days],
                },
                proposed_plan_id=plan.id,
                reason=out.reason_coach[:300],
                data_chips=a.chips,
                policy_rule=cycle.ruling.rule,
                status=_proposal_status(cycle.ruling.decision),
            )
            if self_guided is not None and prop.status == ProposalStatus.PENDING:
                # No coach to ask. A re-plan can only lower load (RPE ceiling), so it is
                # applied and explained to the player on the Today screen.
                prop.status = ProposalStatus.AUTO_APPLIED
                prop.policy_rule = "self-guided player: re-plans only make the week easier, applied automatically"
            db.add(prop)
            if prop.status == ProposalStatus.AUTO_APPLIED:
                activate(db, plan, player)
            run.output["decision"] = cycle.ruling.decision.value
            summary["proposal"] = prop.kind
        elif "first plan" in cycle.notes:
            plan = _plan_from(
                out.result.days,
                player,
                run,
                "draft",
                solver_status=out.result.status,
                explanation_player=out.explanation_player,
                reason_coach=out.reason_coach,
            )
            db.add(plan)
            activate(db, plan, player)
    run.finished_at = _now()
    audit(db, None, "agent_run", "agent_run", run.id, player=player.id, trigger=trigger)
    return summary


def run_squad(db: Session, squad_id: str, day: date, trigger: str = "nightly", llm: LLMBackend | None = None) -> dict:
    out = defaultdict(int)
    for p in db.scalars(select(Player).where(Player.squad_id == squad_id)):
        s = run_player(db, p, day, trigger, llm)
        out["players"] += 1
        out["escalations"] += s["escalations"]
        if s["proposal"]:
            out[f"proposal_{s['proposal']}"] += 1
    db.commit()
    return dict(out)


# --------------------------------------------------------------------------- coach decisions


class EditRejected(ValueError):
    pass


def decide_proposal(
    db: Session, prop: Proposal, approver: StaffMember, action: str, edits: list[dict] | None = None, note: str | None = None
) -> Proposal:
    from domain.models import Approval

    if prop.status != ProposalStatus.PENDING:
        raise EditRejected(f"proposal is {prop.status.value}")
    player = db.get(Player, prop.player_id)
    if prop.kind == ActionKind.NEW_GOAL.value:
        if action in ("approve", "edit"):
            _apply_goals(db, player, prop.payload)
            prop.status = ProposalStatus.APPROVED if action == "approve" else ProposalStatus.EDITED
        else:
            prop.status = ProposalStatus.REJECTED
    else:
        plan = db.get(WeeklyPlan, prop.proposed_plan_id)
        if action == "reject":
            prop.status = ProposalStatus.REJECTED
            plan.status = "superseded"
        else:
            if action == "edit":
                _apply_edits(db, player, plan, edits or [])
                prop.status = ProposalStatus.EDITED
            else:
                prop.status = ProposalStatus.APPROVED
            activate(db, plan, player)
    db.add(Approval(proposal_id=prop.id, approver_id=approver.id, action=action, note=note, decided_at=_now()))
    return prop


def _apply_edits(db: Session, player: Player, plan: WeeklyPlan, edits: list[dict]) -> None:
    by_day = {it.day.isoformat(): it for it in plan.items}
    for e in edits:
        it = by_day.get(e["day"])
        if it is None:
            raise EditRejected(f"no plan item on {e['day']}")
        kind = SessionType(e.get("kind", it.kind))
        it.kind, it.target_rpe = kind, int(e.get("rpe", it.target_rpe))
        it.minutes = SESSION_MINUTES[kind] if kind != SessionType.MATCH else it.minutes
    inp = planner_input(db, player, plan.starts_on)
    days = [
        PlanDay(day=(it.day - plan.starts_on).days, date=it.day, kind=it.kind, rpe=it.target_rpe, minutes=it.minutes)
        for it in sorted(plan.items, key=lambda i: i.day)
    ]
    st = db.scalars(select(DailyStatus).where(DailyStatus.player_id == player.id).order_by(DailyStatus.day.desc())).first()
    inp = inp.model_copy(update={"acwr": st.acwr if st else None, "in_phv_window": bool(st and st.in_phv_window)})
    errors = hard_violations(PlanResult(player_id=player.id, days=days, status="feasible"), inp)
    if errors:
        # Coaches can change the plan, but not past the hard safety rules.
        raise EditRejected("Edit breaks a safety rule: " + "; ".join(errors))


# --------------------------------------------------------------------------- development coach


def latest_tests(db: Session, player: Player) -> dict[str, float]:
    out: dict[str, tuple[date, float]] = {}
    for t in db.scalars(select(TestResult).where(TestResult.player_id == player.id)):
        if t.test not in out or t.day > out[t.test][0]:
            out[t.test] = (t.day, t.value)
    return {k: v for k, (_, v) in out.items()}


def run_dev_coach(db: Session, player: Player, day: date, trigger: str, llm: LLMBackend | None = None) -> Proposal | None:
    tests = latest_tests(db, player)
    if not tests or active_goals(db, player, day + timedelta(days=1)):
        return None
    st = db.scalars(
        select(DailyStatus).where(DailyStatus.player_id == player.id, DailyStatus.day <= day).order_by(DailyStatus.day.desc())
    ).first()
    status = MaturityStatus.CIRCA_PHV if st is None or st.maturity_offset is None else (
        MaturityStatus.PRE_PHV if st.maturity_offset < -1 else MaturityStatus.POST_PHV if st.maturity_offset > 1 else MaturityStatus.CIRCA_PHV
    )
    plan = dev_coach.run(player.id, tests, age_on(player.birth_date, day), status, llm)
    run = AgentRun(
        agent=AgentName.DEVELOPMENT_COACH,
        trigger=trigger,
        player_id=player.id,
        started_at=_now(),
        inputs={"tests": tests, "maturity": status.value},
        output={"goals": [g.kpi for g in plan.goals], "drills": [d.id for d in plan.drills], "source": plan.source},
        used_fallback=plan.source == "rules",
        finished_at=_now(),
    )
    db.add(run)
    db.flush()
    payload = {
        "goals": [
            {
                "kpi": g.kpi,
                "sessions_per_week": g.sessions_per_week,
                "baseline": next(k.value for k in plan.kpis if k.kpi == g.kpi),
                "target": next(k.target_value for k in plan.kpis if k.kpi == g.kpi),
                "bio_percentile": round(next(k.bio_percentile for k in plan.kpis if k.kpi == g.kpi)),
            }
            for g in plan.goals
        ],
        "drills": [d.id for d in plan.drills],
        "feedback": plan.feedback,
        "starts_on": (day + timedelta(days=1)).isoformat(),
    }
    ruling = decide(PolicyProposal(player.id, ActionKind.NEW_GOAL))
    prop = Proposal(
        agent_run_id=run.id,
        player_id=player.id,
        kind=ActionKind.NEW_GOAL.value,
        payload=payload,
        reason=plan.feedback[:300],
        data_chips=[f"{g['kpi']} {g['bio_percentile']}th pct" for g in payload["goals"]],
        policy_rule=ruling.rule,
        status=_proposal_status(ruling.decision),
    )
    db.add(prop)
    # Drill suggestions are auto-applied (policy table); they show on the player card.
    drill_rule = decide(PolicyProposal(player.id, ActionKind.DRILL_SUGGESTION))
    db.add(
        Proposal(
            agent_run_id=run.id,
            player_id=player.id,
            kind=ActionKind.DRILL_SUGGESTION.value,
            payload={"drills": payload["drills"]},
            reason="Drills for your development goals",
            data_chips=[],
            policy_rule=drill_rule.rule,
            status=_proposal_status(drill_rule.decision),
        )
    )
    return prop


def _apply_goals(db: Session, player: Player, payload: dict) -> None:
    start = date.fromisoformat(payload["starts_on"])
    for g in payload["goals"]:
        db.add(
            IDPGoal(
                player_id=player.id,
                kpi=g["kpi"],
                baseline_value=g["baseline"],
                target_value=g["target"],
                starts_on=start,
                ends_on=start + timedelta(days=27),
                sessions_per_week=g["sessions_per_week"],
            )
        )


def drills_by_id(db: Session) -> dict[str, Drill]:
    return {d.id: d for d in db.scalars(select(Drill))}
