"""Set-piece tendencies per team: corners (for and against), penalties, direct free kicks.

Pure functions over the rows written by `scouting.statsbomb`. Every share carries its
sample size and a 95% Wilson interval, and a tendency is called out only when that
interval excludes the rest of the league's rate and the sample has at least `MIN_N`
cases. With 20 teams and a dozen shares each, about one in twenty called-out tendencies
can still be chance, so the notes say "n" every time.

Coordinates are StatsBomb's: 120 x 80, attacking towards x = 120, y = 0 on the attacking
team's left. Left/right for penalties and free kicks is from the kicker's view (the
goalkeeper's right is the kicker's left).
"""

from __future__ import annotations

import json
import math
import unicodedata
from collections import Counter
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data" / "laliga_2015_16.json"

BOX_X, BOX_Y0, BOX_Y1 = 102.0, 18.0, 62.0  # penalty area
SIX_X = 114.0  # six-yard line
# Corner zones are measured from the corner's touchline: posts at 36 and 44 yards in.
NEAR_POST_MAX, FAR_POST_MIN = 37.0, 43.0
SHORT_RADIUS = 25.0  # a delivery that ends outside the box this close to the flag is short
GOAL_Y0, GOAL_Y1, GOAL_H = 36.0, 44.0, 2.67
MIN_N = 20  # below this, shares are shown but never called a tendency
ON_TARGET = {"Goal", "Saved", "Saved to Post"}

ZONES = ("short", "near_post", "six_yard", "penalty_spot", "far_post", "edge")
ZONE_LABEL = {
    "short": "Short corner",
    "near_post": "Near post",
    "six_yard": "Six-yard box, central",
    "penalty_spot": "Penalty spot area",
    "far_post": "Far post",
    "edge": "Edge of the box",
}
TECHNIQUES = ("in", "out", "straight", "unknown")
TECH_LABEL = {"in": "Inswinging", "out": "Outswinging", "straight": "Straight", "unknown": "Not recorded"}
THIRDS = ("left", "centre", "right")
HEIGHTS = ("low", "middle", "high")


@lru_cache(maxsize=1)
def load(path: Path = DATA) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def slug(team: str) -> str:
    ascii_ = unicodedata.normalize("NFKD", team).encode("ascii", "ignore").decode()
    return "-".join("".join(ch if ch.isalnum() else " " for ch in ascii_.lower()).split())


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% interval for a proportion; well behaved for small n and for 0 or n successes.

    >>> [round(x, 3) for x in wilson(5, 10)]
    [0.237, 0.763]
    """
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (max(0.0, centre - half), min(1.0, centre + half))


def corner_zone(c: dict) -> str:
    """Where a corner was delivered, relative to the side it was taken from.

    >>> corner_zone({"side": "R", "x": 116.0, "y": 46.0})  # 34 yards in from the right flag
    'near_post'
    >>> corner_zone({"side": "L", "x": 116.0, "y": 46.0})  # the same spot seen from the left flag
    'far_post'
    >>> corner_zone({"side": "R", "x": 112.0, "y": 72.0})
    'short'
    """
    x, y = c["x"], c["y"]
    if not (x >= BOX_X and BOX_Y0 <= y <= BOX_Y1):
        flag_y = 0.0 if c["side"] == "L" else 80.0
        return "short" if math.hypot(120.0 - x, y - flag_y) <= SHORT_RADIUS else "edge"
    d = y if c["side"] == "L" else 80.0 - y
    if d <= NEAR_POST_MAX:
        return "near_post"
    if d >= FAR_POST_MIN:
        return "far_post"
    return "six_yard" if x >= SIX_X else "penalty_spot"


def goal_third(y: float) -> str:
    """Horizontal third of the goal from the kicker's view (y grows to the kicker's right)."""
    w = (GOAL_Y1 - GOAL_Y0) / 3
    return "left" if y < GOAL_Y0 + w else "right" if y > GOAL_Y1 - w else "centre"


def goal_height(z: float | None) -> str | None:
    if z is None:
        return None
    return "low" if z < GOAL_H / 3 else "middle" if z < 2 * GOAL_H / 3 else "high"


def _share(rows: list, key, values: tuple[str, ...], ref: list, labels: dict | None = None) -> list[dict]:
    """Share of each value in `rows`, against the same share in `ref` (rest of the league)."""
    mine, theirs = Counter(key(r) for r in rows), Counter(key(r) for r in ref)
    out = []
    for v in values:
        k, n = mine[v], len(rows)
        lo, hi = wilson(k, n)
        ref_p = theirs[v] / len(ref) if ref else None
        flag = None
        if n >= MIN_N and ref_p is not None and v != "unknown":  # "not recorded" is not a habit
            flag = "more" if lo > ref_p else "less" if hi < ref_p else None
        out.append({
            "key": v,
            "label": (labels or {}).get(v, v),
            "n": k,
            "pct": round(100 * k / n, 1) if n else None,
            "lo": round(100 * lo, 1),
            "hi": round(100 * hi, 1),
            "league_pct": round(100 * ref_p, 1) if ref_p is not None else None,
            "flag": flag,
        })  # fmt: skip
    return out


def _rate(k: int, n: int, ref_k: int, ref_n: int) -> dict:
    lo, hi = wilson(k, n)
    ref_p = ref_k / ref_n if ref_n else None
    flag = None
    if n >= MIN_N and ref_p is not None:
        flag = "more" if lo > ref_p else "less" if hi < ref_p else None
    return {
        "n": n,
        "k": k,
        "pct": round(100 * k / n, 1) if n else None,
        "lo": round(100 * lo, 1),
        "hi": round(100 * hi, 1),
        "league_pct": round(100 * ref_p, 1) if ref_p is not None else None,
        "flag": flag,
    }


def _tech(c: dict) -> str:
    return c["tech"] or "unknown"


def _corner_block(rows: list[dict], ref: list[dict], matches: int, ref_matches: int) -> dict:
    goals = sum(c["goal"] for c in rows)
    return {
        "total": len(rows),
        "per_match": round(len(rows) / matches, 2) if matches else 0,
        "league_per_match": round(len(ref) / ref_matches, 2) if ref_matches else None,
        "sides": {s: sum(c["side"] == s for c in rows) for s in ("L", "R")},
        "zones": _share(rows, corner_zone, ZONES, ref, ZONE_LABEL),
        "zones_by_side": {
            s: dict(Counter(corner_zone(c) for c in rows if c["side"] == s)) for s in ("L", "R")
        },
        "technique": _share(rows, _tech, TECHNIQUES, ref, TECH_LABEL),
        "shot": _rate(sum(c["shot"] for c in rows), len(rows), sum(c["shot"] for c in ref), len(ref)),
        "goals": goals,
        "xg_per_corner": round(sum(c["xg"] for c in rows) / len(rows), 3) if rows else 0,
        "league_xg_per_corner": round(sum(c["xg"] for c in ref) / len(ref), 3) if ref else None,
    }


def _takers(rows: list[dict]) -> list[dict]:
    by: dict[str, list[dict]] = {}
    for c in rows:
        by.setdefault(c["taker"], []).append(c)
    out = []
    for name, cs in sorted(by.items(), key=lambda kv: -len(kv[1])):
        feet = Counter(c["foot"] for c in cs)
        zones = Counter(corner_zone(c) for c in cs)
        out.append({
            "name": name,
            "n": len(cs),
            "share_pct": round(100 * len(cs) / len(rows), 1),
            "foot": feet.most_common(1)[0][0],
            "sides": {s: sum(c["side"] == s for c in cs) for s in ("L", "R")},
            "technique": {t: n for t, n in Counter(_tech(c) for c in cs).items()},
            "main_zone": zones.most_common(1)[0][0],
            "shots": sum(c["shot"] for c in cs),
            "goals": sum(c["goal"] for c in cs),
        })  # fmt: skip
    return out


def _kick_rows(rows: list[dict], ref: list[dict]) -> dict:
    """Penalties or direct free kicks: placement (kicker's view), height, outcome, takers."""
    on_target = [r for r in rows if r["outcome"] in ON_TARGET]
    ref_on = [r for r in ref if r["outcome"] in ON_TARGET]
    takers: dict[str, list[dict]] = {}
    for r in rows:
        takers.setdefault(r["taker"], []).append(r)
    return {
        "total": len(rows),
        "scored": sum(r["outcome"] == "Goal" for r in rows),
        "on_target": len(on_target),
        "conversion": _rate(
            sum(r["outcome"] == "Goal" for r in rows), len(rows), sum(r["outcome"] == "Goal" for r in ref), len(ref)
        ),
        # Placement is read from on-target kicks; a miss shows where it went, not where it was aimed.
        "placement": _share(on_target, lambda r: goal_third(r["y"]), THIRDS, ref_on),
        "height": _share(on_target, lambda r: goal_height(r["z"]), HEIGHTS, ref_on),
        "kicks": [
            {
                "taker": r["taker"],
                "foot": r["foot"],
                "y": r["y"],
                "z": r["z"],
                "third": goal_third(r["y"]),
                "height": goal_height(r["z"]),
                "outcome": r["outcome"],
                "opp": r["opp"],
                **({"minute": r["minute"]} if "minute" in r else {}),
                **({"x0": r["x0"], "y0": r["y0"], "xg": r["xg"]} if "x0" in r else {}),
            }
            for r in rows
        ],
        "takers": [
            {
                "name": name,
                "n": len(ks),
                "scored": sum(k["outcome"] == "Goal" for k in ks),
                "foot": Counter(k["foot"] for k in ks).most_common(1)[0][0],
                **{t: sum(goal_third(k["y"]) == t for k in ks if k["outcome"] in ON_TARGET) for t in THIRDS},
            }
            for name, ks in sorted(takers.items(), key=lambda kv: -len(kv[1]))
        ],
    }


def _pct(x: float | None) -> str:
    return "?" if x is None else f"{x:.0f}%"


def notes(profile: dict) -> list[str]:
    """Plain-language scouting notes: only tendencies that clear the interval test, plus
    who takes them. Penalty notes always state the sample, which is small for any team."""
    out: list[str] = []
    c = profile["corners"]
    for z in c["zones"]:
        if z["flag"]:
            word = "more often" if z["flag"] == "more" else "less often"
            out.append(
                f"Corners: {z['label'].lower()} {word} than the rest of the league: {_pct(z['pct'])} of {c['total']} "
                f"(league {_pct(z['league_pct'])})."
            )
    for t in c["technique"]:
        if t["flag"] == "more" and t["key"] != "unknown":
            out.append(
                f"Corners: {t['label'].lower()} deliveries {_pct(t['pct'])} (league {_pct(t['league_pct'])}, "
                f"n={c['total']})."
            )
    if c["shot"]["flag"]:
        word = "more" if c["shot"]["flag"] == "more" else "fewer"
        out.append(
            f"Corners: {word} shots than average: {_pct(c['shot']['pct'])} of corners end in a shot within "
            f"15 s (league {_pct(c['shot']['league_pct'])})."
        )
    if profile["corner_takers"]:
        top = profile["corner_takers"][0]
        foot = {"R": "right foot", "L": "left foot"}.get(top["foot"], top["foot"])
        out.append(
            f"Main corner taker: {top['name']} ({top['n']} of {c['total']}, {foot}; "
            f"left side {top['sides']['L']}, right side {top['sides']['R']})."
        )
    a = profile["corners_against"]
    if a["shot"]["flag"]:
        word = "Weak" if a["shot"]["flag"] == "more" else "Strong"
        out.append(
            f"{word} defending corners: they concede a shot from {_pct(a['shot']['pct'])} of {a['total']} corners "
            f"against (league {_pct(a['shot']['league_pct'])}), {a['goals']} goals conceded."
        )
    for t in profile["penalties"]["takers"]:
        aimed = t["left"] + t["centre"] + t["right"]
        if t["n"] >= 2 and aimed:
            out.append(
                f"Penalties: {t['name']} took {t['n']} and scored {t['scored']}. On target, from the kicker's view: "
                f"{t['left']} left (goalkeeper's right), {t['centre']} centre, {t['right']} right. Small sample."
            )
    return out


@lru_cache(maxsize=1)
def teams() -> dict:
    d = load()
    by_team = Counter(c["team"] for c in d["corners"])
    pens = Counter(p["team"] for p in d["penalties"])
    return {
        **_source(d),
        "teams": [
            {"id": slug(t), "name": t, "matches": n, "corners": by_team[t], "penalties": pens[t]}
            for t, n in d["matches_played"].items()
        ],
    }


def _source(d: dict) -> dict:
    return {
        "source": d["source"],
        "source_url": d["source_url"],
        "competition": d["competition"],
        "season": d["season"],
        "matches": d["matches"],
    }


@lru_cache(maxsize=32)
def team_profile(team_id: str) -> dict | None:
    d = load()
    team = next((t for t in d["matches_played"] if slug(t) == team_id), None)
    if team is None:
        return None
    n_m = d["matches_played"][team]
    ref_m = sum(d["matches_played"].values()) - n_m
    corners = d["corners"]
    own = [c for c in corners if c["team"] == team]
    rest = [c for c in corners if c["team"] != team]
    against = [c for c in corners if c["opp"] == team]
    rest_against = [c for c in corners if c["opp"] != team]
    profile = {
        **_source(d),
        "id": team_id,
        "team": team,
        "team_matches": n_m,
        "min_n": MIN_N,
        "corners": _corner_block(own, rest, n_m, ref_m),
        "corner_takers": _takers(own),
        # Delivery end points for the pitch map: x, y, side, technique, result.
        "corner_points": [
            [c["x"], c["y"], c["side"], _tech(c), "goal" if c["goal"] else "shot" if c["shot"] else "none"] for c in own
        ],
        "corners_against": _corner_block(against, rest_against, n_m, ref_m),
        "penalties": _kick_rows(
            [p for p in d["penalties"] if p["team"] == team], [p for p in d["penalties"] if p["team"] != team]
        ),
        "free_kicks": _kick_rows(
            [f for f in d["free_kicks"] if f["team"] == team], [f for f in d["free_kicks"] if f["team"] != team]
        ),
    }
    profile["notes"] = notes(profile)
    return profile
