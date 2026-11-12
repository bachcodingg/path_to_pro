"""Pro player analysis from the StatsBomb competitions: one player's season, and the players
the Pro League app features.

- Featured squads: every player of the clubs in `FEATURED`, in each competition the open data
  has them for. Bayern Munich are not here: the open data has none of their league seasons
  (they appear only as Leverkusen's opponent), so their squad comes from the 2024/25 season
  data (`scouting.season`) instead.
- Best of the rest: for every other club with a full season in the data, the player with the
  most goals plus assists (more minutes break a tie) among those who played at least
  `REGULAR_MINUTES`. It is a plain rule anyone can check, and it favours attackers.
- A player's profile: season totals, per-90 rates, every shot, and for a full-season league a
  percentile against the league's other regulars in the same position group (at least
  `REGULAR_MINUTES`). A club season (one club's matches only) has no fair comparison group,
  so it shows the numbers without percentiles.

Pure functions over the `_play.json` rows written by `scouting.statsbomb`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache

from scouting import style
from scouting.analysis import slug
from scouting.competitions import COMPETITIONS

FEATURED: tuple[tuple[str, str], ...] = (
    ("la-liga", "Real Madrid"),
    ("la-liga", "Barcelona"),
    ("ligue-1-psg", "Paris Saint-Germain"),
    ("ligue-1", "Paris Saint-Germain"),
    ("premier-league", "Manchester City"),
    ("premier-league", "Manchester United"),
    ("premier-league", "Chelsea"),
    ("premier-league", "Liverpool"),
    ("premier-league", "Arsenal"),
)
NOT_IN_OPEN_DATA = {
    "Bayern Munich": "The open data has none of Bayern's league seasons, only their matches against Leverkusen. "
    "Their squad is in the 2024/25 season numbers."
}
REGULAR_MINUTES = 900  # ten full matches: a regular, and enough for per-90 rates to settle
GROUPS = ("Goalkeeper", "Defender", "Midfielder", "Forward")


def group(position: str | None) -> str | None:
    """StatsBomb's position names into four groups.

    >>> [group(p) for p in ("Goalkeeper", "Left Wing Back", "Center Attacking Midfield", "Right Wing", None)]
    ['Goalkeeper', 'Defender', 'Midfielder', 'Forward', None]
    """
    if not position:
        return None
    if "Goalkeeper" in position:
        return "Goalkeeper"
    if "Back" in position:
        return "Defender"
    if "Midfield" in position:
        return "Midfielder"
    return "Forward"


def _per90(key: str) -> Callable[[dict], float | None]:
    return lambda p: 90 * p.get(key, 0) / p["minutes"] if p["minutes"] > 0 else None


def _share(k: str, n: str, min_n: int) -> Callable[[dict], float | None]:
    return lambda p: 100 * p.get(k, 0) / p[n] if p.get(n, 0) >= min_n else None


def _np_goals90(p: dict) -> float:
    return 90 * (p.get("goals", 0) - p.get("pen_goals", 0)) / p["minutes"]


def _tackles_int90(p: dict) -> float:
    return 90 * (p.get("tackles", 0) + p.get("interceptions", 0)) / p["minutes"]


def _aerial_pct(p: dict) -> float | None:
    duels = p.get("aerial_won", 0) + p.get("aerial_lost", 0)
    return 100 * p.get("aerial_won", 0) / duels if duels >= 20 else None


@dataclass(frozen=True)
class Measure:
    key: str
    label: str
    value: Callable[[dict], float | None]
    unit: str = ""  # "%" for shares, "" for per 90
    help: str = ""


MEASURES: dict[str, Measure] = {
    m.key: m
    for m in (
        Measure("np_goals90", "Non-penalty goals", _np_goals90),
        Measure("np_xg90", "Non-penalty xG", _per90("np_xg"), help="Expected goals from his shots, penalties left out"),
        Measure("shots90", "Shots", _per90("shots")),
        Measure("assists90", "Assists", _per90("assists")),
        Measure("key_passes90", "Key passes", _per90("key_passes"), help="Passes that set up a shot"),
        Measure("box_passes90", "Passes into the box", _per90("box_pass_cmp")),
        Measure("final_third90", "Passes into the final third", _per90("final_third_cmp")),
        Measure("dribbles90", "Dribbles completed", _per90("dribbles_cmp")),
        Measure("dribble_pct", "Dribble success", _share("dribbles_cmp", "dribbles", 15), "%"),
        Measure("pass_acc", "Pass accuracy", _share("passes_cmp", "passes", 100), "%"),
        Measure("long_acc", "Long pass accuracy", _share("long_cmp", "long", 30), "%"),
        Measure("pressures90", "Pressures", _per90("pressures")),
        Measure("high_press90", "Pressures in the final third", _per90("pressures_high")),
        Measure("recoveries90", "Ball recoveries", _per90("recoveries")),
        Measure("tackles_int90", "Tackles + interceptions", _tackles_int90),
        Measure("clearances90", "Clearances", _per90("clearances")),
        Measure("blocks90", "Blocks", _per90("blocks")),
        Measure("aerial_won90", "Aerial duels won", _per90("aerial_won")),
        Measure("aerial_pct", "Aerial duel success", _aerial_pct, "%"),
        Measure("passes90", "Passes", _per90("passes")),
    )
}
BY_GROUP: dict[str, tuple[str, ...]] = {
    "Forward": ("np_goals90", "np_xg90", "shots90", "assists90", "key_passes90", "box_passes90", "dribbles90",
                "dribble_pct", "high_press90"),
    "Midfielder": ("np_goals90", "assists90", "key_passes90", "final_third90", "pass_acc", "long_acc", "dribbles90",
                   "tackles_int90", "pressures90", "recoveries90"),
    "Defender": ("tackles_int90", "clearances90", "blocks90", "aerial_won90", "aerial_pct", "pass_acc", "long_acc",
                 "final_third90", "pressures90", "recoveries90"),
    "Goalkeeper": ("passes90", "pass_acc", "long_acc"),
}  # fmt: skip


def _players(comp: str) -> list[dict]:
    return [p for p in style.load(comp)["players"] if p["minutes"] > 0]


def _summary(p: dict) -> dict:
    return {
        "name": p["name"],
        "id": slug(p["name"]),
        "position": p["position"],
        "group": group(p["position"]),
        "matches": p["matches"],
        "minutes": round(p["minutes"]),
        "goals": int(p.get("goals", 0)),
        "assists": int(p.get("assists", 0)),
        "xg": round(p.get("xg", 0), 2),
    }


def _team_meta(comp: str, team: str) -> dict:
    c = COMPETITIONS[comp]
    return {
        "comp": comp,
        "competition": c.name,
        "season": c.season,
        "coverage": c.coverage,
        "team": team,
        "team_id": slug(team),
    }


def best_of(comp: str, team: str) -> dict | None:
    """The team's player with the most goals plus assists among its regulars."""
    regulars = [p for p in _players(comp) if p["team"] == team and p["minutes"] >= REGULAR_MINUTES]
    if not regulars:
        return None
    return _summary(max(regulars, key=lambda p: (p.get("goals", 0) + p.get("assists", 0), p["minutes"])))


@lru_cache(maxsize=1)
def hub() -> dict:
    """The featured squads in full, then the best player of every other club."""
    featured = []
    for comp, team in FEATURED:
        squad = sorted((p for p in _players(comp) if p["team"] == team), key=lambda p: -p["minutes"])
        featured.append(_team_meta(comp, team) | {"players": [_summary(p) for p in squad]})
    featured_names = {team for _, team in FEATURED}
    best = []
    for key, c in COMPETITIONS.items():
        if c.coverage == "finals":
            continue
        clubs = [c.featured] if c.coverage == "club" else sorted(style.load(key)["matches_played"])
        for team in clubs:
            if team in featured_names:
                continue
            player = best_of(key, team)
            if player:
                best.append(_team_meta(key, team) | {"player": player})
    return {
        "source": "StatsBomb Open Data",
        "source_url": "https://github.com/statsbomb/open-data",
        "regular_minutes": REGULAR_MINUTES,
        "featured": featured,
        "best": best,
        "not_in_open_data": [{"team": t, "why": why} for t, why in NOT_IN_OPEN_DATA.items()],
    }


def _percentile(value: float, peers: list[float]) -> int:
    """Share of the peers below the value, ties counted half: 50 is the middle of the group."""
    below = sum(v < value for v in peers)
    same = sum(v == value for v in peers)
    return round(100 * (below + same / 2) / len(peers))


@lru_cache(maxsize=256)
def profile(comp: str, team_id: str, player_id: str) -> dict | None:
    """One player's season: totals, per-90 rates with percentiles, and every shot."""
    team = style._team(team_id, comp)
    if team is None:
        return None
    p = next((x for x in _players(comp) if x["team"] == team and slug(x["name"]) == player_id), None)
    if p is None:
        return None
    c = COMPETITIONS[comp]
    grp = group(p["position"])
    league = c.coverage == "league"
    regular = p["minutes"] >= REGULAR_MINUTES
    peers = (
        [x for x in _players(comp) if group(x["position"]) == grp and x["minutes"] >= REGULAR_MINUTES] if league else []
    )
    measures = []
    for key in BY_GROUP.get(grp or "", ()):
        m = MEASURES[key]
        value = m.value(p) if p["minutes"] >= style.MIN_PLAYER_MINUTES else None
        ref = [v for x in peers if (v := m.value(x)) is not None]
        pct = _percentile(value, ref) if value is not None and regular and len(ref) >= 10 else None
        measures.append({
            "key": key, "label": m.label, "unit": m.unit, "help": m.help,
            "value": None if value is None else round(value, 2 if not m.unit else 1),
            "percentile": pct, "peers": len(ref) if pct is not None else None,
            "peer_median": round(sorted(ref)[len(ref) // 2], 2 if not m.unit else 1) if pct is not None else None,
        })  # fmt: skip
    d = style.load(comp)
    cols = {k: i for i, k in enumerate(d["shot_columns"])}
    keep = ("x", "y", "xg", "outcome", "body", "pattern", "type", "minute")
    shots = [
        [s[cols[k]] for k in keep] for s in d["shots"] if s[cols["team"]] == team and s[cols["player"]] == p["name"]
    ]
    if not league:
        why = f"Only {c.featured}'s matches are in the open data, so there is no fair group to rank him against."
    elif not regular:
        why = f"Ranked only from {REGULAR_MINUTES} minutes; he played {round(p['minutes'])}."
    else:
        why = None
    return {
        "source": "StatsBomb Open Data",
        "source_url": "https://github.com/statsbomb/open-data",
        **_team_meta(comp, team),
        **_summary(p),
        "totals": {
            "goals": int(p.get("goals", 0)),
            "pen_goals": int(p.get("pen_goals", 0)),
            "head_goals": int(p.get("head_goals", 0)),
            "out_goals": int(p.get("out_goals", 0)),
            "xg": round(p.get("xg", 0), 2),
            "np_xg": round(p.get("np_xg", 0), 2),
            "shots": int(p.get("shots", 0)),
            "shots_on_target": int(p.get("shots_ot", 0)),
            "assists": int(p.get("assists", 0)),
            "key_passes": int(p.get("key_passes", 0)),
            "passes": int(p.get("passes", 0)),
            "pass_acc": None if not p.get("passes") else round(100 * p.get("passes_cmp", 0) / p["passes"], 1),
            "dribbles": int(p.get("dribbles_cmp", 0)),
            "tackles": int(p.get("tackles", 0)),
            "interceptions": int(p.get("interceptions", 0)),
            "aerial_won": int(p.get("aerial_won", 0)),
            "yellow": int(p.get("yellow", 0)),
            "red": int(p.get("red", 0)),
        },
        "compared_with": f"{len(peers)} {grp.lower()}s with {REGULAR_MINUTES}+ minutes in {c.name} {c.season}"
        if league and grp
        else None,
        "no_percentiles": why,
        "measures": measures,
        "shot_columns": list(keep),
        "shots": shots,
    }
