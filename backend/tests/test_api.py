import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from api.db import SessionLocal, init_db
from api.main import app
from api.services.seed import seed
from domain.models import AuditLog, Player, SessionLoad


@pytest.fixture(scope="module")
def demo():
    init_db()
    with SessionLocal() as db:
        info = seed(db, n_players=6)
    with TestClient(app) as client:
        yield client, info


def login(client, email, password="demo1234"):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_login_and_me(demo):
    client, _ = demo
    assert client.post("/api/auth/login", json={"email": "coach@demo.pathtopro", "password": "nope"}).status_code == 401
    h = login(client, "coach@demo.pathtopro")
    assert client.get("/api/auth/me", headers=h).json()["role"] == "coach"


def test_rbac(demo):
    client, _ = demo
    assert client.get("/api/coach/inbox").status_code == 401
    player = login(client, "p03@demo.pathtopro")
    assert client.get("/api/coach/inbox", headers=player).status_code == 403
    assert client.get("/api/physio/queue", headers=player).status_code == 403
    assert client.get("/api/guardian/children", headers=player).status_code == 403
    coach = login(client, "coach@demo.pathtopro")
    assert client.get("/api/me/today", headers=coach).status_code == 403


def test_player_screens(demo):
    client, _ = demo
    h = login(client, "p03@demo.pathtopro")
    today = client.get("/api/me/today", headers=h).json()
    assert {"readiness", "session", "tasks", "why", "streak"} <= set(today)
    week = client.get("/api/me/week", headers=h).json()
    assert len(week["days"]) == 7 and len(week["last_week"]) == 7
    growth = client.get("/api/me/growth", headers=h).json()
    assert growth["measurements"] and growth["phv_window"]
    card = client.get("/api/me/card", headers=h).json()
    assert {a["kpi"] for a in card["attributes"]} >= {"sprint_10m", "cmj"}
    road = client.get("/api/me/roadmap", headers=h).json()
    assert road["checkpoints"] and road["badges"]


def test_reads_of_health_data_are_audited(demo):
    client, _ = demo
    h = login(client, "p04@demo.pathtopro")
    with SessionLocal() as db:
        before = db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "read"))
    client.get("/api/me/today", headers=h)
    client.get("/api/me/growth", headers=h)
    with SessionLocal() as db:
        after = db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "read"))
    assert after - before >= 2


def test_normal_checkin_updates_readiness(demo):
    client, _ = demo
    h = login(client, "p05@demo.pathtopro")
    r = client.post(
        "/api/me/checkin",
        headers=h,
        json={"sleep_quality": 2, "fatigue": 2, "stress": 2, "soreness": 2, "mood": "green", "sleep_hours": 8.5, "duration_s": 21},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert not body["escalated"]
    assert body["today"]["checked_in"] and body["today"]["readiness_is_today"]


def test_red_checkin_reaches_physio_within_5_minutes(demo):
    client, _ = demo
    h = login(client, "p06@demo.pathtopro")
    r = client.post(
        "/api/me/checkin",
        headers=h,
        json={"sleep_quality": 5, "fatigue": 5, "stress": 6, "soreness": 3, "mood": "red", "duration_s": 25},
    )
    assert r.json()["escalated"]
    physio = login(client, "physio@demo.pathtopro")
    queue = client.get("/api/physio/queue", headers=physio).json()
    mine = [e for e in queue if e["kind"] == "red_mood"]
    assert mine and mine[0]["notified_after_s"] < 300
    # Acknowledge clears it from the queue.
    assert client.post(f"/api/physio/escalations/{mine[0]['id']}/ack", headers=physio).status_code == 200
    assert not [e for e in client.get("/api/physio/queue", headers=physio).json() if e["id"] == mine[0]["id"]]


def test_coach_inbox_approve_shows_why_card(demo):
    client, info = demo
    coach = login(client, "coach@demo.pathtopro")
    inbox = client.get("/api/coach/inbox", headers=coach).json()
    swaps = [p for p in inbox if p["kind"] != "new_goal"]
    assert swaps, "demo story should leave a plan change in the inbox"
    prop = next((p for p in swaps if p["player"]["name"] == info["story"]["tired_player"]), swaps[0])
    assert prop["current"] and prop["proposed"] and prop["chips"]
    r = client.post(f"/api/coach/proposals/{prop['id']}/decision", headers=coach, json={"action": "approve"})
    assert r.json()["status"] == "approved"
    # Deciding twice is refused.
    again = client.post(f"/api/coach/proposals/{prop['id']}/decision", headers=coach, json={"action": "approve"})
    assert again.status_code == 422
    with SessionLocal() as db:
        email = db.get(Player, prop["player"]["id"]).email
    why = client.get("/api/me/today", headers=login(client, email)).json()["why"]
    assert any(w["approved_by"] == "Alex Weber" for w in why)


def test_coach_edit_cannot_break_hard_rules(demo):
    client, _ = demo
    coach = login(client, "coach@demo.pathtopro")
    inbox = [p for p in client.get("/api/coach/inbox", headers=coach).json() if p["proposed"]]
    if not inbox:
        pytest.skip("no plan proposal left")
    prop = inbox[0]
    match = next((i for i, d in enumerate(prop["proposed"]) if d["kind"] == "match"), None)
    if match is None or match == 0:
        pytest.skip("no match day with a day before it")
    md1 = prop["proposed"][match - 1]["date"]
    r = client.post(
        f"/api/coach/proposals/{prop['id']}/decision",
        headers=coach,
        json={"action": "edit", "edits": [{"day": md1, "kind": "strength", "rpe": 8}]},
    )
    assert r.status_code == 422 and "H3" in r.json()["detail"]


def test_heatmap_lineup_profile_log(demo):
    client, _ = demo
    coach = login(client, "coach@demo.pathtopro")
    hm = client.get("/api/coach/heatmap", headers=coach).json()
    assert len(hm["dates"]) == 14 and len(hm["players"]) == 6
    assert any(c["band"] for p in hm["players"] for c in p["cells"])
    lu = client.get("/api/coach/lineup", headers=coach).json()
    assert len(lu["players"]) == 6
    pid = hm["players"][0]["id"]
    prof = client.get(f"/api/coach/players/{pid}", headers=coach).json()
    assert len(prof["series"]) == 56
    assert client.post(f"/api/coach/players/{pid}/notes", headers=coach, json={"text": "Good week"}).status_code == 200
    log = client.get("/api/coach/agent-log", headers=coach, params={"agent": "planner"}).json()
    assert log and all(r["agent"] == "planner" for r in log)
    csv = client.get("/api/coach/agent-log.csv", headers=coach)
    assert csv.headers["content-type"].startswith("text/csv") and "commentary" in csv.text


def test_guardian_scope_consent_export_delete(demo):
    client, _ = demo
    g = login(client, "guardian02@demo.pathtopro")
    kids = client.get("/api/guardian/children", headers=g).json()
    assert len(kids) == 1
    kid = kids[0]["id"]
    with SessionLocal() as db:
        other = db.scalars(select(Player).where(Player.id != kid)).first().id
    assert client.get(f"/api/guardian/children/{other}/summary", headers=g).status_code == 403
    assert client.get(f"/api/guardian/children/{kid}/summary", headers=g).status_code == 200

    r = client.put(f"/api/guardian/children/{kid}/consent", headers=g, json={"data_type": "wellness", "granted": False})
    assert {i["data_type"]: i["granted"] for i in r.json()["items"]}["wellness"] is False
    with SessionLocal() as db:
        email = db.get(Player, kid).email
    p = login(client, email)
    blocked = client.post(
        "/api/me/checkin", headers=p, json={"sleep_quality": 2, "fatigue": 2, "stress": 2, "soreness": 2}
    )
    assert blocked.status_code == 403
    client.put(f"/api/guardian/children/{kid}/consent", headers=g, json={"data_type": "wellness", "granted": True})

    export = client.get(f"/api/guardian/children/{kid}/export", headers=g)
    assert export.status_code == 200 and export.json()["session_loads"]
    deleted = client.delete(f"/api/guardian/children/{kid}/data", headers=g)
    assert deleted.status_code == 200 and deleted.json()["deleted"]["session_loads"] > 0
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(SessionLoad).where(SessionLoad.player_id == kid)) == 0


def test_staff_rating_and_calibration(demo):
    client, _ = demo
    coach = login(client, "coach@demo.pathtopro")
    pid = client.get("/api/coach/heatmap", headers=coach).json()["players"][0]["id"]
    r = client.post(f"/api/coach/players/{pid}/rating", headers=coach, json={"band": "amber"})
    assert r.status_code == 200 and r.json()["band"] == "amber"
    assert client.post(f"/api/coach/players/{pid}/rating", headers=coach, json={"band": "purple"}).status_code == 422

    rep = client.get("/api/coach/calibration", headers=coach).json()
    assert rep["n"] > 0 and set(rep["current"]) == {"hrv", "hooper", "sleep"}
    assert rep["hysteresis"]["down"] == 0

    bad = client.post("/api/coach/calibration/apply", headers=coach, json={"weights": {"hrv": 0.9, "hooper": 0.05, "sleep": 0.05}})
    assert bad.status_code == 422
    new = {"hrv": 0.3, "hooper": 0.5, "sleep": 0.2}
    ok = client.post("/api/coach/calibration/apply", headers=coach, json={"weights": new})
    assert ok.status_code == 200 and ok.json()["current"] == new
    reset = client.post("/api/coach/calibration/apply", headers=coach, json={"weights": None})
    assert reset.json()["current"] == {"hrv": 0.4, "hooper": 0.35, "sleep": 0.25}

    physio = login(client, "physio@demo.pathtopro")
    assert client.post("/api/coach/calibration/apply", headers=physio, json={"weights": new}).status_code == 403
    player = login(client, "p03@demo.pathtopro")
    assert client.post(f"/api/coach/players/{pid}/rating", headers=player, json={"band": "red"}).status_code == 403


def test_calibration_reports_noise_and_guards_apply(demo):
    client, _ = demo
    coach = login(client, "coach@demo.pathtopro")
    rep = client.get("/api/coach/calibration", headers=coach).json()
    assert {"recommended", "cv_noise", "cv_gain_folds", "min_gain"} <= set(rep)
    if not rep["recommended"] and rep["suggested"] != rep["current"]:
        r = client.post("/api/coach/calibration/apply", headers=coach, json={"weights": rep["suggested"]})
        assert r.status_code == 422 and "noise" in r.json()["detail"]
        forced = client.post("/api/coach/calibration/apply", headers=coach, json={"weights": rep["suggested"], "force": True})
        assert forced.status_code == 200
        client.post("/api/coach/calibration/apply", headers=coach, json={"weights": None})


def test_coach_instruction_preview_and_apply(demo):
    client, _ = demo
    coach = login(client, "coach@demo.pathtopro")
    pid = next(p["id"] for p in client.get("/api/coach/heatmap", headers=coach).json()["players"])
    url = f"/api/coach/players/{pid}/instruction"
    refused = client.post(url, headers=coach, json={"text": "his knee is painful"})
    assert refused.status_code == 422 and "physio" in refused.json()["detail"]
    assert client.post(url, headers=coach, json={"text": "great lad"}).status_code == 422

    prev = client.post(url, headers=coach, json={"text": "keep him light until tomorrow, no gym this week"})
    assert prev.status_code == 200, prev.text
    body = prev.json()
    assert body["source"] == "rules" and not body["applied"] and not body["hard_violations"]
    assert any("effort at most 4" in c for c in body["constraints"]) and "No strength sessions" in body["constraints"]
    assert all(d["kind"] != "strength" for d in body["proposed"])
    assert all(d["rpe"] <= 4 or d["kind"] == "match" for d in body["proposed"][:2])
    # asking only for less never makes a day harder
    assert all(new["rpe"] <= old["rpe"] for new, old in zip(body["proposed"], body["current"]))

    applied = client.post(url, headers=coach, json={"text": "keep him light until tomorrow, no gym this week", "apply": True})
    assert applied.status_code == 200 and applied.json()["applied"]
    prof = client.get(f"/api/coach/players/{pid}", headers=coach).json()
    assert any(c["kind"] == "coach_instruction" for c in prof["changes"])
    assert any("Plan instruction" in n["text"] for n in prof["notes"])
    assert prof["player"]["position"] and prof["gym"]["blocks"]
    log = client.get(f"/api/coach/agent-log?player={pid}", headers=coach).json()
    assert any(r["trigger"] == "coach_instruction" for r in log)
    physio = login(client, "physio@demo.pathtopro")
    assert client.post(url, headers=physio, json={"text": "rest on friday"}).status_code == 403


def test_coach_sets_position(demo):
    client, _ = demo
    coach = login(client, "coach@demo.pathtopro")
    pid = client.get("/api/coach/heatmap", headers=coach).json()["players"][0]["id"]
    r = client.put(f"/api/coach/players/{pid}/position", headers=coach, json={"position": "goalkeeper"})
    assert r.status_code == 200 and r.json()["gym"]["position"] == "goalkeeper"
    assert client.put(f"/api/coach/players/{pid}/position", headers=coach, json={"position": "libero"}).status_code == 422
