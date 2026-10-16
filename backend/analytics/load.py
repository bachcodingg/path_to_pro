"""Training load metrics: session RPE load, EWMA ACWR, monotony and strain."""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass

ACUTE_DAYS = 7
CHRONIC_DAYS = 28
ACWR_FLAG_THRESHOLD = 1.5
MONOTONY_FLAG_THRESHOLD = 2.0


def session_load(rpe: float, minutes: float) -> float:
    """Session RPE load in arbitrary units (AU): RPE x duration in minutes.

    >>> session_load(7, 90)
    630.0
    """
    if not 0 <= rpe <= 10:
        raise ValueError(f"RPE must be in 0-10, got {rpe}")
    if minutes < 0:
        raise ValueError(f"minutes must be >= 0, got {minutes}")
    return float(rpe * minutes)


def ewma_lambda(days: int) -> float:
    # Williams et al. (2017): lambda = 2 / (N + 1)
    return 2.0 / (days + 1)


@dataclass(frozen=True)
class ACWRPoint:
    acute: float
    chronic: float

    @property
    def ratio(self) -> float | None:
        if self.chronic <= 0:
            return None
        return self.acute / self.chronic


def ewma_acwr_series(
    daily_loads: Sequence[float],
    acute_days: int = ACUTE_DAYS,
    chronic_days: int = CHRONIC_DAYS,
    initial: float | None = None,
) -> list[ACWRPoint]:
    """Exponentially weighted acute and chronic load for every day.

    `daily_loads` is one total per calendar day, oldest first, with 0 for rest days.
    Both averages start at `initial` (e.g. a typical pre-season daily load) if given,
    otherwise they are seeded with the first day's load.
    """
    if not daily_loads:
        return []
    la, lc = ewma_lambda(acute_days), ewma_lambda(chronic_days)
    if initial is None:
        acute = chronic = float(daily_loads[0])
        rest = daily_loads[1:]
        out = [ACWRPoint(acute, chronic)]
    else:
        acute = chronic = float(initial)
        rest = daily_loads
        out = []
    for load in rest:
        acute = la * load + (1 - la) * acute
        chronic = lc * load + (1 - lc) * chronic
        out.append(ACWRPoint(acute, chronic))
    return out


def ewma_acwr(daily_loads: Sequence[float], min_history: int = CHRONIC_DAYS) -> float | None:
    """ACWR for the last day, or None until `min_history` days of data exist.

    ACWR is a weak injury predictor in the literature; it is used as one flag
    among several, never as a prediction.
    """
    if len(daily_loads) < min_history:
        return None
    return ewma_acwr_series(daily_loads)[-1].ratio


def monotony(week_loads: Sequence[float]) -> float | None:
    """Foster monotony: mean daily load / SD of daily load over 7 days.

    Returns None when the SD is 0 (identical loads every day), where monotony is undefined.
    """
    if len(week_loads) != 7:
        raise ValueError(f"monotony needs 7 daily loads, got {len(week_loads)}")
    sd = statistics.pstdev(week_loads)
    if sd == 0:
        return None
    return statistics.fmean(week_loads) / sd


def strain(week_loads: Sequence[float]) -> float | None:
    """Foster strain: weekly load x monotony."""
    m = monotony(week_loads)
    if m is None:
        return None
    return sum(week_loads) * m
