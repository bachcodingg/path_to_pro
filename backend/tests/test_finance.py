"""Club finances (contracts, months, bonuses, titles), club history, player line-up view."""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from api import clock
from api.db import SessionLocal, init_db
from api.main import app
from api.services.seed import seed


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


def test_club_finance_view(client):
    coach = _h(client, "coach@demo.pathtopro")
    f = client.get("/api/coach/finance", headers=coach).json()
    t = f["totals"]
    assert t["income_cents"] > 0 and t["expense_cents"] > 0 and t["net_cents"] == t["income_cents"] - t["expense_cents"]
    assert t["overdue_count"] == 3  # three families a month behind
    cats = {c["category"] for c in f["categories"]}
    assert {"academy_fee", "staff", "field_rental", "sponsorship"} <= cats
    assert any(c["kind"] == "academy_fee" for c in f["contracts"])
    assert len(f["months"]) >= 2
    # physios and players don't see club money
    assert client.get("/api/coach/finance", headers=_h(client, "physio@demo.pathtopro")).status_code == 403
    assert client.get("/api/coach/finance", headers=_h(client, "p03@demo.pathtopro")).status_code == 403


def test_run_month_is_idempotent_and_mark_paid(client):
    coach = _h(client, "coach@demo.pathtopro")
    month = clock.today().strftime("%Y-%m")
    a = client.post("/api/coach/finance/run-month", headers=coach, json={"month": month}).json()
    assert a["booked"] == 0  # already booked by the seed: nothing twice
    due = next(e for e in a["ledger"] if e["status"] == "due")
    after = client.post(f"/api/coach/finance/entries/{due['id']}/paid", headers=coach, json={"paid": True}).json()
    assert next(e for e in after["ledger"] if e["id"] == due["id"])["status"] == "paid"
    future = (clock.today() + timedelta(days=70)).strftime("%Y-%m")
    assert client.post("/api/coach/finance/run-month", headers=coach, json={"month": future}).status_code == 422


def test_contracts_and_manual_entries(client):
    coach = _h(client, "coach@demo.pathtopro")
    pid = client.get("/api/coach/heatmap", headers=coach).json()["players"][0]["id"]
    bad = client.post("/api/coach/finance/contracts", headers=coach,
                      json={"player_id": pid, "kind": "pro", "amount_cents": 100, "starts_on": "2026-01-01", "bonus": {"hattrick": 5}})  # fmt: skip
    assert bad.status_code == 422
    ok = client.post("/api/coach/finance/contracts", headers=coach,
                     json={"player_id": pid, "kind": "pro", "amount_cents": 250000, "starts_on": "2026-01-01", "bonus": {"goal": 20000}})  # fmt: skip
    assert ok.status_code == 201 and any(c["kind"] == "pro" for c in ok.json()["contracts"])
    e = client.post("/api/coach/finance/entries", headers=coach,
                    json={"day": clock.today().isoformat(), "category": "equipment", "direction": "expense", "amount_cents": 4500, "description": "Bibs"})  # fmt: skip
    assert e.status_code == 201 and any(x["description"] == "Bibs" for x in e.json()["ledger"])
    assert client.post("/api/coach/finance/entries", headers=coach,
                       json={"day": "2026-01-01", "category": "bitcoin", "direction": "income", "amount_cents": 1, "description": "x"}).status_code == 422  # fmt: skip


def test_bonuses_follow_match_stats_and_titles(client):
    men = _h(client, "mencoach@demo.pathtopro")
    f = client.get("/api/coach/finance", headers=men).json()
    assert f["bonuses"], "dual players earned appearance/win/goal bonuses in men's matches"
    m = client.get("/api/coach/matches", headers=men).json()[0]
    rep = client.get(f"/api/coach/matches/{m['id']}", headers=men).json()
    with_bonus = {b["player_id"] for b in f["bonuses"]}
    row = next(r for r in rep["players"] if r["player"]["id"] in with_bonus)
    # Only the primary team's coach decides plans, but the men's coach owns his stats
    body = {"players": [{"player_id": row["player"]["id"], "minutes": 90, "started": True, "stats": {"goals": 2, "result": "win"}}]}
    assert client.put(f"/api/coach/matches/{m['id']}/ratings", headers=men, json=body).status_code == 200
    after = client.get("/api/coach/finance", headers=men).json()
    goal = [e for e in after["ledger"] if e["match_id"] == m["id"] and "Goal bonus" in e["description"] and row["player"]["name"] in e["description"]]
    assert goal and goal[0]["amount_cents"] == 20000  # 2 goals x 100 EUR
    body["players"][0]["stats"] = {"goals": 1, "result": "win"}
    client.put(f"/api/coach/matches/{m['id']}/ratings", headers=men, json=body)
    again = client.get("/api/coach/finance", headers=men).json()
    goal = [e for e in again["ledger"] if e["match_id"] == m["id"] and "Goal bonus" in e["description"] and row["player"]["name"] in e["description"]]
    assert goal[0]["amount_cents"] == 10000  # unpaid bonus followed the correction

    t = client.post("/api/coach/finance/titles", headers=men, json={"title": "Kakkonen Group A", "prize_cents": 500000}).json()
    assert t["booked"] == 1 + 3  # prize money + 3 title bonuses
    assert client.post("/api/coach/finance/titles", headers=men, json={"title": "Kakkonen Group A", "prize_cents": 500000}).json()["booked"] == 0


def test_player_and_guardian_money(client):
    dual = client.get("/api/me/finance", headers=_h(client, "dual@demo.pathtopro")).json()
    assert dual["salary_cents"] > 0 and dual["bonus_cents"] > 0 and dual["fees_paid_cents"] > 0
    assert {c["kind"] for c in dual["contracts"]} >= {"academy_fee", "semi_pro"}
    g = _h(client, "guardian02@demo.pathtopro")
    kid = client.get("/api/guardian/children", headers=g).json()[0]["id"]
    fees = client.get(f"/api/guardian/children/{kid}/finance", headers=g).json()
    assert fees["contracts"][0]["kind"] == "academy_fee"


def test_club_history_and_player_lineup(client):
    h = _h(client, "dual@demo.pathtopro")
    car = client.get("/api/me/career", headers=h).json()
    clubs = [c["club"] for c in car["clubs"]]
    assert clubs[:2] == ["FC Lahti", "FC Honka"] and "HooGee" in clubs and clubs[-1] == "PathToPro FC"  # current club last (shown first)
    lahti = car["clubs"][0]
    assert lahti["teams"] == ["U12", "U13"] and lahti["from"] < lahti["to"]
    hoogee = next(c for c in car["clubs"] if c["club"] == "HooGee")
    assert "Kolmonen" in hoogee["competitions"]
    now = next(c for c in car["clubs"] if c["club"] == "PathToPro FC")
    assert now["current"] and {"U19", "Men"} <= set(now["teams"])

    mid = [r["match_id"] for r in car["recent"] if "Men" in r["team"]][-1]  # one no other test edits
    lu = client.get(f"/api/me/matches/{mid}", headers=h).json()
    assert len([r for r in lu["players"] if r["minutes"] > 0]) >= 11
    starters = [r for r in lu["players"] if r["started"]]
    groups = {"goalkeeper": "gk", "centre_back": "def", "full_back": "def", "midfielder": "mid", "winger": "fwd", "striker": "fwd"}
    assert len(starters) == 11 and sum(groups[r["position"]] == "gk" for r in starters) == 1
    assert sum(groups[r["position"]] == "def" for r in starters) == 4  # a real 4-3-3
    others = [r for r in lu["players"] if r["player"]["id"] != lu["me"]]
    assert all(r["self_rating"] is None for r in others)  # teammates' own ratings stay private
    assert any(r["recent"] for r in lu["players"])
    # a match of a team the player isn't registered with
    amateur = _h(client, "amateur@demo.pathtopro")
    assert client.get(f"/api/me/matches/{mid}", headers=amateur).status_code == 404


def test_month_helpers():
    from finance.service import month_start, next_month

    assert next_month(date(2026, 12, 15)) == date(2027, 1, 1)
    assert month_start(date(2026, 2, 28)) == date(2026, 2, 1)
