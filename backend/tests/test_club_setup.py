"""A real club from scratch: the administrator adds a team, invites a coach and a physio,
adds players (form and CSV); the coach sets the training week and the fixtures, and a
new player with no history gets a plan."""

import re
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from api import clock
from api.db import SessionLocal, init_db
from api.main import app
from api.security import hash_password
from api.services.notify import SENT
from api.services.seed import seed
from domain.enums import Role
from domain.models import Player, UserAccount
from domain.models import Session as TeamSession


@pytest.fixture(scope="module")
def client():
    init_db()
    with SessionLocal() as db:
        seed(db, n_players=4)
        db.add(UserAccount(email="admin@club.example", password_hash=hash_password("admin-password"), role=Role.ADMIN))
        db.commit()
    SENT.clear()
    with TestClient(app) as c:
        yield c


def _h(c, email, password):
    r = c.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _accept_invite(c, email, password="chosen-password"):
    mail = [m for m in SENT if m["to"] == email and m["kind"] == "invite"][-1]
    token = re.search(r"token=([\w-]+)", mail["body"]).group(1)
    assert c.post("/api/auth/token", json={"token": token}).json()["purpose"] == "invite"
    r = c.post("/api/auth/password/set", json={"token": token, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _birth(age: float) -> str:
    return (clock.today() - timedelta(days=round(age * 365.25))).isoformat()


@pytest.fixture(scope="module")
def club(client):
    admin = _h(client, "admin@club.example", "admin-password")
    team = client.post("/api/admin/squads", headers=admin, json={"name": "U17 Blue", "age_group": "u17"})
    assert team.status_code == 201, team.text
    squad_id = team.json()["id"]
    for name, email, role in (("Jo Coach", "jo@club.example", "coach"), ("Kim Physio", "kim@club.example", "physio")):
        r = client.post("/api/admin/staff", headers=admin, json={"name": name, "email": email, "role": role, "squad_id": squad_id})
        assert r.status_code == 201, r.text
    return {"admin": admin, "squad_id": squad_id}


def test_admin_only(client, club):
    coach = _h(client, "coach@demo.pathtopro", "demo1234")
    assert client.get("/api/admin/overview", headers=coach).status_code == 403
    ov = client.get("/api/admin/overview", headers=club["admin"]).json()
    assert "U17 Blue" in [s["name"] for s in ov["squads"]]
    jo = next(s for s in ov["staff"] if s["email"] == "jo@club.example")
    assert jo["invite_pending"] and jo["squad_id"] == club["squad_id"]


def test_invited_staff_cannot_sign_in_until_they_set_a_password(client, club):
    assert client.post("/api/auth/login", json={"email": "jo@club.example", "password": "invited$"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "jo@club.example", "password": ""}).status_code == 401
    coach = _accept_invite(client, "jo@club.example")
    assert client.get("/api/auth/me", headers=coach).json()["role"] == "coach"
    assert client.get("/api/coach/heatmap", headers=coach).status_code == 200


def test_add_players_by_form(client, club):
    url = f"/api/admin/squads/{club['squad_id']}/players"
    young = {"name": "Ada Young", "birth_date": _birth(14.5), "position": "winger", "email": "ada@club.example"}
    assert client.post(url, headers=club["admin"], json=young).status_code == 422  # under 16: parent needed
    r = client.post(url, headers=club["admin"], json={**young, "guardian_email": "ada.parent@club.example"})
    assert r.status_code == 201, r.text
    assert r.json()["invited"] and r.json()["parent_invited"]
    assert [m for m in SENT if m["to"] == "ada.parent@club.example" and m["kind"] == "guardian_invite"]
    assert client.post(url, headers=club["admin"], json={**young, "guardian_email": "x@club.example"}).status_code == 422  # email taken
    with SessionLocal() as db:
        p = db.scalars(select(Player).where(Player.email == "ada@club.example")).one()
        assert p.escalation_contact_id is not None  # the team's physio


def test_csv_import_checks_every_row_before_saving(client, club):
    url = f"/api/admin/squads/{club['squad_id']}/players/import"
    good = f"Ben Older,{_birth(17)},male,striker,ben@club.example,\n"
    bad = "No Birthday,,male,goalkeeper,,\n"
    csv_text = "name,birth_date,sex,position,email,guardian_email\n" + good + bad
    r = client.post(url, headers=club["admin"], files={"file": ("squad.csv", csv_text, "text/csv")}, data={"dry_run": "false"})
    assert r.status_code == 200, r.text
    assert not r.json()["saved"] and r.json()["errors"][0]["line"] == 3
    with SessionLocal() as db:
        assert db.scalars(select(Player).where(Player.email == "ben@club.example")).first() is None
    # Semicolons (German spreadsheet), a dry run first, then for real
    semi = f"name;birth_date;position;email\nBen Older;{_birth(17)};striker;ben@club.example\nCai Keeper;{_birth(18)};goalkeeper;\n"
    dry = client.post(url, headers=club["admin"], files={"file": ("squad.csv", semi, "text/csv")}, data={"dry_run": "true"}).json()
    assert dry["valid"] == 2 and not dry["errors"] and not dry["saved"]
    real = client.post(url, headers=club["admin"], files={"file": ("squad.csv", semi, "text/csv")}, data={"dry_run": "false"}).json()
    assert real["saved"] and real["valid"] == 2
    assert [m for m in SENT if m["to"] == "ben@club.example" and m["kind"] == "invite"]


def test_coach_sets_training_week_and_fixtures(client, club):
    coach = _h(client, "jo@club.example", "chosen-password")
    week = [
        {"weekday": 0, "kind": "technical", "minutes": 75, "rpe": 5},
        {"weekday": 2, "kind": "tactical", "minutes": 80, "rpe": 6},
        {"weekday": 3, "kind": "speed", "minutes": 50, "rpe": 6},
    ]
    bad = client.put("/api/coach/schedule/week", headers=coach, json={"days": [{"weekday": 1, "kind": "speed", "minutes": 50, "rpe": 3}]})
    assert bad.status_code == 422  # speed below RPE 5 doesn't train speed
    r = client.put("/api/coach/schedule/week", headers=coach, json={"days": week})
    assert r.status_code == 200, r.text
    assert r.json()["added"] == 3 * 8  # 8 weeks ahead: 56 days hold each weekday 8 times
    today = clock.today()
    monday = today + timedelta(days=(0 - today.weekday()) % 7 or 7)
    fx = client.post("/api/coach/fixtures", headers=coach, json={"opponent": "FC Rival", "kickoff": f"{monday.isoformat()}T18:30"})
    assert fx.status_code == 201, fx.text
    assert fx.json()["is_evening"]
    assert client.post("/api/coach/fixtures", headers=coach, json={"opponent": "Twice", "kickoff": f"{monday.isoformat()}T10:00"}).status_code == 409
    with SessionLocal() as db:
        on_day = db.scalars(select(TeamSession).where(TeamSession.squad_id == club["squad_id"], TeamSession.day == monday)).all()
        assert on_day == []  # the match replaced that day's training
    assert client.delete(f"/api/coach/fixtures/{fx.json()['id']}", headers=coach).status_code == 200
    with SessionLocal() as db:
        assert db.scalars(select(TeamSession).where(TeamSession.squad_id == club["squad_id"], TeamSession.day == monday)).first()
    physio = _accept_invite(client, "kim@club.example")
    assert client.get("/api/coach/schedule", headers=physio).status_code == 200
    assert client.put("/api/coach/schedule/week", headers=physio, json={"days": week}).status_code == 403


def test_new_player_without_history_gets_a_plan(client, club):
    """The first nightly run for a brand-new squad must not fail on players with no data."""
    coach = _h(client, "jo@club.example", "chosen-password")
    out = client.post("/api/coach/run-nightly", headers=coach)
    assert out.status_code == 200, out.text
    ben = _accept_invite(client, "ben@club.example")
    today = client.get("/api/me/today", headers=ben)
    assert today.status_code == 200, today.text
    week = client.get("/api/me/week", headers=ben).json()
    assert {d["kind"] for d in week["days"]} - {"rest"}  # the training week reached his plan
    assert client.post(
        "/api/me/checkin",
        headers=ben,
        json={"sleep_quality": 3, "fatigue": 3, "stress": 2, "soreness": 3, "mood": "green", "sleep_hours": 8},
    ).status_code == 200


def test_staff_leaving_is_signed_out(client, club):
    physio = _h(client, "kim@club.example", "chosen-password")
    staff_id = next(s["id"] for s in client.get("/api/admin/overview", headers=club["admin"]).json()["staff"] if s["email"] == "kim@club.example")
    assert client.patch(f"/api/admin/staff/{staff_id}", headers=club["admin"], json={"active": False}).status_code == 200
    assert client.get("/api/auth/me", headers=physio).status_code == 401
    assert client.post("/api/auth/login", json={"email": "kim@club.example", "password": "chosen-password"}).status_code == 401


def test_admin_deletes_a_player(client, club):
    ov = client.get("/api/admin/overview", headers=club["admin"]).json()
    cai = next(p for p in ov["players"] if p["name"] == "Cai Keeper")
    assert client.delete(f"/api/admin/players/{cai['id']}", headers=club["admin"]).status_code == 200
    with SessionLocal() as db:
        assert db.get(Player, cai["id"]) is None
    assert client.delete(f"/api/admin/players/{cai['id']}", headers=club["admin"]).status_code == 404


def test_existing_team_sees_its_current_week_before_saving(client):
    """A team planned before the Schedule page existed: the page starts from the sessions
    already planned, so saving it unchanged keeps them."""
    coach = _h(client, "coach@demo.pathtopro", "demo1234")
    data = client.get("/api/coach/schedule", headers=coach).json()
    assert data["saved"] is False and data["training_week"]
    assert {d["kind"] for d in data["training_week"]} <= {"recovery", "technical", "tactical", "strength", "speed"}
