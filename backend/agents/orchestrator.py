"""One agent cycle for one player: Monitor -> Planner -> diff -> Coordinator.

Pure functions over plain data; the API layer persists AgentRun, Proposal,
Escalation and AuditLog rows from the returned `CycleResult`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from agents import planner_agent
from agents.coordinator import MAX_AUTO_LOAD_INCREASE_PCT, ActionKind, Proposal, Ruling, decide
from agents.llm import LLMBackend
from agents.monitor import Assessment, PlayerHistory, assess
from agents.rules import DevGoal
from analytics.flags import FlagKind
from domain.enums import SessionType
from planner.model import plan_week
from planner.schema import PlanDay, PlannerInput, PlanResult

# Protective plan for a safety flag when no staff member can take over (self-guided players).
PROTECT_DAYS = 2
PAIN_RPE_CEILING = 0  # rest, and no match minutes
EASY_RPE_CEILING = 3  # recovery at most (red mood, missed check-ins)


@dataclass
class PlanDiff:
    changed_days: list[int]
    swapped_days: list[int]
    match_minutes_days: list[int]
    max_rpe_delta: int
    old_load: int
    new_load: int

    @property
    def load_change_pct(self) -> float:
        if self.old_load == 0:
            return 0.0
        return 100 * (self.new_load - self.old_load) / self.old_load

    @property
    def is_empty(self) -> bool:
        return not self.changed_days


def diff(current: list[PlanDay], proposed: list[PlanDay]) -> PlanDiff:
    cur = {d.date: d for d in current}
    changed, swapped, minutes_cut, max_delta = [], [], [], 0
    old = new = 0
    for p in proposed:
        c = cur.get(p.date)
        if c is None:
            continue
        old += c.load
        new += p.load
        if c.kind != p.kind:
            swapped.append(p.day)
            changed.append(p.day)
        elif p.kind == SessionType.MATCH and p.minutes < c.minutes:
            minutes_cut.append(p.day)
            changed.append(p.day)
        elif c.rpe != p.rpe:
            changed.append(p.day)
            max_delta = max(max_delta, abs(c.rpe - p.rpe))
    return PlanDiff(changed, swapped, minutes_cut, max_delta, old, new)


def to_proposal(player_id: str, d: PlanDiff, reason: str) -> Proposal:
    """The most restrictive action the change amounts to."""
    if d.swapped_days:
        return Proposal(player_id, ActionKind.SESSION_SWAP, reason=reason)
    if d.match_minutes_days:
        return Proposal(player_id, ActionKind.MATCH_MINUTES, reason=reason)
    if d.load_change_pct < 0:
        cut = -d.load_change_pct
        if cut > 20:
            return Proposal(player_id, ActionKind.LOAD_CUT, load_cut_pct=cut, reason=reason)
    elif d.load_change_pct > MAX_AUTO_LOAD_INCREASE_PCT:
        # +1 RPE on every day is "within +/-1 RPE" but can add a lot of load: the coach decides.
        return Proposal(player_id, ActionKind.LOAD_INCREASE, reason=reason)
    return Proposal(player_id, ActionKind.INTENSITY_CHANGE, rpe_delta=d.max_rpe_delta, reason=reason)


@dataclass
class CycleResult:
    assessment: Assessment
    outcome: planner_agent.PlannerOutcome | None
    diff: PlanDiff | None
    proposal: Proposal | None
    ruling: Ruling | None
    escalate: bool
    notes: list[str] = field(default_factory=list)


def run_cycle(
    history: PlayerHistory,
    planner_input: PlannerInput,
    goals: list[DevGoal],
    current_plan: list[PlanDay] | None,
    llm: LLMBackend | None,
) -> CycleResult:
    a = assess(history)
    if a.safety_flags:
        # Escalate to the named staff member; the agents take no action for this player.
        ruling = decide(Proposal(history.player_id, ActionKind.REMINDER), a.flags)
        return CycleResult(a, None, None, None, ruling, escalate=True, notes=[f.detail for f in a.safety_flags])

    inp = planner_input.model_copy(
        update={
            "acwr": a.acwr,
            "chronic_daily_load": a.chronic_daily_load or planner_input.chronic_daily_load,
            "acute_daily_load": a.acute_daily_load if a.chronic_daily_load else None,
            "in_phv_window": planner_input.in_phv_window or bool(a.growth and a.growth.in_phv_window),
        }
    )
    outcome = planner_agent.run(inp, a, goals, llm)
    if current_plan is None:
        return CycleResult(a, outcome, None, None, None, escalate=False, notes=["first plan"])
    d = diff(current_plan, outcome.result.days)
    if d.is_empty:
        return CycleResult(a, outcome, d, None, None, escalate=False, notes=["no change"])
    proposal = to_proposal(history.player_id, d, outcome.reason_coach)
    return CycleResult(a, outcome, d, proposal, decide(proposal, a.flags), escalate=False)


def protective_input(inp: PlannerInput, a: Assessment, current: list[PlanDay] | None) -> PlannerInput:
    """The next PROTECT_DAYS days made easy for a safety flag nobody on the staff can act on.

    Pain: rest and no match minutes. Red mood or missed check-ins: recovery at most. Later
    days keep the current plan's ceiling, so the protective plan never adds load anywhere.
    """
    kinds = {f.kind for f in a.safety_flags}
    pain = FlagKind.PAIN_REPORT in kinds
    ceiling = PAIN_RPE_CEILING if pain else EASY_RPE_CEILING
    base = [d.rpe for d in current] if current else [10] * inp.days
    rpe_ceiling = [min(base[d], ceiling) if d < PROTECT_DAYS else base[d] for d in range(inp.days)]
    caps = dict(inp.match_minutes_cap)
    if pain:
        caps.update({d: 0 for d in inp.match_days if d < PROTECT_DAYS})
    return inp.model_copy(
        update={
            "acwr": a.acwr,
            "chronic_daily_load": a.chronic_daily_load or inp.chronic_daily_load,
            "acute_daily_load": a.acute_daily_load if a.chronic_daily_load else None,
            "rpe_ceiling": rpe_ceiling,
            "match_minutes_cap": caps,
        }
    )


def protective_plan(inp: PlannerInput, a: Assessment, current: list[PlanDay] | None) -> PlanResult:
    """Rule-based (no LLM): solved under the same hard rules, falling back to the safe template."""
    return plan_week(protective_input(inp, a, current))
