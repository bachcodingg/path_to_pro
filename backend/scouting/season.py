"""Pro player analysis for the 2024/25 season, from API-Football's season totals
(`scouting.apifootball` writes data/season_2024_25.json). Season totals, not match events:
there are no shot maps here, but there are the squads as they are now, Mbappé at Real Madrid
included, and Bayern Munich, whose league seasons the free event data does not have.

- Featured squads: every player of the clubs in `FEATURED`, with their league numbers.
- Best of the rest: for every other club, the regular (`REGULAR_MINUTES`+) with the most goals
  plus assists, more minutes breaking a tie: the same rule as `scouting.players`.
- A player's profile: totals, per-90 rates, and a percentile against the regulars in the same
  position group across every league in the file.

Without the data file every function says so (`available: False`) instead of failing.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache

from scouting.analysis import slug
from scouting.apifootball import FEATURED, OUT

REGULAR_MINUTES = 900


@lru_cache(maxsize=1)
def load() -> dict | None:
    """The data file, or None when there is none or no club is fully in yet."""
    d = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else None
    return d if d and d.get("leagues") else None


def _all() -> list[dict]:
    d = load() or {"leagues": []}
    return [p | {"league": lg["name"]} for lg in d["leagues"] for p in lg["players"] if p["minutes"] > 0]


def _summary(p: dict) -> dict:
    return {
        "id": p["id"],
        "name": p["name"],
        "slug": slug(p["name"] or str(p["id"])),
        "age": p.get("age"),
        "nationality": p.get("nationality"),
        "position": p["position"],
        "apps": p["apps"],
        "minutes": p["minutes"],
        "rating": p.get("rating"),
        "goals": p["goals"],
        "assists": p["assists"],
    }


def _team_name(p: dict) -> str:
    return FEATURED.get(p["team_id"], p["team"])


def _per90(key: str) -> Callable[[dict], float | None]:
    return lambda p: 90 * p.get(key, 0) / p["minutes"]


def _share(k: str, n: str, min_n: int) -> Callable[[dict], float | None]:
    return lambda p: 100 * p.get(k, 0) / p[n] if p.get(n, 0) >= min_n else None


def _np_goals90(p: dict) -> float:
    return 90 * (p["goals"] - p.get("pen_scored", 0)) / p["minutes"]


@dataclass(frozen=True)
class Measure:
    key: str
    label: str
    value: Callable[[dict], float | None]
    unit: str = ""
    lower_is_better: bool = False


MEASURES: dict[str, Measure] = {
    m.key: m
    for m in (
        Measure("rating", "Average match rating", lambda p: p.get("rating"), "/10"),
        Measure("np_goals90", "Non-penalty goals", _np_goals90),
        Measure("assists90", "Assists", _per90("assists")),
        Measure("shots90", "Shots", _per90("shots")),
        Measure("shots_on_pct", "Shots on target", _share("shots_on", "shots", 15), "%"),
        Measure("key_passes90", "Key passes", _per90("key_passes")),
        Measure("dribbles90", "Dribbles completed", _per90("dribbles_won")),
        Measure("dribble_pct", "Dribble success", _share("dribbles_won", "dribbles", 15), "%"),
        Measure("duel_pct", "Duels won", _share("duels_won", "duels", 50), "%"),
        Measure("tackles90", "Tackles", _per90("tackles")),
        Measure("interceptions90", "Interceptions", _per90("interceptions")),
        Measure("blocks90", "Blocks", _per90("blocks")),
        Measure("passes90", "Passes", _per90("passes")),
        Measure("fouls_drawn90", "Fouls won", _per90("fouls_drawn")),
        Measure("saves90", "Saves", _per90("saves")),
        Measure("conceded90", "Goals conceded", _per90("conceded"), lower_is_better=True),
    )
}
BY_GROUP: dict[str, tuple[str, ...]] = {
    "Attacker": ("rating", "np_goals90", "assists90", "shots90", "shots_on_pct", "key_passes90", "dribbles90",
                 "dribble_pct", "duel_pct", "fouls_drawn90"),
    "Midfielder": ("rating", "np_goals90", "assists90", "key_passes90", "passes90", "dribbles90", "duel_pct",
                   "tackles90", "interceptions90"),
    "Defender": ("rating", "tackles90", "interceptions90", "blocks90", "duel_pct", "passes90", "key_passes90",
                 "assists90"),
    "Goalkeeper": ("rating", "saves90", "conceded90", "passes90"),
}  # fmt: skip


def _source() -> dict:
    d = load()
    if d is None:
        return {
            "available": False,
            "season": "2024/25",
            "source": "API-Football",
            "source_url": "https://www.api-football.com",
        }
    return {
        "available": True,
        "season": d["season"],
        "source": d["source"],
        "source_url": d["source_url"],
        "fetched": d["fetched"],
        # Clubs in so far: the free plan imports about 30 a day (scouting.apifootball)
        "clubs": d.get("clubs"),
        "clubs_total": d.get("clubs_total"),
    }


def _so_far() -> str:
    d = load() or {}
    if d.get("clubs") is None or d["clubs"] >= d["clubs_total"]:
        return ""
    return f" ({d['clubs']} of {d['clubs_total']} clubs imported so far)"


def hub() -> dict:
    if load() is None:
        return _source()
    players = _all()
    featured = []
    for team_id, name in FEATURED.items():
        squad = sorted((p for p in players if p["team_id"] == team_id), key=lambda p: -p["minutes"])
        if squad:
            featured.append(
                {
                    "team_id": team_id,
                    "team": name,
                    "league": squad[0]["league"],
                    "players": [_summary(p) for p in squad],
                }
            )
    best = []
    clubs = sorted({(p["league"], p["team_id"], p["team"]) for p in players if p["team_id"] not in FEATURED})
    for league, team_id, team in clubs:
        regulars = [p for p in players if p["team_id"] == team_id and p["minutes"] >= REGULAR_MINUTES]
        if regulars:
            top = max(regulars, key=lambda p: (p["goals"] + p["assists"], p["minutes"]))
            best.append({"league": league, "team_id": team_id, "team": team, "player": _summary(top)})
    return _source() | {"regular_minutes": REGULAR_MINUTES, "featured": featured, "best": best}


def _percentile(value: float, peers: list[float], lower_is_better: bool) -> int:
    below = sum((v > value) if lower_is_better else (v < value) for v in peers)
    same = sum(v == value for v in peers)
    return round(100 * (below + same / 2) / len(peers))


def profile(team_id: int, player_id: int) -> dict | None:
    if load() is None:
        return None
    players = _all()
    p = next((x for x in players if x["team_id"] == team_id and x["id"] == player_id), None)
    if p is None:
        return None
    regular = p["minutes"] >= REGULAR_MINUTES
    peers = [x for x in players if x["position"] == p["position"] and x["minutes"] >= REGULAR_MINUTES]
    measures = []
    for key in BY_GROUP.get(p["position"] or "", ()):
        m = MEASURES[key]
        value = m.value(p)
        ref = [v for x in peers if (v := m.value(x)) is not None]
        pct = _percentile(value, ref, m.lower_is_better) if value is not None and regular and len(ref) >= 10 else None
        measures.append({
            "key": key, "label": m.label, "unit": m.unit,
            "value": None if value is None else round(value, 2 if m.unit in ("", "/10") else 1),
            "percentile": pct, "peers": len(ref) if pct is not None else None,
            "peer_median": round(sorted(ref)[len(ref) // 2], 2) if pct is not None else None,
            "lower_is_better": m.lower_is_better,
        })  # fmt: skip
    keys = ("apps", "starts", "minutes", "goals", "assists", "pen_scored", "pen_missed", "shots", "shots_on", "passes",
            "key_passes", "tackles", "interceptions", "blocks", "duels", "duels_won", "dribbles", "dribbles_won",
            "fouls_drawn", "fouls", "yellow", "red", "saves", "conceded")  # fmt: skip
    return _source() | {
        **_summary(p),
        "team_id": team_id,
        "team": _team_name(p),
        "league": p["league"],
        "first": p.get("first"),
        "last": p.get("last"),
        "totals": {k: p.get(k, 0) for k in keys},
        "compared_with": f"{len(peers)} {(p['position'] or 'player').lower()}s with {REGULAR_MINUTES}+ league minutes "
        f"across {', '.join(lg['name'] for lg in load()['leagues'])}{_so_far()}",
        "no_percentiles": None if regular else f"Ranked only from {REGULAR_MINUTES} minutes; he played {p['minutes']}.",
        "measures": measures,
    }
