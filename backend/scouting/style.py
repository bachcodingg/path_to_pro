"""How a team plays: passing, shooting, duels, pressing and discipline over a season,
compared with the rest of the league, plus a player table and a shot map.

Each measure is computed from the per-match team counts in `laliga_2015_16_play.json`
(see `scouting.play` for the event definitions). A share is pooled over the season
(all completed long passes / all long passes); a rate is a per-match mean. The 95%
interval comes from match-to-match variation (t distribution over the team's matches),
not from the number of passes, because passes within a match are not independent: a
team that plays long in one match plays long all match. A measure is called a strength,
weakness or style trait only when that interval excludes the rest of the league's value.
"""

from __future__ import annotations

import json
import math
import statistics
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from scouting.analysis import slug

DATA = Path(__file__).resolve().parent / "data" / "laliga_2015_16_play.json"
MIN_PLAYER_MINUTES = 450  # five full matches before per-90 numbers mean much
# Two-sided 95% t quantiles; a team plays 38 matches, fewer count for a share with no attempts that day.
_T95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
        12: 2.179, 15: 2.131, 20: 2.086, 25: 2.060, 30: 2.042, 37: 2.026}  # fmt: skip


@lru_cache(maxsize=1)
def load(path: Path = DATA) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


Row = dict  # one team in one match, with its opponent's counts under "o"


@dataclass(frozen=True)
class Metric:
    key: str
    group: str
    label: str
    num: Callable[[Row], float]
    den: Callable[[Row], float] | None = None  # None: a per-match rate
    better: str | None = None  # "high", "low", or None for a matter of style
    unit: str = ""  # "%" for shares
    digits: int = 1
    help: str = ""


def g(key: str) -> Callable[[Row], float]:
    return lambda r: r.get(key, 0)


def o(key: str) -> Callable[[Row], float]:
    return lambda r: r["o"].get(key, 0)


def np_shots(r: Row) -> float:
    return r.get("shots", 0) - r.get("pen_shots", 0)


def np_goals(r: Row) -> float:
    return r.get("goals", 0) - r.get("pen_goals", 0)


def aerials(r: Row) -> float:
    return r.get("aerial_won", 0) + r.get("aerial_lost", 0)


GROUPS = {
    "results": "Results",
    "passing": "Passing",
    "shooting": "Shooting",
    "duels": "Duels and headers",
    "defending": "Pressing and defending",
    "discipline": "Discipline",
}

METRICS: tuple[Metric, ...] = (
    # Results
    Metric("goals", "results", "Goals a match", g("gf"), better="high", digits=2),
    Metric("conceded", "results", "Goals conceded a match", g("ga"), better="low", digits=2),
    Metric("xg", "results", "xG a match", g("xg"), better="high", digits=2, help="Expected goals from all shots"),
    Metric("xga", "results", "xG conceded a match", o("xg"), better="low", digits=2),
    Metric("possession", "results", "Share of the match's passes", g("passes_all"),
           lambda r: r.get("passes_all", 0) + r["o"].get("passes_all", 0), unit="%",
           help="A stand-in for possession: StatsBomb's open data has no possession clock"),
    # Passing
    Metric("passes", "passing", "Open-play passes a match", g("passes"), digits=0),
    Metric("pass_acc", "passing", "Pass accuracy", g("passes_cmp"), g("passes"), "high", "%"),
    Metric("short_acc", "passing", "Short pass accuracy (< 15 yd)", g("short_cmp"), g("short"), "high", "%"),
    Metric("medium_acc", "passing", "Medium pass accuracy (15-35 yd)", g("medium_cmp"), g("medium"), "high", "%"),
    Metric("long_acc", "passing", "Long pass accuracy (35+ yd)", g("long_cmp"), g("long"), "high", "%"),
    Metric("long_share", "passing", "Long-ball share of passes", g("long"), g("passes"), unit="%",
           help="How direct they play: share of open-play passes of 35 yards or more"),
    Metric("crosses", "passing", "Crosses a match", g("cross")),
    Metric("cross_acc", "passing", "Cross accuracy", g("cross_cmp"), g("cross"), "high", "%"),
    Metric("through", "passing", "Through balls a match", g("through"), better="high"),
    Metric("final_third", "passing", "Completed passes into the final third", g("final_third_cmp"), better="high"),
    Metric("box_passes", "passing", "Completed passes into the box", g("box_pass_cmp"), better="high"),
    Metric("key_passes", "passing", "Key passes a match", g("key_passes"), better="high",
           help="Passes followed directly by a shot"),
    Metric("switches", "passing", "Switches of play a match", g("switch")),
    Metric("head_pass_acc", "passing", "Headed pass accuracy", g("head_pass_cmp"), g("head_pass"), "high", "%"),
    Metric("gk_long", "passing", "Goal kicks played long", g("goal_kicks_long"), g("goal_kicks"), unit="%",
           help="Build-up from the goalkeeper: share of goal kicks of 35 yards or more"),
    # Shooting
    Metric("shots", "shooting", "Shots a match", g("shots"), better="high"),
    Metric("on_target", "shooting", "Shots on target", g("shots_ot"), g("shots"), "high", "%"),
    Metric("conversion", "shooting", "Conversion (non-penalty)", np_goals, np_shots, "high", "%"),
    Metric("xg_per_shot", "shooting", "xG per shot (non-penalty)", g("np_xg"), np_shots, "high", digits=3,
           help="Average chance quality"),
    Metric("six_share", "shooting", "Shots from tap-in range", g("six_shots"), np_shots, unit="%",
           help="Inside the six-yard box"),
    Metric("six_conv", "shooting", "Tap-in range conversion", g("six_goals"), g("six_shots"), "high", "%"),
    Metric("box_conv", "shooting", "Conversion elsewhere in the box", g("box_goals"), g("box_shots"), "high", "%"),
    Metric("long_share_shots", "shooting", "Long shots (outside the box)", g("out_shots"), np_shots, unit="%"),
    Metric("long_conv", "shooting", "Long-shot conversion", g("out_goals"), g("out_shots"), "high", "%"),
    Metric("head_shots", "shooting", "Headed shots a match", g("head_shots")),
    Metric("head_conv", "shooting", "Headed shot conversion", g("head_goals"), g("head_shots"), "high", "%"),
    Metric("big_chances", "shooting", "Big chances a match (xG >= 0.3)", g("big_chances"), better="high"),
    Metric("big_conv", "shooting", "Big chances scored", g("big_chance_goals"), g("big_chances"), "high", "%"),
    Metric("counter_shots", "shooting", "Shots from counter-attacks a match", g("counter_shots"), better="high"),
    Metric("set_piece_shots", "shooting", "Shots from set plays a match", g("set_piece_shots"), better="high",
           help="Corners, free kicks and throw-ins, excluding penalties"),
    Metric("first_time", "shooting", "First-time shots", g("first_time_shots"), np_shots, unit="%"),
    # Duels and headers
    Metric("aerial_win", "duels", "Aerial duels won", g("aerial_won"), aerials, "high", "%"),
    Metric("aerials", "duels", "Aerial duels a match", aerials),
    Metric("dribble_success", "duels", "Dribbles completed", g("dribbles_cmp"), g("dribbles"), "high", "%"),
    Metric("dribbles", "duels", "Dribbles a match", g("dribbles")),
    Metric("tackle_success", "duels", "Tackles won", g("tackles_cmp"), g("tackles"), "high", "%"),
    # Pressing and defending
    Metric("ppda", "defending", "Passes allowed per defensive action (PPDA)", o("passes_own60"),
           g("def_actions_opp60"), "low", digits=1,
           help="Opponent passes in their own 60% per tackle, interception or foul there. Lower = more pressing"),
    Metric("pressures", "defending", "Pressures a match", g("pressures"), digits=0),
    Metric("high_press", "defending", "Pressures in the attacking third", g("pressures_high"), g("pressures"), unit="%"),
    Metric("counterpress", "defending", "Counter-pressures a match", g("counterpress"), digits=0,
           help="Pressure within 5 seconds of losing the ball"),
    Metric("high_recoveries", "defending", "Ball recoveries in the attacking third", g("recoveries_high"), better="high"),
    Metric("interceptions", "defending", "Interceptions a match", g("interceptions")),
    Metric("clearances", "defending", "Clearances a match", g("clearances")),
    Metric("blocks", "defending", "Blocks a match", g("blocks")),
    Metric("shots_against", "defending", "Shots conceded a match", o("shots"), better="low"),
    Metric("xga_per_shot", "defending", "xG per shot conceded", o("np_xg"),
           lambda r: r["o"].get("shots", 0) - r["o"].get("pen_shots", 0), "low", digits=3,
           help="How good the chances they allow are"),
    Metric("long_shots_against", "defending", "Opponent shots from outside the box", o("out_shots"),
           lambda r: r["o"].get("shots", 0) - r["o"].get("pen_shots", 0), "high", "%",
           help="A compact defence keeps opponents shooting from distance"),
    Metric("aerial_against", "defending", "Opponent headed shots a match", o("head_shots"), better="low"),
    # Discipline
    Metric("fouls", "discipline", "Fouls a match", g("fouls"), better="low"),
    Metric("fouls_won", "discipline", "Fouls won a match", g("fouls_won")),
    Metric("yellow", "discipline", "Yellow cards a match", g("yellow"), better="low", digits=2),
    Metric("red", "discipline", "Red cards a match", g("red"), better="low", digits=2),
    Metric("offsides", "discipline", "Offsides a match", g("offsides")),
)  # fmt: skip
BY_KEY = {m.key: m for m in METRICS}


@lru_cache(maxsize=1)
def rows_by_team() -> dict[str, list[Row]]:
    """Each team-match row with the opponent's counts attached under "o"."""
    d = load()
    by_match: dict[int, list[dict]] = {}
    for r in d["team_matches"]:
        by_match.setdefault(r["m"], []).append(r)
    out: dict[str, list[Row]] = {}
    for pair in by_match.values():
        a, b = pair
        out.setdefault(a["team"], []).append(a | {"o": b})
        out.setdefault(b["team"], []).append(b | {"o": a})
    return out


def _t95(n: int) -> float:
    df = n - 1
    return _T95[max(k for k in _T95 if k <= df)]  # the next smaller df: slightly wide, never narrow


def season_value(m: Metric, rows: list[Row]) -> float | None:
    if m.den is None:
        return statistics.fmean(m.num(r) for r in rows) if rows else None
    den = sum(m.den(r) for r in rows)
    return sum(m.num(r) for r in rows) / den if den else None


def _scale(m: Metric, v: float | None) -> float | None:
    return None if v is None else (100 * v if m.unit == "%" else v)


def measure(m: Metric, team: str, by_team: dict[str, list[Row]]) -> dict:
    rows = by_team[team]
    rest = [r for t, rs in by_team.items() if t != team for r in rs]
    value = season_value(m, rows)
    league = season_value(m, rest)
    per_match = [m.num(r) / m.den(r) if m.den else m.num(r) for r in rows if m.den is None or m.den(r) > 0]
    half = _t95(len(per_match)) * statistics.stdev(per_match) / math.sqrt(len(per_match)) if len(per_match) > 2 else None
    lo, hi = (value - half, value + half) if value is not None and half is not None else (None, None)
    flag = None
    if lo is not None and league is not None:
        flag = "high" if lo > league else "low" if hi < league else None
    values = {t: season_value(m, rs) for t, rs in by_team.items()}
    ordered = sorted((v for v in values.values() if v is not None), reverse=m.better != "low")
    rank = ordered.index(value) + 1 if value is not None else None
    verdict = None
    if flag and m.better:
        verdict = "strength" if (flag == "high") == (m.better == "high") else "weakness"
    elif flag:
        verdict = "style"
    return {
        "key": m.key,
        "group": m.group,
        "label": m.label,
        "unit": m.unit,
        "digits": m.digits,
        "better": m.better,
        "help": m.help,
        "value": _round(_scale(m, value), m),
        "lo": _round(_scale(m, lo), m),
        "hi": _round(_scale(m, hi), m),
        "league": _round(_scale(m, league), m),
        "league_min": _round(_scale(m, min(ordered)), m) if ordered else None,
        "league_max": _round(_scale(m, max(ordered)), m) if ordered else None,
        "rank": rank,
        "teams": len(ordered),
        "flag": flag,
        "verdict": verdict,
    }


def _round(v: float | None, m: Metric) -> float | None:
    return None if v is None else round(v, m.digits + (1 if m.unit == "%" else 0))


def _ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _fmt(x: dict, v: float | None) -> str:
    if v is None:
        return "–"
    return f"{v:.{0 if x['unit'] == '%' else x['digits']}f}{x['unit']}"


def rank_text(x: dict) -> str:
    """'best in the league', '3rd best of 20', '2nd worst of 20'; for style measures
    'highest' / 'lowest', counted from whichever end is nearer.

    >>> rank_text({"rank": 19, "teams": 20, "better": None})
    '2nd lowest of 20'
    """
    rank, n = x["rank"], x["teams"]
    if rank is None:
        return ""
    top, bottom = ("best", "worst") if x["better"] else ("highest", "lowest")
    if rank == 1:
        return f"{top} in the league"
    if rank == n:
        return f"{bottom} in the league"
    return f"{_ordinal(rank)} {top} of {n}" if rank <= (n + 1) // 2 else f"{_ordinal(n - rank + 1)} {bottom} of {n}"


def summary(measures: list[dict], limit: int = 6) -> dict[str, list[str]]:
    """Strengths, weaknesses and style traits, most distinctive first (largest gap from
    the league relative to the team's own interval)."""

    def gap(x: dict) -> float:
        width = (x["hi"] - x["lo"]) / 2 or 1e-9
        return abs(x["value"] - x["league"]) / width

    out: dict[str, list[str]] = {"strength": [], "weakness": [], "style": []}
    for x in sorted((x for x in measures if x["verdict"]), key=gap, reverse=True):
        bucket = out[x["verdict"]]
        if len(bucket) < limit:
            bucket.append(f"{x['label']}: {_fmt(x, x['value'])} ({rank_text(x)}; league {_fmt(x, x['league'])})")
    return out


def standings(venue: str = "all") -> list[dict]:
    """League table from the match scores: the data check that every match is there.

    venue "home" or "away" counts only those matches, as the league's own home / away tables do.
    form: the last five results, oldest first ("W", "D", "L").
    """
    table: dict[str, dict] = {}
    for team, all_rows in rows_by_team().items():
        rows = [r for r in all_rows if venue == "all" or r["home"] == (venue == "home")]
        w = sum(r["gf"] > r["ga"] for r in rows)
        dr = sum(r["gf"] == r["ga"] for r in rows)
        gf, ga = sum(r["gf"] for r in rows), sum(r["ga"] for r in rows)
        recent = sorted(rows, key=lambda r: (r.get("date") or "", r["m"]))[-5:]
        form = ["W" if r["gf"] > r["ga"] else "D" if r["gf"] == r["ga"] else "L" for r in recent]
        table[team] = {"team": team, "id": slug(team), "played": len(rows), "won": w, "drawn": dr,
                       "lost": len(rows) - w - dr, "gf": gf, "ga": ga, "points": 3 * w + dr, "form": form}  # fmt: skip
    ordered = sorted(table.values(), key=lambda t: (-t["points"], -(t["gf"] - t["ga"]), -t["gf"]))
    return [t | {"position": i} for i, t in enumerate(ordered, 1)]


def _team(team_id: str) -> str | None:
    return next((t for t in rows_by_team() if slug(t) == team_id), None)


@lru_cache(maxsize=32)
def style_profile(team_id: str) -> dict | None:
    team = _team(team_id)
    if team is None:
        return None
    by_team = rows_by_team()
    measures = [measure(m, team, by_team) for m in METRICS]
    table = next(t for t in standings() if t["team"] == team)
    return {
        "id": team_id,
        "team": team,
        "matches": len(by_team[team]),
        "standing": table,
        "groups": [{"key": k, "label": v} for k, v in GROUPS.items()],
        "measures": measures,
        "summary": summary(measures),
    }


def _per90(p: dict, key: str) -> float | None:
    return round(90 * p.get(key, 0) / p["minutes"], 2) if p["minutes"] >= MIN_PLAYER_MINUTES else None


def _pct(k: float, n: float, min_n: int) -> float | None:
    return round(100 * k / n, 1) if n >= min_n else None


def player_rows(team_id: str) -> dict | None:
    """Every player who played for the team, with season totals, per-90 rates and accuracies.
    Rates are left empty below `MIN_PLAYER_MINUTES`, accuracies below a minimum of attempts."""
    team = _team(team_id)
    if team is None:
        return None
    rows = []
    for p in load()["players"]:
        if p["team"] != team or p["minutes"] <= 0:
            continue
        enough = p["minutes"] >= MIN_PLAYER_MINUTES
        air = p.get("aerial_won", 0) + p.get("aerial_lost", 0)
        rows.append({
            "name": p["name"],
            "position": p["position"],
            "matches": p["matches"],
            "minutes": round(p["minutes"]),
            "goals": int(p.get("goals", 0)),
            "pen_goals": int(p.get("pen_goals", 0)),
            "six_goals": int(p.get("six_goals", 0)),
            "out_goals": int(p.get("out_goals", 0)),
            "head_goals": int(p.get("head_goals", 0)),
            "xg": round(p.get("xg", 0), 2),
            "shots": int(p.get("shots", 0)),
            "shots90": _per90(p, "shots"),
            "conversion": _pct(p.get("goals", 0) - p.get("pen_goals", 0), p.get("shots", 0) - p.get("pen_shots", 0), 10),
            "assists": int(p.get("assists", 0)),
            "key_passes90": _per90(p, "key_passes"),
            "passes90": _per90(p, "passes"),
            "pass_acc": _pct(p.get("passes_cmp", 0), p.get("passes", 0), 100),
            "short_acc": _pct(p.get("short_cmp", 0), p.get("short", 0), 50),
            "long_acc": _pct(p.get("long_cmp", 0), p.get("long", 0), 30),
            "crosses_cmp": int(p.get("cross_cmp", 0)),
            "final_third90": _per90(p, "final_third_cmp"),
            "aerial_won": int(p.get("aerial_won", 0)),
            "aerial_pct": _pct(p.get("aerial_won", 0), air, 20),
            "dribbles90": _per90(p, "dribbles_cmp"),
            "dribble_pct": _pct(p.get("dribbles_cmp", 0), p.get("dribbles", 0), 15),
            "tackles_int90": round(90 * (p.get("tackles", 0) + p.get("interceptions", 0)) / p["minutes"], 2)
            if enough
            else None,
            "pressures90": _per90(p, "pressures"),
            "recoveries90": _per90(p, "recoveries"),
            "yellow": int(p.get("yellow", 0)),
            "red": int(p.get("red", 0)),
        })  # fmt: skip
    return {"team": team, "min_minutes": MIN_PLAYER_MINUTES, "players": sorted(rows, key=lambda r: -r["minutes"])}


def shot_map(team_id: str) -> dict | None:
    """The team's shots and the shots it conceded, for the pitch map."""
    team = _team(team_id)
    if team is None:
        return None
    d = load()
    cols = {c: i for i, c in enumerate(d["shot_columns"])}
    opp_of = {(r["m"], r["team"]): r["opp"] for r in d["team_matches"]}
    keep = ("x", "y", "xg", "outcome", "body", "pattern", "type", "player", "minute")
    own, against = [], []
    for s in d["shots"]:
        row = [s[cols[k]] for k in keep]
        if s[cols["team"]] == team:
            own.append(row)
        elif opp_of.get((s[cols["m"]], s[cols["team"]])) == team:
            against.append(row)
    return {"team": team, "columns": list(keep), "for": own, "against": against}
