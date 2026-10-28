"""Accounts: password reset, email verification, password change, signing out everywhere,
deleting your own account, and the safety emails behind escalations."""

import re
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from api import clock
from api.db import SessionLocal, init_db
from api.main import app
from api.services.notify import SENT
from api.services.seed import seed
from domain.models import ConsentRecord, Notification, Player, UserAccount


@pytest.fixture(scope="module")
def client():
    init_db()
    with SessionLocal() as db:
        seed(db, n_players=6)
    SENT.clear()
    with TestClient(app) as c:
        yield c


def _login(c, email, password="demo1234"):
    return c.post("/api/auth/login", json={"email": email, "password": password})


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _link_token(email: str, kind: str) -> str:
    mail = [m for m in SENT if m["to"] == email and m["kind"] == kind][-1]
    return re.search(r"token=([\w-]+)", mail["body"]).group(1)


def _signup(c, email, age=19, **kw):
    body = {
        "name": "Robin Self",
        "email": email,
        "password": "goodpassword",
        "birth_date": (clock.today() - timedelta(days=round(age * 365.25))).isoformat(),
        "accept_terms": True,
        **kw,
    }
    return c.post("/api/auth/register", json=body)


def test_seeded_history_sends_no_email(client):
    with SessionLocal() as db:
        assert db.scalars(select(Notification)).first() is None
    assert client.get("/api/auth/me", headers=_h(_login(client, "p03@demo.pathtopro").json()["token"])).json()["email_verified"]


def test_forgot_password_then_reset(client):
    old = _login(client, "p03@demo.pathtopro").json()["token"]
    assert client.post("/api/auth/password/forgot", json={"email": "nobody@example.com"}).status_code == 202
    assert not [m for m in SENT if m["to"] == "nobody@example.com"]  # same answer, no email
    assert client.post("/api/auth/password/forgot", json={"email": " P03@demo.pathtopro "}).status_code == 202
    token = _link_token("p03@demo.pathtopro", "reset")
    assert client.post("/api/auth/token", json={"token": token}).json()["purpose"] == "reset"
    assert client.post("/api/auth/password/set", json={"token": token, "password": "short"}).status_code == 422
    r = client.post("/api/auth/password/set", json={"token": token, "password": "a-new-password"})
    assert r.status_code == 200, r.text
    assert client.get("/api/me/today", headers=_h(r.json()["token"])).status_code == 200
    # Older sessions are signed out, the old password is gone, and the link works once
    assert client.get("/api/auth/me", headers=_h(old)).status_code == 401
    assert _login(client, "p03@demo.pathtopro").status_code == 401
    assert _login(client, "p03@demo.pathtopro", "a-new-password").status_code == 200
    assert client.post("/api/auth/password/set", json={"token": token, "password": "another-one"}).status_code == 400
    assert client.post("/api/auth/token", json={"token": "x" * 43}).status_code == 400


def test_reset_emails_are_rate_limited(client):
    for _ in range(5):
        client.post("/api/auth/password/forgot", json={"email": "p04@demo.pathtopro"})
    assert len([m for m in SENT if m["to"] == "p04@demo.pathtopro" and m["kind"] == "reset"]) == 3


def test_change_password_and_sign_out_everywhere(client):
    phone = _login(client, "p05@demo.pathtopro").json()["token"]
    laptop = _login(client, "p05@demo.pathtopro").json()["token"]
    bad = client.post("/api/auth/password/change", headers=_h(laptop), json={"current_password": "wrong", "new_password": "longenough"})
    assert bad.status_code == 403
    r = client.post("/api/auth/password/change", headers=_h(laptop), json={"current_password": "demo1234", "new_password": "longenough"})
    assert r.status_code == 200
    fresh = r.json()["token"]
    assert client.get("/api/auth/me", headers=_h(phone)).status_code == 401
    assert client.get("/api/auth/me", headers=_h(fresh)).status_code == 200
    assert client.post("/api/auth/logout-everywhere", headers=_h(fresh)).status_code == 200
    assert client.get("/api/auth/me", headers=_h(fresh)).status_code == 401


def test_signup_sends_verification_and_parent_invite(client):
    r = _signup(client, "young@example.com", age=14, guardian_email="parent@example.com")
    assert r.status_code == 201, r.text
    h = _h(r.json()["token"])
    assert r.json()["user"]["email_verified"] is False
    invite = [m for m in SENT if m["to"] == "parent@example.com" and m["kind"] == "guardian_invite"][-1]
    assert r.json()["guardian_invite"] in invite["body"]
    v = client.post("/api/auth/verify-email", json={"token": _link_token("young@example.com", "verify")})
    assert v.status_code == 200
    assert client.get("/api/auth/me", headers=h).json()["email_verified"] is True
    assert client.post("/api/auth/verify-email/resend", headers=h).json()["already_verified"] is True


def test_adult_deletes_own_account(client):
    r = _signup(client, "leaving@example.com")
    h = _h(r.json()["token"])
    player_id = r.json()["user"]["player_id"]
    client.post("/api/me/checkin", headers=h, json={"sleep_quality": 2, "fatigue": 2, "stress": 2, "soreness": 2, "mood": "green"})
    assert client.get("/api/auth/me/deletion", headers=h).json()["allowed"] is True
    assert client.post("/api/auth/me/delete", headers=h, json={"password": "wrong"}).status_code == 403
    assert client.post("/api/auth/me/delete", headers=h, json={"password": "goodpassword"}).status_code == 200
    assert _login(client, "leaving@example.com", "goodpassword").status_code == 401
    with SessionLocal() as db:
        assert db.get(Player, player_id) is None
        assert db.scalars(select(UserAccount).where(UserAccount.email == "leaving@example.com")).first() is None


def test_who_can_delete_themselves(client):
    academy = _h(_login(client, "p06@demo.pathtopro").json()["token"])
    rule = client.get("/api/auth/me/deletion", headers=academy).json()
    assert rule["allowed"] is False and "club" in rule["reason"]
    assert client.post("/api/auth/me/delete", headers=academy, json={"password": "demo1234"}).status_code == 403
    coach = _h(_login(client, "coach@demo.pathtopro").json()["token"])
    assert client.get("/api/auth/me/deletion", headers=coach).json()["allowed"] is False


def test_guardian_deletes_own_account_and_consent_stays_on_record(client):
    with SessionLocal() as db:  # a parent who gave consent (child under 16)
        rec = db.scalars(select(ConsentRecord).where(ConsentRecord.guardian_id.is_not(None))).first()
        email = db.scalars(select(UserAccount.email).where(UserAccount.guardian_id == rec.guardian_id)).one()
    h = _h(_login(client, email).json()["token"])
    kid = client.get("/api/guardian/children", headers=h).json()[0]["id"]
    assert client.post("/api/auth/me/delete", headers=h, json={"password": "demo1234"}).status_code == 200
    assert _login(client, email).status_code == 401
    with SessionLocal() as db:
        assert db.get(Player, kid) is not None  # the child's account is untouched
        records = db.scalars(select(ConsentRecord).where(ConsentRecord.player_id == kid)).all()
        assert records and all(r.guardian_id is None for r in records)


def test_red_checkin_emails_the_named_adult(client):
    h = _h(_login(client, "p01@demo.pathtopro").json()["token"])
    r = client.post(
        "/api/me/checkin",
        headers=h,
        json={"sleep_quality": 5, "fatigue": 5, "stress": 6, "soreness": 3, "mood": "red", "duration_s": 25},
    )
    assert r.json()["escalated"]
    mail = [m for m in SENT if m["kind"] == "escalation"][-1]
    assert mail["to"] == "physio@demo.pathtopro"
    assert "/physio" in mail["body"] and "mood" not in mail["body"].lower()  # no health detail by email
    physio = _h(_login(client, "physio@demo.pathtopro").json()["token"])
    item = [e for e in client.get("/api/physio/queue", headers=physio).json() if e["kind"] == "red_mood"][0]
    assert item["emailed_after_s"] is not None and item["emailed_after_s"] < 300


def test_failed_email_is_retried(client, monkeypatch):
    from api.services import notify

    calls = []

    def flaky(n):
        calls.append(n.id)
        if len(calls) == 1:
            raise OSError("mail server down")
        SENT.append({"to": n.to_email, "kind": n.kind, "subject": n.subject, "body": n.body})

    monkeypatch.setattr(notify, "_send", flaky)
    client.post("/api/auth/password/forgot", json={"email": "p02@demo.pathtopro"})
    with SessionLocal() as db:
        n = db.scalars(select(Notification).where(Notification.to_email == "p02@demo.pathtopro")).one()
        assert n.sent_at is None and n.attempts == 1 and "mail server down" in n.error
    assert notify.deliver_pending() == 1
    with SessionLocal() as db:
        assert db.get(Notification, n.id).sent_at is not None
