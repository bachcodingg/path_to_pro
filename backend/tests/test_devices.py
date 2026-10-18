"""Apple Watch / Apple Health: export parsing, Shortcut ingest, tokens, consent, safety."""

import io
import zipfile
from datetime import date, datetime, timedelta

import pytest
from defusedxml import DefusedXmlException
from fastapi.testclient import TestClient

from api import clock
from api.db import SessionLocal, init_db
from api.main import app
from api.services.seed import seed
from devices.apple_health import HealthPayload, Workout, daily_hrv, estimate_rpe, merge_hours, night_of, parse_export


def _export(today: date) -> bytes:
    """A small synthetic export.xml in Apple's format (with its internal DTD)."""
    d1, d0 = today - timedelta(days=1), today

    def ts(d: date, hm: str) -> str:
        return f"{d.isoformat()} {hm}:00 +0200"

    rows = [
        # HRV: two morning samples and one evening sample yesterday; one this morning
        f'<Record type="HKQuantityTypeIdentifierHeartRateVariabilitySDNN" sourceName="Watch" unit="ms" startDate="{ts(d1, "06:50")}" endDate="{ts(d1, "06:51")}" value="50"/>',
        f'<Record type="HKQuantityTypeIdentifierHeartRateVariabilitySDNN" sourceName="Watch" unit="ms" startDate="{ts(d1, "08:10")}" endDate="{ts(d1, "08:11")}" value="60"/>',
        f'<Record type="HKQuantityTypeIdentifierHeartRateVariabilitySDNN" sourceName="Watch" unit="ms" startDate="{ts(d1, "21:00")}" endDate="{ts(d1, "21:01")}" value="90"/>',
        f'<Record type="HKQuantityTypeIdentifierHeartRateVariabilitySDNN" sourceName="Watch" unit="ms" startDate="{ts(d0, "07:00")}" endDate="{ts(d0, "07:01")}" value="42"/>',
        # Sleep last night: Watch stages plus an overlapping iPhone "asleep" block, and in-bed time
        f'<Record type="HKCategoryTypeIdentifierSleepAnalysis" sourceName="Watch" startDate="{ts(d1, "23:00")}" endDate="{ts(d0, "02:00")}" value="HKCategoryValueSleepAnalysisAsleepCore"/>',
        f'<Record type="HKCategoryTypeIdentifierSleepAnalysis" sourceName="Watch" startDate="{ts(d0, "02:00")}" endDate="{ts(d0, "06:30")}" value="HKCategoryValueSleepAnalysisAsleepDeep"/>',
        f'<Record type="HKCategoryTypeIdentifierSleepAnalysis" sourceName="iPhone" startDate="{ts(d1, "23:30")}" endDate="{ts(d0, "05:00")}" value="HKCategoryValueSleepAnalysisAsleepUnspecified"/>',
        f'<Record type="HKCategoryTypeIdentifierSleepAnalysis" sourceName="iPhone" startDate="{ts(d1, "22:30")}" endDate="{ts(d0, "07:00")}" value="HKCategoryValueSleepAnalysisInBed"/>',
        # Old data, ignored
        '<Record type="HKQuantityTypeIdentifierHeartRateVariabilitySDNN" sourceName="Watch" unit="ms" startDate="2015-01-01 07:00:00 +0100" endDate="2015-01-01 07:01:00 +0100" value="70"/>',
        # A football session with heart rate
        f'<Workout workoutActivityType="HKWorkoutActivityTypeSoccer" duration="88.5" durationUnit="min" sourceName="Watch" startDate="{ts(d1, "17:00")}" endDate="{ts(d1, "18:30")}">'
        f'<WorkoutStatistics type="HKQuantityTypeIdentifierHeartRate" startDate="{ts(d1, "17:00")}" endDate="{ts(d1, "18:30")}" average="160" minimum="90" maximum="195" unit="count/min"/>'
        "</Workout>",
    ]
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE HealthData [\n<!ELEMENT HealthData (ExportDate,Me,(Record|Workout)*)>\n'
        '<!ATTLIST HealthData locale CDATA #REQUIRED>\n]>\n<HealthData locale="en_FI">\n<ExportDate value="x"/>\n<Me/>\n'
        + "\n".join(rows)
        + "\n</HealthData>\n"
    )
    return xml.encode()


def test_helpers():
    t = datetime.fromisoformat
    assert night_of(t("2026-10-18T06:30:00+02:00")) == date(2026, 10, 18)
    assert night_of(t("2026-10-17T23:59:00+02:00")) == date(2026, 10, 18)
    a, b = t("2026-10-17T23:00:00+02:00"), t("2026-10-18T03:00:00+02:00")
    c, d = t("2026-10-18T02:00:00+02:00"), t("2026-10-18T06:00:00+02:00")
    assert merge_hours([(a, b), (c, d)]) == pytest.approx(7.0)  # overlap counted once
    hrv = daily_hrv([(t("2026-10-18T07:00:00+00:00"), 40), (t("2026-10-18T20:00:00+00:00"), 100)])
    assert hrv[date(2026, 10, 18)] == 40  # morning sample wins
    w = Workout("x", t("2026-10-18T17:00:00+00:00"), 90, "soccer", avg_hr=165)
    assert 7 <= estimate_rpe(w, 17) <= 9
    assert estimate_rpe(Workout("y", w.start, 30, "walking"), 17) == 2


def test_parse_export():
    today = date(2026, 10, 18)
    b = parse_export(io.BytesIO(_export(today)), today - timedelta(days=60))
    assert b.hrv_sdnn[today - timedelta(days=1)] == pytest.approx(55)  # morning mean, evening ignored
    assert b.hrv_sdnn[today] == pytest.approx(42)
    assert b.sleep_hours[today] == pytest.approx(7.5)  # 23:00-06:30, in-bed not counted
    assert len(b.workouts) == 1 and b.workouts[0].avg_hr == 160 and b.workouts[0].kind == "soccer"
    assert all(d.year > 2020 for d in b.hrv_sdnn)


def test_malicious_xml_is_refused():
    bomb = (
        b'<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol"><!ENTITY lol2 "&lol;&lol;&lol;&lol;">]>'
        b"<HealthData><Record type='x' value='&lol2;'/></HealthData>"
    )
    with pytest.raises(DefusedXmlException):  # entity expansion forbidden
        parse_export(io.BytesIO(bomb), date(2026, 1, 1))
    external = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><HealthData>&e;</HealthData>'
    with pytest.raises(DefusedXmlException):  # external entities forbidden
        parse_export(io.BytesIO(external), date(2026, 1, 1))


def test_shortcut_payload():
    p = HealthPayload.model_validate(
        {
            "days": [{"date": "2026-10-18", "hrv_sdnn_ms": 48, "sleep_hours": 7.2}],
            "workouts": [{"start": "2026-10-17T17:00:00+02:00", "minutes": 75, "type": "Soccer", "avg_hr": 150}],
        }
    )
    b = p.to_batch()
    assert b.hrv_sdnn[date(2026, 10, 18)] == 48 and b.sleep_hours[date(2026, 10, 18)] == 7.2
    assert b.workouts[0].kind == "soccer"
    with pytest.raises(ValueError):
        HealthPayload.model_validate({"days": [{"date": "2026-10-18", "hrv_sdnn_ms": -3}]})


# --------------------------------------------------------------------------- API


@pytest.fixture(scope="module")
def client():
    init_db()
    with SessionLocal() as db:
        seed(db, n_players=4)
    with TestClient(app) as c:
        yield c


def _h(c, email="amateur@demo.pathtopro"):
    r = c.post("/api/auth/login", json={"email": email, "password": "demo1234"})
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_token_lifecycle_and_shortcut_ingest(client):
    h = _h(client)
    out = client.post("/api/me/devices", headers=h, json={"label": "Maya's Apple Watch"})
    assert out.status_code == 201
    token = out.json()["new_token"]["token"]
    assert token.startswith("ptp_") and out.json()["ingest_url"].endswith("/api/ingest/apple-health")
    listed = client.get("/api/me/devices", headers=h).json()
    assert all("token" not in t for t in listed["tokens"])  # never shown again

    today = clock.today()
    payload = {
        "days": [{"date": (today - timedelta(days=k)).isoformat(), "hrv_sdnn_ms": 50 + k, "sleep_hours": 7.5} for k in range(8)],
        "workouts": [{"id": "w1", "start": f"{(today - timedelta(days=2)).isoformat()}T17:00:00+02:00", "minutes": 60, "type": "soccer", "avg_hr": 150}],
    }
    r = client.post("/api/ingest/apple-health", headers={"Authorization": f"Bearer {token}"}, json=payload)
    assert r.status_code == 200, r.text
    assert r.json()["hrv_days"] == 8 and r.json()["sleep_nights"] == 8
    again = client.post("/api/ingest/apple-health", headers={"Authorization": f"Bearer {token}"}, json=payload).json()
    assert again["workouts"] == 0  # the same workout isn't counted twice
    # The readiness now uses the watch's HRV (SDNN baseline)
    today_view = client.get("/api/me/today", headers=h).json()
    assert "hrv" in (today_view["readiness"] or {}).get("components", {})

    assert client.post("/api/ingest/apple-health", headers={"Authorization": "Bearer ptp_wrong"}, json=payload).status_code == 401
    assert client.post("/api/ingest/apple-health", json=payload).status_code == 401
    # a login token is not a device token
    assert client.post("/api/ingest/apple-health", headers=h, json=payload).status_code == 401
    tid = listed["tokens"][0]["id"]
    assert client.delete(f"/api/me/devices/{tid}", headers=h).status_code == 200
    assert client.post("/api/ingest/apple-health", headers={"Authorization": f"Bearer {token}"}, json=payload).status_code == 401


def test_export_upload(client):
    h = _h(client)
    today = clock.today()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("apple_health_export/export.xml", _export(today))
        z.writestr("apple_health_export/export_cda.xml", "<x/>")
    r = client.post("/api/me/health/import", headers=h, files={"file": ("export.zip", buf.getvalue(), "application/zip")})
    assert r.status_code == 200, r.text
    assert r.json()["hrv_days"] == 2 and r.json()["sleep_nights"] == 1
    bad = client.post("/api/me/health/import", headers=h, files={"file": ("x.zip", b"hello", "application/zip")})
    assert bad.status_code == 422
    coach = _h(client, "coach@demo.pathtopro")
    assert client.post("/api/me/health/import", headers=coach, files={"file": ("export.zip", buf.getvalue())}).status_code == 403


def test_minor_without_consent_stores_nothing(client):
    r = client.post(
        "/api/auth/register",
        json={
            "name": "Kid A.",
            "email": "kidwatch@example.com",
            "password": "goodpassword",
            "birth_date": (clock.today() - timedelta(days=round(14 * 365.25))).isoformat(),
            "guardian_email": "parentwatch@example.com",
            "accept_terms": True,
        },
    )
    h = {"Authorization": f"Bearer {r.json()['token']}"}
    token = client.post("/api/me/devices", headers=h, json={}).json()["new_token"]["token"]
    out = client.post(
        "/api/ingest/apple-health",
        headers={"Authorization": f"Bearer {token}"},
        json={"days": [{"date": clock.today().isoformat(), "hrv_sdnn_ms": 50, "sleep_hours": 8}]},
    ).json()
    assert out["hrv_days"] == 0 and out["sleep_nights"] == 0
    assert any("no consent" in s for s in out["skipped"])
