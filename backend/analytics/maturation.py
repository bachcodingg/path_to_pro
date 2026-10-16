"""Biological maturation: Mirwald (2002) maturity offset and PHV window."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# Years from PHV counted as "in the growth window". Clubs can override this.
PHV_WINDOW = (-1.0, 1.0)


class Sex(str, Enum):
    MALE = "male"
    FEMALE = "female"


class MaturityStatus(str, Enum):
    PRE_PHV = "pre_phv"
    CIRCA_PHV = "circa_phv"
    POST_PHV = "post_phv"


def maturity_offset(
    age_years: float,
    height_cm: float,
    sitting_height_cm: float,
    weight_kg: float,
    sex: Sex = Sex.MALE,
) -> float:
    """Years from peak height velocity (negative = before PHV).

    Mirwald RL et al. (2002), Med Sci Sports Exerc 34(4):689-694.
    Standard error is about 0.5 years, so treat the result as an estimate.
    """
    if not (0 < sitting_height_cm < height_cm):
        raise ValueError("sitting height must be positive and less than standing height")
    leg = height_cm - sitting_height_cm
    ratio = weight_kg / height_cm * 100
    if sex == Sex.MALE:
        return (
            -9.236
            + 0.0002708 * leg * sitting_height_cm
            - 0.001663 * age_years * leg
            + 0.007216 * age_years * sitting_height_cm
            + 0.02292 * ratio
        )
    return (
        -9.376
        + 0.0001882 * leg * sitting_height_cm
        + 0.0022 * age_years * leg
        + 0.005841 * age_years * sitting_height_cm
        - 0.002658 * age_years * weight_kg
        + 0.07693 * ratio
    )


@dataclass(frozen=True)
class GrowthStatus:
    maturity_offset: float
    age_at_phv: float
    status: MaturityStatus

    @property
    def in_phv_window(self) -> bool:
        return self.status == MaturityStatus.CIRCA_PHV


def growth_status(
    age_years: float,
    height_cm: float,
    sitting_height_cm: float,
    weight_kg: float,
    sex: Sex = Sex.MALE,
    window: tuple[float, float] = PHV_WINDOW,
) -> GrowthStatus:
    mo = maturity_offset(age_years, height_cm, sitting_height_cm, weight_kg, sex)
    lo, hi = window
    if mo < lo:
        status = MaturityStatus.PRE_PHV
    elif mo > hi:
        status = MaturityStatus.POST_PHV
    else:
        status = MaturityStatus.CIRCA_PHV
    return GrowthStatus(maturity_offset=mo, age_at_phv=age_years - mo, status=status)
