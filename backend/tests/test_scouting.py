from scouting import analysis
from scouting.statsbomb import extract

MATCH = {"match_id": 1, "home_team": {"home_team_name": "Home FC"}, "away_team": {"away_team_name": "Away CF"}}


def ev(kind, team, t, possession, period=1, **extra):
    m, s = divmod(t, 60)
    e = {
        "type": {"name": kind},
        "team": {"name": team},
        "player": {"id": 7, "name": "Full Legal Name"},
        "period": period,
        "timestamp": f"00:{m:02d}:{s:06.3f}",
        "minute": m,
        "possession": possession,
        "location": [120.0, 80.0],
    }
    return e | extra


def corner(team, t, possession, end=(116.0, 46.0), **p):
    return ev("Pass", team, t, possession, **{"pass": {"type": {"name": "Corner"}, "end_location": list(end), **p}})


def shot(team, t, possession, kind="Open Play", outcome="Goal", xg=0.2, end=(120, 38, 0.5), period=1):
    s = {"type": {"name": kind}, "outcome": {"name": outcome}, "statsbomb_xg": xg, "end_location": list(end)}
    return ev("Shot", team, t, possession, period=period, shot=s)


def test_shot_counts_for_a_corner_only_within_the_window_and_possession():
    events = [
        corner("Home FC", 100, 5, technique={"name": "Inswinging"}),
        shot("Home FC", 108, 5, outcome="Saved", xg=0.1),
        shot("Home FC", 110, 5, outcome="Goal", xg=0.3),
        corner("Home FC", 300, 9),
        shot("Home FC", 330, 9),  # 30 s later: the corner is long over
        corner("Away CF", 500, 12),
        shot("Home FC", 505, 13),  # the other team's possession
    ]
    out = extract(MATCH, events, {7: "Nickname"})
    first, second, third = out["corners"]
    assert (first["shot"], first["goal"], first["xg"], first["tech"]) == (True, True, 0.4, "in")
    assert first["taker"] == "Nickname" and first["side"] == "R" and first["opp"] == "Away CF"
    assert not second["shot"] and not third["shot"]


def test_penalties_skip_shootouts_and_keep_placement():
    events = [
        shot("Away CF", 600, 20, kind="Penalty", outcome="Saved", end=(120, 37.0, 0.3)),
        shot("Away CF", 30, 99, kind="Penalty", outcome="Goal", period=5),
    ]
    out = extract(MATCH, events, {})
    assert len(out["penalties"]) == 1
    pen = out["penalties"][0]
    assert (pen["team"], pen["outcome"], pen["y"], pen["z"]) == ("Away CF", "Saved", 37.0, 0.3)
    assert analysis.goal_third(pen["y"]) == "left" and analysis.goal_height(pen["z"]) == "low"


def test_corner_zones_follow_the_side_it_was_taken_from():
    zone = analysis.corner_zone
    assert zone({"side": "L", "x": 116, "y": 33}) == "near_post"
    assert zone({"side": "R", "x": 116, "y": 33}) == "far_post"
    assert zone({"side": "R", "x": 116, "y": 40}) == "six_yard"
    assert zone({"side": "R", "x": 108, "y": 40}) == "penalty_spot"
    assert zone({"side": "L", "x": 108, "y": 8}) == "short"
    assert zone({"side": "L", "x": 92, "y": 40}) == "edge"


def test_wilson_interval_contains_the_estimate_and_narrows_with_n():
    lo, hi = analysis.wilson(30, 100)
    assert lo < 0.3 < hi
    lo2, hi2 = analysis.wilson(300, 1000)
    assert hi2 - lo2 < hi - lo
    assert analysis.wilson(0, 0) == (0.0, 1.0)


def test_real_madrid_profile_is_consistent():
    listing = analysis.teams()
    assert listing["source"] == "StatsBomb Open Data" and listing["matches"] == 380
    assert len(listing["teams"]) == 20 and all(t["matches"] == 38 for t in listing["teams"])
    p = analysis.team_profile("real-madrid")
    c = p["corners"]
    assert c["total"] > 100 and sum(z["n"] for z in c["zones"]) == c["total"]
    assert c["sides"]["L"] + c["sides"]["R"] == c["total"] == len(p["corner_points"])
    assert sum(t["n"] for t in p["corner_takers"]) == c["total"]
    for share in c["zones"] + c["technique"]:
        # A flag means the interval excludes the league rate, never just a different number
        if share["flag"] == "more":
            assert share["lo"] > share["league_pct"]
        elif share["flag"] == "less":
            assert share["hi"] < share["league_pct"]
    pens = p["penalties"]
    assert pens["total"] == len(pens["kicks"]) and sum(t["n"] for t in pens["takers"]) == pens["total"]
    assert all(isinstance(n, str) for n in p["notes"])
    assert analysis.team_profile("not-a-team") is None
