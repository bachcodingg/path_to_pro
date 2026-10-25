"""Deterministic risk flags emitted by the Monitor agent (no LLM involved)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum

from analytics.load import ACWR_FLAG_THRESHOLD, MONOTONY_FLAG_THRESHOLD, ewma_acwr, monotony
from analytics.readiness import Band

SHORT_SLEEP_HOURS = 6.0
SHORT_SLEEP_NIGHTS = 3
LOW_HRV_Z = -1.0
MISSED_CHECKINS_ESCALATE = 2  # with red readiness
# With no readiness at all (no check-in, no sleep, no wearable) silence itself is the warning:
# a player who stops answering would otherwise never be flagged.
MISSED_CHECKINS_UNKNOWN_ESCALATE = 3


class FlagKind(str, Enum):
    # Planning flags: go to the Planner
    LOAD_SPIKE = "load_spike"
    HIGH_MONOTONY = "high_monotony"
    SHORT_SLEEP = "short_sleep"
    LOW_HRV = "low_hrv"
    PHV_WINDOW = "phv_window"
    READINESS_RED = "readiness_red"
    # Safety flags: escalate to named staff, no agent action
    PAIN_REPORT = "pain_report"
    RED_MOOD = "red_mood"
    MISSED_CHECKINS = "missed_checkins"


SAFETY_FLAGS = frozenset({FlagKind.PAIN_REPORT, FlagKind.RED_MOOD, FlagKind.MISSED_CHECKINS})


@dataclass(frozen=True)
class Flag:
    kind: FlagKind
    detail: str
    value: float | None = None

    @property
    def is_safety(self) -> bool:
        return self.kind in SAFETY_FLAGS


@dataclass
class PlayerSnapshot:
    """Everything the Monitor knows about one player on one evening."""

    daily_loads: Sequence[float] = ()  # oldest first, includes today, 0 on rest days
    acwr: float | None = None  # precomputed (e.g. EWMA seeded with pre-season load); else from daily_loads
    recent_sleep_hours: Sequence[float] = ()  # oldest first, includes last night
    hrv_z: float | None = None
    readiness_band: Band | None = None
    in_phv_window: bool = False
    maturity_offset: float | None = None
    pain_reported: bool = False
    mood_red: bool = False
    missed_checkins_in_row: int = 0
    extra: dict = field(default_factory=dict)


def evaluate(s: PlayerSnapshot) -> list[Flag]:
    flags: list[Flag] = []

    acwr = s.acwr if s.acwr is not None else ewma_acwr(s.daily_loads)
    if acwr is not None and acwr > ACWR_FLAG_THRESHOLD:
        flags.append(Flag(FlagKind.LOAD_SPIKE, f"ACWR {acwr:.2f}", acwr))

    if len(s.daily_loads) >= 7:
        m = monotony(s.daily_loads[-7:])
        if m is not None and m > MONOTONY_FLAG_THRESHOLD:
            flags.append(Flag(FlagKind.HIGH_MONOTONY, f"Monotony {m:.1f}", m))

    last = s.recent_sleep_hours[-SHORT_SLEEP_NIGHTS:]
    if len(last) == SHORT_SLEEP_NIGHTS and all(h < SHORT_SLEEP_HOURS for h in last):
        flags.append(
            Flag(FlagKind.SHORT_SLEEP, f"Sleep < {SHORT_SLEEP_HOURS:g} h x {SHORT_SLEEP_NIGHTS}", min(last))
        )

    if s.hrv_z is not None and s.hrv_z <= LOW_HRV_Z:
        flags.append(Flag(FlagKind.LOW_HRV, f"HRV {s.hrv_z:+.1f} SD", s.hrv_z))

    if s.in_phv_window:
        detail = "Growth zone"
        if s.maturity_offset is not None:
            detail += f" ({s.maturity_offset:+.1f} y from PHV)"
        flags.append(Flag(FlagKind.PHV_WINDOW, detail, s.maturity_offset))

    if s.readiness_band == Band.RED:
        flags.append(Flag(FlagKind.READINESS_RED, "Readiness red"))

    if s.pain_reported:
        flags.append(Flag(FlagKind.PAIN_REPORT, "Pain reported"))
    if s.mood_red:
        flags.append(Flag(FlagKind.RED_MOOD, "Red mood check-in"))
    if s.missed_checkins_in_row >= MISSED_CHECKINS_ESCALATE and s.readiness_band == Band.RED:
        flags.append(
            Flag(FlagKind.MISSED_CHECKINS, f"{s.missed_checkins_in_row} missed check-ins with red readiness")
        )
    elif s.missed_checkins_in_row >= MISSED_CHECKINS_UNKNOWN_ESCALATE and s.readiness_band is None:
        flags.append(
            Flag(FlagKind.MISSED_CHECKINS, f"{s.missed_checkins_in_row} missed check-ins and no readiness data")
        )
    return flags
