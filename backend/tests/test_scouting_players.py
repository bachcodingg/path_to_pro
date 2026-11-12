"""Pro player analysis: the event-data profiles (committed StatsBomb files) and the 2024/25
season import (a made-up API-Football page in the API's documented shape, no network)."""

import json

import pytest

from scouting import apifootball, players, season


def test_featured_squads_and_best_of_the_rest():
    hub = players.hub()
    teams = {(f["comp"], f["team"]) for f in hub["featured"]}
    assert ("la-liga", "Real Madrid") in teams and ("ligue-1-psg", "Paris Saint-Germain") in teams
    real = next(f for f in hub["featured"] if f["team"] == "Real Madrid")
    assert len(real["players"]) >= 20  # the full squad, not a highlight
    assert [p["minutes"] for p in real["players"]] == sorted((p["minutes"] for p in real["players"]), reverse=True)
    # one player for every other club, never one of the featured clubs
    best_teams = [(b["comp"], b["team"]) for b in hub["best"]]
    assert len(best_teams) == len(set(best_teams))
    assert not {t for _, t in best_teams} & {t for _, t in players.FEATURED}
    atletico = next(b for b in hub["best"] if b["team"] == "Atlético Madrid")
    assert atletico["player"]["name"] == "Antoine Griezmann"
    assert any(n["team"] == "Bayern Munich" for n in hub["not_in_open_data"])


def test_profile_has_percentiles_in_a_full_league_only():
    ronaldo = players.profile("la-liga", "real-madrid", "cristiano-ronaldo")
    assert ronaldo["group"] == "Forward" and ronaldo["goals"] == 35
    goals = next(m for m in ronaldo["measures"] if m["key"] == "np_goals90")
    assert goals["percentile"] >= 90 and goals["peers"] >= 10
    assert all(len(s) == len(ronaldo["shot_columns"]) for s in ronaldo["shots"])
    assert len(ronaldo["shots"]) == ronaldo["totals"]["shots"]

    mbappe = players.profile("ligue-1-psg", "paris-saint-germain", "kylian-mbappe")
    assert mbappe["minutes"] > 4000 and mbappe["shots"]
    assert all(m["percentile"] is None for m in mbappe["measures"])  # one club's matches: no fair group
    assert "Paris Saint-Germain" in mbappe["no_percentiles"]
    assert players.profile("la-liga", "real-madrid", "nobody") is None


def test_position_groups():
    assert players.group("Right Center Back") == "Defender"
    assert players.group("Center Defensive Midfield") == "Midfielder"
    assert players.group("Center Forward") == "Forward"


def _item(pid, name, team_id, team, position, minutes, goals, assists, league=140, **extra):
    """One entry of API-Football's /players response."""
    return {
        "player": {"id": pid, "name": name, "firstname": name, "lastname": name, "age": 25, "nationality": "France",
                   "photo": "https://media.api-sports.io/x.png"},
        "statistics": [{
            "team": {"id": team_id, "name": team, "logo": "https://media.api-sports.io/t.png"},
            "league": {"id": league, "season": 2024},
            "games": {"appearences": 30, "lineups": 28, "minutes": minutes, "position": position, "rating": "7.4"},
            "shots": {"total": 100, "on": 50}, "goals": {"total": goals, "assists": assists, "conceded": 0, "saves": None},
            "passes": {"total": 900, "key": 40, "accuracy": 80}, "tackles": {"total": 10, "blocks": 1, "interceptions": 3},
            "duels": {"total": 300, "won": 150}, "dribbles": {"attempts": 90, "success": 50},
            "fouls": {"drawn": 40, "committed": 10}, "cards": {"yellow": 2, "yellowred": 0, "red": 0},
            "penalty": {"scored": extra.get("pens", 0), "missed": 0},
        }],
    }  # fmt: skip


@pytest.fixture
def season_file(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    cache.mkdir()
    # API-Football's free plan reads each club's players: /teams per league, then /players?team=
    squads = {541: [_item(278, "K. Mbappé", 541, "Real Madrid", "Attacker", 2900, 31, 3, pens=7)]}
    for i in range(12):
        squads[600 + i] = [_item(1000 + i, f"Forward {i}", 600 + i, f"Club {i}", "Attacker", 1500 + 50 * i, i, 1)]
    squads[600].append(_item(2000, "Bench", 600, "Club 0", "Attacker", 200, 0, 0))
    names = {541: "Real Madrid"} | {600 + i: f"Club {i}" for i in range(12)} | {700: "Not fetched yet"}

    def put(name, body):
        (cache / name).write_text(json.dumps(body | {"errors": []}), encoding="utf-8")

    put("teams_league140_season2024.json", {"response": [{"team": {"id": t, "name": n}} for t, n in names.items()]})
    for team, items in squads.items():
        # Club 1's list has two pages: both are needed before the club counts as in
        pages = [items[:1], items[1:] or [_item(3000, "Reserve", team, names[team], "Defender", 90, 0, 0)]] \
            if team == 601 else [items]
        for n, chunk in enumerate(pages, 1):
            put(f"players_page{n}_season2024_team{team}.json",
                {"paging": {"current": n, "total": len(pages)}, "response": chunk})
    # Club 11's second page is missing: the club is left out, not shown with half a squad
    put("players_page1_season2024_team611.json", {"paging": {"current": 1, "total": 2}, "response": squads[611]})
    out = tmp_path / "season.json"
    monkeypatch.setattr(apifootball, "OUT", out)
    monkeypatch.setattr(season, "OUT", out)
    season.load.cache_clear()
    apifootball.write(cache, out)
    yield out
    season.load.cache_clear()


def test_season_import_keeps_numbers_not_photos(season_file):
    text = season_file.read_text(encoding="utf-8")
    assert "media.api-sports.io" not in text  # no photos or logos kept
    data = json.loads(text)
    mbappe = next(p for p in data["leagues"][0]["players"] if p["id"] == 278)
    assert (mbappe["goals"], mbappe["pen_scored"], mbappe["minutes"], mbappe["rating"]) == (31, 7, 2900, 7.4)
    # 12 of 14 clubs in: Club 11 has a page missing and "Not fetched yet" has none
    assert (data["clubs"], data["clubs_total"]) == (12, 14)
    assert {p["team"] for p in data["leagues"][0]["players"]} == {"Real Madrid"} | {f"Club {i}" for i in range(11)}
    assert any(p["name"] == "Reserve" for p in data["leagues"][0]["players"])  # Club 1's second page


def test_season_hub_and_profile(season_file):
    hub = season.hub()
    assert hub["available"] and hub["season"] == "2024/25"
    real = next(f for f in hub["featured"] if f["team"] == "Real Madrid")
    assert real["players"][0]["name"] == "K. Mbappé"
    assert {b["team"] for b in hub["best"]} == {f"Club {i}" for i in range(11)}  # one per other club in so far
    assert (hub["clubs"], hub["clubs_total"]) == (12, 14)
    club0 = next(b for b in hub["best"] if b["team"] == "Club 0")
    assert club0["player"]["name"] == "Forward 0"  # the bench player is below the minutes line
    p = season.profile(541, 278)
    goals = next(m for m in p["measures"] if m["key"] == "np_goals90")
    assert goals["value"] == round(90 * 24 / 2900, 2) and goals["percentile"] >= 95  # top of 12, himself included
    assert p["compared_with"].endswith("(12 of 14 clubs imported so far)")
    assert season.profile(541, 999) is None


def test_season_without_the_file(tmp_path, monkeypatch):
    monkeypatch.setattr(season, "OUT", tmp_path / "missing.json")
    season.load.cache_clear()
    assert season.hub() == season._source() and season.hub()["available"] is False
    assert season.profile(541, 278) is None
    season.load.cache_clear()
