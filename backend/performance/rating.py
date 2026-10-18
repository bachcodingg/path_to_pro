"""Match rating from match stats, on the familiar 3.0-10.0 scale (6.0-7.0 is an ordinary
game, 8+ is outstanding).

Inspired by public rating apps, but our own transparent formula: a base score plus
position-weighted contributions, and every rating comes with its breakdown ("goal +1.0,
3 key passes +0.36, 2 goals conceded -0.30"), so a coach can see why. The weights are
team defaults to be tuned against the club's own judgement, like the readiness weights.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

BASE = 6.3
MIN_MINUTES = 10  # fewer minutes: no rating (too little to judge)
LOW, HIGH = 3.0, 10.0

GROUP = {
    "goalkeeper": "gk",
    "centre_back": "def",
    "full_back": "def",
    "midfielder": "mid",
    "winger": "fwd",
    "striker": "fwd",
}

# Per stat: (label, weight per unit) by position group. Missing = 0.
WEIGHTS: dict[str, tuple[str, dict[str, float]]] = {
    "goals": ("Goals", {"gk": 1.5, "def": 1.2, "mid": 1.0, "fwd": 0.9}),
    "assists": ("Assists", {"gk": 1.0, "def": 0.8, "mid": 0.7, "fwd": 0.7}),
    "shots_on_target": ("Shots on target", {"gk": 0.1, "def": 0.1, "mid": 0.1, "fwd": 0.12}),
    "big_chances_missed": ("Big chances missed", {"gk": -0.2, "def": -0.2, "mid": -0.25, "fwd": -0.3}),
    "key_passes": ("Key passes", {"gk": 0.12, "def": 0.12, "mid": 0.12, "fwd": 0.1}),
    "dribbles_won": ("Dribbles won", {"gk": 0.05, "def": 0.06, "mid": 0.07, "fwd": 0.08}),
    "tackles_won": ("Tackles won", {"gk": 0.05, "def": 0.1, "mid": 0.08, "fwd": 0.06}),
    "interceptions": ("Interceptions", {"gk": 0.05, "def": 0.1, "mid": 0.08, "fwd": 0.05}),
    "clearances": ("Clearances", {"gk": 0.03, "def": 0.04, "mid": 0.03, "fwd": 0.02}),
    "duels_won": ("Duels won", {"gk": 0.03, "def": 0.04, "mid": 0.04, "fwd": 0.04}),
    "duels_lost": ("Duels lost", {"gk": -0.03, "def": -0.05, "mid": -0.04, "fwd": -0.03}),
    "saves": ("Saves", {"gk": 0.25, "def": 0.0, "mid": 0.0, "fwd": 0.0}),
    "goals_conceded": ("Goals conceded", {"gk": -0.3, "def": -0.15, "mid": -0.05, "fwd": 0.0}),
    "errors_to_goal": ("Errors leading to a goal", {"gk": -1.0, "def": -0.9, "mid": -0.8, "fwd": -0.7}),
    "own_goals": ("Own goals", {"gk": -0.8, "def": -0.8, "mid": -0.8, "fwd": -0.8}),
    "yellow": ("Yellow card", {"gk": -0.2, "def": -0.2, "mid": -0.2, "fwd": -0.2}),
    "red": ("Red card", {"gk": -1.2, "def": -1.2, "mid": -1.2, "fwd": -1.2}),
}
CLEAN_SHEET = {"gk": 0.6, "def": 0.4, "mid": 0.1, "fwd": 0.0}
RESULT = {"win": 0.15, "draw": 0.0, "loss": -0.1}
STAT_KEYS = [*WEIGHTS, "passes", "passes_accurate", "result"]


@dataclass
class Rating:
    value: float | None
    breakdown: list[dict] = field(default_factory=list)

    def to_json(self) -> dict:
        return {"rating": self.value, "breakdown": self.breakdown}


def rate(position: str | None, minutes: int, stats: Mapping[str, float | str | None]) -> Rating:
    """Rating for one player in one match (None under MIN_MINUTES)."""
    if minutes < MIN_MINUTES:
        return Rating(None, [{"label": f"Under {MIN_MINUTES} minutes: no rating", "value": 0.0}])
    g = GROUP.get(position or "", "mid")
    parts: list[tuple[str, float]] = []
    for key, (label, w) in WEIGHTS.items():
        n = float(stats.get(key) or 0)
        if n and w[g]:
            parts.append((f"{label} x{n:g}" if n != 1 else label, n * w[g]))
    passes, acc = float(stats.get("passes") or 0), float(stats.get("passes_accurate") or 0)
    if passes >= 10:
        share = min(1.0, acc / passes)
        parts.append((f"Pass accuracy {share:.0%} ({passes:g} passes)", (share - 0.80) * 3 * min(passes, 50) / 50))
    if minutes >= 60 and stats.get("goals_conceded") is not None and float(stats.get("goals_conceded") or 0) == 0 and CLEAN_SHEET[g]:
        parts.append(("Clean sheet", CLEAN_SHEET[g]))
    result = stats.get("result")
    if result in RESULT and RESULT[result]:
        parts.append((f"Team result: {result}", RESULT[result]))
    value = max(LOW, min(HIGH, BASE + sum(v for _, v in parts)))
    breakdown = [{"label": label, "value": round(v, 2)} for label, v in sorted(parts, key=lambda p: -abs(p[1])) if round(v, 2)]
    return Rating(round(value, 1), breakdown)


def rate_diary(position: str | None, minutes: int, goals: int, assists: int) -> Rating:
    """A rough estimate from the player's own match diary (no full stats)."""
    r = rate(position, minutes, {"goals": goals, "assists": assists})
    if r.value is not None:
        r.breakdown.append({"label": "Estimate from your match diary (no full stats)", "value": 0.0})
    return r


def band(value: float | None) -> str | None:
    """Colour band for display."""
    if value is None:
        return None
    if value >= 8.0:
        return "elite"
    if value >= 7.0:
        return "good"
    if value >= 6.5:
        return "fair"
    if value >= 6.0:
        return "average"
    return "poor"
