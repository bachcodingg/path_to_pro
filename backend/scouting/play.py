"""Open-play counts per team and player from StatsBomb events: passing, shooting, duels,
defending, discipline. Pure: no I/O, so tests can feed it hand-made events.

Definitions (StatsBomb pitch: 120 x 80 yards, attacking towards x = 120):

- Open-play pass: a pass that is not a set piece (corner, free kick, throw-in, goal kick,
  kick-off). Passes the data marks "Unknown" or "Injury Clearance" are not counted as
  attempts. A pass is complete when StatsBomb records no outcome.
- Short < 15 yards, medium 15-35, long >= 35 yards (32 m, the usual "long ball" cut-off).
- Final-third entry: starts before x = 80, ends at or beyond it. Box entry: starts outside
  the penalty area and ends inside it.
- Shot zones: six-yard box ("tap-in range": x >= 114, y 30-50), rest of the penalty area,
  outside the box ("long shot"). Big chance: a non-penalty shot with xG >= 0.3.
- Aerial duel won: StatsBomb's `aerial_won` on a pass, shot, clearance or miscontrol;
  lost: a Duel of type "Aerial Lost".
- High pressure / recovery: in the attacking third (x >= 80).
- PPDA denominator: tackles, interceptions and fouls in the opponent's 60% (x >= 48);
  numerator: the opponent's open-play passes in their own 60% (x < 72).
"""

from __future__ import annotations

from collections import Counter, defaultdict

SHORT_MAX, LONG_MIN = 15.0, 35.0
FINAL_THIRD_X = 80.0
BIG_CHANCE_XG = 0.3
SET_PIECE_TYPES = {"Corner", "Free Kick", "Throw-in", "Goal Kick", "Kick Off"}
NOT_ATTEMPTS = {"Unknown", "Injury Clearance"}
WON = {"Won", "Success In Play", "Success Out"}
PATTERN = {
    "Regular Play": "regular",
    "From Counter": "counter",
    "From Corner": "corner",
    "From Free Kick": "free_kick",
    "From Throw In": "throw_in",
    "From Goal Kick": "goal_kick",
    "From Keeper": "keeper",
    "From Kick Off": "kick_off",
}
BODY = {"Right Foot": "R", "Left Foot": "L", "Head": "H"}
SHOT_COLUMNS = ["m", "team", "player", "x", "y", "xg", "outcome", "body", "pattern", "type", "minute", "first_time"]


def in_box(x: float, y: float) -> bool:
    return x >= 102 and 18 <= y <= 62


def in_six(x: float, y: float) -> bool:
    return x >= 114 and 30 <= y <= 50


def shot_zone(x: float, y: float) -> str:
    """Six-yard box, rest of the penalty area, or outside it.

    >>> shot_zone(116, 40), shot_zone(108, 40), shot_zone(95, 40)
    ('six', 'box', 'out')
    """
    return "six" if in_six(x, y) else "box" if in_box(x, y) else "out"


def _minutes(events: list[dict]) -> dict[int, float]:
    """Minutes on the pitch per player id: starters from 0, substitutes from their entry,
    red cards end a player's match."""
    end = max(e["minute"] + e["second"] / 60 for e in events if e["period"] <= 4)
    on: dict[int, float] = {}
    off: dict[int, float] = {}
    for e in events:
        t = e["minute"] + e["second"] / 60
        kind = e["type"]["name"]
        if kind == "Starting XI":
            for p in e["tactics"]["lineup"]:
                on[p["player"]["id"]] = 0.0
        elif kind == "Substitution":
            off[e["player"]["id"]] = t
            on[e["substitution"]["replacement"]["id"]] = t
        else:
            card = (e.get("foul_committed") or e.get("bad_behaviour") or {}).get("card", {}).get("name")
            if card in ("Red Card", "Second Yellow") and "player" in e:
                off[e["player"]["id"]] = t
    return {pid: round(max(0.0, off.get(pid, end) - start), 1) for pid, start in on.items()}


def extract_play(match: dict, events: list[dict], names: dict[int, str]) -> dict:
    home, away = match["home_team"]["home_team_name"], match["away_team"]["away_team_name"]
    mid = match["match_id"]
    team_c: dict[str, Counter] = {home: Counter(), away: Counter()}
    player_c: dict[tuple[str, int], Counter] = defaultdict(Counter)
    positions: dict[tuple[str, int], Counter] = defaultdict(Counter)
    shots: list[list] = []
    team_of: dict[int, str] = {}
    seen_name: dict[int, str] = {}

    def add(ev: dict, key: str, v: float = 1) -> None:
        team_c[ev["team"]["name"]][key] += v
        if "player" in ev:
            player_c[(ev["team"]["name"], ev["player"]["id"])][key] += v

    def add_k(ev: dict, key: str, ok: bool) -> None:
        add(ev, key)
        if ok:
            add(ev, key + "_cmp")

    shootout: Counter = Counter()  # goals in a penalty shoot-out, kept apart from match play
    for ev in events:
        if ev["period"] > 4:  # penalty shoot-outs are not match play
            if ev["type"]["name"] == "Shot" and ev["shot"]["outcome"]["name"] == "Goal":
                shootout[ev["team"]["name"]] += 1
            continue
        kind = ev["type"]["name"]
        loc = ev.get("location") or [60.0, 40.0]
        if kind == "Starting XI":
            for p in ev["tactics"]["lineup"]:
                team_of[p["player"]["id"]] = ev["team"]["name"]
                seen_name[p["player"]["id"]] = p["player"]["name"]
        elif kind == "Substitution":
            rep = ev["substitution"]["replacement"]
            team_of[rep["id"]] = ev["team"]["name"]
            seen_name[rep["id"]] = rep["name"]
        if "player" in ev:
            team_of.setdefault(ev["player"]["id"], ev["team"]["name"])
            seen_name.setdefault(ev["player"]["id"], ev["player"]["name"])
        if "player" in ev and ev.get("position"):
            positions[(ev["team"]["name"], ev["player"]["id"])][ev["position"]["name"]] += 1

        if kind == "Pass":
            p = ev["pass"]
            ptype = p.get("type", {}).get("name")
            outcome = p.get("outcome", {}).get("name")
            ok = outcome is None
            add(ev, "passes_all")
            if p.get("aerial_won"):
                add(ev, "aerial_won")
            if p.get("shot_assist") or p.get("goal_assist"):
                add(ev, "key_passes")
            if p.get("goal_assist"):
                add(ev, "assists")
            if ptype == "Goal Kick":
                add_k(ev, "goal_kicks", ok)
                if p["length"] >= LONG_MIN:
                    add(ev, "goal_kicks_long")
            if outcome == "Pass Offside":
                add(ev, "offsides")
            if ptype in SET_PIECE_TYPES or outcome in NOT_ATTEMPTS:
                continue
            end = p["end_location"]
            add_k(ev, "passes", ok)
            length = p["length"]
            add_k(ev, "short" if length < SHORT_MAX else "long" if length >= LONG_MIN else "medium", ok)
            if p.get("cross"):
                add_k(ev, "cross", ok)
            if p.get("through_ball") or p.get("technique", {}).get("name") == "Through Ball":
                add_k(ev, "through", ok)
            if p.get("switch"):
                add_k(ev, "switch", ok)
            if p.get("body_part", {}).get("name") == "Head":
                add_k(ev, "head_pass", ok)
            if loc[0] < FINAL_THIRD_X <= end[0]:
                add_k(ev, "final_third", ok)
            if not in_box(*loc[:2]) and in_box(*end[:2]):
                add_k(ev, "box_pass", ok)
            if loc[0] < 72:
                add(ev, "passes_own60")
        elif kind == "Shot":
            s = ev["shot"]
            stype = s["type"]["name"]
            outcome = s["outcome"]["name"]
            xg = s.get("statsbomb_xg", 0.0)
            goal = outcome == "Goal"
            body = BODY.get(s.get("body_part", {}).get("name"), "O")
            pattern = PATTERN.get(ev["play_pattern"]["name"], "other")
            if s.get("aerial_won"):
                add(ev, "aerial_won")
            add(ev, "shots")
            add(ev, "xg", xg)
            if outcome in ("Goal", "Saved", "Saved to Post"):
                add(ev, "shots_ot")
            if goal:
                add(ev, "goals")
            if stype == "Penalty":
                add(ev, "pen_shots")
                add(ev, "pen_goals", goal)
            else:
                zone = shot_zone(*loc[:2])
                add(ev, f"{zone}_shots")
                add(ev, f"{zone}_goals", goal)
                add(ev, f"{zone}_xg", xg)
                add(ev, "np_xg", xg)
                if body == "H":
                    add(ev, "head_shots")
                    add(ev, "head_goals", goal)
                    add(ev, "head_xg", xg)
                if xg >= BIG_CHANCE_XG:
                    add(ev, "big_chances")
                    add(ev, "big_chance_goals", goal)
                if pattern == "counter":
                    add(ev, "counter_shots")
                    add(ev, "counter_goals", goal)
                if pattern in ("corner", "free_kick", "throw_in"):
                    add(ev, "set_piece_shots")
                    add(ev, "set_piece_goals", goal)
                if s.get("first_time"):
                    add(ev, "first_time_shots")
            shots.append([
                mid, ev["team"]["name"], names.get(ev["player"]["id"], ev["player"]["name"]),
                round(loc[0], 1), round(loc[1], 1), round(xg, 3), outcome, body, pattern,
                {"Open Play": "open", "Free Kick": "free_kick", "Penalty": "penalty", "Corner": "corner"}.get(stype, "other"),
                ev["minute"], bool(s.get("first_time")),
            ])  # fmt: skip
        elif kind == "Duel":
            d = ev["duel"]
            if d.get("type", {}).get("name") == "Aerial Lost":
                add(ev, "aerial_lost")
            elif d.get("type", {}).get("name") == "Tackle":
                add_k(ev, "tackles", d.get("outcome", {}).get("name") in WON)
                if loc[0] >= 48:
                    add(ev, "def_actions_opp60")
        elif kind == "Dribble":
            add_k(ev, "dribbles", ev["dribble"].get("outcome", {}).get("name") == "Complete")
        elif kind == "Interception":
            add_k(ev, "interceptions", ev["interception"].get("outcome", {}).get("name") in WON)
            if loc[0] >= 48:
                add(ev, "def_actions_opp60")
        elif kind == "Pressure":
            add(ev, "pressures")
            if loc[0] >= FINAL_THIRD_X:
                add(ev, "pressures_high")
            if ev.get("counterpress"):
                add(ev, "counterpress")
        elif kind == "Ball Recovery":
            if not ev.get("ball_recovery", {}).get("recovery_failure"):
                add(ev, "recoveries")
                if loc[0] >= FINAL_THIRD_X:
                    add(ev, "recoveries_high")
        elif kind == "Clearance":
            add(ev, "clearances")
            if ev.get("clearance", {}).get("aerial_won"):
                add(ev, "aerial_won")
        elif kind == "Miscontrol":
            add(ev, "miscontrols")
            if ev.get("miscontrol", {}).get("aerial_won"):
                add(ev, "aerial_won")
        elif kind == "Block":
            add(ev, "blocks")
        elif kind == "Dispossessed":
            add(ev, "dispossessed")
        elif kind == "Offside":
            add(ev, "offsides")
        elif kind == "Foul Won":
            add(ev, "fouls_won")
        if kind in ("Foul Committed", "Bad Behaviour"):
            if kind == "Foul Committed":
                add(ev, "fouls")
                if loc[0] >= 48:
                    add(ev, "def_actions_opp60")
            card = (ev.get("foul_committed") or ev.get("bad_behaviour") or {}).get("card", {}).get("name")
            if card == "Yellow Card":
                add(ev, "yellow")
            elif card in ("Red Card", "Second Yellow"):
                add(ev, "red")

    minutes = _minutes(events)
    score = {home: match["home_score"], away: match["away_score"]}
    team_stats = {
        t: {"opp": opp, "home": t == home, "gf": score[t], "ga": score[opp], **{k: round(v, 3) for k, v in c.items()}}
        for t, opp, c in ((home, away, team_c[home]), (away, home, team_c[away]))
    }
    if any(ev["period"] == 5 for ev in events):
        for t, opp in ((home, away), (away, home)):
            team_stats[t] |= {"so_gf": shootout[t], "so_ga": shootout[opp]}
    players: dict[str, dict[str, dict]] = {home: {}, away: {}}
    for pid in {pid for _, pid in player_c} | set(minutes):
        team = team_of.get(pid)
        if team is None:
            continue
        stats = {k: round(v, 3) for k, v in player_c[(team, pid)].items()}
        pos = positions[(team, pid)].most_common(1)
        players[team][names.get(pid) or seen_name.get(pid, str(pid))] = {
            "minutes": minutes.get(pid, 0.0),
            "position": pos[0][0] if pos else None,
            **stats,
        }
    return {"team_stats": team_stats, "players": players, "shots": shots}
