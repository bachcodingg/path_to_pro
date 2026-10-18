"""Match ratings, H8 (dual registration), careers, match diary, training pitch."""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from api.db import SessionLocal, init_db
from api.main import app
from api.services.seed import seed
from performance import competitions
from performance.rating import band, rate, rate_diary

# --------------------------------------------------------------------------- rating engine


def test_rating_scale_and_breakdown():
    quiet = rate("midfielder", 90, {"passes": 40, "passes_accurate": 32})
    assert 6.0 <= quiet.value <= 6.6
    star = rate("striker", 90, {"goals": 2, "assists": 1, "shots_on_target": 4, "key_passes": 3, "result": "win"})
    assert star.value >= 8.0 and band(star.value) == "elite"
    assert star.breakdown[0]["label"].startswith("Goals")  # biggest contribution first
    bad = rate("centre_back", 90, {"errors_to_goal": 2, "goals_conceded": 4, "red": 1, "result": "loss"})
    assert bad.value < 6.0 and band(bad.value) == "poor"
    assert rate("winger", 5, {"goals": 1}).value is None  # too few minutes
    assert 3.0 <= rate("goalkeeper", 90, {"own_goals": 3, "errors_to_goal": 3, "goals_conceded": 8}).value


def test_position_weights_matter():
    gk = rate("goalkeeper", 90, {"saves": 6, "goals_conceded": 0})
    st = rate("striker", 90, {"saves": 6, "goals_conceded": 0})
    assert gk.value > st.value  # saves and clean sheets count for keepers
    assert any(b["label"] == "Clean sheet" for b in gk.breakdown)


def test_diary_estimate_is_labelled():
    r = rate_diary("winger", 70, 1, 0)
    assert r.value is not None and "Estimate" in r.breakdown[-1]["label"]


def test_competition_ladder():
    assert competitions.level("fi_veikkausliiga") > competitions.level("fi_kakkonen") > competitions.level("fi_u17_national")
    assert competitions.academy_competition(16.2) == "fi_u17_national"
    assert competitions.academy_competition(17.5) == "fi_u19_national"
    # 90 minutes in the men's 4th tier count more than in a U17 league
    assert competitions.exposure(90, "fi_kakkonen") > competitions.exposure(90, "fi_u17_national")


# --------------------------------------------------------------------------- H8


def test_h8_shares_back_to_back_match_minutes():
    from planner.model import hard_violations, plan_week
    from planner.schema import PlannerInput

    inp = PlannerInput(player_id="d", start=date(2026, 11, 23), match_days=[5, 6], under_18=True, match_priority={5: 2, 6: 1})
    r = plan_week(inp)
    assert not hard_violations(r, inp)
    assert r.days[5].minutes + r.days[6].minutes <= 90
    assert r.days[5].minutes >= r.days[6].minutes  # the primary team's match keeps its minutes
    adult = plan_week(inp.model_copy(update={"under_18": False}))
    assert adult.days[5].minutes + adult.days[6].minutes > 90


# --------------------------------------------------------------------------- API


@pytest.fixture(scope="module")
def client():
    init_db()
    with SessionLocal() as db:
        seed(db, n_players=8)
    with TestClient(app) as c:
        yield c


def _h(c, email):
    r = c.post("/api/auth/login", json={"email": email, "password": "demo1234"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_dual_player_week_career_and_diary(client):
    h = _h(client, "dual@demo.pathtopro")
    for off in (0, 1):
        days = client.get(f"/api/me/week?offset={off}", headers=h).json()["days"]
        for a, b in zip(days, days[1:]):
            if a["kind"] == b["kind"] == "match":
                assert a["minutes"] + b["minutes"] <= 90
    week = client.get("/api/me/week", headers=h).json()["days"]
    teams = {d["match"]["team"] for d in week if d.get("match")}
    assert "PathToPro FC Men" in teams

    car = client.get("/api/me/career", headers=h).json()
    assert len(car["registrations"]) == 2 and car["registrations"][0]["primary"]
    assert car["past"] and car["ladder"] and car["summary"]["apps"] > 0
    assert any(r["rating"] is not None for r in car["recent"])
    due = car["diary_due"]
    assert due, "the last week's matches without a diary are due"
    mid = due[0]["match_id"]
    out = client.post(
        f"/api/me/matches/{mid}/diary",
        headers=h,
        json={"minutes": 30, "goals": 0, "assists": 1, "self_rating": 7, "rpe": 6},
    )
    assert out.status_code == 200, out.text
    assert mid not in {d["match_id"] for d in out.json()["diary_due"]}
    assert client.post(f"/api/me/matches/{mid}/diary", headers=h, json={"minutes": 30, "self_rating": 11}).status_code == 422

    s = client.post(
        "/api/me/career/seasons",
        headers=h,
        json={"season": "2023", "club": "FC Home", "team": "U15", "competition": "fi_u15_regional", "apps": 12, "starts": 8, "minutes": 700, "goals": 3},
    )
    assert s.status_code == 201 and any(r["season"] == "2023" for r in s.json()["past"])
    bad = client.post("/api/me/career/seasons", headers=h, json={"season": "2023", "club": "x", "team": "y", "competition": "nope"})
    assert bad.status_code == 422
    sid = next(r["id"] for r in s.json()["past"] if r["season"] == "2023")
    assert client.delete(f"/api/me/career/seasons/{sid}", headers=h).status_code == 200


def test_second_team_coach_sees_but_does_not_decide(client):
    men = _h(client, "mencoach@demo.pathtopro")
    players = client.get("/api/coach/heatmap", headers=men).json()["players"]
    assert len(players) == 3
    for p in client.get("/api/coach/inbox", headers=men).json():
        r = client.post(f"/api/coach/proposals/{p['id']}/decision", headers=men, json={"action": "approve"})
        assert r.status_code == 403 and "primary" in r.json()["detail"]
    ms = client.get("/api/coach/matches", headers=men).json()
    assert ms and all(m["team"] == "PathToPro FC Men" for m in ms)


def test_coach_match_ratings(client):
    coach = _h(client, "coach@demo.pathtopro")
    ms = client.get("/api/coach/matches", headers=coach).json()
    assert ms and ms[0]["rated"] > 0
    rep = client.get(f"/api/coach/matches/{ms[0]['id']}", headers=coach).json()
    row = rep["players"][0]
    body = {"players": [{"player_id": row["player"]["id"], "minutes": 90, "started": True, "position": "striker",
                         "stats": {"goals": 2, "assists": 1, "shots_on_target": 3, "result": "win"}}]}  # fmt: skip
    saved = client.put(f"/api/coach/matches/{ms[0]['id']}/ratings", headers=coach, json=body)
    assert saved.status_code == 200, saved.text
    new = next(r for r in saved.json()["players"] if r["player"]["id"] == row["player"]["id"])
    assert new["rating"] >= 8.0 and new["rating_source"] == "stats" and new["breakdown"]
    body["players"][0]["stats"] = {"tackles": 3}
    assert client.put(f"/api/coach/matches/{ms[0]['id']}/ratings", headers=coach, json=body).status_code == 422
    prev = client.post("/api/coach/ratings/preview", headers=coach, json={"position": "goalkeeper", "minutes": 90, "stats": {"saves": 5}})
    assert prev.json()["rating"] > 6.3
    player = _h(client, "p03@demo.pathtopro")
    assert client.put(f"/api/coach/matches/{ms[0]['id']}/ratings", headers=player, json=body).status_code == 403


def test_training_pitch(client):
    coach = _h(client, "coach@demo.pathtopro")
    sw = client.get("/api/coach/squad-week", headers=coach).json()
    assert len(sw["dates"]) == 7 and sw["players"]
    today = date.fromisoformat(sw["today"])
    assert client.post("/api/coach/squad-week/session", headers=coach,
                       json={"day": (today - timedelta(days=1)).isoformat(), "kind": "speed", "rpe": 7}).status_code == 422  # fmt: skip
    assert client.post("/api/coach/squad-week/session", headers=coach,
                       json={"day": today.isoformat(), "kind": "speed", "rpe": 2}).status_code == 422  # fmt: skip
    # Pick a day that is the day before a match for someone: they get an easier version
    match_days = {d["date"] for p in sw["players"] for d in p["days"] if d["kind"] == "match"}
    md1 = next((x for x in sw["dates"] if (date.fromisoformat(x) + timedelta(days=1)).isoformat() in match_days and date.fromisoformat(x) >= today), None)
    day = md1 or sw["dates"][-1]
    prev = client.post("/api/coach/squad-week/session", headers=coach, json={"day": day, "kind": "speed", "rpe": 7}).json()
    assert not prev["applied"] and sum(prev["counts"].values()) == len(prev["players"])
    for r in prev["players"]:
        if r["status"] == "adjusted":
            assert r["reasons"] and r["proposed"]["rpe"] <= 7
    if md1:
        assert prev["counts"].get("adjusted", 0) > 0
    applied = client.post("/api/coach/squad-week/session", headers=coach, json={"day": day, "kind": "speed", "rpe": 7, "apply": True}).json()
    assert applied["applied"]
    after = client.get("/api/coach/squad-week", headers=coach).json()
    i = after["dates"].index(day)
    for r in applied["players"]:
        if r["status"] in ("ok", "adjusted"):
            row = next(p for p in after["players"] if p["id"] == r["player"]["id"])
            assert row["days"][i]["kind"] == r["proposed"]["kind"] and row["days"][i]["rpe"] == r["proposed"]["rpe"]
    log = client.get("/api/coach/agent-log?limit=50", headers=coach).json()
    assert any(x["trigger"] == "team_session" for x in log)
