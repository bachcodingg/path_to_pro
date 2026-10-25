"""Import set pieces from StatsBomb Open Data into one compact JSON file.

StatsBomb publish full-season event data for La Liga 2015/16 (all 380 matches) under
their open-data terms: free for research, credit "StatsBomb" when you publish. Each match
file is ~3.5 MB of events; we keep only corners, penalties and direct free kicks, plus
what followed each corner, so the committed dataset stays small.

    python -m scouting.statsbomb --competition 11 --season 27 \
        --out scouting/data/laliga_2015_16.json --cache ../.statsbomb-cache

Pitch coordinates are StatsBomb's: 120 x 80 yards, every team attacking towards x = 120,
y = 0 on the attacking team's left. The goal mouth spans y 36-44 and is 2.67 high.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
# A shot this many seconds after a corner, in the same possession, counts as "from" it.
CORNER_SHOT_WINDOW_S = 15


def _get(url: str, retries: int = 4) -> object:
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=180) as r:
                return json.loads(r.read().decode("utf-8"))
        except (OSError, ValueError):
            if attempt == retries - 1:
                raise
            time.sleep(2 * (attempt + 1))
    raise AssertionError("unreachable")


def _secs(ev: dict) -> float:
    h, m, s = ev["timestamp"].split(":")
    return ev["period"] * 10_000 + int(h) * 3600 + int(m) * 60 + float(s)


def _foot(body_part: dict | None) -> str:
    name = (body_part or {}).get("name", "")
    return {"Right Foot": "R", "Left Foot": "L"}.get(name, "other")


def _short_names(lineups: list[dict]) -> dict[int, str]:
    """StatsBomb events carry full legal names; lineups add the name players are known by."""
    out = {}
    for team in lineups:
        for p in team["lineup"]:
            out[p["player_id"]] = p.get("player_nickname") or p["player_name"]
    return out


def extract(match: dict, events: list[dict], names: dict[int, str]) -> dict:
    """Set-piece rows for one match. Pure: no I/O, so tests can feed it events."""
    home, away = match["home_team"]["home_team_name"], match["away_team"]["away_team_name"]
    opp = {home: away, away: home}
    mid = match["match_id"]

    def who(ev: dict) -> str:
        p = ev.get("player") or {}
        return names.get(p.get("id"), p.get("name", "Unknown"))

    corners, penalties, free_kicks = [], [], []
    last_corner: dict[tuple[str, int], tuple[float, dict]] = {}
    for ev in events:
        if ev["period"] > 4:  # penalty shoot-outs are not match play
            continue
        kind = ev["type"]["name"]
        team = ev["team"]["name"]
        if kind == "Pass" and ev["pass"].get("type", {}).get("name") == "Corner":
            p = ev["pass"]
            row = {
                "m": mid,
                "team": team,
                "opp": opp[team],
                "taker": who(ev),
                "side": "L" if ev["location"][1] < 40 else "R",
                "x": round(p["end_location"][0], 1),
                "y": round(p["end_location"][1], 1),
                "tech": {"Inswinging": "in", "Outswinging": "out", "Straight": "straight"}.get(
                    p.get("technique", {}).get("name")
                ),
                "foot": _foot(p.get("body_part")),
                "height": {"Ground Pass": "ground", "Low Pass": "low", "High Pass": "high"}.get(
                    p.get("height", {}).get("name"), "high"
                ),
                "complete": "outcome" not in p,
                "shot": False,
                "goal": False,
                "xg": 0.0,
            }
            corners.append(row)
            last_corner[(team, ev["possession"])] = (_secs(ev), row)
        elif kind == "Shot":
            s = ev["shot"]
            stype = s["type"]["name"]
            if stype == "Penalty":
                end = s.get("end_location") or [120, 40, 0]
                penalties.append({
                    "m": mid,
                    "team": team,
                    "opp": opp[team],
                    "taker": who(ev),
                    "foot": _foot(s.get("body_part")),
                    "y": round(end[1], 2),
                    "z": round(end[2], 2) if len(end) > 2 else None,
                    "outcome": s["outcome"]["name"],
                    "minute": ev["minute"],
                })  # fmt: skip
            elif stype == "Free Kick":
                end = s.get("end_location") or [120, 40, 0]
                free_kicks.append({
                    "m": mid,
                    "team": team,
                    "opp": opp[team],
                    "taker": who(ev),
                    "foot": _foot(s.get("body_part")),
                    "x0": round(ev["location"][0], 1),
                    "y0": round(ev["location"][1], 1),
                    "y": round(end[1], 2),
                    "z": round(end[2], 2) if len(end) > 2 else None,
                    "outcome": s["outcome"]["name"],
                    "xg": round(s.get("statsbomb_xg", 0.0), 3),
                })  # fmt: skip
            hit = last_corner.get((team, ev["possession"]))
            if hit and _secs(ev) - hit[0] <= CORNER_SHOT_WINDOW_S and stype != "Penalty":
                row = hit[1]
                row["shot"] = True
                row["goal"] = row["goal"] or s["outcome"]["name"] == "Goal"
                row["xg"] = round(row["xg"] + s.get("statsbomb_xg", 0.0), 3)
    return {"match": mid, "teams": [home, away], "corners": corners, "penalties": penalties, "free_kicks": free_kicks}


def _one(match: dict, cache: Path) -> dict:
    path = cache / f"{match['match_id']}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    events = _get(f"{BASE}/events/{match['match_id']}.json")
    lineups = _get(f"{BASE}/lineups/{match['match_id']}.json")
    out = extract(match, events, _short_names(lineups))
    path.write_text(json.dumps(out), encoding="utf-8")
    return out


def build(competition: int, season: int, cache: Path, workers: int = 16, log=print) -> dict:
    comps = _get(f"{BASE}/competitions.json")
    meta = next(c for c in comps if c["competition_id"] == competition and c["season_id"] == season)
    matches = _get(f"{BASE}/matches/{competition}/{season}.json")
    cache.mkdir(parents=True, exist_ok=True)
    rows, t0 = [], time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = [pool.submit(_one, m, cache) for m in matches]
        for i, f in enumerate(as_completed(futs), 1):
            rows.append(f.result())
            if i % 20 == 0 or i == len(futs):
                log(f"  {i}/{len(futs)} matches ({time.perf_counter() - t0:.0f} s)")
    rows.sort(key=lambda r: r["match"])
    matches_played: dict[str, int] = {}
    for r in rows:
        for t in r["teams"]:
            matches_played[t] = matches_played.get(t, 0) + 1
    return {
        "source": "StatsBomb Open Data",
        "source_url": "https://github.com/statsbomb/open-data",
        "competition": meta["competition_name"],
        "season": meta["season_name"],
        "matches": len(rows),
        "matches_played": dict(sorted(matches_played.items())),
        "corners": [c for r in rows for c in r["corners"]],
        "penalties": [p for r in rows for p in r["penalties"]],
        "free_kicks": [f for r in rows for f in r["free_kicks"]],
    }


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--competition", type=int, default=11)
    ap.add_argument("--season", type=int, default=27)
    ap.add_argument("--out", type=Path, default=Path("scouting/data/laliga_2015_16.json"))
    ap.add_argument("--cache", type=Path, default=Path("../.statsbomb-cache"))
    ap.add_argument("--workers", type=int, default=16)
    args = ap.parse_args(argv)
    data = build(args.competition, args.season, args.cache, args.workers)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    # One row per line: small diffs when the data is re-imported.
    body = {k: v for k, v in data.items() if k not in ("corners", "penalties", "free_kicks")}
    lines = ["{"] + [f"  {json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}," for k, v in body.items()]
    for i, key in enumerate(("corners", "penalties", "free_kicks")):
        items = ",\n".join("    " + json.dumps(x, ensure_ascii=False) for x in data[key])
        lines.append(f'  "{key}": [\n{items}\n  ]' + ("," if i < 2 else ""))
    args.out.write_text("\n".join(lines) + "\n}\n", encoding="utf-8")
    print(f"{args.out}: {data['matches']} matches, {len(data['corners'])} corners, "
          f"{len(data['penalties'])} penalties, {len(data['free_kicks'])} direct free kicks")  # fmt: skip


if __name__ == "__main__":
    main()
