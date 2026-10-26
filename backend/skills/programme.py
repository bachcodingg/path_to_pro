"""Personal ball-skills session, per position, next to the gym session.

A session is: a ball-mastery warm-up (everyone), two blocks written for the player's
position, one shared game skill (first touch, scanning, weak foot, passing) and a short
finish. Drills rotate week to week. The same safety thinking as the gym and the planner:

  - growth-spurt window (PHV): no jumping drills (their standing version instead), half
    the striking reps, diving on soft ground with fewer reps; kicking volume while growing
    is what makes knees and hips sore (Osgood-Schlatter, Sever's)
  - red readiness: technique only, 20 minutes, nothing flat-out
  - amber readiness or the day before a match: no sprint drills, shorter session
  - match day: no session, a few touches only
  - no partner (self-guided players): drills that need one are swapped for solo ones

Deterministic: same inputs and week, same session.
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path

import yaml

CONFIG = Path(__file__).resolve().parent.parent / "config" / "skills.yaml"


@dataclass(frozen=True)
class Drill:
    id: str
    name: str
    positions: tuple[str, ...]
    focus: str
    partner: str  # none | optional | needed
    minutes: int
    reps: str
    steps: tuple[str, ...]
    cues: tuple[str, ...]
    harder: str = ""
    tags: tuple[str, ...] = ()
    safe_version: str | None = None

    def to_json(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "positions": list(self.positions),
            "focus": self.focus,
            "partner": self.partner,
            "minutes": self.minutes,
            "reps": self.reps,
            "steps": list(self.steps),
            "cues": list(self.cues),
            "harder": self.harder,
            "tags": list(self.tags),
        }


@dataclass(frozen=True)
class SkillsContext:
    position: str = "midfielder"
    in_phv_window: bool = False
    band: str | None = None  # today's readiness: green | amber | red
    day_kind: str | None = None  # the plan's session type for the day
    days_to_match: int | None = None  # 0 = match today, 1 = tomorrow
    partner: bool = True  # someone to train with (academy players); False: alone or a wall
    day: date | None = None


@dataclass
class Session:
    position: str
    position_label: str
    focus: str
    title: str
    minutes: int
    mode: str  # full | short | technique | rest
    blocks: list[dict] = field(default_factory=list)
    adjustments: list[str] = field(default_factory=list)

    def to_json(self) -> dict:
        return self.__dict__.copy()


@lru_cache(maxsize=1)
def library() -> tuple[dict[str, Drill], dict, dict]:
    data = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    drills = {
        d["id"]: Drill(
            **{**d, "positions": tuple(d["positions"]), "steps": tuple(d["steps"]), "cues": tuple(d["cues"]),
               "tags": tuple(d.get("tags", ()))}  # fmt: skip
        )
        for d in data["drills"]
    }
    return drills, data["positions"], {"warmup": data["warmup"], "shared": data["shared"]}


def positions() -> dict[str, dict]:
    return library()[1]


def drills_for(position: str) -> list[Drill]:
    """Every drill written for a position, its own first, then the ones everyone does."""
    drills, _, _ = library()
    own = [d for d in drills.values() if position in d.positions]
    return own + [d for d in drills.values() if "all" in d.positions]


def _mode(ctx: SkillsContext) -> str:
    if ctx.days_to_match == 0 or ctx.day_kind == "match":
        return "rest"
    if ctx.band == "red" or ctx.day_kind in ("rest", "recovery"):
        return "technique"
    if ctx.band == "amber" or ctx.days_to_match == 1:
        return "short"
    return "full"


def _halve(reps: str) -> str:
    """'3 x 10 each side' -> '2 x 10 each side' (sets), or prefix 'Half:' when not in sets."""
    head, sep, rest = reps.partition(" x ")
    if sep and head.strip().isdigit():
        return f"{(int(head) + 1) // 2} x {rest}"
    return f"Half of it: {reps}"


def _prescribe(d: Drill, block: str, ctx: SkillsContext, notes: set[str]) -> dict:
    out = d.to_json() | {"block": block, "minutes": d.minutes}
    if ctx.in_phv_window:
        if "jumping" in d.tags and d.safe_version:
            out |= {"reps": d.reps, "variant": d.safe_version}
            notes.add("growth_jump")
        if "striking" in d.tags:
            out |= {"reps": _halve(d.reps), "minutes": max(5, d.minutes // 2)}
            notes.add("growth_strike")
        if "diving" in d.tags:
            out |= {"reps": _halve(d.reps), "variant": "Soft ground or a mat only; stop if a hip or shoulder hurts."}
            notes.add("growth_dive")
    return out


def _allowed(d: Drill, ctx: SkillsContext, mode: str) -> bool:
    if d.partner == "needed" and not ctx.partner:
        return False
    if mode in ("short", "technique") and "sprint" in d.tags:
        return False
    if mode == "technique" and ({"striking", "jumping", "diving"} & set(d.tags)):
        return False
    if ctx.in_phv_window and "jumping" in d.tags and not d.safe_version:
        return False
    return True


def _pick(
    ids: list[str], slot: str, ctx: SkillsContext, mode: str, used: set[str], notes: set[str], fallback: list[str] = ()
) -> Drill | None:
    """This week's drill for the slot: the rotation's next one the player may do today,
    else the first allowed fallback."""
    drills, _, _ = library()
    week = ctx.day.isocalendar()[1] if ctx.day else 0
    shift = (week + zlib.crc32(slot.encode())) % len(ids) if ids else 0
    for i in [*ids[shift:], *ids[:shift], *fallback]:
        d = drills[i]
        if i in used:
            continue
        if _allowed(d, ctx, mode):
            used.add(i)
            return d
        if d.partner == "needed" and not ctx.partner:
            notes.add("solo")
    return None


ADJUSTMENTS = {
    "rest": "Match day: no skills session. Ten minutes of easy touches in the warm-up is enough.",
    "technique": "Recovery or low-battery day: technique only, at an easy pace. Nothing flat-out, no shooting volume.",
    "short_amber": "Battery is low today: a shorter session without sprints.",
    "short_match": "Match tomorrow: short and sharp, no sprints. Finish with a few of your best reps for confidence.",
    "growth_jump": "Growth zone: heading and other jumping drills are done standing, as technique.",
    "growth_strike": "Growth zone: half the shooting and long-passing reps. Kicking a lot while you grow makes knees and hips sore.",
    "growth_dive": "Growth zone: dives on soft ground only, half the reps.",
    "solo": "No partner today: drills that need a friend are swapped for ones you can do alone or against a wall.",
}


def build(ctx: SkillsContext) -> Session:
    drills, pos, slots = library()
    key = ctx.position if ctx.position in pos else "midfielder"
    p = pos[key]
    mode = _mode(ctx)
    notes: set[str] = set()
    used: set[str] = set()
    blocks: list[dict] = []

    def add(block: str, d: Drill | None) -> None:
        if d is not None:
            # a fallback from the shared drills is labelled as such, not as a position drill
            label = block if block != p["label"] or key in d.positions else "Game skill"
            blocks.append(_prescribe(d, label, ctx, notes))

    a, b = p["blocks"]

    if mode == "rest":
        add("Warm-up touches", _pick(slots["warmup"], "warmup", ctx, "technique", used, notes))
    else:
        add("Warm-up", _pick(slots["warmup"], "warmup", ctx, mode, used, notes))
        if mode == "technique":
            add("Technique", _pick(slots["shared"], "shared", ctx, mode, used, notes))
            add(p["label"], _pick([*a, *b], "pos", ctx, mode, used, notes))
        else:
            add(p["label"], _pick(a, "pos-a", ctx, mode, used, notes, [*b, *slots["shared"]]))
            add(p["label"], _pick(b, "pos-b", ctx, mode, used, notes, [*a, *slots["shared"]]))
            if mode == "full":
                add("Game skill", _pick(slots["shared"], "shared", ctx, mode, used, notes))
                finish = drills.get(p["finish"])
                if finish is not None and finish.id not in used and _allowed(finish, ctx, mode):
                    used.add(finish.id)
                    add("Finish", finish)
    adjustments = [ADJUSTMENTS[mode]] if mode in ("rest", "technique") else []
    if mode == "short":
        adjustments.append(ADJUSTMENTS["short_match" if ctx.days_to_match == 1 else "short_amber"])
    adjustments += [ADJUSTMENTS[k] for k in ("growth_jump", "growth_strike", "growth_dive", "solo") if k in notes]
    minutes = sum(b["minutes"] for b in blocks)
    title = {"rest": "Match day touches", "technique": "Easy technique session"}.get(mode, f"{p['label']} skills session")
    return Session(key, p["label"], p["focus"], title, minutes, mode, blocks, adjustments)
