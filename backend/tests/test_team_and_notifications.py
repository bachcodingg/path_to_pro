"""Two-step sign-in, check-in reminders, web push, calendar feeds, team availability and
announcements."""

import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from api.db import SessionLocal, init_db
from api.main import app
from api.security import hash_password
from api.services import mfa, push, reminders
from api.services.notify import SENT
from api.services.seed import seed
from api.settings import settings
from domain.enums import Role
from domain.models import StaffMember, UserAccount


@pytest.fixture(scope="module")
def client():
    init_db()
    with SessionLocal() as db:
        seed(db, n_players=6)
        db.add(UserAccount(email="admin@club.example", password_hash=hash_password("admin-password"), role=Role.ADMIN))
        db.commit()
    SENT.clear()
    push.SENT.clear()
    with TestClient(app) as c:
        yield c


def _login(c, email, password="demo1234"):
    return c.post("/api/auth/login", json={"email": email, "password": password})


def _h(c, email, password="demo1234"):
    r = _login(c, email, password)
    assert r.status_code == 200 and "token" in r.json(), r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _sub(n: int) -> dict:
    return {"endpoint": f"https://push.example/send/{n}", "keys": {"p256dh": "BPk" + "x" * 80, "auth": "authsecret"}}


# --------------------------------------------------------------------------- two-step sign-in


def test_totp_matches_the_rfc_test_vector():
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"  # "12345678901234567890"
    assert mfa.code_at(secret, 59) == "287082"
    assert mfa.code_at(secret, 1111111109) == "081804"
    assert mfa.verify(secret, "287 082", at=59) and mfa.verify(secret, "287082", at=59 + 30)
    assert not mfa.verify(secret, "287082", at=59 + 90)


def test_two_step_sign_in(client):
    h = _h(client, "coach@demo.pathtopro")
    setup = client.post("/api/auth/mfa/setup", headers=h).json()
    assert setup["otpauth_uri"].startswith("otpauth://totp/PathToPro:")
    assert client.post("/api/auth/mfa/enable", headers=h, json={"code": "000000"}).status_code == 422
    on = client.post("/api/auth/mfa/enable", headers=h, json={"code": mfa.code_at(setup["secret"], time.time())})
    assert on.status_code == 200, on.text
    codes = on.json()["recovery_codes"]
    assert len(codes) == 8 and on.json()["user"]["mfa_enabled"]
    assert client.get("/api/auth/me", headers=h).status_code == 401  # other sessions sign in again

    step = _login(client, "coach@demo.pathtopro").json()
    assert step["mfa_required"] and "token" not in step
    # The step token is not an access token
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {step['mfa_token']}"}).status_code == 401
    assert client.post("/api/auth/login/mfa", json={"mfa_token": step["mfa_token"], "code": "123456"}).status_code == 401
    ok = client.post("/api/auth/login/mfa", json={"mfa_token": step["mfa_token"], "code": mfa.code_at(setup["secret"], time.time())})
    assert ok.status_code == 200 and ok.json()["user"]["role"] == "coach"

    # A recovery code works once
    step = _login(client, "coach@demo.pathtopro").json()
    assert client.post("/api/auth/login/mfa", json={"mfa_token": step["mfa_token"], "code": codes[0].lower()}).status_code == 200
    step = _login(client, "coach@demo.pathtopro").json()
    assert client.post("/api/auth/login/mfa", json={"mfa_token": step["mfa_token"], "code": codes[0]}).status_code == 401

    # A password reset proves the inbox, not the phone: the code is still asked for
    client.post("/api/auth/password/forgot", json={"email": "coach@demo.pathtopro"})
    token = re.search(r"token=([\w-]+)", [m for m in SENT if m["kind"] == "reset"][-1]["body"]).group(1)
    reset = client.post("/api/auth/password/set", json={"token": token, "password": "demo1234"}).json()
    assert reset["mfa_required"] and "token" not in reset

    # Lost phone: the administrator switches it off
    admin = _h(client, "admin@club.example", "admin-password")
    with SessionLocal() as db:
        staff_id = db.scalars(select(StaffMember.id).where(StaffMember.email == "coach@demo.pathtopro")).one()
    assert client.patch(f"/api/admin/staff/{staff_id}", headers=admin, json={"reset_mfa": True}).status_code == 200
    assert "token" in _login(client, "coach@demo.pathtopro").json()


def test_turning_two_step_off_needs_the_password(client):
    h = _h(client, "physio@demo.pathtopro")
    secret = client.post("/api/auth/mfa/setup", headers=h).json()["secret"]
    h = {"Authorization": f"Bearer {client.post('/api/auth/mfa/enable', headers=h, json={'code': mfa.code_at(secret, time.time())}).json()['token']}"}
    assert client.post("/api/auth/mfa/disable", headers=h, json={"password": "wrong"}).status_code == 403
    assert client.post("/api/auth/mfa/disable", headers=h, json={"password": "demo1234"}).json()["mfa_enabled"] is False
    assert "token" in _login(client, "physio@demo.pathtopro").json()


# --------------------------------------------------------------------------- reminders and push


def _at_local(hour: int) -> datetime:
    return datetime.now(ZoneInfo(settings.timezone)).replace(hour=hour, minute=0)


def test_checkin_reminder_by_email_then_push(client):
    h = _h(client, "p02@demo.pathtopro")
    assert client.put("/api/account/reminder", headers=h, json={"hour": 4}).status_code == 422
    assert client.put("/api/account/reminder", headers=h, json={"hour": 7}).json()["reminder_hour"] == 7
    with SessionLocal() as db:
        assert reminders.send_due(db, _at_local(8)) == 0  # not this hour
        assert reminders.send_due(db, _at_local(7)) == 1
        db.commit()
    assert [m for m in SENT if m["to"] == "p02@demo.pathtopro" and m["kind"] == "reminder"]

    assert client.post("/api/account/push", headers=h, json=_sub(1)).status_code == 201
    with SessionLocal() as db:
        reminders.send_due(db, _at_local(7))
        db.commit()
    assert push.SENT[-1]["title"] == "Morning check-in"

    client.post("/api/me/checkin", headers=h, json={"sleep_quality": 2, "fatigue": 2, "stress": 2, "soreness": 2, "mood": "green"})
    with SessionLocal() as db:
        assert reminders.send_due(db, _at_local(7)) == 0  # already checked in
    coach = _h(client, "mencoach@demo.pathtopro")
    assert client.put("/api/account/reminder", headers=coach, json={"hour": 7}).status_code == 403


def test_push_test_and_unsubscribe(client):
    h = _h(client, "p03@demo.pathtopro")
    client.post("/api/account/push", headers=h, json=_sub(2))
    assert client.get("/api/account/notifications", headers=h).json()["push_devices"] == 1
    client.post("/api/account/push/test", headers=h)
    assert push.SENT[-1]["title"] == "PathToPro notifications are on"
    client.post("/api/account/push/remove", headers=h, json={"endpoint": _sub(2)["endpoint"]})
    assert client.get("/api/account/notifications", headers=h).json()["push_devices"] == 0
    bad = {**_sub(3), "endpoint": "http://not-https.example/x"}
    assert client.post("/api/account/push", headers=h, json=bad).status_code == 422


def test_red_checkin_pushes_to_the_physio(client):
    physio = _h(client, "physio@demo.pathtopro")
    client.post("/api/account/push", headers=physio, json=_sub(4))
    h = _h(client, "p04@demo.pathtopro")
    r = client.post("/api/me/checkin", headers=h, json={"sleep_quality": 5, "fatigue": 5, "stress": 6, "soreness": 3, "mood": "red"})
    assert r.json()["escalated"]
    last = push.SENT[-1]
    assert last["url"] == "/physio" and "mood" not in last["body"].lower()


# --------------------------------------------------------------------------- calendar


def test_calendar_feed(client):
    h = _h(client, "p05@demo.pathtopro")
    first = client.post("/api/account/calendar", headers=h).json()
    assert first["webcal"].startswith("webcal://")
    path = first["url"].split("://", 1)[1].split("/", 1)[1]
    ics = client.get(f"/{path}")
    assert ics.status_code == 200 and ics.headers["content-type"].startswith("text/calendar")
    body = ics.text
    assert body.startswith("BEGIN:VCALENDAR\r\n") and "BEGIN:VEVENT" in body and "Match vs" in body
    assert all(len(line.encode()) <= 75 for line in body.split("\r\n"))
    second = client.post("/api/account/calendar", headers=h).json()  # a new address cancels the old one
    assert client.get(f"/{path}").status_code == 404
    assert client.get("/" + second["url"].split("://", 1)[1].split("/", 1)[1]).status_code == 200
    coach = _h(client, "mencoach@demo.pathtopro")
    team = client.post("/api/account/calendar", headers=coach).json()
    assert "Match vs" in client.get("/" + team["url"].split("://", 1)[1].split("/", 1)[1]).text
    guardian = _h(client, "guardian01@demo.pathtopro")
    assert client.post("/api/account/calendar", headers=guardian).status_code == 403


# --------------------------------------------------------------------------- availability and announcements


def test_availability(client):
    h = _h(client, "p06@demo.pathtopro")
    data = client.get("/api/team/events", headers=h).json()
    assert data["events"] and all(e["available"] is None for e in data["events"])
    event = data["events"][0]["key"]
    r = client.put("/api/team/availability", headers=h, json={"event": event, "available": False, "reason": "school"})
    assert r.status_code == 200, r.text
    assert client.put("/api/team/availability", headers=h, json={"event": "match:" + "0" * 36, "available": False}).status_code == 404
    assert client.put("/api/team/availability", headers=h, json={"event": event, "available": False, "reason": "headache"}).status_code == 422
    coach = _h(client, "coach@demo.pathtopro")
    staff_view = next(e for e in client.get("/api/team/events", headers=coach).json()["events"] if e["key"] == event)
    assert staff_view["unavailable"][0]["reason"] == "School or exams"
    assert staff_view["no_answer"] >= 1
    amateur = _h(client, "amateur@demo.pathtopro")
    assert client.get("/api/team/events", headers=amateur).json()["events"] == []


def test_announcements(client):
    player = _h(client, "p01@demo.pathtopro")
    client.post("/api/account/push", headers=player, json=_sub(5))
    coach = _h(client, "coach@demo.pathtopro")
    physio = _h(client, "physio@demo.pathtopro")
    assert client.post("/api/team/announcements", headers=physio, json={"text": "Hi"}).status_code == 403
    a = client.post("/api/team/announcements", headers=coach, json={"text": "Bring both kits on Saturday."})
    assert a.status_code == 201
    assert push.SENT[-1]["body"] == "Bring both kits on Saturday."
    assert client.get("/api/team/announcements", headers=player).json()[0]["text"] == "Bring both kits on Saturday."
    assert client.delete(f"/api/team/announcements/{a.json()['id']}", headers=coach).status_code == 200
    assert client.get("/api/team/announcements", headers=player).json() == []


def test_announcement_times_carry_their_zone(client):
    coach = _h(client, "coach@demo.pathtopro")
    a = client.post("/api/team/announcements", headers=coach, json={"text": "Training at 17:30 today."}).json()
    assert a["created_at"].endswith("+00:00")
    client.delete(f"/api/team/announcements/{a['id']}", headers=coach)
