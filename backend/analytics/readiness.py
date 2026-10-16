"""Daily readiness score from HRV, Hooper index and sleep (plan section 3).

R = 0.40 * S_hrv + 0.35 * S_hooper + 0.25 * S_sleep, each component on 0-100.
The weights are team defaults, not from a study, and live in config/readiness.yaml.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import yaml

HRV_BASELINE_DAYS = 7
DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "readiness.yaml"


class Band(str, Enum):
    GREEN = "green"
    AMBER = "amber"
    RED = "red"


@dataclass(frozen=True)
class ReadinessConfig:
    weights: Mapping[str, float] = field(
        default_factory=lambda: {"hrv": 0.40, "hooper": 0.35, "sleep": 0.25}
    )
    green_min: float = 70.0
    amber_min: float = 50.0
    sleep_target_hours: float = 9.0

    @classmethod
    def load(cls, path: Path = DEFAULT_CONFIG) -> ReadinessConfig:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return cls(
            weights=data["weights"],
            green_min=data["bands"]["green_min"],
            amber_min=data["bands"]["amber_min"],
            sleep_target_hours=data["sleep_target_hours"],
        )


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def hrv_z(today_ln_rmssd: float, baseline: Sequence[float]) -> float | None:
    """z-score of today's lnRMSSD against the previous 7 days.

    Returns None until 7 days of baseline exist. Only the last 7 values are used.
    """
    if len(baseline) < HRV_BASELINE_DAYS:
        return None
    window = baseline[-HRV_BASELINE_DAYS:]
    sd = statistics.stdev(window)
    if sd == 0:
        return 0.0
    return (today_ln_rmssd - statistics.fmean(window)) / sd


def hrv_score(z: float) -> float:
    return _clamp(50 + 25 * z)


def hooper_score(sleep_quality: int, fatigue: int, stress: int, soreness: int) -> float:
    """Each item 1 (very good) to 7 (very bad); total H in 4-28. Score = (28 - H) / 24 * 100."""
    items = (sleep_quality, fatigue, stress, soreness)
    if any(not 1 <= i <= 7 for i in items):
        raise ValueError(f"Hooper items must be 1-7, got {items}")
    return (28 - sum(items)) / 24 * 100


def sleep_score(hours: float, target_hours: float = 9.0) -> float:
    """min(hours / 9, 1) x 100 (teen guideline is 8-10 h)."""
    if hours < 0:
        raise ValueError("sleep hours must be >= 0")
    return min(hours / target_hours, 1.0) * 100


@dataclass(frozen=True)
class Readiness:
    score: float
    band: Band
    components: Mapping[str, float]
    weights_used: Mapping[str, float]


def band_for(score: float, config: ReadinessConfig) -> Band:
    if score >= config.green_min:
        return Band.GREEN
    if score >= config.amber_min:
        return Band.AMBER
    return Band.RED


def combine(
    components: Mapping[str, float | None],
    config: ReadinessConfig | None = None,
) -> Readiness | None:
    """Weighted readiness. Missing (None) inputs are dropped and the rest rescaled.

    Returns None if no input is available at all.
    """
    config = config or ReadinessConfig()
    present = {k: v for k, v in components.items() if v is not None and not math.isnan(v)}
    total_w = sum(config.weights[k] for k in present)
    if not present or total_w == 0:
        return None
    weights = {k: config.weights[k] / total_w for k in present}
    score = sum(weights[k] * present[k] for k in present)
    return Readiness(score=score, band=band_for(score, config), components=present, weights_used=weights)


def readiness(
    *,
    hooper: tuple[int, int, int, int] | None,
    sleep_hours: float | None,
    ln_rmssd: float | None = None,
    hrv_baseline: Sequence[float] = (),
    config: ReadinessConfig | None = None,
) -> Readiness | None:
    """Convenience wrapper from raw inputs to a Readiness result."""
    config = config or ReadinessConfig()
    s_hrv = None
    if ln_rmssd is not None:
        z = hrv_z(ln_rmssd, hrv_baseline)
        s_hrv = None if z is None else hrv_score(z)
    return combine(
        {
            "hrv": s_hrv,
            "hooper": None if hooper is None else hooper_score(*hooper),
            "sleep": None if sleep_hours is None else sleep_score(sleep_hours, config.sleep_target_hours),
        },
        config,
    )
