"""Development Coach agent: 4-week goals and drills from test results.

Triggered after a test day and weekly on Sunday. Weak KPIs are found by code
(bio-banded percentiles, so late maturers aren't judged against early maturers).
The LLM chooses drills for them from the curated library and writes the weekly
feedback; it can only pick drills the safety filter allowed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from statistics import NormalDist

import yaml
from pydantic import BaseModel, Field

from agents.llm import Call, LLMBackend, Tool, complete_with_retry
from agents.rules import KPI_LABEL, DevGoal
from analytics.maturation import MaturityStatus
from analytics.norms import NormTable

DRILLS_FILE = Path(__file__).resolve().parent.parent / "config" / "drills.yaml"
WEAK_PERCENTILE = 50.0
MAX_GOALS = 2
GOAL_GAIN_PERCENTILE = 5.0  # 4-week target: +5 percentile points


@dataclass(frozen=True)
class DrillInfo:
    id: str
    name: str
    kpi: str
    session: str
    rpe: int
    minutes: int
    plyometric: bool
    min_age: int
    description: str


def load_drills(path: Path = DRILLS_FILE) -> list[DrillInfo]:
    return [DrillInfo(**d) for d in yaml.safe_load(path.read_text(encoding="utf-8"))["drills"]]


def allowed_drills(drills: list[DrillInfo], age: float, in_phv_window: bool) -> list[DrillInfo]:
    """Safety filter: age limit, and no plyometric drills during a growth spurt."""
    return [d for d in drills if d.min_age <= age and not (in_phv_window and d.plyometric)]


@dataclass
class KpiStatus:
    kpi: str
    value: float
    age_percentile: float
    bio_percentile: float
    target_value: float


@dataclass
class DevPlan:
    goals: list[DevGoal]
    kpis: list[KpiStatus]
    drills: list[DrillInfo]
    feedback: str
    source: str
    rejected_drills: list[str] = field(default_factory=list)


class DrillChoice(BaseModel):
    drill_ids: list[str] = Field(description="2-4 drill ids from search_drills results", max_length=4)
    feedback: str = Field(description="Weekly feedback for the player, 2-3 sentences", max_length=500)


SYSTEM = """\
You are the Development Coach agent of PathToPro, for academy players aged 13-18. Code has already \
found the player's weakest attributes (bio-banded percentiles) and set 4-week goals. Use the \
search_drills tool to see the drills allowed for this player, then pick 2-4 drills that target \
the goals and fit together in a week. Only use ids returned by search_drills. Then write short, \
encouraging feedback: what they're working on and why, compared with their own progress and \
players of the same maturity. Never predict whether they will become a professional. No medical advice.
"""


def assess_kpis(latest: dict[str, float], age: float, status: MaturityStatus, norms: NormTable) -> list[KpiStatus]:
    out = []
    for kpi, value in latest.items():
        n = norms.norm(kpi, status.value)
        bio = norms.bio_banded_percentile(kpi, value, status)
        # target: the value at bio percentile + 5
        z = NormalDist().inv_cdf(min(0.99, (bio + GOAL_GAIN_PERCENTILE) / 100))
        target = n.mean - z * n.sd if n.lower_is_better else n.mean + z * n.sd
        out.append(
            KpiStatus(
                kpi=kpi,
                value=value,
                age_percentile=norms.age_percentile(kpi, value, age),
                bio_percentile=bio,
                target_value=round(target, 2),
            )
        )
    return sorted(out, key=lambda k: k.bio_percentile)


def choose_goals(kpis: list[KpiStatus]) -> list[DevGoal]:
    weak = [k for k in kpis if k.bio_percentile < WEAK_PERCENTILE][:MAX_GOALS]
    if not weak and kpis:
        weak = kpis[:1]  # everyone works on something: their relative weakest
    goals, seen = [], set()
    for k in weak:
        g = DevGoal(kpi=k.kpi, sessions_per_week=2 if len(weak) == 1 else 1)
        if g.session not in seen:
            goals.append(g)
            seen.add(g.session)
    return goals


def _rule_drills(goals: list[DevGoal], allowed: list[DrillInfo]) -> list[DrillInfo]:
    picked = []
    for g in goals:
        picked += [d for d in allowed if d.kpi == g.kpi][:2]
    return picked[:4]


def _rule_feedback(kpis: list[KpiStatus], goals: list[DevGoal]) -> str:
    if not goals:
        return "Great consistency this week. Keep building on your strengths."
    k = next(k for k in kpis if k.kpi == goals[0].kpi)
    label = KPI_LABEL.get(k.kpi, k.kpi)
    return (
        f"This block focuses on your {label}: you're at the {k.bio_percentile:.0f}th percentile for players "
        f"at your stage of growth, and the 4-week target is {k.target_value}. "
        "Quality beats quantity, so give every rep full effort and rest well between them."
    )


def run(
    player_id: str,
    latest_tests: dict[str, float],
    age: float,
    status: MaturityStatus,
    llm: LLMBackend | None,
    norms: NormTable | None = None,
    drills: list[DrillInfo] | None = None,
) -> DevPlan:
    norms = norms or NormTable.load()
    drills = drills if drills is not None else load_drills()
    kpis = assess_kpis(latest_tests, age, status, norms)
    goals = choose_goals(kpis)
    allowed = allowed_drills(drills, age, status == MaturityStatus.CIRCA_PHV)
    by_id = {d.id: d for d in allowed}

    def search_drills(args: dict) -> list[dict]:
        kpi = args["kpi"]
        return [
            {"id": d.id, "name": d.name, "session": d.session, "rpe": d.rpe, "minutes": d.minutes, "about": d.description}
            for d in allowed
            if d.kpi == kpi
        ]

    tool = Tool(
        name="search_drills",
        description="List drills from the curated library that are allowed for this player for one KPI.",
        input_schema={
            "type": "object",
            "properties": {"kpi": {"type": "string", "enum": sorted({d.kpi for d in drills})}},
            "required": ["kpi"],
            "additionalProperties": False,
        },
        fn=search_drills,
    )
    context = json.dumps(
        {
            "player": player_id,
            "age": round(age, 1),
            "maturity": status.value,
            "kpis": [
                {
                    "kpi": k.kpi,
                    "label": KPI_LABEL.get(k.kpi, k.kpi),
                    "value": k.value,
                    "bio_banded_percentile": round(k.bio_percentile),
                    "age_group_percentile": round(k.age_percentile),
                }
                for k in kpis
            ],
            "goals": [{"kpi": g.kpi, "target": next(k.target_value for k in kpis if k.kpi == g.kpi)} for g in goals],
        }
    )
    choice, source = complete_with_retry(
        llm, Call(agent="dev_coach", system=SYSTEM, user=context, output=DrillChoice, tools=[tool])
    )
    rejected: list[str] = []
    if choice is not None:
        rejected = [i for i in choice.drill_ids if i not in by_id]
        picked = [by_id[i] for i in choice.drill_ids if i in by_id]
        if rejected or not picked:
            # The model named a drill outside the safe library: don't trust the pick.
            choice, source = None, "rules"
    if choice is None:
        return DevPlan(goals, kpis, _rule_drills(goals, allowed), _rule_feedback(kpis, goals), "rules", rejected)
    return DevPlan(goals, kpis, picked, choice.feedback, source, rejected)
