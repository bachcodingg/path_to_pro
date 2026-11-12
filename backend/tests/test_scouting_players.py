"""Pro player analysis: the event-data profiles (committed StatsBomb files), their photos
(committed links to Wikimedia), and the API-Football season import (made-up pages in the API's
documented shape, no network)."""

import io
import json

import pytest

from scouting import apifootball, media, players, season


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


def _item(pid, name, team_id, team, position, minutes, goals, assists, league=140, year=2024, **extra):
    """One entry of API-Football's /players response."""
    return {
        "player": {"id": pid, "name": name, "firstname": name, "lastname": name, "age": 25, "nationality": "France",
                   "photo": "https://media.api-sports.io/x.png"},
        "statistics": [{
            "team": {"id": team_id, "name": team, "logo": "https://media.api-sports.io/t.png"},
            "league": {"id": league, "season": year},
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
    # API-Football files his Club 2 season under Club 3 too, where he only arrived in July 2025
    squads[602].append(_item(4000, "Moved Later", 602, "Club 2", "Midfielder", 2000, 0, 2))
    squads[603].append(_item(4000, "Moved Later", 603, "Club 3", "Midfielder", 2000, 0, 2))
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
    move = {"date": "2025-07-01", "type": "Free", "teams": {"in": {"id": 603}, "out": {"id": 602}}}
    for team in squads:
        if team != 610:  # Club 10's transfers are not in yet: left out until they are
            moves = [{"player": {"id": 4000}, "transfers": [move]}] if team in (602, 603) else []
            put(f"transfers_team{team}.json", {"response": moves})
    monkeypatch.setattr(apifootball, "DATA", tmp_path)
    season.load.cache_clear()
    apifootball.write(cache)
    yield apifootball.out_path(2024)
    season.load.cache_clear()


def test_season_import_keeps_numbers_and_image_links(season_file):
    assert season_file.name == "season_2024_25.json"
    data = json.loads(season_file.read_text(encoding="utf-8"))
    mbappe = next(p for p in data["leagues"][0]["players"] if p["id"] == 278)
    assert (mbappe["goals"], mbappe["pen_scored"], mbappe["minutes"], mbappe["rating"]) == (31, 7, 2900, 7.4)
    # The addresses of API-Football's photo and logo, shown from its servers; not the images
    assert (mbappe["photo"], mbappe["logo"]) == ("https://media.api-sports.io/x.png", "https://media.api-sports.io/t.png")
    # 11 of 14 clubs in: Club 10 lacks its transfers, Club 11 a page, "Not fetched yet" everything
    assert (data["clubs"], data["clubs_total"]) == (11, 14)
    assert {p["team"] for p in data["leagues"][0]["players"]} == {"Real Madrid"} | {f"Club {i}" for i in range(10)}
    # His season counts for Club 2, where he played it, not for Club 3, where he went next
    assert [p["team"] for p in data["leagues"][0]["players"] if p["id"] == 4000] == ["Club 2"]
    assert data["left_out_not_at_the_club_that_season"] == 1
    assert any(p["name"] == "Reserve" for p in data["leagues"][0]["players"])  # Club 1's second page


def test_season_hub_and_profile(season_file):
    hub = season.hub()
    assert hub["available"] and hub["season"] == "2024/25" and hub["year"] == 2024
    assert hub["seasons"] == [
        {"year": 2025, "season": "2025/26", "available": False},
        {"year": 2024, "season": "2024/25", "available": True},
    ]
    real = next(f for f in hub["featured"] if f["team"] == "Real Madrid")
    assert real["players"][0]["name"] == "K. Mbappé" and real["logo"] == "https://media.api-sports.io/t.png"
    assert real["players"][0]["photo"] == {"url": "https://media.api-sports.io/x.png", "via": "API-Football"}
    assert {b["team"] for b in hub["best"]} == {f"Club {i}" for i in range(10)}  # one per other club in so far
    assert (hub["clubs"], hub["clubs_total"]) == (11, 14)
    club0 = next(b for b in hub["best"] if b["team"] == "Club 0")
    assert club0["player"]["name"] == "Forward 0"  # the bench player is below the minutes line
    p = season.profile(541, 278)
    goals = next(m for m in p["measures"] if m["key"] == "np_goals90")
    assert goals["value"] == round(90 * 24 / 2900, 2) and goals["percentile"] >= 95  # top of 11, himself included
    assert p["compared_with"].endswith("(11 of 14 clubs imported so far)")
    assert season.profile(541, 999) is None
    assert p["logo"] and p["photo"]["url"]


def test_a_second_season_from_its_own_pages(season_file):
    cache = season_file.parent / "cache"
    (cache / "teams_league140_season2025.json").write_text(
        json.dumps({"response": [{"team": {"id": 541, "name": "Real Madrid"}}], "errors": []}), encoding="utf-8"
    )
    # Pages of the 2025/26 season; the club's transfer list is the one 2024/25 already has
    item = _item(278, "K. Mbappé", 541, "Real Madrid", "Attacker", 3000, 40, 5, year=2025)
    (cache / "players_page1_season2025_team541.json").write_text(
        json.dumps({"paging": {"current": 1, "total": 1}, "response": [item], "errors": []}), encoding="utf-8"
    )
    apifootball.write(cache, 2025)
    season.load.cache_clear()
    later, earlier = season.hub(2025), season.hub(2024)
    assert later["available"] and later["season"] == "2025/26" and (later["clubs"], later["clubs_total"]) == (1, 1)
    assert later["featured"][0]["players"][0]["goals"] == 40
    assert earlier["featured"][0]["players"][0]["goals"] == 31  # each season keeps its own numbers
    assert season.profile(541, 278, 2025)["season"] == "2025/26"
    assert all(s["available"] for s in later["seasons"])


def test_the_free_plan_refusing_a_season_is_told_apart(tmp_path, monkeypatch):
    body = {"errors": {"plan": "Free plans do not have access to this season, try from 2022 to 2024."}}
    monkeypatch.setattr(apifootball, "GAP_S", 0)
    monkeypatch.setattr(apifootball.urllib.request, "urlopen", lambda req, timeout: io.BytesIO(json.dumps(body).encode()))
    with pytest.raises(apifootball.PlanLimit, match="2022 to 2024"):
        apifootball.fetch("key", tmp_path, log=lambda _: None, season=2025)
    assert not list(tmp_path.iterdir())  # a refusal is not cached


def _move(day, to, frm):
    return {"date": day, "teams": {"in": {"id": to}, "out": {"id": frm}}}


def test_a_player_counts_for_a_club_only_if_he_was_there_that_season():
    at = apifootball._at_club
    assert at([], 1)  # no transfer with the club: an academy player
    assert at([_move("2024-07-01", 1, 2)], 1)  # signed before the season (Mbappé)
    assert not at([_move("2025-07-01", 1, 2)], 1)  # signed after it (Joan García at Barcelona)
    assert at([_move("2025-07-01", 1, 2)], 2)  # ... and still counts for the club he left
    loan = [_move("2024-07-10", 3, 1), _move("2025-06-30", 1, 3)]
    assert not at(loan, 1) and at(loan, 3)  # a season on loan counts for the loan club only
    january = [_move("2025-01-20", 2, 1)]
    assert at(january, 1) and at(january, 2)  # a January move: both clubs
    assert not at([_move("2024-08-25", 2, 1)], 1)  # left in the first ten days: not his club
    assert at([_move("bad date", 1, 2)], 1)  # an unreadable date is ignored


def test_season_without_the_file(tmp_path, monkeypatch):
    monkeypatch.setattr(apifootball, "DATA", tmp_path)
    season.load.cache_clear()
    assert season.hub() == season._source(2024) and season.hub()["available"] is False
    assert season.hub(2025)["season"] == "2025/26" and not season.hub(2025)["available"]
    assert season.profile(541, 278) is None
    season.load.cache_clear()


def test_a_statsbomb_name_matches_one_wikidata_player_or_none():
    assert media._score("Lionel Andrés Messi Cuccittini", {"Lionel Messi"}) == 2
    assert media._score("Luka Modrić", {"Luka Modric"}) == 3  # accents do not matter
    assert media._score("Neymar da Silva Santos Júnior", {"Neymar"}) == 1
    assert media._score("Jesé", {"Jesé Rodríguez", "Jese"}) == 3
    assert media._score("Sergio Ramos", {"Sergio Busquets"}) == 0
    people = {
        "Q1": {"names": {"Marcelo"}, "img": "a.jpg", "spells": [(2007, 2022)]},
        "Q2": {"names": {"Marcelo Díaz"}, "img": "b.jpg", "spells": [(1990, 1992)]},
        "Q3": {"names": {"Daniel Carvajal"}, "img": None, "spells": [(2013, None)]},
    }
    assert media.match("Marcelo", people, (2015, 2016)) == "Q1"
    assert media.match("Daniel Carvajal", people, (2015, 2016)) == "Q3"
    two = {"Q4": {"names": {"Juan Pérez"}, "img": None, "spells": [(2015, 2016)]}} | {
        "Q5": {"names": {"Juan Perez"}, "img": None, "spells": [(2015, 2016)]}
    }
    assert media.match("Juan Pérez", two, (2015, 2016)) is None  # two of them: no photo rather than the wrong one
    # A sparse duplicate item with no dates loses to the one whose spell covers the season
    dup = {"Q6": {"names": {"Kylian Mbappé"}, "img": "k.jpg", "spells": [(2017, 2024)]},
           "Q7": {"names": {"Kylian Mbappé"}, "img": None, "spells": [(None, None)]}}  # fmt: skip
    assert media.match("Kylian Mbappé", dup, (2021, 2023)) == "Q6"


def test_players_carry_their_commons_photo_and_credit():
    real = next(f for f in players.hub()["featured"] if f["team"] == "Real Madrid")
    ronaldo = next(p for p in real["players"] if p["name"] == "Cristiano Ronaldo")["photo"]
    assert ronaldo["url"].startswith("https://") and "wikimedia.org/" in ronaldo["url"]
    assert ronaldo["page"].startswith("https://commons.wikimedia.org/") and ronaldo["licence"] and ronaldo["author"]
    with_photo = sum(bool(p["photo"]) for p in real["players"])
    assert with_photo >= len(real["players"]) * 0.8
    assert media.photo("Nobody At All", "Real Madrid") is None
    # Two players of one name are two people, each with his own photo
    villa, monaco = media.photo("Adama Traoré", "Aston Villa"), media.photo("Adama Traoré", "AS Monaco")
    assert villa != monaco
