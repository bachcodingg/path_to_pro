"""Planner agent: turns Monitor flags and development goals into next week's plan.

Pipeline (plan section 4):
  1. flags + IDP goals go to the LLM
  2. LLM returns a ConstraintSet, validated against the schema
  3. invalid: 1 retry with the error, then rule-based default constraints
  4. CP-SAT solves with a 2 s limit
  5. no solution: relax soft constraints, then the safe template
  6. LLM writes a 3-sentence explanation for the player and a 1-line coach reason
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import timedelta

from pydantic import BaseModel, Field

from agents.llm import Call, LLMBackend, complete_with_retry
from agents.monitor import Assessment
from agents.rules import KPI_LABEL, DevGoal, default_constraints, default_explanation
from planner.model import hard_violations, plan_week
from planner.schema import ConstraintSet, PlannerInput, PlanResult

CONSTRAINT_SYSTEM = """\
You are the Planner agent of PathToPro, a training-load assistant for youth football academies \
(players aged 13-18). You do not compute numbers and you cannot change safety rules: a constraint \
solver enforces fixed hard rules (fixtures, a rest day, easy day before matches, growth-spurt \
limits, load caps, exam evenings off). Your job is to turn the monitor's risk flags and the \
player's development goals into soft constraints and weights for the solver.

Guidance:
- Weight 1-10; weight >= 8 means "treat as hard if at all possible".
- Load spike (ACWR > 1.5): lower load_factor (0.7-0.85) and avoid hard back-to-back days.
- Poor sleep, low HRV or red readiness: keep the next 1-2 days at RPE <= 4.
- Growth zone (PHV window): limit strength and plyometric volume; speed work stays short.
- Development goals: ask for the matching sessions (speed for sprint, strength for jump, \
tactical for endurance), usually 2 per week, unless flags say the week must be light.
- Days are numbered 0-6 from the plan's first day. Never constrain match days.
- Keep `why` short and concrete. Do not give medical advice.
"""

EXPLAIN_SYSTEM = """\
You explain a youth football player's training week, for PathToPro. Write for a 13-18 year old: \
plain words, encouraging, no jargon, no medical claims, no predictions about turning pro. \
`player` is exactly 3 short sentences: what changed, why (use the data given), what they can do. \
`coach` is one line under 200 characters with the decisive data and the solver status.
"""


class Explanation(BaseModel):
    player: str = Field(max_length=500)
    coach: str = Field(max_length=300)


@dataclass
class PlannerOutcome:
    result: PlanResult
    constraints: ConstraintSet
    constraint_source: str  # llm | llm_retry | rules
    explanation_player: str
    reason_coach: str
    explanation_source: str
    hard_violations: list[str] = field(default_factory=list)


def _context(inp: PlannerInput, a: Assessment, goals: list[DevGoal]) -> str:
    return json.dumps(
        {
            "plan_start": inp.start.isoformat(),
            "days": {d: (inp.start + timedelta(days=d)).strftime("%a") for d in range(7)},
            "match_days": inp.match_days,
            "exam_days": inp.exam_days,
            "in_phv_window": inp.in_phv_window,
            "acwr": None if a.acwr is None else round(a.acwr, 2),
            "readiness": None if a.readiness is None else {"score": round(a.readiness.score), "band": a.readiness.band},
            "flags": [{"kind": f.kind.value, "detail": f.detail} for f in a.planning_flags],
            "goals": [{"kpi": KPI_LABEL.get(g.kpi, g.kpi), "sessions_per_week": g.sessions_per_week} for g in goals],
        },
        default=str,
    )


def run(
    inp: PlannerInput,
    assessment: Assessment,
    goals: list[DevGoal],
    llm: LLMBackend | None,
) -> PlannerOutcome:
    ctx = _context(inp, assessment, goals)
    cs, source = complete_with_retry(
        llm, Call(agent="planner", system=CONSTRAINT_SYSTEM, user=f"Player context:\n{ctx}", output=ConstraintSet)
    )
    if cs is None:
        cs, source = default_constraints(assessment.planning_flags, goals, inp), "rules"
    result = plan_week(inp, cs)

    summary = json.dumps(
        {
            "flags": [f.detail for f in assessment.planning_flags],
            "data_chips": assessment.chips,
            "goals": [KPI_LABEL.get(g.kpi, g.kpi) for g in goals],
            "week": [{"date": d.date.isoformat(), "session": d.kind.value, "rpe": d.rpe} for d in result.days],
            "solver_status": result.status,
            "weekly_load_au": result.weekly_load,
            "load_cap_au": result.weekly_load_cap,
            "rationale": cs.rationale,
        }
    )
    exp, exp_source = complete_with_retry(
        llm, Call(agent="explainer", system=EXPLAIN_SYSTEM, user=f"Week summary:\n{summary}", output=Explanation)
    )
    if exp is None:
        player, coach = default_explanation(assessment.planning_flags, result, goals)
        exp_source = "rules"
    else:
        player, coach = exp.player, exp.coach
    return PlannerOutcome(
        result=result,
        constraints=cs,
        constraint_source=source,
        explanation_player=player,
        reason_coach=coach,
        explanation_source=exp_source,
        hard_violations=hard_violations(result, inp),
    )
