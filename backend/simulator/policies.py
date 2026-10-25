"""Planning policies the simulator can run a season under.

`BaselinePolicy` is the evaluation baseline from plan section 9: the same four
sessions every week with no adjustment. The agent planner will implement the
same `Policy` protocol so both can be compared on identical seasons.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Protocol

import numpy as np

from domain.enums import SessionType

if TYPE_CHECKING:
    from simulator.season import PlayerState


@dataclass(frozen=True)
class PlannedSession:
    kind: SessionType
    rpe: float
    minutes: float


@dataclass(frozen=True)
class WeekContext:
    week: int
    dates: tuple[date, ...]  # Monday..Sunday
    match_days: frozenset[int]  # weekday indices, 0 = Monday
    evening_match_days: frozenset[int]
    exam_days: frozenset[int]
    test_day: int | None


# weekday index -> session; missing weekday = rest. Matches are fixed by the
# simulator, so a policy never schedules or moves them.
WeekPlan = dict[int, PlannedSession]


class Policy(Protocol):
    name: str

    def plan_week(self, player: PlayerState, ctx: WeekContext, rng: np.random.Generator) -> WeekPlan: ...


BASELINE_TEMPLATE: dict[int, SessionType] = {
    0: SessionType.TECHNICAL,
    1: SessionType.STRENGTH,
    2: SessionType.TACTICAL,
    3: SessionType.SPEED,
}


class BaselinePolicy:
    """Fixed weekly template: Mon technical, Tue strength, Wed tactical, Thu speed."""

    name = "baseline"

    def __init__(self, rpe_mean: float = 5.5, rpe_sd: float = 1.5, minutes: tuple[int, int] = (60, 100)):
        self.rpe_mean, self.rpe_sd, self.minutes = rpe_mean, rpe_sd, minutes

    def plan_week(self, player: PlayerState, ctx: WeekContext, rng: np.random.Generator) -> WeekPlan:
        plan: WeekPlan = {}
        for day, kind in BASELINE_TEMPLATE.items():
            if day in ctx.match_days:
                continue
            rpe = float(np.clip(rng.normal(self.rpe_mean, self.rpe_sd), 1, 10))
            minutes = float(rng.integers(self.minutes[0], self.minutes[1] + 1))
            plan[day] = PlannedSession(kind, rpe, minutes)
        return plan


class HeuristicPolicy:
    """A sensible coach with a spreadsheet: the fixed template plus the rules of thumb the
    agents' hard rules encode, written as plain if-statements (no solver, no LLM).

    This is the fair baseline. `BaselinePolicy` knows nothing about exams or fixtures, so
    beating it mostly shows that the rules exist; beating this shows what the planner adds.

    Weekly (Monday): fixed planned RPE per session type; no session on exam days; the day
    before a match becomes recovery (RPE 3); the day after a match is rest; in the measured
    growth window speed work stays at RPE <= 6; observed EWMA ACWR > 1.5 cuts session
    minutes by 20%, > 1.3 by 10%.
    Daily (morning check-in): pain, a red mood or red readiness turns today's session into
    recovery.
    """

    name = "heuristic"
    RPE = {SessionType.TECHNICAL: 5.0, SessionType.STRENGTH: 6.0, SessionType.TACTICAL: 6.0, SessionType.SPEED: 6.0}
    MINUTES = 80.0  # the baseline's mean session length (60-100)
    RECOVERY = PlannedSession(SessionType.RECOVERY, 3.0, 40.0)

    def plan_week(self, player: PlayerState, ctx: WeekContext, rng: np.random.Generator) -> WeekPlan:
        from analytics.load import ewma_acwr_series
        from analytics.maturation import growth_status
        from simulator.season import PRESEASON_DAILY_LOAD

        series = ewma_acwr_series(player.daily_loads, initial=PRESEASON_DAILY_LOAD)
        acwr = series[-1].ratio if series else 1.0
        scale = 0.8 if acwr is not None and acwr > 1.5 else 0.9 if acwr is not None and acwr > 1.3 else 1.0
        m = player.latest_measure
        in_phv = bool(
            m and growth_status(m["age"], m["height_cm"], m["sitting_height_cm"], m["weight_kg"]).in_phv_window
        )
        plan: WeekPlan = {}
        for day, kind in BASELINE_TEMPLATE.items():
            if day in ctx.match_days or day in ctx.exam_days or day - 1 in ctx.match_days:
                continue
            if day + 1 in ctx.match_days:
                plan[day] = self.RECOVERY
                continue
            rpe = self.RPE[kind]
            if in_phv and kind == SessionType.SPEED:
                rpe = min(rpe, 6.0)
            plan[day] = PlannedSession(kind, rpe, self.MINUTES * scale)
        return plan

    def adjust_day(self, player: PlayerState, ctx: WeekContext, wd: int, plan: WeekPlan, rng) -> WeekPlan:
        chk = player.today_checkin or {}
        score = player.readiness_scores[-1] if player.readiness_scores else None
        if wd in plan and (chk.get("pain") or chk.get("mood_red") or (score is not None and score < 50)):
            plan = dict(plan)
            plan[wd] = self.RECOVERY
        return plan
