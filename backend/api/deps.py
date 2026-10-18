"""Request dependencies: current user, role checks (RBAC), scope checks, audit, consent."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.db import get_db
from api.security import decode_token
from api.settings import settings
from domain.enums import ConsentDataType, Role
from domain.models import AuditLog, ConsentRecord, Player, StaffMember, UserAccount, player_guardians

bearer = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    account: UserAccount
    role: Role

    @property
    def id(self) -> str:
        return self.account.id


def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)
) -> CurrentUser:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in")
    try:
        payload = decode_token(creds.credentials)
    except jwt.PyJWTError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from e
    acc = db.get(UserAccount, payload.get("sub"))
    if acc is None or not acc.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account not found")
    return CurrentUser(acc, acc.role)


def require(*roles: Role) -> Callable[..., CurrentUser]:
    """RBAC check, applied on every endpoint."""

    def dep(user: CurrentUser = Depends(current_user)) -> CurrentUser:
        if user.role not in roles and user.role != Role.ADMIN:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed for your role")
        return user

    return dep


def staff_of(user: CurrentUser, db: Session) -> StaffMember:
    if user.account.staff_id is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Staff only")
    return db.get(StaffMember, user.account.staff_id)


def player_in_scope(player_id: str, user: CurrentUser, db: Session) -> Player:
    """Players see themselves, guardians their children, staff their squad."""
    player = db.get(Player, player_id)
    if player is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Player not found")
    if user.role == Role.ADMIN:
        return player
    if user.role == Role.PLAYER and user.account.player_id == player_id:
        return player
    if user.role == Role.GUARDIAN:
        linked = db.execute(
            select(player_guardians).where(
                player_guardians.c.player_id == player_id, player_guardians.c.guardian_id == user.account.guardian_id
            )
        ).first()
        if linked:
            return player
    if user.role in (Role.COACH, Role.PHYSIO):
        from domain.models import Registration

        staff = staff_of(user, db)
        if staff.squad_id is None or staff.squad_id == player.squad_id:
            return player
        # Dual registration: the second team's staff see the player too
        if db.scalars(
            select(Registration.id).where(Registration.player_id == player_id, Registration.squad_id == staff.squad_id)
        ).first():
            return player
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your player")


def audit(db: Session, user: CurrentUser | None, action: str, entity: str, entity_id: str | None = None, **details):
    db.add(
        AuditLog(
            at=datetime.now(UTC),
            actor_role=user.role.value if user else "system",
            actor_id=user.id if user else None,
            action=action,
            entity=entity,
            entity_id=entity_id,
            details=details,
        )
    )


def age_on(birth: date, day: date) -> float:
    return (day - birth).days / 365.25


def has_consent(db: Session, player: Player, data_type: ConsentDataType, today: date) -> bool:
    """Players at or above the age of digital consent consent themselves (at sign-up);
    younger players need a guardian's consent for each data type. Latest record wins."""
    rec = db.scalars(
        select(ConsentRecord)
        .where(ConsentRecord.player_id == player.id, ConsentRecord.data_type == data_type)
        .order_by(ConsentRecord.recorded_at.desc())
        .limit(1)
    ).first()
    if rec is not None:
        return rec.granted
    return age_on(player.birth_date, today) >= settings.digital_consent_age
