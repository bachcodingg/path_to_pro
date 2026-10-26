"""Record what each demo account sees, for the static demo website.

Seeds the synthetic season into a throwaway database, signs in as every demo account
through the real API (FastAPI TestClient) and saves the responses. The frontend's
demo mode (VITE_DEMO=1) answers API calls from this file in the browser, so the
website runs without a server. All data is synthetic, except the pro-league analysis
(public StatsBomb match data), which is written to one file per competition next to the
snapshot (pro/<competition>.json) so the demo only downloads the league someone opens.

    python scripts/demo_snapshot.py ../frontend/public/demo/snapshot.json
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

_tmp = tempfile.mkdtemp(prefix="pathtopro-snapshot-")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/demo.db"
os.environ.setdefault("PATHTOPRO_SCHEDULER", "off")
os.environ.setdefault("PATHTOPRO_LLM", "off")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from analytics.readiness import ReadinessConfig  # noqa: E402
from api.db import SessionLocal, init_db  # noqa: E402
from api.main import app  # noqa: E402
from api.services.seed import DEMO_PASSWORD, seed  # noqa: E402

PLAYERS = ["p15@demo.pathtopro", "p03@demo.pathtopro", "p07@demo.pathtopro", "dual@demo.pathtopro", "amateur@demo.pathtopro"]
STAFF = ["coach@demo.pathtopro", "physio@demo.pathtopro"]
SECOND_TEAM_COACH = "mencoach@demo.pathtopro"
GUARDIANS = ["guardian02@demo.pathtopro"]


def main(out: Path) -> None:
    init_db()
    with SessionLocal() as db:
        info = seed(db)
    import datetime as _dt

    rc = ReadinessConfig.load()  # the demo's check-in maths reads these, so it can't drift from the server
    readiness = {
        "weights": dict(rc.weights),
        "green_min": rc.green_min,
        "amber_min": rc.amber_min,
        "sleep_target_hours": rc.sleep_target_hours,
        "hysteresis_up": rc.hysteresis_up,
        "hysteresis_down": rc.hysteresis_down,
    }
    snap: dict = {
        "meta": {
            "today": info["today"],
            "story": info["story"],
            "password": DEMO_PASSWORD,
            "generated": _dt.datetime.now(_dt.UTC).isoformat(),
            "readiness": readiness,
        },
        "users": {},
        "staff": {},
    }
    with TestClient(app) as c:

        def login(email: str) -> dict:
            r = c.post("/api/auth/login", json={"email": email, "password": DEMO_PASSWORD})
            r.raise_for_status()
            return {"Authorization": f"Bearer {r.json()['token']}"}

        def get(h: dict, path: str):
            r = c.get(path, headers=h)
            r.raise_for_status()
            return r.json()

        for email in PLAYERS:
            h = login(email)
            me = get(h, "/api/auth/me")
            paths = [
                "/api/me/today",
                "/api/me/week?offset=-1",
                "/api/me/week?offset=0",
                "/api/me/week?offset=1",
                "/api/me/gym?offset=-1",
                "/api/me/gym?offset=0",
                "/api/me/gym?offset=1",
                "/api/me/growth",
                "/api/me/career",
                "/api/me/skills",
                "/api/me/tips",
            ]
            paths += ["/api/me/pathway"] if me["pathway"] == "amateur" else ["/api/me/card", "/api/me/roadmap"]
            paths += ["/api/me/finance"]
            responses = {p: get(h, p) for p in paths}
            for a in responses["/api/me/career"]["recent"][:3]:  # line-ups of the last matches
                responses[f"/api/me/matches/{a['match_id']}"] = get(h, f"/api/me/matches/{a['match_id']}")
            snap["users"][email] = {"me": me, "responses": responses}
        for email in STAFF:
            snap["users"][email] = {"me": get(login(email), "/api/auth/me"), "responses": {}}
        h = login("coach@demo.pathtopro")
        heatmap = get(h, "/api/coach/heatmap")
        staff = {
            "/api/coach/heatmap": heatmap,
            "/api/coach/inbox": get(h, "/api/coach/inbox"),
            "/api/coach/lineup": get(h, "/api/coach/lineup"),
            "/api/coach/agent-log": get(h, "/api/coach/agent-log?limit=300"),
            "/api/coach/calibration": get(h, "/api/coach/calibration"),
            "/api/physio/queue": get(h, "/api/physio/queue"),
            "/api/physio/phv": get(h, "/api/physio/phv"),
        }
        for row in heatmap["players"]:
            staff[f"/api/coach/players/{row['id']}"] = get(h, f"/api/coach/players/{row['id']}")
        # Pro leagues: public match data, the same for every account
        snap["pro"] = {"/api/pro/competitions": get(h, "/api/pro/competitions")}
        pro: dict[str, dict] = {}
        for comp in snap["pro"]["/api/pro/competitions"]:
            base = f"/api/pro/{comp['id']}"
            rec = {f"{base}/teams": get(h, f"{base}/teams"), f"{base}/matches": get(h, f"{base}/matches")}
            for t in rec[f"{base}/teams"]["teams"]:
                for sub in ("", "/style", "/players", "/shots"):
                    rec[f"{base}/teams/{t['id']}{sub}"] = get(h, f"{base}/teams/{t['id']}{sub}")
            for m in rec[f"{base}/matches"]["matches"]:
                rec[f"{base}/matches/{m['id']}"] = get(h, f"{base}/matches/{m['id']}")
            pro[comp["id"]] = rec

        def team_views(h: dict) -> dict:
            out = {f"/api/coach/squad-week?offset={o}": get(h, f"/api/coach/squad-week?offset={o}") for o in (0, 1)}
            out["/api/coach/matches"] = get(h, "/api/coach/matches")
            out["/api/coach/finance"] = get(h, "/api/coach/finance")
            for m in out["/api/coach/matches"]:
                out[f"/api/coach/matches/{m['id']}"] = get(h, f"/api/coach/matches/{m['id']}")
            return out

        staff.update(team_views(h))
        snap["staff"] = staff
        # The men's team coach sees his own team (and the dual-registered players)
        h = login(SECOND_TEAM_COACH)
        own = {
            "/api/coach/heatmap": get(h, "/api/coach/heatmap"),
            "/api/coach/inbox": get(h, "/api/coach/inbox"),
            "/api/coach/lineup": get(h, "/api/coach/lineup"),
            **team_views(h),
        }
        snap["users"][SECOND_TEAM_COACH] = {"me": get(h, "/api/auth/me"), "responses": own}
        for email in GUARDIANS:
            h = login(email)
            kids = get(h, "/api/guardian/children")
            resp = {"/api/guardian/children": kids}
            for k in kids:
                for sub in ("summary", "consent", "export", "finance"):
                    resp[f"/api/guardian/children/{k['id']}/{sub}"] = get(h, f"/api/guardian/children/{k['id']}/{sub}")
            snap["users"][email] = {"me": get(h, "/api/auth/me"), "responses": resp}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snap, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size / 1024:.0f} KB), today={info['today']}")
    (out.parent / "pro").mkdir(exist_ok=True)
    for key, rec in pro.items():
        f = out.parent / "pro" / f"{key}.json"
        f.write_text(json.dumps(rec, separators=(",", ":")), encoding="utf-8")
        print(f"wrote {f} ({f.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "../frontend/public/demo/snapshot.json"))
