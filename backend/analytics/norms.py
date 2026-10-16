"""Development percentiles: test results vs age-group (or bio-banded) norms.

The norm values in config/norms.yaml are PLACEHOLDERS for the demo and must be
replaced with published academy norms before any real use.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import yaml

from analytics.maturation import MaturityStatus

DEFAULT_NORMS = Path(__file__).resolve().parent.parent / "config" / "norms.yaml"


@dataclass(frozen=True)
class Norm:
    mean: float
    sd: float
    lower_is_better: bool


def _normal_cdf(z: float) -> float:
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def percentile(value: float, norm: Norm) -> float:
    """Percentile (0-100) of `value` assuming normally distributed norms.

    Higher percentile always means better, so a fast sprint time scores high.
    """
    z = (value - norm.mean) / norm.sd
    if norm.lower_is_better:
        z = -z
    return _normal_cdf(z) * 100


def age_group(age_years: float) -> str:
    """U13 ... U19 by completed years (a 16.4-year-old plays U17)."""
    return f"U{math.floor(age_years) + 1}"


class NormTable:
    def __init__(self, data: dict):
        self._data = data

    @classmethod
    def load(cls, path: Path = DEFAULT_NORMS) -> NormTable:
        return cls(yaml.safe_load(path.read_text(encoding="utf-8")))

    def tests(self) -> list[str]:
        return list(self._data["tests"])

    def norm(self, test: str, group: str) -> Norm:
        t = self._data["tests"][test]
        g = t["groups"][group]
        return Norm(mean=g["mean"], sd=g["sd"], lower_is_better=t["lower_is_better"])

    def age_percentile(self, test: str, value: float, age_years: float) -> float:
        # Outside the U13-U19 table, compare with the nearest group.
        return percentile(value, self.norm(test, age_group(min(max(age_years, 12.0), 18.99))))

    def bio_banded_percentile(self, test: str, value: float, status: MaturityStatus) -> float:
        """Compare against players of the same maturity, so late maturers aren't
        judged against early maturers."""
        return percentile(value, self.norm(test, status.value))
