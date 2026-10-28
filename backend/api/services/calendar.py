"""Calendar feeds (.ics, RFC 5545) for Google, Apple and Outlook calendars.

A player's feed is their own plan (the planner's sessions, not just the team's) and every
match of every team they play for; a coach's or physio's feed is the team's sessions and
fixtures. Sessions have no clock time in PathToPro, so they are all-day events. Event
titles say what the session is, never why (no readiness or health detail).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.services import agent_runner
from domain.enums import SessionType
from domain.models import Match, Player, Squad, StaffMember, UserAccount
from domain.models import Session as TeamSession

PAST_DAYS = 14
AHEAD_DAYS = 56
MATCH_LENGTH = timedelta(hours=2)


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line: str) -> str:
    """Lines longer than 75 octets continue on the next line after a space (RFC 5545 3.1)."""
    out, raw = [], line.encode()
    while len(raw) > 75:
        cut = 75
        while (raw[cut] & 0xC0) == 0x80:  # don't split a UTF-8 character
            cut -= 1
        out.append(raw[:cut].decode())
        raw = b" " + raw[cut:]
    out.append(raw.decode())
    return "\r\n".join(out)


def _stamp(t: datetime) -> str:
    return t.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def _event(uid: str, summary: str, start: date | datetime, end: date | datetime, description: str = "") -> list[str]:
    lines = ["BEGIN:VEVENT", f"UID:{uid}@pathtopro", f"DTSTAMP:{_stamp(datetime.now(UTC))}"]
    if isinstance(start, datetime):
        lines += [f"DTSTART:{_stamp(start)}", f"DTEND:{_stamp(end)}"]
    else:
        lines += [f"DTSTART;VALUE=DATE:{start:%Y%m%d}", f"DTEND;VALUE=DATE:{end:%Y%m%d}"]
    lines.append(f"SUMMARY:{_escape(summary)}")
    if description:
        lines.append(f"DESCRIPTION:{_escape(description)}")
    lines.append("END:VEVENT")
    return lines


def _aware(t: datetime) -> datetime:
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _match_event(m: Match, team: str | None = None) -> list[str]:
    kickoff = _aware(m.kickoff)
    title = f"Match vs {m.opponent}" + (f" ({team})" if team else "")
    return _event(f"match-{m.id}", title, kickoff, kickoff + MATCH_LENGTH, m.competition or "")


def player_events(db: Session, player: Player, today: date) -> list[str]:
    start, n = today - timedelta(days=PAST_DAYS), PAST_DAYS + AHEAD_DAYS
    matches = agent_runner.match_days(db, player, start, n)
    primary = player.squad_id
    lines: list[str] = []
    days = [d for k in range(0, n, 7) for d in agent_runner.plan_days(db, player, start + timedelta(days=k), min(7, n - k))]
    for d in days:
        if d.date in matches:
            m = matches[d.date]
            other = db.get(Squad, m.squad_id).name if m.squad_id != primary else None
            lines += _match_event(m, other)
        elif d.kind != SessionType.REST:
            lines += _event(
                f"plan-{player.id}-{d.date:%Y%m%d}",
                f"Training: {d.kind.value} ({d.minutes} min)",
                d.date,
                d.date + timedelta(days=1),
                "Your PathToPro plan for the day. It can change after your check-in: open the app for today's version.",
            )
    return lines


def team_events(db: Session, squad_id: str, today: date) -> list[str]:
    start, end = today - timedelta(days=PAST_DAYS), today + timedelta(days=AHEAD_DAYS)
    lines: list[str] = []
    for s in db.scalars(
        select(TeamSession).where(
            TeamSession.squad_id == squad_id, TeamSession.player_id.is_(None), TeamSession.day >= start, TeamSession.day < end
        )
    ):
        lines += _event(f"session-{s.id}", f"Team training: {s.kind.value}", s.day, s.day + timedelta(days=1))
    for m in db.scalars(
        select(Match).where(
            Match.squad_id == squad_id,
            Match.kickoff >= datetime.combine(start, datetime.min.time(), tzinfo=UTC),
            Match.kickoff < datetime.combine(end, datetime.min.time(), tzinfo=UTC),
        )
    ):
        lines += _match_event(m)
    return lines


def feed(db: Session, acc: UserAccount, today: date) -> str:
    if acc.player_id:
        events = player_events(db, db.get(Player, acc.player_id), today)
        name = "PathToPro: my plan"
    else:
        staff = db.get(StaffMember, acc.staff_id) if acc.staff_id else None
        squad = db.get(Squad, staff.squad_id) if staff and staff.squad_id else None
        events = team_events(db, squad.id, today) if squad else []
        name = f"PathToPro: {squad.name}" if squad else "PathToPro"
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//PathToPro//Training plan//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escape(name)}",
        "REFRESH-INTERVAL;VALUE=DURATION:PT6H",
        "X-PUBLISHED-TTL:PT6H",
        *events,
        "END:VCALENDAR",
    ]
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"
