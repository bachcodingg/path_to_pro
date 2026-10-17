"""Self-guided pathway: levels and benchmarks, sign-up, parent linking, gym, level-ups."""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from api import clock
from api.db import SessionLocal, init_db
from api.main import app
from api.services.seed import seed
from pathway import levels

# --------------------------------------------------------------------------- pure level logic


def test_thresholds_adjust_for_age_and_sex():
    adult = levels.threshold("sprint_30m", 3, 20, "male")
    young = levels.threshold("sprint_30m", 3, 14, "male")
    female = levels.threshold("sprint_30m", 3, 20, "female")
    assert young > adult and female > adult  # slower times allowed
    assert levels.threshold("yoyo_ir1", 3, 14) < levels.threshold("yoyo_ir1", 3, 20)
    assert levels.threshold("juggling", 1, 15) is None  # level 1 has no entry test
    assert levels.meets("sprint_30m", 4.6, 4.7) and not levels.meets("sprint_30m", 4.8, 4.7)


def _results(level, age=20):
    return {t: levels.threshold(t, level, age) for t in levels.tests()}


def test_benchmark_level_needs_enough_tests():
    assert levels.benchmark_level({}, 20) == 1
    assert levels.benchmark_level(_results(3), 20) == 3
    partial = dict(list(_results(4).items())[:3])  # only 3 of 6 tests at level 4
    assert levels.benchmark_level({**_results(2), **partial}, 20) == 2


def test_assess_level_up_needs_tests_and_consistency():
    a = levels.assess(_results(3), 20, "male", 2, sessions_28d=2)
    assert a["next"]["tests_met"] >= 4 and not a["consistency"]["ok"]
    assert not a["ready_to_level_up"]
    b = levels.assess(_results(3), 20, "male", 2, sessions_28d=12)
    assert b["ready_to_level_up"]
    top = levels.assess(_results(5), 20, "male", 5, sessions_28d=30)
    assert top["next"] is None and not top["ready_to_level_up"]


def test_focus_is_weakest_tests():
    r = _results(4)
    r["juggling"] = 5  # far below
    r.pop("weak_foot_10")  # not tested
    a = levels.assess(r, 20, "male", 3, 0)
    assert set(a["focus"]) == {"juggling", "weak_foot_10"}
    assert levels.focus_kpis(a["focus"]) == ["technique"]


# --------------------------------------------------------------------------- API


@pytest.fixture(scope="module")
def client():
    init_db()
    with SessionLocal() as db:
        seed(db, n_players=4)
    with TestClient(app) as c:
        yield c


def _signup(c, email, age=19, **kw):
    today = clock.today()
    body = {
        "name": "Sam Amateur",
        "email": email,
        "password": "goodpassword",
        "birth_date": (today - timedelta(days=round(age * 365.25))).isoformat(),
        "position": "winger",
        "level": 2,
        "team_days": [1, 3],
        "match_day": 5,
        "equipment": "home",
        "accept_terms": True,
        **kw,
    }
    return c.post("/api/auth/register", json=body)


def test_register_validation(client):
    assert _signup(client, "x@example.com", accept_terms=False).status_code == 422
    assert _signup(client, "young@example.com", age=12).status_code == 422
    assert _signup(client, "minor@example.com", age=14).status_code == 422  # needs a parent's email
    assert _signup(client, "not-an-email").status_code == 422
    assert _signup(client, "coach@demo.pathtopro").status_code == 409


def test_adult_signup_gets_a_planned_week_around_the_club(client):
    r = _signup(client, "sam@example.com")
    assert r.status_code == 201, r.text
    h = {"Authorization": f"Bearer {r.json()['token']}"}
    assert r.json()["user"]["pathway"] == "amateur" and r.json()["guardian_invite"] is None
    week = client.get("/api/me/week?offset=1", headers=h).json()  # a full week
    kinds = {date.fromisoformat(d["date"]).weekday(): d for d in week["days"]}
    assert kinds[5]["kind"] == "match"
    assert all(kinds[d]["kind"] in ("technical", "tactical") and kinds[d]["team_day"] for d in (1, 3))
    assert kinds[4]["rpe"] <= 4  # day before the match stays easy
    assert any(d["kind"] == "rest" for d in week["days"])
    today = client.get("/api/me/today", headers=h).json()
    assert today["pathway"]["level"] == 2 and today["consent"]["test_results"]

    gym = client.get("/api/me/gym?offset=1", headers=h).json()
    assert gym["position"] == "winger" and gym["equipment"] == "home"
    progs = [s["programme"] for s in gym["sessions"]] or [gym["optional"]]
    for prog in progs:
        assert {b["tag"] for b in prog["blocks"]} >= {"everyone"}
        assert all(it["equipment"] in {"bodyweight", "band", "dumbbell", "partner", "bench", "box"} for b in prog["blocks"] for it in b["items"])

    # Academy-only screens and staff screens stay closed
    assert client.get("/api/coach/heatmap", headers=h).status_code == 403


def test_tests_and_level_up(client):
    h = {"Authorization": f"Bearer {client.post('/api/auth/login', json={'email': 'sam@example.com', 'password': 'goodpassword'}).json()['token']}"}
    assert client.post("/api/me/pathway/tests", json={"test": "juggling", "value": -1}, headers=h).status_code == 422
    assert client.post("/api/me/pathway/tests", json={"test": "bench_press", "value": 50}, headers=h).status_code == 422
    today = clock.today()
    for k in range(10):  # consistent training: logged sessions in the last week (some days twice)
        k = k % 7
        r = client.post("/api/me/log", json={"kind": "technical", "minutes": 60, "rpe": 5, "day": (today - timedelta(days=k)).isoformat()}, headers=h)
        assert r.status_code == 200, r.text
    assert client.post("/api/me/log", json={"kind": "technical", "minutes": 60, "rpe": 5, "day": (today + timedelta(days=1)).isoformat()}, headers=h).status_code == 422
    view, ups = None, 0
    for test, value in _results(3).items():
        view = client.post("/api/me/pathway/tests", json={"test": test, "value": value}, headers=h).json()
        ups += view["levelled_up"]
    assert view["profile"]["level"] == 3 and ups == 1  # one level at a time
    assert view["assessment"]["next"]["level"] == 4
    assert len(view["ladder"]) == 5 and view["note"]


def test_minor_needs_parent_consent_then_parent_links(client):
    r = _signup(client, "kid@example.com", age=14, guardian_email="parent@example.com")
    assert r.status_code == 201, r.text
    code = r.json()["guardian_invite"]
    assert code and len(code) == 8
    h = {"Authorization": f"Bearer {r.json()['token']}"}
    # No consent yet: plan works, but no health data or tests are stored
    assert client.get("/api/me/week", headers=h).status_code == 200
    assert client.post("/api/me/pathway/tests", json={"test": "juggling", "value": 30}, headers=h).status_code == 403
    assert client.post("/api/me/log", json={"kind": "technical", "minutes": 30, "rpe": 4}, headers=h).status_code == 403
    assert client.get("/api/me/pathway", headers=h).json()["guardian_invite"] == code

    assert client.post("/api/auth/register/guardian", json={"invite_code": "WRONG123", "name": "Pa", "password": "goodpassword"}).status_code == 404
    g = client.post("/api/auth/register/guardian", json={"invite_code": code.lower(), "name": "Pat Parent", "password": "goodpassword"})
    assert g.status_code == 201, g.text
    gh = {"Authorization": f"Bearer {g.json()['token']}"}
    kids = client.get("/api/guardian/children", headers=gh).json()
    assert len(kids) == 1
    kid = kids[0]["id"]
    for dt in ("wellness", "test_results"):
        assert client.put(f"/api/guardian/children/{kid}/consent", json={"data_type": dt, "granted": True}, headers=gh).status_code == 200
    assert client.post("/api/me/pathway/tests", json={"test": "juggling", "value": 30}, headers=h).status_code == 200
    # the code is single-use
    assert client.post("/api/auth/register/guardian", json={"invite_code": code, "name": "Xa", "password": "goodpassword"}).status_code == 404


def test_settings_change_moves_the_match(client):
    h = {"Authorization": f"Bearer {client.post('/api/auth/login', json={'email': 'sam@example.com', 'password': 'goodpassword'}).json()['token']}"}
    out = client.put("/api/me/pathway/profile", json={"match_day": 6, "team_days": [0, 2], "equipment": "gym"}, headers=h)
    assert out.status_code == 200, out.text
    week = client.get("/api/me/week?offset=1", headers=h).json()
    by_wd = {date.fromisoformat(d["date"]).weekday(): d["kind"] for d in week["days"]}
    assert by_wd[6] == "match" and by_wd[5] != "match"


def test_academy_player_gym_by_position(client):
    h = {"Authorization": f"Bearer {client.post('/api/auth/login', json={'email': 'p01@demo.pathtopro', 'password': 'demo1234'}).json()['token']}"}
    gym = client.get("/api/me/gym", headers=h).json()
    assert gym["equipment"] == "gym" and gym["position"]
    assert client.get("/api/me/pathway", headers=h).status_code == 403
    assert client.put("/api/me/position", json={"position": "striker"}, headers=h).status_code == 403
