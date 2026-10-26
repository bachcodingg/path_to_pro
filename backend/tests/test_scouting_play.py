from scouting import style
from scouting.play import extract_play

MATCH = {
    "match_id": 1,
    "home_team": {"home_team_name": "Home FC"},
    "away_team": {"away_team_name": "Away CF"},
    "home_score": 1,
    "away_score": 0,
}
PLAYERS = {"Home FC": (10, "Striker"), "Away CF": (20, "Keeper")}


def ev(kind, team, minute=10, loc=(60.0, 40.0), pid=None, period=1, **extra):
    pid = pid or PLAYERS[team][0]
    return {
        "type": {"name": kind},
        "team": {"name": team},
        "player": {"id": pid, "name": f"P{pid}"},
        "position": {"name": "Center Forward"},
        "period": period,
        "minute": minute,
        "second": 0,
        "location": list(loc),
        "play_pattern": {"name": "Regular Play"},
    } | extra


def lineup(team, ids):
    return {
        "type": {"name": "Starting XI"},
        "team": {"name": team},
        "period": 1,
        "minute": 0,
        "second": 0,
        "tactics": {"lineup": [{"player": {"id": i, "name": f"P{i}"}} for i in ids]},
    }


def pas(team, length, end, loc=(50.0, 40.0), outcome=None, **p):
    body = {"length": length, "end_location": list(end), **p}
    if outcome:
        body["outcome"] = {"name": outcome}
    return ev("Pass", team, loc=loc, **{"pass": body})


def shot(team, loc, xg, outcome="Goal", body="Right Foot", kind="Open Play", **e):
    s = {"type": {"name": kind}, "outcome": {"name": outcome}, "statsbomb_xg": xg, "body_part": {"name": body}}
    return ev("Shot", team, loc=loc, shot=s, **e)


def run(events):
    base = [lineup("Home FC", [10, 11]), lineup("Away CF", [20])]
    end = ev("Half End", "Home FC", minute=90, period=2)
    return extract_play(MATCH, base + events + [end], {10: "Striker"})


def test_passes_are_split_by_length_and_set_pieces_left_out():
    out = run([
        pas("Home FC", 10, (60, 40)),
        pas("Home FC", 20, (70, 40), outcome="Incomplete"),
        pas("Home FC", 40, (90, 40)),  # long, and into the final third
        pas("Home FC", 30, (110, 30), loc=(95, 10), cross=True),  # cross into the box
        pas("Home FC", 30, (100, 40), type={"name": "Corner"}),  # set piece: not an open-play pass
        pas("Home FC", 12, (60, 40), outcome="Unknown"),  # not an attempt
    ])  # fmt: skip
    s = out["team_stats"]["Home FC"]
    assert (s["passes"], s["passes_cmp"]) == (4, 3)
    assert (s["short"], s["medium"], s["medium_cmp"], s["long"]) == (1, 2, 1, 1)
    assert s["final_third_cmp"] == 1 and s["cross_cmp"] == 1 and s["box_pass_cmp"] == 1
    assert s["passes_all"] == 6


def test_shots_by_zone_header_and_penalty():
    out = run([
        shot("Home FC", (116, 40), 0.5),  # tap-in range, big chance
        shot("Home FC", (108, 40), 0.1, outcome="Saved", body="Head"),
        shot("Home FC", (90, 40), 0.03, outcome="Off T"),
        shot("Home FC", (108, 40), 0.76, kind="Penalty"),
        shot("Home FC", (108, 40), 0.76, kind="Penalty", period=5),  # shoot-out: ignored
    ])  # fmt: skip
    s = out["team_stats"]["Home FC"]
    assert (s["shots"], s["goals"], s["shots_ot"]) == (4, 2, 3)
    assert (s["six_shots"], s["six_goals"], s["box_shots"], s["out_shots"]) == (1, 1, 1, 1)
    assert (s["head_shots"], s["head_goals"], s["big_chances"], s["pen_goals"]) == (1, 0, 1, 1)
    assert round(s["np_xg"], 2) == 0.63
    assert len(out["shots"]) == 4 and out["shots"][0][2] == "Striker"


def test_aerials_duels_and_minutes():
    out = run([
        pas("Home FC", 10, (60, 40), aerial_won=True),
        ev("Duel", "Away CF", duel={"type": {"name": "Aerial Lost"}}),
        ev("Duel", "Away CF", loc=(70, 40), duel={"type": {"name": "Tackle"}, "outcome": {"name": "Won"}}),
        ev("Substitution", "Home FC", minute=60, substitution={"replacement": {"id": 12, "name": "P12"}}),
        ev("Foul Committed", "Away CF", minute=80, foul_committed={"card": {"name": "Red Card"}}),
    ])  # fmt: skip
    home, away = out["team_stats"]["Home FC"], out["team_stats"]["Away CF"]
    assert home["aerial_won"] == 1 and away["aerial_lost"] == 1
    assert away["tackles_cmp"] == 1 and away["def_actions_opp60"] == 2  # tackle + foul, both at x >= 48
    assert (away["red"], home["gf"], away["ga"]) == (1, 1, 1)
    mins = {n: p["minutes"] for n, p in out["players"]["Home FC"].items()}
    assert mins == {"Striker": 60.0, "P11": 90.0, "P12": 30.0}
    assert out["players"]["Away CF"]["P20"]["minutes"] == 80.0


def test_league_table_matches_the_real_final_standings():
    table = style.standings()
    assert [(t["team"], t["points"]) for t in table[:3]] == [("Barcelona", 91), ("Real Madrid", 90), ("Atlético Madrid", 88)]
    assert all(t["played"] == 38 for t in table) and len(table) == 20


def test_home_and_away_tables_add_up_and_form_is_the_last_five_results():
    full = {t["team"]: t for t in style.standings()}
    home = {t["team"]: t for t in style.standings("home")}
    away = {t["team"]: t for t in style.standings("away")}
    for team, t in full.items():
        assert home[team]["played"] == away[team]["played"] == 19
        assert home[team]["points"] + away[team]["points"] == t["points"]
        assert len(t["form"]) == 5 and set(t["form"]) <= {"W", "D", "L"}
    # 2015/16 last five: Barcelona won all five; Real Madrid won their last twelve
    assert full["Barcelona"]["form"] == ["W"] * 5 and full["Real Madrid"]["form"] == ["W"] * 5


def test_style_measures_are_consistent():
    p = style.style_profile("real-madrid")
    assert p["matches"] == 38 and len(p["measures"]) == len(style.METRICS)
    for x in p["measures"]:
        assert 1 <= x["rank"] <= 20
        if x["flag"] == "high":
            assert x["lo"] > x["league"]
        if x["flag"] == "low":
            assert x["hi"] < x["league"]
        if x["unit"] == "%":
            assert 0 <= x["value"] <= 100
    acc = {x["key"]: x["value"] for x in p["measures"]}
    assert min(acc["short_acc"], acc["medium_acc"]) > acc["long_acc"] + 10  # long balls are the risky ones
    players = style.player_rows("real-madrid")["players"]
    assert any(r["name"] == "Cristiano Ronaldo" and r["goals"] >= 30 for r in players)
    shots = style.shot_map("real-madrid")
    assert len(shots["for"]) > 500 and len(shots["against"]) > 200
