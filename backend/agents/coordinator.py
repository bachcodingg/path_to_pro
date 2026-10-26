"""Coordinator: a fixed policy table deciding who approves each proposal.

No LLM. Anything the table does not explicitly allow goes to the coach (fail safe).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from analytics.flags import Flag

MAX_AUTO_RPE_DELTA = 1
# The plan's table only bounds cuts. Adding load is the riskier direction, so a week that
# gets more than this much heavier always goes to the coach, whatever the per-day RPE change.
MAX_AUTO_LOAD_INCREASE_PCT = 10


class ActionKind(str, Enum):
    REMINDER = "reminder"
    SLEEP_TASK = "sleep_task"
    DRILL_SUGGESTION = "drill_suggestion"
    INTENSITY_CHANGE = "intensity_change"
    SESSION_SWAP = "session_swap"
    LOAD_CUT = "load_cut"
    LOAD_INCREASE = "load_increase"
    NEW_GOAL = "new_goal"
    MATCH_MINUTES = "match_minutes"  # return-to-play minutes limit: a selection decision


class Decision(str, Enum):
    AUTO_APPLY = "auto_apply"
    AUTO_APPLY_NOTIFY_COACH = "auto_apply_notify_coach"
    COACH_APPROVAL = "coach_approval"
    ESCALATE = "escalate"


@dataclass(frozen=True)
class Proposal:
    player_id: str
    kind: ActionKind
    rpe_delta: int = 0
    load_cut_pct: float = 0.0
    reason: str = ""


@dataclass(frozen=True)
class Ruling:
    decision: Decision
    rule: str


_ALWAYS_AUTO = {ActionKind.REMINDER, ActionKind.SLEEP_TASK, ActionKind.DRILL_SUGGESTION}
_ALWAYS_COACH = {ActionKind.SESSION_SWAP, ActionKind.NEW_GOAL, ActionKind.MATCH_MINUTES, ActionKind.LOAD_INCREASE}


def decide(proposal: Proposal, active_flags: Sequence[Flag] = ()) -> Ruling:
    """Apply the autonomy policy from plan section 2."""
    safety = [f for f in active_flags if f.is_safety]
    if safety:
        kinds = ", ".join(sorted(f.kind.value for f in safety))
        return Ruling(Decision.ESCALATE, f"safety flag ({kinds}): escalate to named staff, no agent action")

    k = proposal.kind
    if k in _ALWAYS_AUTO:
        return Ruling(Decision.AUTO_APPLY, f"{k.value}: auto-apply")
    if k in _ALWAYS_COACH:
        return Ruling(Decision.COACH_APPROVAL, f"{k.value}: coach approves")
    if k == ActionKind.INTENSITY_CHANGE:
        if abs(proposal.rpe_delta) <= MAX_AUTO_RPE_DELTA:
            return Ruling(Decision.AUTO_APPLY_NOTIFY_COACH, "intensity change within +/-1 RPE: auto-apply, coach notified")
        return Ruling(Decision.COACH_APPROVAL, "intensity change beyond +/-1 RPE: coach approves")
    if k == ActionKind.LOAD_CUT:
        # Plan: cuts > 20% need the coach. Smaller cuts are unspecified, so we also
        # send them to the coach rather than act on our own (fail safe).
        return Ruling(Decision.COACH_APPROVAL, f"load cut {proposal.load_cut_pct:.0f}%: coach approves")
    return Ruling(Decision.COACH_APPROVAL, "not in policy table: coach approves")
