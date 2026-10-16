from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.db import get_db
from api.deps import CurrentUser, audit, current_user
from api.security import create_token, verify_password
from domain.models import Guardian, Player, StaffMember, UserAccount

router = APIRouter(prefix="/api/auth", tags=["auth"])


class Login(BaseModel):
    email: str
    password: str


def _profile(db: Session, acc: UserAccount) -> dict:
    name = "Admin"
    if acc.player_id:
        name = db.get(Player, acc.player_id).display_name
    elif acc.guardian_id:
        name = db.get(Guardian, acc.guardian_id).name
    elif acc.staff_id:
        name = db.get(StaffMember, acc.staff_id).name
    return {"id": acc.id, "email": acc.email, "role": acc.role.value, "name": name, "player_id": acc.player_id}


@router.post("/login")
def login(body: Login, db: Session = Depends(get_db)) -> dict:
    acc = db.scalars(select(UserAccount).where(UserAccount.email == body.email.strip().lower())).first()
    if acc is None or not acc.active or not verify_password(body.password, acc.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password")
    audit(db, CurrentUser(acc, acc.role), "login", "user_account", acc.id)
    db.commit()
    return {"token": create_token(acc.id, acc.role.value), "user": _profile(db, acc)}


@router.get("/me")
def me(user: CurrentUser = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return _profile(db, user.account)
