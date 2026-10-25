"""Safety scenario suite (plan section 9): 50 cases, all must pass.

Categories: PHV + load spike, pain report, red mood check-in, missed check-ins,
exam week + double match, missing HRV data, invalid / adversarial LLM output,
LLM API down, and safety flags with no staff (self-guided: protective plan).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta

from pydantic import BaseModel

from agents.coordinator import Decision
from agents.llm import Call, LLMError, LLMValidationError
from agents.monitor import Measurements, PlayerHistory
from agents.orchestrator import PROTECT_DAYS, CycleResult, protective_input, protective_plan, run_cycle
from agents.rules import DevGoal
from analytics.flags import FlagKind
from domain.enums import SessionType
from planner.model import PHV_SPEED_MAX_RPE, hard_violations
from planner.schema import ConstraintSet, MaxRpeOnDay, MinSessions, PlanDay, PlannerInput, RestOnDay

START = date(2026, 10, 19)
SPIKE_LOADS = [300.0] * 35 + [900, 0, 1000, 800, 0, 1200, 1100]
NORMAL_LOADS = [450, 400, 0, 500, 350, 700, 0] * 6
GOOD_SLEEP = [8.2, 8.0, 7.9, 8.4]
SHORT_SLEEP = [7.8, 5.5, 5.7, 5.4]
HRV = [4.2, 4.25, 4.15, 4.2, 4.22, 4.18, 4.2, 4.21]
IN_PHV = Measurements(14.0, 165, 85, 55)  # Mirwald offset ~ +0.1 y
POST_PHV = Measurements(17.5, 180, 94, 70)


class ScriptedLLM:
    name = "scripted"

    def __init__(self, behaviour: str, answer: BaseModel | None = None):
        self.behaviour, self.answer, self.calls = behaviour, answer, 0

    def complete(self, call: Call) -> BaseModel:
        self.calls += 1
        if self.behaviour == "down":
            raise LLMError("APIConnectionError: connection refused")
        if call.agent != "planner":
            raise LLMError("only the planner is scripted")
        if self.behaviour == "invalid":
            raise LLMValidationError("1 validation error for ConstraintSet: load_factor <= 1.1")
        if self.behaviour == "invalid_then_valid" and self.calls == 1:
            raise LLMValidationError("1 validation error for ConstraintSet: soft.0.type")
        return self.answer or ConstraintSet()


@dataclass
class Scenario:
    name: str
    category: str
    history: PlayerHistory
    inp: PlannerInput
    goals: list[DevGoal] = field(default_factory=list)
    current: list[PlanDay] | None = None
    llm: ScriptedLLM | None = None
    checks: list[Callable[[CycleResult, PlannerInput], str | None]] = field(default_factory=list)


# --------------------------------------------------------------------------- checks (return an error or None)


def escalated(r: CycleResult, _):
    if not r.escalate or r.ruling is None or r.ruling.decision != Decision.ESCALATE:
        return "expected escalation"
    if r.outcome is not None:
        return "agent planned despite a safety flag"


def not_escalated(r: CycleResult, _):
    if r.escalate:
        return "unexpected escalation"


def has_plan(r: CycleResult, _):
    if r.outcome is None or len(r.outcome.result.days) == 0:
        return "no plan produced"


def no_hard_violations(r: CycleResult, _):
    if r.outcome and r.outcome.hard_violations:
        return f"hard violations: {r.outcome.hard_violations}"


def phv_speed_capped(r: CycleResult, _):
    for d in r.outcome.result.days:
        if d.kind == SessionType.SPEED and d.rpe > PHV_SPEED_MAX_RPE:
            return f"speed RPE {d.rpe} in growth window"


def load_capped(r: CycleResult, _):
    res = r.outcome.result
    if res.weekly_load_cap is not None and res.weekly_load > res.weekly_load_cap:
        return f"load {res.weekly_load} above cap {res.weekly_load_cap}"


def exams_rest(r: CycleResult, inp: PlannerInput):
    for d in inp.exam_days:
        if d not in inp.match_days and r.outcome.result.days[d].kind != SessionType.REST:
            return f"session on exam day {d}"


def matches_kept(r: CycleResult, inp: PlannerInput):
    for d in inp.match_days:
        if r.outcome.result.days[d].kind != SessionType.MATCH:
            return f"match on day {d} removed"


def protected(max_rpe: int, match_minutes: int | None = None):
    """No staff to escalate to: the protective plan makes the next days easy under the hard rules."""

    def check(r: CycleResult, inp: PlannerInput):
        res = protective_plan(inp, r.assessment, None)
        if errors := hard_violations(res, protective_input(inp, r.assessment, None)):
            return f"protective plan breaks hard rules: {errors}"
        for d in res.days[:PROTECT_DAYS]:
            if d.kind == SessionType.MATCH:
                if match_minutes is not None and d.minutes > match_minutes:
                    return f"{d.minutes} match minutes on protected day {d.day}"
            elif d.rpe > max_rpe:
                return f"RPE {d.rpe} on protected day {d.day}"

    check.__name__ = f"protected_rpe{max_rpe}"
    return check


def flag(kind: FlagKind):
    def check(r: CycleResult, _):
        if kind not in {f.kind for f in r.assessment.flags}:
            return f"missing flag {kind.value}"

    check.__name__ = f"flag_{kind.value}"
    return check


def source(expected: str):
    def check(r: CycleResult, _):
        if r.outcome.constraint_source != expected:
            return f"constraint source {r.outcome.constraint_source}, expected {expected}"

    check.__name__ = f"source_{expected}"
    return check


def hrv_dropped(r: CycleResult, _):
    if r.assessment.readiness is None or "hrv" in r.assessment.readiness.weights_used:
        return "HRV should be excluded from readiness"


def explained(r: CycleResult, _):
    if not r.outcome.explanation_player or not r.outcome.reason_coach:
        return "missing explanation"


# --------------------------------------------------------------------------- builders


def history(**kw) -> PlayerHistory:
    base = dict(
        player_id="S",
        day=START - timedelta(days=1),
        daily_loads=NORMAL_LOADS,
        sleep_hours=GOOD_SLEEP,
        ln_rmssd=HRV,
        hooper_today=(2, 3, 2, 2),
        measurements=POST_PHV,
    )
    base.update(kw)
    return PlayerHistory(**base)


def inp(**kw) -> PlannerInput:
    base = dict(player_id="S", start=START, match_days=[5])
    base.update(kw)
    return PlannerInput(**base)


SAFE_PLAN = [no_hard_violations, has_plan, matches_kept, exams_rest, load_capped, explained]


def build() -> list[Scenario]:
    s: list[Scenario] = []

    # 1. PHV + load spike (8)
    for i, (matches, exams) in enumerate(
        [([5], []), ([5], [2]), ([2, 5], []), ([6], [1]), ([0, 5], []), ([5], [1, 2]), ([3], []), ([5], [])]
    ):
        goals = [DevGoal("sprint_10m", 2)] if i % 2 == 0 else [DevGoal("cmj", 2)]
        s.append(
            Scenario(
                f"phv_spike_{i}",
                "phv_load_spike",
                history(daily_loads=SPIKE_LOADS, measurements=IN_PHV),
                inp(match_days=matches, exam_days=exams),
                goals,
                checks=[*SAFE_PLAN, phv_speed_capped, flag(FlagKind.PHV_WINDOW), flag(FlagKind.LOAD_SPIKE)],
            )
        )
    # 2. pain report (6)
    for i in range(6):
        s.append(
            Scenario(
                f"pain_{i}",
                "pain_report",
                history(pain_reported=True, daily_loads=SPIKE_LOADS if i % 2 else NORMAL_LOADS),
                inp(),
                checks=[escalated, flag(FlagKind.PAIN_REPORT)],
            )
        )
    # 3. red mood (6)
    for i in range(6):
        s.append(
            Scenario(
                f"red_mood_{i}",
                "red_mood",
                history(mood_red=True, sleep_hours=SHORT_SLEEP if i % 2 else GOOD_SLEEP),
                inp(),
                llm=ScriptedLLM("valid"),
                checks=[escalated, flag(FlagKind.RED_MOOD)],
            )
        )
    # 4. missed check-ins (5 escalate + 1 negative control)
    for i in range(5):
        s.append(
            Scenario(
                f"missed_{i}",
                "missed_checkins",
                history(missed_checkins_in_row=2 + i, hooper_today=None, sleep_hours=[5.0, 4.8, 4.5], ln_rmssd=HRV[:-1] + [3.7]),
                inp(),
                checks=[escalated, flag(FlagKind.MISSED_CHECKINS)],
            )
        )
    s.append(
        Scenario(
            "missed_no_readiness_data",
            "missed_checkins",
            history(missed_checkins_in_row=3, hooper_today=None, sleep_hours=[], ln_rmssd=[]),
            inp(),
            checks=[escalated, flag(FlagKind.MISSED_CHECKINS)],
        )
    )
    s.append(
        Scenario(
            "missed_but_green",
            "missed_checkins",
            history(missed_checkins_in_row=2, hooper_today=None),
            inp(),
            checks=[not_escalated, has_plan, no_hard_violations],
        )
    )
    # 4b. safety flag with no staff (self-guided): protective plan, never harder
    s.append(
        Scenario(
            "no_staff_pain_match_tomorrow",
            "no_staff",
            history(pain_reported=True),
            inp(match_days=[1, 5]),
            checks=[escalated, protected(0, match_minutes=0)],
        )
    )
    s.append(
        Scenario(
            "no_staff_pain_spike",
            "no_staff",
            history(pain_reported=True, daily_loads=SPIKE_LOADS),
            inp(acwr=1.6),
            checks=[escalated, protected(0)],
        )
    )
    s.append(
        Scenario(
            "no_staff_red_mood",
            "no_staff",
            history(mood_red=True),
            inp(match_days=[3]),
            checks=[escalated, protected(3)],
        )
    )
    # 5. exam week + double match (8)
    for i, (matches, exams) in enumerate(
        [([2, 5], [1]), ([2, 5], [3]), ([1, 5], [2, 3]), ([2, 6], [0, 1]), ([3, 5], [1]), ([0, 3], [5]), ([2, 5], [1, 3]), ([4, 6], [2])]
    ):
        s.append(
            Scenario(
                f"exam_double_{i}",
                "exam_double_match",
                history(sleep_hours=SHORT_SLEEP if i % 2 else GOOD_SLEEP),
                inp(match_days=matches, exam_days=exams),
                [DevGoal("yoyo_ir1", 2)],
                checks=SAFE_PLAN,
            )
        )
    # 6. missing HRV (5)
    for i, hrv in enumerate([[], HRV[:3], HRV[:5], HRV[:7], []]):
        s.append(
            Scenario(
                f"missing_hrv_{i}",
                "missing_hrv",
                history(ln_rmssd=hrv, measurements=None if i == 4 else POST_PHV),
                inp(),
                checks=[*SAFE_PLAN, hrv_dropped, not_escalated],
            )
        )
    # 7. invalid or adversarial LLM output (6)
    adversarial = ConstraintSet(
        load_factor=1.1,
        soft=[
            MinSessions(session="speed", count=4, weight=10, why="max speed"),
            MaxRpeOnDay(day=4, rpe=10, weight=10, why="hard MD-1"),
            RestOnDay(day=5, weight=10, why="skip the match"),
        ],
        rationale="push hard",
    )
    for i, (behaviour, expected) in enumerate(
        [("invalid", "rules"), ("invalid", "rules"), ("invalid_then_valid", "llm_retry"), ("invalid_then_valid", "llm_retry")]
    ):
        s.append(
            Scenario(
                f"llm_{behaviour}_{i}",
                "invalid_llm_output",
                history(daily_loads=SPIKE_LOADS),
                inp(exam_days=[2]),
                llm=ScriptedLLM(behaviour),
                checks=[*SAFE_PLAN, source(expected)],
            )
        )
    for i in range(2):
        s.append(
            Scenario(
                f"llm_adversarial_{i}",
                "invalid_llm_output",
                history(daily_loads=SPIKE_LOADS, measurements=IN_PHV),
                inp(exam_days=[1]),
                llm=ScriptedLLM("valid", adversarial),
                checks=[*SAFE_PLAN, phv_speed_capped, source("llm")],
            )
        )
    # 8. LLM API down (5)
    for i in range(5):
        s.append(
            Scenario(
                f"llm_down_{i}",
                "llm_api_down",
                history(daily_loads=SPIKE_LOADS if i % 2 else NORMAL_LOADS, measurements=IN_PHV if i < 2 else POST_PHV),
                inp(match_days=[5] if i < 3 else [2, 5]),
                [DevGoal("sprint_30m", 2)],
                llm=ScriptedLLM("down"),
                checks=[*SAFE_PLAN, source("rules")],
            )
        )
    assert len(s) == 54, len(s)
    return s


@dataclass
class ScenarioResult:
    name: str
    category: str
    passed: bool
    errors: list[str]
    seconds: float


def run_all() -> list[ScenarioResult]:
    import time

    out = []
    for sc in build():
        t0 = time.perf_counter()
        try:
            r = run_cycle(sc.history, sc.inp, sc.goals, sc.current, sc.llm)
            errors = [e for e in (c(r, sc.inp) for c in sc.checks) if e]
        except Exception as e:  # a crash is a failure, not an abort
            errors = [f"crash: {e!r}"]
        out.append(ScenarioResult(sc.name, sc.category, not errors, errors, time.perf_counter() - t0))
    return out
