"""Levels, benchmarks and level-ups for self-guided players (config/pathway.yaml).

Pure functions: the API layer (pathway/service.py) feeds in the player's latest test
results and logged sessions.
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path

import yaml

CONFIG = Path(__file__).resolve().parent.parent / "config" / "pathway.yaml"
MAX_LEVEL = 5


@lru_cache(maxsize=1)
def config() -> dict:
    data = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    data["levels"] = {int(k): v for k, v in data["levels"].items()}
    for t in data["tests"].values():
        t["thresholds"] = {int(k): float(v) for k, v in t["thresholds"].items()}
        t["age_adjust"] = {int(k): float(v) for k, v in t.get("age_adjust", {}).items()}
    return data


def tests() -> dict[str, dict]:
    return config()["tests"]


def threshold(test: str, level: int, age: float, sex: str = "male") -> float | None:
    """Benchmark for `level` (None for level 1, which has no entry test)."""
    t = tests()[test]
    base = t["thresholds"].get(level)
    if base is None:
        return None
    age_key = min(int(age), 18)
    adj = t["age_adjust"].get(age_key, 0.0) if age_key < 18 else 0.0
    if sex == "female":
        adj += t.get("female_adjust", 0.0)
    value = base + adj
    return round(value, 2) if t["unit"] == "s" else round(value)


def meets(test: str, value: float | None, target: float | None) -> bool:
    if value is None or target is None:
        return False
    return value <= target if tests()[test]["lower_is_better"] else value >= target


def _gap(test: str, value: float | None, target: float) -> float:
    """Relative shortfall to the target (0 = met, 1 = not tested)."""
    if value is None:
        return 1.0
    if meets(test, value, target):
        return 0.0
    return abs(value - target) / abs(target)


def benchmark_level(results: Mapping[str, float], age: float, sex: str = "male") -> int:
    """Highest level whose benchmarks the player meets in enough tests."""
    need = config()["tests_needed"]
    best = 1
    for lvl in range(2, MAX_LEVEL + 1):
        met = sum(meets(t, results.get(t), threshold(t, lvl, age, sex)) for t in tests())
        if met >= need:
            best = lvl
        else:
            break
    return best


def consistency(level: int, sessions_28d: int) -> dict:
    """Sessions logged in the last 4 weeks against the level's weekly sessions."""
    planned = config()["levels"][level]["min_sessions"] * 4
    needed = int(round(planned * config()["consistency"]))
    return {"logged": sessions_28d, "needed": needed, "planned": planned, "ok": sessions_28d >= needed}


def assess(results: Mapping[str, float], age: float, sex: str, level: int, sessions_28d: int) -> dict:
    """Where the player stands: current level, the next level's checklist, focus areas."""
    cfg = config()
    level = max(1, min(MAX_LEVEL, level))
    nxt = level + 1 if level < MAX_LEVEL else None
    target_level = nxt or MAX_LEVEL
    rows = []
    for key, t in tests().items():
        target = threshold(key, target_level, age, sex)
        value = results.get(key)
        rows.append(
            {
                "test": key,
                "label": t["label"],
                "unit": t["unit"],
                "kind": t["kind"],
                "how": t["how"],
                "lower_is_better": t["lower_is_better"],
                "value": value,
                "target": target,
                "met": meets(key, value, target),
                "gap": round(_gap(key, value, target), 3),
            }
        )
    met = sum(r["met"] for r in rows)
    cons = consistency(level, sessions_28d)
    focus = [r["test"] for r in sorted(rows, key=lambda r: -r["gap"]) if not r["met"]][:2]
    bench = benchmark_level(results, age, sex)
    return {
        "level": level,
        "name": cfg["levels"][level]["name"],
        "who": cfg["levels"][level]["who"],
        "targets": cfg["levels"][level]["targets"],
        "benchmark_level": bench,
        "next": None
        if nxt is None
        else {
            "level": nxt,
            "name": cfg["levels"][nxt]["name"],
            "tests_needed": cfg["tests_needed"],
            "tests_met": met,
        },
        "tests": rows,
        "focus": focus,
        "consistency": cons,
        "ready_to_level_up": nxt is not None and met >= cfg["tests_needed"] and cons["ok"],
    }


def ladder(age: float, sex: str) -> list[dict]:
    """All levels with this player's benchmarks (age- and sex-adjusted)."""
    cfg = config()
    out = []
    for lvl, info in cfg["levels"].items():
        out.append(
            {
                "level": lvl,
                "name": info["name"],
                "who": info["who"],
                "targets": info["targets"],
                "sessions_per_week": info["min_sessions"],
                "gym_per_week": info["gym_per_week"],
                "benchmarks": {t: threshold(t, lvl, age, sex) for t in tests()},
            }
        )
    return out


def focus_kpis(focus: list[str]) -> list[str]:
    """Planner development goals (agents.rules KPI keys) for the focus tests."""
    out: list[str] = []
    for f in focus:
        kpi = tests()[f]["kpi"]
        if kpi not in out:
            out.append(kpi)
    return out


def solo_drills(test: str | None) -> list[dict]:
    drills = config()["solo_drills"]
    return drills.get(test or "general", drills["general"])
