"""Club finances: contracts, running costs and income, bonuses, and the ledger.

All amounts are euro cents. Generated entries carry a unique `key`, so running a month
or booking a match's bonuses twice never books anything twice.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from domain.models import Appearance, Contract, LedgerEntry, Match, Player, RecurringItem, Squad, StaffMember
from domain.models import Session as TeamSession

CATEGORIES = {
    "academy_fee": "Academy fees",
    "membership": "Membership fees",
    "salary": "Player salaries",
    "bonus": "Player bonuses",
    "staff": "Coach and staff",
    "field_rental": "Pitch hire",
    "referee": "Referees",
    "travel": "Travel",
    "equipment": "Equipment",
    "sponsorship": "Sponsorship",
    "ticketing": "Gate money",
    "prize_money": "Prize money",
    "other": "Other",
}
KINDS = {
    "academy_fee": ("income", "academy_fee", "Academy fee"),
    "membership": ("income", "membership", "Membership fee"),
    "amateur": ("expense", "salary", "Amateur expenses"),
    "semi_pro": ("expense", "salary", "Semi-pro salary"),
    "pro": ("expense", "salary", "Professional salary"),
    "staff_salary": ("expense", "staff", "Staff salary"),
    "coach_fee": ("expense", "staff", "Coach fee"),
}
BONUS_TYPES = {
    "appearance": "Appearance",
    "goal": "Goal",
    "assist": "Assist",
    "win": "Win",
    "clean_sheet": "Clean sheet",
    "title": "Title",
}
CLEAN_SHEET_POSITIONS = {"goalkeeper", "centre_back", "full_back"}


def month_start(d: date) -> date:
    return d.replace(day=1)


def next_month(d: date) -> date:
    return (d.replace(day=28) + timedelta(days=4)).replace(day=1)


def _book(db: Session, key: str, **kw) -> LedgerEntry | None:
    if db.scalars(select(LedgerEntry.id).where(LedgerEntry.key == key)).first():
        return None
    e = LedgerEntry(key=key, created_at=datetime.now(UTC), **kw)
    db.add(e)
    return e


def _active(c: Contract, start: date, end: date) -> bool:
    return c.starts_on < end and (c.ends_on is None or c.ends_on >= start)


def _party(db: Session, c: Contract) -> str:
    if c.player_id:
        return db.get(Player, c.player_id).display_name
    if c.staff_id:
        return db.get(StaffMember, c.staff_id).name
    return "Club"


# --------------------------------------------------------------------------- generating entries


def run_month(db: Session, month: date, squad_ids: list[str] | None = None, paid: bool = False) -> int:
    """Book a month: monthly contracts, monthly running items, and per-session / per-match
    items counted from that month's training sessions and fixtures."""
    start = month_start(month)
    end = next_month(start)
    label = start.strftime("%b %Y")
    status = "paid" if paid else "due"
    n = 0
    for c in db.scalars(select(Contract)):
        if c.period != "month" or not _active(c, start, end):
            continue
        if squad_ids is not None and c.squad_id not in squad_ids:
            continue
        direction, category, _ = KINDS[c.kind]
        e = _book(
            db,
            f"c:{c.id}:{start:%Y-%m}",
            squad_id=c.squad_id,
            day=start,
            category=category,
            direction=direction,
            amount_cents=c.amount_cents,
            description=f"{c.title}, {label}: {_party(db, c)}",
            player_id=c.player_id,
            staff_id=c.staff_id,
            contract_id=c.id,
            status=status,
        )
        n += e is not None
    for it in db.scalars(select(RecurringItem).where(RecurringItem.active.is_(True))):
        if squad_ids is not None and it.squad_id not in squad_ids:
            continue
        if it.period == "month":
            count = 1
        elif it.period == "session":
            count = len(
                db.scalars(
                    select(TeamSession.id).where(TeamSession.squad_id == it.squad_id, TeamSession.day >= start, TeamSession.day < end)
                ).all()
            )
        else:  # match
            count = len(
                db.scalars(
                    select(Match.id).where(
                        Match.squad_id == it.squad_id,
                        Match.kickoff >= datetime.combine(start, datetime.min.time(), tzinfo=UTC),
                        Match.kickoff < datetime.combine(end, datetime.min.time(), tzinfo=UTC),
                    )
                ).all()
            )
        if count == 0:
            continue
        unit = {"month": "", "session": f" ({count} sessions)", "match": f" ({count} matches)"}[it.period]
        e = _book(
            db,
            f"r:{it.id}:{start:%Y-%m}",
            squad_id=it.squad_id,
            day=start,
            category=it.category,
            direction=it.direction,
            amount_cents=it.amount_cents * count,
            description=f"{it.name}, {label}{unit}",
            status=status,
        )
        n += e is not None
    db.flush()
    return n


def match_bonuses(db: Session, match: Match, paid: bool = False) -> int:
    """Bonuses from a match for players with bonus clauses: appearance, goals, assists,
    win, clean sheet (keepers and defenders, 60+ minutes)."""
    n = 0
    day = match.kickoff.date()
    for a in db.scalars(select(Appearance).where(Appearance.match_id == match.id, Appearance.minutes > 0)):
        for c in db.scalars(select(Contract).where(Contract.player_id == a.player_id, Contract.direction == "expense")):
            if not c.bonus or not _active(c, day, day + timedelta(days=1)) or (c.squad_id and c.squad_id != match.squad_id):
                continue
            stats = a.stats or {}
            counts = {
                "appearance": 1,
                "goal": a.goals,
                "assist": a.assists,
                "win": 1 if stats.get("result") == "win" else 0,
                "clean_sheet": 1
                if a.minutes >= 60 and a.position in CLEAN_SHEET_POSITIONS and stats.get("goals_conceded") is not None
                and float(stats.get("goals_conceded") or 0) == 0
                else 0,
            }
            for kind, k in counts.items():
                per = int(c.bonus.get(kind) or 0)
                key = f"b:{c.id}:{match.id}:{kind}"
                old = db.scalars(select(LedgerEntry).where(LedgerEntry.key == key)).first()
                if old is not None and old.status == "due":
                    # stats were corrected: an unpaid bonus follows them (paid ones stay as paid)
                    if not (per and k):
                        db.delete(old)
                    elif old.amount_cents != per * k:
                        old.amount_cents = per * k
                    continue
                if per and k:
                    e = _book(
                        db,
                        key,
                        squad_id=match.squad_id,
                        day=day,
                        category="bonus",
                        direction="expense",
                        amount_cents=per * k,
                        description=f"{BONUS_TYPES[kind]} bonus{f' x{k}' if k > 1 else ''} vs {match.opponent}: {db.get(Player, a.player_id).display_name}",
                        player_id=a.player_id,
                        contract_id=c.id,
                        match_id=match.id,
                        status="paid" if paid else "due",
                    )
                    n += e is not None
    db.flush()
    return n


def record_title(db: Session, squad: Squad, title: str, prize_cents: int, day: date) -> int:
    """A trophy: prize money in, title bonuses out for the team's players with a title clause."""
    n = 0
    key = title.strip().lower().replace(" ", "-")[:60]
    if prize_cents:
        e = _book(
            db,
            f"t:{squad.id}:{key}:prize",
            squad_id=squad.id,
            day=day,
            category="prize_money",
            direction="income",
            amount_cents=prize_cents,
            description=f"Prize money: {title}",
            status="due",
        )
        n += e is not None
    for c in db.scalars(select(Contract).where(Contract.squad_id == squad.id, Contract.direction == "expense")):
        per = int((c.bonus or {}).get("title") or 0)
        if per and c.player_id and _active(c, day, day + timedelta(days=1)):
            e = _book(
                db,
                f"t:{squad.id}:{key}:{c.id}",
                squad_id=squad.id,
                day=day,
                category="bonus",
                direction="expense",
                amount_cents=per,
                description=f"Title bonus, {title}: {_party(db, c)}",
                player_id=c.player_id,
                contract_id=c.id,
                status="due",
            )
            n += e is not None
    db.flush()
    return n


# --------------------------------------------------------------------------- views


@dataclass
class Scope:
    squad_ids: list[str] | None  # None = whole club (admin)


def contract_json(db: Session, c: Contract) -> dict:
    direction, category, label = KINDS[c.kind]
    return {
        "id": c.id,
        "party": _party(db, c),
        "player_id": c.player_id,
        "staff_id": c.staff_id,
        "team": (db.get(Squad, c.squad_id).name if c.squad_id else None),
        "kind": c.kind,
        "kind_label": label,
        "title": c.title,
        "direction": direction,
        "amount_cents": c.amount_cents,
        "period": c.period,
        "bonus": c.bonus or {},
        "starts_on": c.starts_on.isoformat(),
        "ends_on": c.ends_on.isoformat() if c.ends_on else None,
    }


def entry_json(e: LedgerEntry) -> dict:
    return {
        "id": e.id,
        "date": e.day.isoformat(),
        "category": e.category,
        "category_label": CATEGORIES.get(e.category, e.category),
        "direction": e.direction,
        "amount_cents": e.amount_cents,
        "description": e.description,
        "status": e.status,
        "player_id": e.player_id,
        "match_id": e.match_id,
    }


def _entries(db: Session, scope: Scope, since: date, until: date) -> list[LedgerEntry]:
    q = select(LedgerEntry).where(LedgerEntry.day >= since, LedgerEntry.day <= until)
    if scope.squad_ids is not None:
        q = q.where(LedgerEntry.squad_id.in_(scope.squad_ids))
    return list(db.scalars(q.order_by(LedgerEntry.day.desc(), LedgerEntry.created_at.desc())))


def club_view(db: Session, scope: Scope, today: date) -> dict:
    season_start = date(today.year, 1, 1)
    entries = _entries(db, scope, season_start, today + timedelta(days=31))
    income = sum(e.amount_cents for e in entries if e.direction == "income")
    expense = sum(e.amount_cents for e in entries if e.direction == "expense")
    months: dict[str, dict] = defaultdict(lambda: {"income": 0, "expense": 0})
    by_cat: dict[tuple[str, str], int] = defaultdict(int)
    for e in entries:
        months[f"{e.day:%Y-%m}"][e.direction] += e.amount_cents
        by_cat[(e.category, e.direction)] += e.amount_cents
    fees_due = [e for e in entries if e.direction == "income" and e.status == "due" and e.category in ("academy_fee", "membership")]
    overdue = [e for e in fees_due if e.day < month_start(today)]
    bonuses: dict[str, dict] = {}
    for e in entries:
        if e.category == "bonus" and e.player_id:
            b = bonuses.setdefault(e.player_id, {"player_id": e.player_id, "name": db.get(Player, e.player_id).display_name, "total_cents": 0, "items": 0})
            b["total_cents"] += e.amount_cents
            b["items"] += 1
    contracts = db.scalars(select(Contract))
    if scope.squad_ids is not None:
        contracts = [c for c in contracts if c.squad_id in scope.squad_ids]
    items = db.scalars(select(RecurringItem).where(RecurringItem.active.is_(True)))
    if scope.squad_ids is not None:
        items = [i for i in items if i.squad_id in scope.squad_ids]
    return {
        "season": str(today.year),
        "today": today.isoformat(),
        "currency": "EUR",
        "totals": {
            "income_cents": income,
            "expense_cents": expense,
            "net_cents": income - expense,
            "fees_due_cents": sum(e.amount_cents for e in fees_due),
            "fees_overdue_cents": sum(e.amount_cents for e in overdue),
            "overdue_count": len(overdue),
        },
        "months": [{"month": k, **v} for k, v in sorted(months.items())],
        "categories": sorted(
            ({"category": k, "label": CATEGORIES.get(k, k), "direction": d, "amount_cents": v} for (k, d), v in by_cat.items()),
            key=lambda r: -r["amount_cents"],
        ),
        "contracts": [contract_json(db, c) for c in contracts],
        "recurring": [
            {"id": i.id, "name": i.name, "category": i.category, "direction": i.direction, "amount_cents": i.amount_cents, "period": i.period}
            for i in items
        ],
        "bonuses": sorted(bonuses.values(), key=lambda b: -b["total_cents"]),
        "ledger": [entry_json(e) for e in entries[:200]],
        "categories_all": CATEGORIES,
        "kinds": {k: v[2] for k, v in KINDS.items()},
        "note": "Amounts are synthetic examples for a demo. Not tax, payroll or legal advice.",
    }


def player_view(db: Session, player: Player, today: date) -> dict:
    season_start = date(today.year, 1, 1)
    contracts = list(db.scalars(select(Contract).where(Contract.player_id == player.id)))
    entries = list(
        db.scalars(
            select(LedgerEntry)
            .where(LedgerEntry.player_id == player.id, LedgerEntry.day >= season_start)
            .order_by(LedgerEntry.day.desc())
        )
    )
    pays = [e for e in entries if e.direction == "income"]  # the player pays the club
    earns = [e for e in entries if e.direction == "expense"]  # the club pays the player
    bonus_by_type: dict[str, int] = defaultdict(int)
    for e in earns:
        if e.category == "bonus":
            label = e.description.split(" bonus")[0]
            bonus_by_type[label] += e.amount_cents
    return {
        "currency": "EUR",
        "contracts": [contract_json(db, c) for c in contracts],
        "fees_paid_cents": sum(e.amount_cents for e in pays if e.status == "paid"),
        "fees_due_cents": sum(e.amount_cents for e in pays if e.status == "due"),
        "salary_cents": sum(e.amount_cents for e in earns if e.category == "salary"),
        "bonus_cents": sum(e.amount_cents for e in earns if e.category == "bonus"),
        "bonus_by_type": [{"type": k, "amount_cents": v} for k, v in sorted(bonus_by_type.items(), key=lambda kv: -kv[1])],
        "entries": [entry_json(e) for e in entries[:30]],
    }
