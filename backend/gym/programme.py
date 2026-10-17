"""Gym programme for one strength session, per player.

Every session has the shared part every footballer does (warm-up, injury prevention,
core, mobility) and a power, strength and position block chosen for the player's
position. The same safety thinking as the planner applies:

  - growth-spurt window (PHV): no jumps, no heavy loads, technique doses only
  - before the growth spurt or under 14: technique doses, bodyweight and light loads
  - heavy lifts only after the growth spurt and from 16, on a normal-or-better day
  - red readiness: recovery gym only (isometric prevention, core, mobility)
  - amber readiness: one set less, no jumps
  - day before a match: short activation; two days before: no eccentric (sore) work
  - the session's planned effort (RPE) caps the dose

Deterministic: same inputs and date, same programme. Exercises rotate week to week.
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path

import yaml

CONFIG = Path(__file__).resolve().parent.parent / "config" / "gym.yaml"

EQUIPMENT = {
    "gym": {"bodyweight", "band", "dumbbell", "barbell", "box", "med_ball", "partner", "bench", "bar"},
    "home": {"bodyweight", "band", "dumbbell", "partner", "bench", "box"},
    "none": {"bodyweight", "partner", "bench", "box"},  # park bench, stairs, a friend
}
STAGES = ("foundation", "development", "performance")
STAGE_LABEL = {
    "foundation": "Foundation: technique and control",
    "development": "Development: moderate loads",
    "performance": "Performance: progressive strength",
}

# (sets, amount) per exercise kind and stage; amount is reps, seconds or metres by unit.
DOSE = {
    "prep": {"foundation": (1, 10), "development": (1, 10), "performance": (1, 10)},
    "power": {"foundation": (2, 4), "development": (3, 4), "performance": (4, 3)},
    "strength": {"foundation": (2, 10), "development": (3, 8), "performance": (4, 5)},
    "prevention": {"foundation": (2, 5), "development": (2, 6), "performance": (3, 6)},
    "core": {"foundation": (2, 8), "development": (3, 10), "performance": (3, 12)},
    "mobility": {"foundation": (1, 6), "development": (1, 6), "performance": (1, 6)},
}
SECONDS = {"foundation": 20, "development": 30, "performance": 40}
METRES = {"foundation": 20, "development": 30, "performance": 40}
REST_S = {"prep": 0, "power": 90, "strength": 90, "prevention": 60, "core": 45, "mobility": 0}
INTENSITY = {
    "foundation": "light: perfect technique, stop well before it gets hard",
    "development": "moderate: finish each set with about 3 reps left in the tank",
    "performance": "challenging: finish each set with about 2 reps left in the tank",
}


@dataclass(frozen=True)
class Exercise:
    id: str
    name: str
    kind: str
    equipment: str
    unit: str
    cue: str
    heavy: bool = False
    plyometric: bool = False
    eccentric: bool = False
    min_age: int = 13
    alternative: str | None = None


@dataclass(frozen=True)
class GymContext:
    position: str = "midfielder"
    age: float = 16.0
    maturity: str | None = None  # pre_phv | circa_phv | post_phv
    in_phv_window: bool = False
    band: str | None = None  # green | amber | red
    planned_rpe: int = 6
    days_to_match: int | None = None  # 1 = match tomorrow
    equipment: str = "gym"  # gym | home | none
    level: int | None = None  # amateur pathway level (1-5); None for academy players
    day: date | None = None


@dataclass
class Prescription:
    id: str
    name: str
    block: str
    tag: str  # everyone | position
    sets: int
    amount: str  # "8", "8 each side", "30 s", "20 m"
    rest_s: int
    cue: str
    equipment: str
    plyometric: bool
    heavy: bool


@dataclass
class Programme:
    position: str
    position_label: str
    focus: str
    stage: str
    stage_label: str
    intensity: str
    title: str
    minutes: int
    blocks: list[dict] = field(default_factory=list)
    adjustments: list[str] = field(default_factory=list)

    def to_json(self) -> dict:
        return {
            "position": self.position,
            "position_label": self.position_label,
            "focus": self.focus,
            "stage": self.stage,
            "stage_label": self.stage_label,
            "intensity": self.intensity,
            "title": self.title,
            "minutes": self.minutes,
            "blocks": self.blocks,
            "adjustments": self.adjustments,
        }


@lru_cache(maxsize=1)
def library() -> tuple[dict[str, Exercise], dict, dict]:
    data = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    ex = {e["id"]: Exercise(**e) for e in data["exercises"]}
    for slot in [*data["shared"].values(), *(v for p in data["positions"].values() for k, v in p.items() if isinstance(v, list))]:
        for i in slot:
            if i not in ex:
                raise ValueError(f"gym.yaml: unknown exercise {i}")
    return ex, data["shared"], data["positions"]


def positions() -> dict[str, dict]:
    _, _, pos = library()
    return {k: {"label": v["label"], "focus": v["focus"]} for k, v in pos.items()}


def stage_for(ctx: GymContext) -> str:
    if ctx.in_phv_window or ctx.maturity == "pre_phv" or ctx.age < 14 or ctx.planned_rpe <= 4:
        return "foundation"
    if ctx.level is not None and ctx.level <= 2:
        return "foundation"  # new to the gym: learn the movements first
    performance = (
        ctx.maturity == "post_phv"
        and ctx.age >= 16
        and (ctx.level is None or ctx.level >= 4)
        and ctx.planned_rpe >= 6
        and ctx.equipment == "gym"
        and ctx.band != "amber"
    )
    return "performance" if performance else "development"


class _Picker:
    def __init__(self, ctx: GymContext, stage: str):
        self.ctx, self.stage = ctx, stage
        self.ex, _, _ = library()
        self.used: set[str] = set()
        self.week = ctx.day.isocalendar()[1] if ctx.day else 0
        self.no_jumps = ctx.in_phv_window or ctx.band in ("amber", "red") or ctx.days_to_match == 1
        self.no_eccentric = ctx.band == "red" or ctx.days_to_match in (1, 2)

    def allowed(self, e: Exercise) -> bool:
        c = self.ctx
        if e.id in self.used or e.equipment not in EQUIPMENT.get(c.equipment, EQUIPMENT["none"]):
            return False
        if c.age < e.min_age or (e.plyometric and self.no_jumps) or (e.eccentric and self.no_eccentric):
            return False
        if e.heavy and (self.stage != "performance" or c.in_phv_window):
            return False
        return True

    def pick(self, candidates: list[str], slot: str, fallback: tuple[str, ...] = ()) -> Exercise | None:
        if not candidates:
            return None
        shift = (self.week + zlib.crc32(slot.encode())) % len(candidates)
        for cid in [*candidates[shift:], *candidates[:shift], *fallback]:
            for e in (self.ex[cid], self.ex.get(self.ex[cid].alternative or "")):
                if e is not None and self.allowed(e):
                    self.used.add(e.id)
                    return e
        return None


def _amount(e: Exercise, stage: str, reps: int) -> str:
    if e.unit == "s":
        return f"{SECONDS[stage]} s"
    if e.unit == "m":
        return f"{METRES[stage]} m"
    return f"{reps} each side" if e.unit == "each side" else str(reps)


def _prescribe(e: Exercise, block: str, tag: str, stage: str, minus_sets: int) -> Prescription:
    sets, reps = DOSE[e.kind][stage]
    if e.kind in ("power", "strength", "core"):
        sets = max(1, sets - minus_sets)
    if e.id == "nordic":
        reps = {"foundation": 3, "development": 5, "performance": 6}[stage]  # eccentric: keep it low
    return Prescription(
        id=e.id,
        name=e.name,
        block=block,
        tag=tag,
        sets=sets,
        amount=_amount(e, stage, reps),
        rest_s=REST_S[e.kind],
        cue=e.cue,
        equipment=e.equipment,
        plyometric=e.plyometric,
        heavy=e.heavy,
    )


def _minutes(blocks: list[dict]) -> int:
    per_set = {"prep": 1.0, "power": 1.5, "strength": 2.5, "prevention": 1.5, "core": 1.25, "mobility": 1.5}
    total = 4.0  # moving between stations
    for b in blocks:
        for it in b["items"]:
            total += it["sets"] * per_set[b["kind"]]
    return int(round(total / 5) * 5)


def build(ctx: GymContext) -> Programme:
    ex, shared, pos_table = library()
    position = ctx.position if ctx.position in pos_table else "midfielder"
    pos = pos_table[position]
    stage = stage_for(ctx)
    p = _Picker(ctx, stage)
    minus = 1 if ctx.band == "amber" or ctx.days_to_match == 2 else 0
    notes: list[str] = []
    if ctx.in_phv_window:
        notes.append("Growth zone: no jumps and no heavy weights. Bones are growing faster than muscles and tendons, so the focus is technique and control.")
    elif ctx.maturity == "pre_phv" or ctx.age < 14:
        notes.append("Before the growth spurt: learn the movements with bodyweight and light loads. Strength comes from better technique now.")
    if ctx.band == "red":
        notes.append("Low battery today: recovery gym only (holds, core and mobility). No hard sets.")
    elif ctx.band == "amber":
        notes.append("Take care today: one set less and no jumps.")
    if ctx.days_to_match == 1:
        notes.append("Match tomorrow: short activation only, so your legs are fresh.")
    elif ctx.days_to_match == 2:
        notes.append("Match in two days: no Nordic curls or other work that makes you sore; one set less.")
    if ctx.equipment != "gym":
        notes.append("No gym needed: exercises use " + ("bodyweight, a band and dumbbells." if ctx.equipment == "home" else "bodyweight, a bench or stairs and a partner."))

    def block(title: str, kind: str, tag: str, slots: list[tuple[list[str], str]], fallback: tuple[str, ...] = ()) -> dict | None:
        items = []
        for candidates, slot in slots:
            e = p.pick(candidates, slot, fallback)
            if e is not None:
                items.append(_prescribe(e, title, tag, stage, minus).__dict__)
        return {"title": title, "kind": kind, "tag": tag, "items": items} if items else None

    red = ctx.band == "red"
    activation = ctx.days_to_match == 1
    plan: list[dict | None] = [block("Warm-up", "prep", "everyone", [(shared["prep"][:1], "prep1"), (shared["prep"][1:], "prep2")])]
    if not red:
        # A-skips are the fallback: no jump, no equipment, fine the day before a match.
        plan.append(block("Power", "power", "position", [(pos["power"], "power")], fallback=("w-a-skip",)))
    if not red and not activation:
        plan.append(
            block(
                "Strength",
                "strength",
                "everyone",
                [(shared["lower"], "lower"), (shared["hinge"], "hinge"), (shared["upper"], "upper")],
            )
        )
        plan.append(
            block(f"{pos['label']} work", "strength", "position", [(pos["position"], "pos1"), (pos["position"], "pos2")])
        )
    if not activation:
        if red:  # holds only: they keep the tissue loaded without fatigue
            prevention = [(["hamstring-bridge-iso"], "nordic"), (["adductor-squeeze"], "copenhagen"), (["sl-balance"], "balance")]
        else:
            prevention = [(["nordic"], "nordic"), (["copenhagen"], "copenhagen")]
            if stage == "foundation":
                prevention.append((["sl-balance"], "balance"))
        plan.append(block("Injury prevention", "prevention", "everyone", prevention))
    plan.append(block("Core", "core", "everyone", [(shared["core"], "core")]))
    plan.append(block("Cool-down", "mobility", "everyone", [(shared["mobility"], "mob1"), (shared["mobility"], "mob2")]))
    blocks = [b for b in plan if b is not None]

    title = (
        "Recovery gym"
        if red
        else "Pre-match activation"
        if activation
        else f"{pos['label']} gym session"
    )
    return Programme(
        position=position,
        position_label=pos["label"],
        focus=pos["focus"],
        stage=stage,
        stage_label=STAGE_LABEL[stage],
        intensity=INTENSITY[stage] if not red else "easy: you should feel better after than before",
        title=title,
        minutes=_minutes(blocks),
        blocks=blocks,
        adjustments=notes,
    )
