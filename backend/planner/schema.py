"""Planner inputs and the constraint set the LLM proposes.

The LLM only ever fills a `ConstraintSet`. It is validated against this schema;
the hard safety rules are NOT in it and cannot be switched off by the LLM.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from domain.enums import SessionType

Weekday = Annotated[int, Field(ge=0, le=6, description="0 = first day of the plan")]
TRAINABLE = [t for t in SessionType if t not in (SessionType.MATCH,)]

# Minutes per session type, and allowed RPE range. Rest is 0 minutes at RPE 0.
SESSION_MINUTES: dict[SessionType, int] = {
    SessionType.REST: 0,
    SessionType.RECOVERY: 40,
    SessionType.TECHNICAL: 75,
    SessionType.TACTICAL: 80,
    SessionType.STRENGTH: 60,
    SessionType.SPEED: 50,
    SessionType.MATCH: 90,
}
RPE_RANGE: dict[SessionType, tuple[int, int]] = {
    SessionType.REST: (0, 0),
    SessionType.RECOVERY: (2, 3),
    SessionType.TECHNICAL: (3, 6),
    SessionType.TACTICAL: (4, 7),
    SessionType.STRENGTH: (4, 8),
    SessionType.SPEED: (5, 8),  # below RPE 5 a sprint block doesn't train speed
    SessionType.MATCH: (6, 10),
}
MATCH_RPE = 8


class PlannerInput(BaseModel):
    """What the planner knows about one player for the next 7 days."""

    player_id: str
    start: date
    match_days: list[Weekday] = []
    exam_days: list[Weekday] = []  # no session on exam evenings
    in_phv_window: bool = False
    acwr: float | None = None
    chronic_daily_load: float = 300.0  # EWMA chronic load, AU per day
    preferred_days: list[Weekday] = []
    min_training_sessions: int = 3
    days: int = Field(default=7, ge=1, le=7, description="planning horizon; < 7 for a mid-week re-plan")
    club_weekly_load: float = 2350.0  # the club's planned weekly load in AU (= the fixed template's volume)
    max_ramp: float = 1.3  # plan at most chronic load x 1.3, the top of the usual 0.8-1.3 ACWR range
    target_load_factor: float = 1.0
    # Re-plans may only make days easier: per-day RPE ceiling from the current plan (0 = stays rest).
    rpe_ceiling: list[int] | None = None

    def target_load(self, llm_factor: float = 1.0) -> int:
        planned = self.club_weekly_load * self.days / 7
        safe = self.chronic_daily_load * self.days * self.max_ramp
        return round(min(planned, safe) * self.target_load_factor * llm_factor)


# --------------------------------------------------------------------------- LLM constraint set


class _Soft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    weight: int = Field(ge=1, le=10, description="1 = nice to have, 10 = very important")
    why: str = Field(max_length=160, description="One short reason, shown in the audit log")


class MinSessions(_Soft):
    type: Literal["min_sessions"] = "min_sessions"
    session: SessionType
    count: int = Field(ge=1, le=4)


class MaxSessions(_Soft):
    type: Literal["max_sessions"] = "max_sessions"
    session: SessionType
    count: int = Field(ge=0, le=7)


class MaxRpeOnDay(_Soft):
    type: Literal["max_rpe_on_day"] = "max_rpe_on_day"
    day: Weekday
    rpe: int = Field(ge=0, le=10)


class RestOnDay(_Soft):
    type: Literal["rest_on_day"] = "rest_on_day"
    day: Weekday


class NoHardBackToBack(_Soft):
    type: Literal["no_hard_back_to_back"] = "no_hard_back_to_back"
    rpe_threshold: int = Field(default=7, ge=5, le=9)


SoftConstraint = Annotated[
    MinSessions | MaxSessions | MaxRpeOnDay | RestOnDay | NoHardBackToBack,
    Field(discriminator="type"),
]


class ConstraintSet(BaseModel):
    """What the Planner agent's LLM returns."""

    model_config = ConfigDict(extra="forbid")
    load_factor: float = Field(
        default=1.0,
        ge=0.5,
        le=1.1,
        description="Target weekly load as a multiple of the chronic weekly load",
    )
    soft: list[SoftConstraint] = Field(default_factory=list, max_length=12)
    rationale: str = Field(default="", max_length=400)


# --------------------------------------------------------------------------- result


class PlanDay(BaseModel):
    day: Weekday
    date: date
    kind: SessionType
    rpe: int
    minutes: int

    @property
    def load(self) -> int:
        return self.rpe * self.minutes


class PlanResult(BaseModel):
    player_id: str
    days: list[PlanDay]
    status: Literal["optimal", "feasible", "relaxed", "template"]
    dropped: list[str] = []
    penalty: int = 0
    solve_seconds: float = 0.0
    weekly_load_cap: int | None = None

    @property
    def weekly_load(self) -> int:
        return sum(d.load for d in self.days)

    def signature(self) -> tuple:
        return tuple((d.kind.value, d.rpe) for d in self.days)
