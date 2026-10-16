"""Rule-based default constraints and explanations.

Used when the LLM is unavailable or its output stays invalid after one retry
(plan section 4, step 3). Also the reference behaviour the LLM is compared to.
"""

from __future__ import annotations

from dataclasses import dataclass

from analytics.flags import Flag, FlagKind
from domain.enums import SessionType
from planner.schema import (
    ConstraintSet,
    MaxRpeOnDay,
    MaxSessions,
    MinSessions,
    NoHardBackToBack,
    PlannerInput,
    PlanResult,
)

SPIKE_CUT_MIN_SHARE = 0.8  # only cut after a spike if chronic load is >= 80% of the planned volume

KPI_SESSION: dict[str, SessionType] = {
    "sprint_10m": SessionType.SPEED,
    "sprint_30m": SessionType.SPEED,
    "cmj": SessionType.STRENGTH,
    "yoyo_ir1": SessionType.TACTICAL,
}

KPI_LABEL = {
    "sprint_10m": "10 m sprint",
    "sprint_30m": "30 m sprint",
    "cmj": "jump power",
    "yoyo_ir1": "endurance",
}


@dataclass(frozen=True)
class DevGoal:
    kpi: str
    sessions_per_week: int = 2

    @property
    def session(self) -> SessionType:
        return KPI_SESSION[self.kpi]


def default_constraints(flags: list[Flag], goals: list[DevGoal], inp: PlannerInput) -> ConstraintSet:
    kinds = {f.kind for f in flags}
    soft = []
    load_factor = 1.0
    reasons = []

    if FlagKind.LOAD_SPIKE in kinds:
        soft.append(NoHardBackToBack(rpe_threshold=7, weight=6, why="load spike: spread intensity"))
        # At low absolute load (e.g. back from time off) ACWR flags almost any session;
        # the planner's ramp limit already protects, and cutting further only deepens the hole.
        if inp.chronic_daily_load * 7 >= SPIKE_CUT_MIN_SHARE * inp.club_weekly_load:
            load_factor = 0.8
            reasons.append("cut load 20% after a spike")
        else:
            reasons.append("rebuild load gradually after time off")
    if kinds & {FlagKind.SHORT_SLEEP, FlagKind.LOW_HRV, FlagKind.READINESS_RED}:
        # Shift load later in the week rather than removing it: easy days now.
        for d in (0, 1):
            if d not in inp.match_days:
                soft.append(MaxRpeOnDay(day=d, rpe=4, weight=7, why="poor recovery: easy first two days"))
        reasons.append("easy start while recovery is low")
    if FlagKind.HIGH_MONOTONY in kinds:
        soft.append(NoHardBackToBack(rpe_threshold=6, weight=5, why="monotony high: vary intensity"))
        reasons.append("vary intensity")
    if FlagKind.PHV_WINDOW in kinds:
        soft.append(MaxSessions(session=SessionType.STRENGTH, count=1, weight=4, why="growth zone: limit heavy work"))
        reasons.append("limit jumps and sprints in the growth zone")

    for g in goals:
        soft.append(
            MinSessions(
                session=g.session,
                count=g.sessions_per_week,
                weight=6,
                why=f"development goal: {KPI_LABEL.get(g.kpi, g.kpi)}",
            )
        )
    return ConstraintSet(load_factor=load_factor, soft=soft[:12], rationale="; ".join(reasons) or "normal week")


def default_explanation(flags: list[Flag], result: PlanResult, goals: list[DevGoal]) -> tuple[str, str]:
    """(3 sentences for the player, 1 line for the coach)."""
    kinds = {f.kind for f in flags if not f.is_safety}
    why = []
    if FlagKind.LOAD_SPIKE in kinds:
        why.append("your training load jumped a lot recently")
    if FlagKind.SHORT_SLEEP in kinds:
        why.append("you've slept less than 6 hours for 3 nights")
    if FlagKind.LOW_HRV in kinds or FlagKind.READINESS_RED in kinds:
        why.append("your body is showing signs of fatigue")
    if FlagKind.PHV_WINDOW in kinds:
        why.append("you're in a growth spurt, when joints and tendons need extra care")
    s1 = (
        "This week is lighter because " + _join(why) + "."
        if why
        else "This week follows your normal rhythm around your matches."
    )
    hard = [d for d in result.days if d.kind in (SessionType.SPEED, SessionType.STRENGTH)]
    if goals:
        s2 = f"You still get {len(hard)} focused block{'s' if len(hard) != 1 else ''} for your goal: " + ", ".join(
            KPI_LABEL.get(g.kpi, g.kpi) for g in goals
        ) + "."
    else:
        s2 = "Every session has a clear purpose, and the day before each match is kept easy."
    s3 = "Sleep 8-10 hours and tell your coach if anything hurts."
    coach = f"{result.status}: {_join([f.detail for f in flags if not f.is_safety]) or 'no flags'}; load {result.weekly_load} AU"
    if result.weekly_load_cap:
        coach += f" (cap {result.weekly_load_cap})"
    return f"{s1} {s2} {s3}", coach[:300]


def _join(parts: list[str]) -> str:
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + " and " + parts[-1]
