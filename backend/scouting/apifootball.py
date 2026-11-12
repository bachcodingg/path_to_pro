"""Import league seasons of player numbers from API-Football into data/season_2024_25.json
and data/season_2025_26.json.

API-Football (api-sports.io) has season totals per player: appearances, minutes, rating,
goals, assists, shots, passes, duels, dribbles, tackles, cards. Its free plan allows 100
requests a day, only the seasons from two to four years back (in 2026: up to 2024 = 2024/25,
Mbappé's first season at Real Madrid), and only the first 3 pages of any list, so a whole
league (50+ pages) cannot be read in one go. This script reads each club's own players
instead: the clubs of each league (1 request per league), then for every club its players
(2-3 pages of 20) and its transfers (1 request), the featured clubs first. That is about 320
requests for the five leagues, so four days on the free plan.

Why the transfers: API-Football files a player's whole 2024/25 season under the club he is at
now, as well as under the club he played for. Joan García's Espanyol season also appears as
Barcelona's, where he only arrived in July 2025, and a player back from a loan appears at his
parent club too. A club's transfer list says when each player came and went, so a player
counts for a club only if he was there for at least a month of the season (`window`). It
caches every page it gets and stops cleanly at the daily limit: run it again the next day and
it carries on from the cache. The data file says how many clubs are in so far, and the app
shows that.

2025/26: the free plan refuses it (in 2026 it covers 2022 to 2024). With a paid plan the same
script imports it; the transfer lists are shared, so it needs only the squads (about 230
requests). With the free plan it says so and goes on with 2024/25.

    set APIFOOTBALL_KEY=<your key>            (PowerShell: $env:APIFOOTBALL_KEY = "<your key>")
    python -m scouting.apifootball            # fetch what is missing, then write the files
    python -m scouting.apifootball --season 2025
    python -m scouting.apifootball --write    # only rebuild the files from the cache

The key never leaves your machine except in the request header to API-Football. The files keep
the addresses of the API's player photos and club logos, not the images: the app shows them
from API-Football's servers. Check API-Football's terms before you publish the data files;
they are in .gitignore by default.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

BASE = "https://v3.football.api-sports.io"
SEASONS = {2024: "2024/25", 2025: "2025/26"}  # API-Football's season = the year it starts
LEAGUES = {140: "La Liga", 39: "Premier League", 61: "Ligue 1", 78: "Bundesliga", 135: "Serie A"}
# The clubs shown in full (API-Football team ids), fetched first
FEATURED: dict[int, str] = {
    541: "Real Madrid",
    529: "Barcelona",
    85: "Paris Saint-Germain",
    50: "Manchester City",
    33: "Manchester United",
    49: "Chelsea",
    40: "Liverpool",
    42: "Arsenal",
    157: "Bayern Munich",
}
MAX_PAGES = 3  # the free plan refuses page 4 and beyond
MIN_DAYS = 30  # at a club for less than this of the season: not his club that season
DATA = Path(__file__).resolve().parent / "data"
GAP_S = 6.5  # the free plan allows 10 requests a minute


class DailyLimit(Exception):
    pass


class PlanLimit(Exception):
    """The key's plan does not include this season."""


def out_path(season: int) -> Path:
    """data/season_2024_25.json for 2024"""
    return DATA / f"season_{season}_{(season + 1) % 100:02d}.json"


def window(season: int) -> tuple[date, date]:
    """The league season's first and last match days, roughly: mid-August to late May."""
    return date(season, 8, 15), date(season + 1, 5, 25)


def _fetch(path: str, params: dict, key: str, cache: Path) -> dict:
    name = path.strip("/").replace("/", "_") + "_" + "_".join(f"{k}{v}" for k, v in sorted(params.items())) + ".json"
    hit = cache / name
    if hit.exists():
        return json.loads(hit.read_text(encoding="utf-8"))
    for attempt in range(3):
        time.sleep(GAP_S)
        req = urllib.request.Request(
            f"{BASE}{path}?{urllib.parse.urlencode(params)}", headers={"x-apisports-key": key}
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                body = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429:  # the daily quota, sometimes sent as HTTP 429 instead of an "errors" object
                raise DailyLimit(f"HTTP 429 {e.reason}") from e
            raise
        errors = body.get("errors")
        # API-Football reports plan and quota problems with HTTP 200 and an "errors" object:
        # "requests" = the daily quota, "rateLimit" = too many this minute, anything else = refused
        if isinstance(errors, dict) and "rateLimit" in errors and attempt < 2:
            time.sleep(61)
            continue
        break
    if errors:
        text = json.dumps(errors)
        if isinstance(errors, dict) and "requests" in errors:
            raise DailyLimit(text)
        if isinstance(errors, dict) and "plan" in errors:
            raise PlanLimit(errors["plan"])
        raise RuntimeError(f"API-Football refused {path} {params}: {text}")
    cache.mkdir(parents=True, exist_ok=True)
    hit.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    return body


def _cached(cache: Path, path: str, params: dict) -> Path:
    return cache / (path.strip("/") + "_" + "_".join(f"{k}{v}" for k, v in sorted(params.items())) + ".json")


def _clubs(cache: Path, league: int, key: str | None = None, season: int = 2024) -> list[tuple[int, str]] | None:
    """The league's clubs as (id, name), from the cache, or fetched when a key is given."""
    params = {"league": league, "season": season}
    if key is None and not _cached(cache, "/teams", params).exists():
        return None
    body = _fetch("/teams", params, key or "", cache)
    return [(t["team"]["id"], t["team"]["name"]) for t in body.get("response", [])]


def _squad_pages(cache: Path, team: int, key: str | None = None, season: int = 2024) -> list[dict] | None:
    """Every page of one club's players (at most MAX_PAGES), or None when not all are cached."""
    pages, page, total = [], 1, 1
    while page <= min(total, MAX_PAGES):
        params = {"page": page, "season": season, "team": team}
        if key is None and not _cached(cache, "/players", params).exists():
            return None
        body = _fetch("/players", params, key or "", cache)
        pages.append(body)
        total = body.get("paging", {}).get("total", 1)
        page += 1
    return pages


def _transfers(cache: Path, team: int, key: str | None = None) -> list[dict] | None:
    """The club's transfer list (every player who came or went, with dates), or None if not cached."""
    params = {"team": team}
    if key is None and not _cached(cache, "/transfers", params).exists():
        return None
    return _fetch("/transfers", params, key or "", cache).get("response", [])


def _day(text) -> date | None:
    try:
        return date.fromisoformat(str(text)[:10])
    except ValueError:
        return None


def _at_club(moves: list[dict], team: int, season: int = 2024) -> bool:
    """From one player's transfers involving this club: was he there for MIN_DAYS of the season?
    No transfer involving the club (an academy player, or no record) counts as there."""
    events = sorted(
        (d, (m.get("teams") or {}).get("in", {}).get("id") == team)
        for m in moves
        if (d := _day(m.get("date"))) is not None
        and team in ((m.get("teams") or {}).get("in", {}).get("id"), (m.get("teams") or {}).get("out", {}).get("id"))
    )
    if not events:
        return True
    start, end = window(season)
    days, since = 0, None if events[0][1] else date.min  # first move out of the club: he was there before
    for d, arrives in events + [(date.max, False)]:
        if arrives and since is None:
            since = d
        elif not arrives and since is not None:
            days += max(0, (min(d, end) - max(since, start)).days)
            since = None
    return days >= MIN_DAYS


def fetch(key: str, cache: Path, log=print, season: int = 2024) -> None:
    """Every club of every league in the season, the featured clubs first. Raises DailyLimit at
    the day's quota and PlanLimit when the key's plan does not include the season."""
    clubs = {league: _clubs(cache, league, key, season) or [] for league in LEAGUES}
    names = {c: n for cs in clubs.values() for c, n in cs}
    order = [t for t in FEATURED if t in names] + [c for c in names if c not in FEATURED]
    for i, team in enumerate(order, 1):
        pages = _squad_pages(cache, team, key, season) or []
        moves = _transfers(cache, team, key) or []
        log(f"  {SEASONS[season]} {i}/{len(order)} {names[team]}: {len(pages)} page(s), {len(moves)} in its transfers")


def _num(v) -> float:
    try:
        return float(v) if v not in (None, "") else 0.0
    except (TypeError, ValueError):
        return 0.0


def _rows(item: dict, league: int, season: int = 2024) -> list[dict]:
    """A player's numbers in this league, one row per club (a January move gives two)."""
    return [
        r
        for st in item.get("statistics", [])
        if st.get("league", {}).get("id") == league
        and st.get("league", {}).get("season", season) == season
        and (r := _row(item["player"], st))
    ]


def _row(p: dict, st: dict) -> dict | None:
    if not (st.get("games") or {}).get("minutes"):
        return None
    g = st["games"]
    get = lambda block, k: _num((st.get(block) or {}).get(k))  # noqa: E731
    return {
        "id": p["id"],
        "name": p.get("name"),
        "first": p.get("firstname"),
        "last": p.get("lastname"),
        "age": p.get("age"),
        "nationality": p.get("nationality"),
        "photo": p.get("photo"),  # the address of API-Football's photo, not the image
        "team_id": st["team"]["id"],
        "team": st["team"]["name"],
        "logo": st["team"].get("logo"),
        "position": g.get("position"),
        "apps": int(_num(g.get("appearences"))),
        "starts": int(_num(g.get("lineups"))),
        "minutes": int(_num(g.get("minutes"))),
        "rating": round(_num(g.get("rating")), 2) or None,
        "goals": int(get("goals", "total")),
        "assists": int(get("goals", "assists")),
        "conceded": int(get("goals", "conceded")),
        "saves": int(get("goals", "saves")),
        "shots": int(get("shots", "total")),
        "shots_on": int(get("shots", "on")),
        "passes": int(get("passes", "total")),
        "key_passes": int(get("passes", "key")),
        "tackles": int(get("tackles", "total")),
        "blocks": int(get("tackles", "blocks")),
        "interceptions": int(get("tackles", "interceptions")),
        "duels": int(get("duels", "total")),
        "duels_won": int(get("duels", "won")),
        "dribbles": int(get("dribbles", "attempts")),
        "dribbles_won": int(get("dribbles", "success")),
        "fouls_drawn": int(get("fouls", "drawn")),
        "fouls": int(get("fouls", "committed")),
        "yellow": int(get("cards", "yellow")),
        "red": int(get("cards", "red")) + int(get("cards", "yellowred")),
        "pen_scored": int(get("penalty", "scored")),
        "pen_missed": int(get("penalty", "missed")),
    }


def write(cache: Path, season: int = 2024) -> dict:
    """The season's data file from the cache: every club whose players and transfers are in."""
    leagues, total, cut, dropped = [], 0, [], 0
    for league, name in LEAGUES.items():
        clubs = _clubs(cache, league, season=season) or []
        total += len(clubs)
        rows: dict[tuple[int, int], dict] = {}
        done = 0
        for team, club in clubs:
            pages = _squad_pages(cache, team, season=season)
            transfers = _transfers(cache, team)
            if pages is None or transfers is None:  # not all in yet: leave the club out
                continue
            moves = {t["player"]["id"]: t.get("transfers", []) for t in transfers if t.get("player")}
            done += 1
            if pages[-1].get("paging", {}).get("total", 1) > MAX_PAGES:
                # Past page 3 the free plan stops; for Real Madrid that was youth players with no minutes
                cut.append(club)
            for body in pages:
                for item in body.get("response", []):
                    for r in _rows(item, league, season):
                        if r["team_id"] != team:  # a January move: each club keeps its own part
                            continue
                        if not _at_club(moves.get(r["id"], []), team, season):  # filed under his later club
                            dropped += 1
                            continue
                        rows[(r["team_id"], r["id"])] = r
        if rows:
            leagues.append({
                "id": league, "name": name, "clubs": done, "clubs_total": len(clubs),
                "players": sorted(rows.values(), key=lambda r: (r["team"], -r["minutes"])),
            })  # fmt: skip
    data = {
        "source": "API-Football",
        "source_url": "https://www.api-football.com",
        "season": SEASONS[season],
        "fetched": date.today().isoformat(),
        "clubs": sum(lg["clubs"] for lg in leagues),
        "clubs_total": total,
        "lists_cut_after_3_pages": cut,
        "left_out_not_at_the_club_that_season": dropped,
        "leagues": leagues,
    }
    out_path(season).write_text(json.dumps(data, ensure_ascii=False, indent=0), encoding="utf-8")
    return data


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache", type=Path, default=Path("../.apifootball-cache"))
    ap.add_argument("--write", action="store_true", help="only rebuild the data files from the cache")
    ap.add_argument("--season", type=int, choices=sorted(SEASONS), action="append",
                    help="the year the season starts (default: every season, 2024/25 first)")  # fmt: skip
    args = ap.parse_args(argv)
    seasons = args.season or sorted(SEASONS)
    if not args.write:
        key = os.environ.get("APIFOOTBALL_KEY")
        if not key:
            ap.error("set APIFOOTBALL_KEY to your API-Football key first")
        for season in seasons:
            try:
                fetch(key, args.cache, season=season)
            except PlanLimit as e:
                print(f"{SEASONS[season]}: your API-Football plan does not include it ({e}).")
            except DailyLimit as e:
                print(f"Stopped at API-Football's daily limit ({e}). Run again tomorrow; the cache keeps what came in.")
                break
    for season in seasons:
        if _clubs(args.cache, next(iter(LEAGUES)), season=season) is None:
            continue  # nothing of this season fetched
        data = write(args.cache, season)
        print(
            f"{out_path(season).name}: {data['clubs']} of {data['clubs_total']} clubs; "
            + ", ".join(f"{lg['name']} {lg['clubs']}/{lg['clubs_total']}, {len(lg['players'])} players" for lg in data["leagues"])
        )


if __name__ == "__main__":
    main()
