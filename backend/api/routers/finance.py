"""Club finances: coaches (and admins) see their team's money; players their own
contract, fees and bonuses; guardians their child's fees."""

from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from api import clock
from api.db import get_db
from api.deps import CurrentUser, audit, player_in_scope, require, staff_of
from domain.enums import Role
from domain.models import Contract, LedgerEntry, Player, Squad, StaffMember
from finance import service as fin

router = APIRouter(tags=["finance"])


def _scope(user: CurrentUser, db: Session) -> fin.Scope:
    if user.role == Role.ADMIN:
        return fin.Scope(None)
    staff = staff_of(user, db)
    return fin.Scope(None if staff.squad_id is None else [staff.squad_id])


def _view(user: CurrentUser, db: Session) -> dict:
    return fin.club_view(db, _scope(user, db), clock.today())


@router.get("/api/coach/finance")
def finance(user: CurrentUser = Depends(require(Role.COACH)), db: Session = Depends(get_db)) -> dict:
    out = _view(user, db)
    audit(db, user, "read", "ledger", None)
    db.commit()
    return out


class Month(BaseModel):
    month: str = Field(pattern=r"^\d{4}-\d{2}$")


@router.post("/api/coach/finance/run-month")
def run_month(body: Month, user: CurrentUser = Depends(require(Role.COACH)), db: Session = Depends(get_db)) -> dict:
    """Book a month's fees, salaries and running costs (safe to run twice)."""
    month = date.fromisoformat(body.month + "-01")
    if month > fin.next_month(clock.today()):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Book this month or earlier")
    booked = fin.run_month(db, month, _scope(user, db).squad_ids)
    audit(db, user, "create", "ledger", None, month=body.month, entries=booked)
    db.commit()
    return {**_view(user, db), "booked": booked}


class Entry(BaseModel):
    day: date
    category: str
    direction: Literal["income", "expense"]
    amount_cents: int = Field(gt=0, le=100_000_000)
    description: str = Field(min_length=1, max_length=200)
    player_id: str | None = None
    paid: bool = True


@router.post("/api/coach/finance/entries", status_code=201)
def add_entry(body: Entry, user: CurrentUser = Depends(require(Role.COACH)), db: Session = Depends(get_db)) -> dict:
    if body.category not in fin.CATEGORIES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown category")
    if body.player_id:
        player_in_scope(body.player_id, user, db)
    scope = _scope(user, db)
    db.add(
        LedgerEntry(
            squad_id=scope.squad_ids[0] if scope.squad_ids else None,
            day=body.day,
            category=body.category,
            direction=body.direction,
            amount_cents=body.amount_cents,
            description=body.description.strip(),
            player_id=body.player_id,
            status="paid" if body.paid else "due",
        )
    )
    audit(db, user, "create", "ledger", None, category=body.category)
    db.commit()
    return _view(user, db)


class Paid(BaseModel):
    paid: bool = True


@router.post("/api/coach/finance/entries/{entry_id}/paid")
def mark_paid(entry_id: str, body: Paid, user: CurrentUser = Depends(require(Role.COACH)), db: Session = Depends(get_db)) -> dict:
    e = db.get(LedgerEntry, entry_id)
    scope = _scope(user, db)
    if e is None or (scope.squad_ids is not None and e.squad_id not in scope.squad_ids):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entry not found")
    e.status = "paid" if body.paid else "due"
    audit(db, user, "update", "ledger", e.id, status=e.status)
    db.commit()
    return _view(user, db)


class ContractIn(BaseModel):
    player_id: str | None = None
    staff_id: str | None = None
    kind: Literal["academy_fee", "membership", "amateur", "semi_pro", "pro", "staff_salary", "coach_fee"]
    amount_cents: int = Field(ge=0, le=100_000_000)
    period: Literal["month", "season"] = "month"
    bonus: dict[str, int] = Field(default_factory=dict)
    starts_on: date
    ends_on: date | None = None
    title: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def _one_party(self):
        if bool(self.player_id) == bool(self.staff_id):
            raise ValueError("Give either a player or a staff member")
        if set(self.bonus) - set(fin.BONUS_TYPES) or any(v < 0 for v in self.bonus.values()):
            raise ValueError(f"Bonus types: {', '.join(fin.BONUS_TYPES)} (cents, not negative)")
        if self.ends_on and self.ends_on < self.starts_on:
            raise ValueError("The contract ends before it starts")
        return self


@router.post("/api/coach/finance/contracts", status_code=201)
def add_contract(body: ContractIn, user: CurrentUser = Depends(require(Role.COACH)), db: Session = Depends(get_db)) -> dict:
    staff = staff_of(user, db) if user.role != Role.ADMIN else None
    squad_id = staff.squad_id if staff else None
    if body.player_id:
        p = player_in_scope(body.player_id, user, db)
        squad_id = squad_id or p.squad_id
        if body.kind in ("staff_salary", "coach_fee"):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "That contract type is for staff")
    else:
        s = db.get(StaffMember, body.staff_id)
        if s is None or (squad_id and s.squad_id != squad_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Staff member not found")
        if body.kind not in ("staff_salary", "coach_fee"):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Staff contracts are staff salary or coach fee")
    direction, _, label = fin.KINDS[body.kind]
    c = Contract(
        player_id=body.player_id,
        staff_id=body.staff_id,
        squad_id=squad_id,
        kind=body.kind,
        title=body.title or label,
        direction=direction,
        amount_cents=body.amount_cents,
        period=body.period,
        bonus=body.bonus if direction == "expense" else {},
        starts_on=body.starts_on,
        ends_on=body.ends_on,
    )
    db.add(c)
    audit(db, user, "create", "contract", None, kind=body.kind)
    db.commit()
    return _view(user, db)


@router.delete("/api/coach/finance/contracts/{contract_id}")
def end_contract(contract_id: str, user: CurrentUser = Depends(require(Role.COACH)), db: Session = Depends(get_db)) -> dict:
    c = db.get(Contract, contract_id)
    scope = _scope(user, db)
    if c is None or (scope.squad_ids is not None and c.squad_id not in scope.squad_ids):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contract not found")
    c.ends_on = clock.today()
    audit(db, user, "update", "contract", c.id, ended=True)
    db.commit()
    return _view(user, db)


class Title(BaseModel):
    title: str = Field(min_length=2, max_length=100)
    prize_cents: int = Field(default=0, ge=0, le=100_000_000)


@router.post("/api/coach/finance/titles")
def record_title(body: Title, user: CurrentUser = Depends(require(Role.COACH)), db: Session = Depends(get_db)) -> dict:
    """A trophy (league won, cup): prize money in, title bonuses for players with that clause."""
    staff = staff_of(user, db)
    if staff.squad_id is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Record titles from a team coach account")
    booked = fin.record_title(db, db.get(Squad, staff.squad_id), body.title, body.prize_cents, clock.today())
    audit(db, user, "create", "ledger", None, title=body.title, entries=booked)
    db.commit()
    return {**_view(user, db), "booked": booked}


# --------------------------------------------------------------------------- players and guardians


@router.get("/api/me/finance")
def my_finance(user: CurrentUser = Depends(require(Role.PLAYER)), db: Session = Depends(get_db)) -> dict:
    p = db.get(Player, user.account.player_id)
    out = fin.player_view(db, p, clock.today())
    audit(db, user, "read", "ledger", p.id)
    db.commit()
    return out


@router.get("/api/guardian/children/{player_id}/finance")
def child_finance(player_id: str, user: CurrentUser = Depends(require(Role.GUARDIAN)), db: Session = Depends(get_db)) -> dict:
    p = player_in_scope(player_id, user, db)
    out = fin.player_view(db, p, clock.today())
    audit(db, user, "read", "ledger", p.id)
    db.commit()
    return out
