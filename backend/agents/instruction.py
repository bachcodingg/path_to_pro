"""Coach instructions in plain words -> planner constraints.

"Keep Leon light until Thursday", "no gym this week", "rest on Friday", "extra speed
work". Claude turns the note into a ConstraintSet when a key is configured; otherwise
(and whenever the LLM output is invalid) a rule-based parser handles common phrasings.
Either way the result only feeds the planner as weighted constraints: the hard safety
rules still apply, and pain or injury notes are refused (they go to the physio).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from agents.llm import Call, LLMBackend, complete_with_retry
from domain.enums import SessionType
from planner.schema import (
    ConstraintSet,
    MaxRpeOnDay,
    MaxSessions,
    MinSessions,
    NoHardBackToBack,
    RestOnDay,
    SoftConstraint,
)

WEIGHT = 9  # coach's word: imposed as hard when the safety rules allow it
LIGHT_RPE = 4
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_DAY = r"(today|tomorrow|mon|tue|wed|thu|fri|sat|sun)[a-z]*"
SAFETY = re.compile(r"\b(pain|painful|injur\w*|hurt\w*|concuss\w*|fracture\w*|sprain\w*)\b", re.I)

SYSTEM = """\
You turn a youth football coach's instruction about one player's week into soft constraints for \
PathToPro's planner. Days are numbered from 0 (the plan's first day); `days` maps each number to \
its weekday. Use weight 9 for what the coach explicitly asked. "Light" or "easy" means \
max_rpe_on_day with rpe 4 on each affected day. Only constrain days the coach mentioned (or all \
days for "this week"); with no day given, an intensity instruction covers days 0 and 1. Never \
invent other changes. Leave load_factor at 1.0 unless the coach asks for a lighter or heavier \
week overall (0.8 lighter, 1.1 heavier). Put a short summary of the instruction in rationale.
"""


class InstructionRefused(ValueError):
    pass


@dataclass
class Parsed:
    constraints: ConstraintSet
    source: str  # llm | llm_retry | rules
    summary: list[str] = field(default_factory=list)


def _offset(word: str, start: date) -> int | None:
    w = word.lower()
    if w.startswith("today"):
        return 0
    if w.startswith("tomorrow"):
        return 1
    for i, name in enumerate(DAYS):
        if w.startswith(name[:3]):
            return (i - start.weekday()) % 7
    return None


def _days(text: str, start: date, n: int) -> list[int] | None:
    """Days the instruction refers to (None = none named)."""
    t = text.lower()
    if re.search(r"\b(this|all|whole|rest of the) week\b", t):
        return list(range(n))
    if "weekend" in t:
        return [d for d in (_offset("sat", start), _offset("sun", start)) if d is not None and d < n]
    m = re.search(rf"\b(?:until|till|til|through|up to|to)\s+{_DAY}\b", t)
    if m:
        end = _offset(m.group(1), start)
        return list(range(0, min(n, (end or 0) + 1)))
    found = sorted({o for w in re.findall(rf"\b{_DAY}\b", t) if (o := _offset(w, start)) is not None and o < n})
    return found or None


def _sessions(word: str) -> SessionType:
    return SessionType.STRENGTH if re.match(r"gym|strength|weights|lifting", word) else SessionType.SPEED


def parse_rules(text: str, start: date, n: int, current_counts: dict[SessionType, int] | None = None) -> list[SoftConstraint]:
    """Each clause ("light until Thursday", "no gym this week") is read with its own days,
    so a "this week" in one clause doesn't stretch another clause's day range."""
    why = text.strip()[:150] or "coach instruction"
    out: list[SoftConstraint] = []
    for clause in re.split(r"[,;.]|\bbut\b|\band then\b", text):
        if clause.strip():
            out += _parse_clause(clause, start, n, current_counts or {}, why)
    return out


def _parse_clause(text: str, start: date, n: int, counts: dict[SessionType, int], why: str) -> list[SoftConstraint]:
    t = text.lower()
    days = _days(t, start, n)
    out: list[SoftConstraint] = []

    m = re.search(r"(?:max(?:imum)?|cap(?:ped)?(?: at)?|no more than|at most)\s*(?:rpe|effort|intensity)?\s*(\d{1,2})", t)
    light = re.search(r"\b(light|lighter|easy|easier|gentle|low[- ]intensity|take it easy|go easy|fresh|knock|sore|niggle|tired)\b", t)
    if m or light:
        rpe = min(10, int(m.group(1))) if m else LIGHT_RPE
        for d in days if days is not None else [0, 1][:n]:
            out.append(MaxRpeOnDay(day=d, rpe=rpe, weight=WEIGHT, why=why))

    if re.search(r"\b(rest|day off|off day)\b", t) and days is not None and not light:
        for d in days:
            out.append(RestOnDay(day=d, weight=WEIGHT, why=why))

    for m in re.finditer(r"\b(?:no|skip|cancel|without)\s+(?:the\s+)?(gym|strength|weights|lifting|speed|sprints?|sprinting)\b", t):
        out.append(MaxSessions(session=_sessions(m.group(1)), count=0, weight=WEIGHT, why=why))

    for m in re.finditer(r"\b(extra|more|another|add(?:\s+an?)?|two|2|second)\s+(gym|strength|weights|speed|sprint\w*)\b", t):
        kind = _sessions(m.group(2))
        want = 2 if m.group(1) in ("two", "2", "second") else counts.get(kind, 0) + 1
        out.append(MinSessions(session=kind, count=max(1, min(4, want)), weight=WEIGHT, why=why))

    if re.search(r"back[- ]to[- ]back", t):
        out.append(NoHardBackToBack(rpe_threshold=7, weight=WEIGHT, why=why))
    return out


def describe(c: SoftConstraint, start: date) -> str:
    def day(d: int) -> str:
        return (start + timedelta(days=d)).strftime("%a %d %b")

    if isinstance(c, MaxRpeOnDay):
        return f"{day(c.day)}: effort at most {c.rpe}/10"
    if isinstance(c, RestOnDay):
        return f"{day(c.day)}: rest day"
    if isinstance(c, MaxSessions):
        return f"No {c.session.value} sessions" if c.count == 0 else f"At most {c.count} {c.session.value} sessions"
    if isinstance(c, MinSessions):
        return f"At least {c.count} {c.session.value} session{'s' if c.count > 1 else ''}"
    if isinstance(c, NoHardBackToBack):
        return f"No hard days (RPE {c.rpe_threshold}+) back to back"
    return c.type


def parse(
    text: str,
    start: date,
    n: int,
    llm: LLMBackend | None = None,
    current_counts: dict[SessionType, int] | None = None,
) -> Parsed:
    if SAFETY.search(text):
        raise InstructionRefused(
            "This sounds like pain or an injury. Please send it to the physio queue: the agents don't plan around injuries."
        )
    ctx = json.dumps(
        {"instruction": text, "days": {d: (start + timedelta(days=d)).strftime("%A") for d in range(n)}, "plan_start": start.isoformat()}
    )
    cs, source = complete_with_retry(llm, Call(agent="instruction", system=SYSTEM, user=ctx, output=ConstraintSet))
    if cs is not None:
        # The LLM may only constrain days inside the plan
        cs.soft = [c for c in cs.soft if not hasattr(c, "day") or 0 <= c.day < n]
    if cs is None or not cs.soft:
        soft = parse_rules(text, start, n, current_counts)
        cs, source = ConstraintSet(soft=soft[:12], rationale=text[:400]), "rules"
    if not cs.soft and cs.load_factor == 1.0:
        raise InstructionRefused(
            "I couldn't turn this into a plan change. Try 'keep him light until Thursday', 'no gym this week', "
            "'rest on Friday' or 'extra speed work'."
        )
    return Parsed(cs, source, [describe(c, start) for c in cs.soft])
