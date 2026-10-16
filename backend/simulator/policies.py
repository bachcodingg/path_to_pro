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
