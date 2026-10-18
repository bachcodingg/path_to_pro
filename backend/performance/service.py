"""Appearances, match ratings, the match diary and the career view (football CV)."""

from __future__ import annotations

import random
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import age_on
from domain.models import Appearance, CareerSeason, Match, Player, Registration, SessionLoad, Squad
from performance import competitions
from performance.rating import band, rate, rate_diary

DIARY_DAYS = 7  # the match diary asks about matches from the last week
MATCH_DIARY_RPE_DEFAULT = 7


def season_of(day: date) -> str:
    return str(day.year)  # Finnish football runs within the calendar year


def competition_for(db: Session, player: Player, match: Match) -> str:
    squad = db.get(Squad, match.squad_id)
    if squad is not None and squad.competition:
        return squad.competition
    return competitions.academy_competition(age_on(player.birth_date, match.kickoff.date()))


def team_label(squad: Squad | None) -> str:
    return "Team" if squad is None else squad.name


def registrations(db: Session, player: Player, today: date) -> list[dict]:
    rows = [(db.get(Squad, player.squad_id), True)]
    rows += [(db.get(Squad, r.squad_id), False) for r in db.scalars(select(Registration).where(Registration.player_id == player.id))]
    out = []
    for squad, primary in rows:
        if squad is None:
            continue
        comp = squad.competition or competitions.academy_competition(age_on(player.birth_date, today))
        out.append(
            {
                "team_id": squad.id,
                "team": squad.name,
                "club": squad.club,
                "competition": comp,
                "competition_label": competitions.label(comp),
                "level": competitions.level(comp),
                "primary": primary,
            }
        )
    return out


def is_registered(db: Session, player: Player, squad_id: str) -> bool:
    if player.squad_id == squad_id:
        return True
    return db.scalars(
        select(Registration.id).where(Registration.player_id == player.id, Registration.squad_id == squad_id)
    ).first() is not None


# --------------------------------------------------------------------------- appearances


def appearance(db: Session, player: Player, match: Match, create: bool = True) -> Appearance | None:
    a = db.scalars(select(Appearance).where(Appearance.player_id == player.id, Appearance.match_id == match.id)).first()
    if a is None and create:
        a = Appearance(
            player_id=player.id,
            match_id=match.id,
            day=match.kickoff.date(),
            competition=competition_for(db, player, match),
            position=player.position,
            stats={},
            breakdown=[],
        )
        db.add(a)
    return a


def apply_stats(a: Appearance, minutes: int, started: bool, position: str | None, stats: dict) -> Appearance:
    """Coach (or data provider) stats: they set the rating."""
    a.minutes, a.started, a.position = minutes, started, position or a.position
    a.stats = {k: v for k, v in stats.items() if v not in (None, "")}
    a.goals, a.assists = int(stats.get("goals") or 0), int(stats.get("assists") or 0)
    r = rate(a.position, minutes, a.stats)
    a.rating, a.breakdown, a.rating_source = r.value, r.breakdown, "stats" if r.value is not None else None
    return a


def apply_diary(
    db: Session, player: Player, match: Match, minutes: int, position: str | None, goals: int, assists: int, self_rating: int, rpe: int
) -> Appearance:
    """The player's match diary: self-rating and effort; minutes and goals only fill in
    what the coach hasn't entered. Match load (RPE x minutes) goes into the load history."""
    a = appearance(db, player, match)
    a.self_rating, a.self_rpe, a.diary_at = self_rating, rpe, datetime.now(UTC)
    if a.rating_source != "stats":
        a.minutes, a.position, a.goals, a.assists = minutes, position or a.position, goals, assists
        r = rate_diary(a.position, minutes, goals, assists)
        a.rating, a.breakdown, a.rating_source = r.value, r.breakdown, "diary" if r.value is not None else None
    if minutes > 0:
        load = db.scalars(select(SessionLoad).where(SessionLoad.player_id == player.id, SessionLoad.match_id == match.id)).first()
        if load is None:
            db.add(SessionLoad(player_id=player.id, match_id=match.id, day=match.kickoff.date(), rpe=rpe, minutes=minutes, load_au=rpe * minutes))
        else:
            load.rpe, load.minutes, load.load_au = rpe, minutes, rpe * minutes
    return a


def diary_due(db: Session, player: Player, today: date) -> list[dict]:
    from api.services.agent_runner import match_days

    out = []
    for d, m in sorted(match_days(db, player, today - timedelta(days=DIARY_DAYS - 1), DIARY_DAYS).items()):
        if d > today:
            continue
        a = appearance(db, player, m, create=False)
        if a is None or a.diary_at is None:
            out.append(
                {
                    "match_id": m.id,
                    "date": d.isoformat(),
                    "team": team_label(db.get(Squad, m.squad_id)),
                    "opponent": m.opponent,
                    "minutes": a.minutes if a else None,
                }
            )
    return out


def appearance_json(db: Session, a: Appearance) -> dict:
    m = db.get(Match, a.match_id)
    squad = db.get(Squad, m.squad_id) if m else None
    return {
        "match_id": a.match_id,
        "date": a.day.isoformat(),
        "team": team_label(squad),
        "opponent": m.opponent if m else "",
        "competition": a.competition,
        "competition_label": competitions.label(a.competition),
        "minutes": a.minutes,
        "started": a.started,
        "position": a.position,
        "goals": a.goals,
        "assists": a.assists,
        "rating": a.rating,
        "rating_band": band(a.rating),
        "rating_source": a.rating_source,
        "breakdown": a.breakdown or [],
        "self_rating": a.self_rating,
        "stats": a.stats or {},
    }


# --------------------------------------------------------------------------- career


def _summary(apps: list[Appearance]) -> dict:
    played = [a for a in apps if a.minutes > 0]
    rated = [a.rating for a in played if a.rating is not None]
    avg = round(sum(rated) / len(rated), 2) if rated else None
    return {
        "apps": len(played),
        "starts": sum(a.started for a in played),
        "minutes": sum(a.minutes for a in played),
        "goals": sum(a.goals for a in played),
        "assists": sum(a.assists for a in played),
        "avg_rating": avg,
        "rating_band": band(avg),
        "exposure": round(sum(competitions.exposure(a.minutes, a.competition) for a in played), 1),
    }


def career_view(db: Session, player: Player, today: date) -> dict:
    season = season_of(today)
    apps = list(
        db.scalars(select(Appearance).where(Appearance.player_id == player.id, Appearance.day <= today).order_by(Appearance.day))
    )
    this = [a for a in apps if season_of(a.day) == season]
    by_comp: dict[str, list[Appearance]] = {}
    for a in this:
        by_comp.setdefault(a.competition or "", []).append(a)
    current_rows = [
        {"season": season, "competition": k, "competition_label": competitions.label(k), "level": competitions.level(k), **_summary(v)}
        for k, v in sorted(by_comp.items(), key=lambda kv: -competitions.level(kv[0]))
    ]
    past = list(db.scalars(select(CareerSeason).where(CareerSeason.player_id == player.id).order_by(CareerSeason.season)))
    past_rows = [
        {
            "id": c.id,
            "season": c.season,
            "club": c.club,
            "team": c.team,
            "competition": c.competition,
            "competition_label": competitions.label(c.competition),
            "level": competitions.level(c.competition),
            "apps": c.apps,
            "starts": c.starts,
            "minutes": c.minutes,
            "goals": c.goals,
            "assists": c.assists,
            "avg_rating": c.avg_rating,
            "rating_band": band(c.avg_rating),
            "exposure": round(competitions.exposure(c.minutes, c.competition), 1),
        }
        for c in past
    ]
    # Pathway chart: per season, the highest level the player got minutes at
    ladder: dict[str, dict] = {}
    for row in [*past_rows, *current_rows]:
        if row["minutes"] <= 0:
            continue
        best = ladder.get(row["season"])
        if best is None or row["level"] > best["level"]:
            ladder[row["season"]] = {"season": row["season"], "level": row["level"], "competition_label": row["competition_label"]}
    rated = [a for a in apps if a.rating is not None and a.minutes > 0]
    regs = registrations(db, player, today)
    current_rows_for_clubs = [
        {
            "season": season,
            "club": r["club"] or r["team"],
            "team": short_team(r["competition"]),
            "competition": r["competition"],
            "apps": sum(c["apps"] for c in current_rows if c["competition"] == r["competition"]),
            "goals": sum(c["goals"] for c in current_rows if c["competition"] == r["competition"]),
            "current": True,
        }
        for r in regs
    ]
    return {
        "clubs": club_history(past_rows, current_rows_for_clubs),
        "season": season,
        "registrations": regs,
        "summary": _summary(this),
        "current": current_rows,
        "past": past_rows,
        "ladder": [ladder[k] for k in sorted(ladder)],
        "recent": [appearance_json(db, a) for a in reversed(apps[-10:]) if a.minutes > 0 or a.diary_at],
        "trend": [{"date": a.day.isoformat(), "rating": a.rating} for a in rated[-15:]],
        "history": rating_history(db, player, today),
        "diary_due": diary_due(db, player, today),
        "competitions": [{"id": k, "label": v["name"], "level": v["level"], "category": v["category"]} for k, v in competitions.all_competitions().items()],
        "note": "Ratings: our own transparent formula on a 3-10 scale (6-7 is an ordinary game). Competition levels are placeholder judgements.",
    }


# --------------------------------------------------------------------------- synthetic demo stats


def synthetic_stats(rng: random.Random, position: str, minutes: int, result: str, conceded: int, form: float = 1.0) -> dict:
    """Plausible match stats for the synthetic demo season (no real data). `form` > 1
    means a player in better form: more positive actions, fewer duels lost."""
    f = minutes / 90 * form
    g = {"goalkeeper": "gk", "centre_back": "def", "full_back": "def", "midfielder": "mid", "winger": "fwd", "striker": "fwd"}[position]

    def n(mean: float) -> int:
        return max(0, round(rng.gauss(mean * f, max(0.6, mean * f) ** 0.5)))

    passes = n({"gk": 25, "def": 45, "mid": 50, "fwd": 25}[g])
    stats = {
        "goals": 1 if rng.random() < {"gk": 0.0, "def": 0.04, "mid": 0.1, "fwd": 0.25}[g] * f else 0,
        "assists": 1 if rng.random() < {"gk": 0.01, "def": 0.06, "mid": 0.12, "fwd": 0.15}[g] * f else 0,
        "shots_on_target": n({"gk": 0, "def": 0.2, "mid": 0.6, "fwd": 1.3}[g]),
        "key_passes": n({"gk": 0.1, "def": 0.5, "mid": 1.4, "fwd": 1.1}[g]),
        "passes": passes,
        "passes_accurate": round(passes * min(0.97, max(0.55, rng.gauss(0.82 + 0.15 * (form - 1), 0.07)))),
        "dribbles_won": n({"gk": 0, "def": 0.4, "mid": 1.0, "fwd": 1.6}[g]),
        "tackles_won": n({"gk": 0.1, "def": 2.0, "mid": 1.6, "fwd": 0.6}[g]),
        "interceptions": n({"gk": 0.2, "def": 1.6, "mid": 1.0, "fwd": 0.3}[g]),
        "duels_won": n({"gk": 0.5, "def": 5.0, "mid": 4.5, "fwd": 4.0}[g]),
        "duels_lost": n({"gk": 0.3, "def": 3.5, "mid": 4.0, "fwd": 4.5}[g] / form**2),
        "saves": n(3.0) if g == "gk" else 0,
        "goals_conceded": round(conceded * f),
        "yellow": 1 if rng.random() < 0.08 * f else 0,
        "result": result,
    }
    return stats


# --------------------------------------------------------------------------- rating history and progress

ROLLING = 5


def rating_history(db: Session, player: Player, today: date) -> dict:
    """Every rated match in order, labelled "Jan M1", "Jan M2" (match number within the
    month), with a 5-match rolling average and a least-squares trend line."""
    apps = [
        a
        for a in db.scalars(
            select(Appearance).where(Appearance.player_id == player.id, Appearance.day <= today).order_by(Appearance.day)
        )
        if a.rating is not None and a.minutes > 0
    ]
    points, per_month = [], {}
    for i, a in enumerate(apps):
        key = (a.day.year, a.day.month)
        per_month[key] = per_month.get(key, 0) + 1
        m = db.get(Match, a.match_id)
        window = [x.rating for x in apps[max(0, i - ROLLING + 1) : i + 1]]
        points.append(
            {
                "match_id": a.match_id,
                "date": a.day.isoformat(),
                "label": f"{a.day.strftime('%b')} M{per_month[key]}",
                "opponent": m.opponent if m else "",
                "team": team_label(db.get(Squad, m.squad_id)) if m else "",
                "minutes": a.minutes,
                "goals": a.goals,
                "assists": a.assists,
                "rating": a.rating,
                "rating_band": band(a.rating),
                "source": a.rating_source,
                "rolling": round(sum(window) / len(window), 2),
            }
        )
    n = len(points)
    progress = {"matches": n, "average": None, "slope_per_match": None, "change_10": None, "first_vs_last": None, "verdict": "not enough matches"}
    if n:
        progress["average"] = round(sum(p["rating"] for p in points) / n, 2)
    if n >= 3:
        xs, ys = range(n), [p["rating"] for p in points]
        mx, my = (n - 1) / 2, sum(ys) / n
        sxx = sum((x - mx) ** 2 for x in xs)
        slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
        for x, p in zip(xs, points):
            p["trend"] = round(my + slope * (x - mx), 2)
        k = min(ROLLING, n // 2) or 1
        first, last = sum(ys[:k]) / k, sum(ys[-k:]) / k
        progress.update(
            {
                "slope_per_match": round(slope, 3),
                "change_10": round(slope * 10, 2),
                "first_vs_last": round(last - first, 2),
                "verdict": "improving" if slope * 10 >= 0.15 else "dipping" if slope * 10 <= -0.15 else "steady",
            }
        )
    return {"points": points, "progress": progress}


def club_history(past: list[dict], current: list[dict]) -> list[dict]:
    """Clubs in the order the player joined them: years, teams (U12, U15, men...), leagues,
    appearances and goals. Overlapping clubs (dual registration, loans) are kept apart."""
    clubs: dict[str, dict] = {}
    for r in sorted([*past, *current], key=lambda r: r["season"]):
        c = clubs.setdefault(
            r["club"],
            {"club": r["club"], "from": r["season"], "to": r["season"], "teams": [], "competitions": [], "apps": 0, "goals": 0,
             "current": False, "top_level": 0, "seasons": []},
        )  # fmt: skip
        c["to"] = max(c["to"], r["season"])
        if r["team"] not in c["teams"]:
            c["teams"].append(r["team"])
        label = competitions.label(r["competition"])
        if label not in c["competitions"]:
            c["competitions"].append(label)
        c["apps"] += r.get("apps") or 0
        c["goals"] += r.get("goals") or 0
        c["current"] = c["current"] or bool(r.get("current"))
        c["top_level"] = max(c["top_level"], competitions.level(r["competition"]))
        c["seasons"].append({"season": r["season"], "team": r["team"], "competition_label": label})
    # oldest first (the app shows them newest first): ordered by the last season at the club
    return sorted(clubs.values(), key=lambda c: (c["current"], c["to"], c["from"], c["club"]))


def short_team(competition: str) -> str:
    """"U19" / "Men" from the league: short team names for the club history."""
    c = competitions.get(competition) or {}
    if c.get("category") == "youth" and c.get("age_limit"):
        return f"U{c['age_limit']}"
    return "Reserves" if c.get("category") == "reserve" else "Men"


def match_rows(db: Session, match: Match, players: list[Player]) -> list[dict]:
    """One row per player of the team in a match: minutes, stats, rating with breakdown,
    own rating, and the player's last ratings (for the trend on the line-up card)."""
    rows = []
    for p in players:
        a = appearance(db, p, match, create=False)
        recent = [
            {"date": x.day.isoformat(), "rating": x.rating}
            for x in db.scalars(
                select(Appearance)
                .where(Appearance.player_id == p.id, Appearance.day <= match.kickoff.date(), Appearance.rating.is_not(None))
                .order_by(Appearance.day.desc())
                .limit(8)
            )
        ][::-1]
        rows.append(
            {
                "player": {"id": p.id, "name": p.display_name, "position": p.position},
                "minutes": a.minutes if a else 0,
                "started": a.started if a else False,
                "position": (a.position if a else None) or p.position,
                "stats": (a.stats if a else {}) or {},
                "rating": a.rating if a else None,
                "rating_band": band(a.rating if a else None),
                "rating_source": a.rating_source if a else None,
                "breakdown": (a.breakdown if a else []) or [],
                "self_rating": a.self_rating if a else None,
                "recent": recent,
            }
        )
    rows.sort(key=lambda r: (-(r["minutes"] or 0), r["player"]["name"]))
    return rows


def team_players(db: Session, squad_id: str) -> list[Player]:
    dual = select(Registration.player_id).where(Registration.squad_id == squad_id)
    return list(db.scalars(select(Player).where((Player.squad_id == squad_id) | Player.id.in_(dual))))
