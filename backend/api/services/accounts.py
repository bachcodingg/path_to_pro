"""One-time email links (password reset, email verification, invitations) and the emails
that carry them. Tokens are random, stored as SHA-256 hashes, expire and work once."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from api.services import notify
from domain.enums import Pathway
from domain.models import (
    AgentRun,
    AuthToken,
    Guardian,
    Match,
    Player,
    Proposal,
    SessionLoad,
    Squad,
    StaffMember,
    UserAccount,
    WeeklyPlan,
)
from domain.models import Session as TeamSession

LIFETIME = {"reset": timedelta(hours=1), "verify": timedelta(days=7), "invite": timedelta(days=14)}

# An account that was invited but has not set a password yet: verify_password never accepts it
UNUSABLE_PASSWORD = "invited$"


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _aware(t: datetime) -> datetime:
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def issue(db: Session, acc: UserAccount, purpose: str) -> str:
    """A new link for this purpose; earlier unused links for the same purpose stop working."""
    now = datetime.now(UTC)
    db.execute(
        update(AuthToken)
        .where(AuthToken.account_id == acc.id, AuthToken.purpose == purpose, AuthToken.used_at.is_(None))
        .values(used_at=now)
    )
    raw = secrets.token_urlsafe(32)
    db.add(AuthToken(account_id=acc.id, purpose=purpose, token_hash=_hash(raw), created_at=now, expires_at=now + LIFETIME[purpose]))
    return raw


def lookup(db: Session, raw: str, purposes: tuple[str, ...]) -> tuple[AuthToken, UserAccount]:
    tok = db.scalars(select(AuthToken).where(AuthToken.token_hash == _hash(raw))).first()
    if tok is None or tok.purpose not in purposes or tok.used_at is not None or _aware(tok.expires_at) < datetime.now(UTC):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This link has expired or was already used. Ask for a new one.")
    acc = db.get(UserAccount, tok.account_id)
    if acc is None or not acc.active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This account is no longer active")
    return tok, acc


def display_name(db: Session, acc: UserAccount) -> str:
    if acc.player_id:
        return db.get(Player, acc.player_id).display_name
    if acc.guardian_id:
        return db.get(Guardian, acc.guardian_id).name
    if acc.staff_id:
        return db.get(StaffMember, acc.staff_id).name
    return "Admin"


def _greeting(db: Session, acc: UserAccount) -> str:
    return f"Hi {display_name(db, acc).split()[0]},"


def send_reset(db: Session, acc: UserAccount) -> None:
    raw = issue(db, acc, "reset")
    notify.queue(
        db,
        acc.email,
        "reset",
        "Reset your PathToPro password",
        f"{_greeting(db, acc)}\n\nSomeone asked to reset the password of your PathToPro account. "
        f"To choose a new password, open this link within an hour:\n\n{notify.link('/set-password?token=' + raw)}\n\n"
        "If this wasn't you, ignore this email: your password stays the same.",
    )


def send_verify(db: Session, acc: UserAccount) -> None:
    raw = issue(db, acc, "verify")
    notify.queue(
        db,
        acc.email,
        "verify",
        "Confirm your email for PathToPro",
        f"{_greeting(db, acc)}\n\nPlease confirm that this is your email address, so we can reach you "
        f"if you forget your password:\n\n{notify.link('/verify-email?token=' + raw)}",
    )


def send_invite(db: Session, acc: UserAccount, club: str, team: str) -> None:
    raw = issue(db, acc, "invite")
    who = {"coach": "a coach", "physio": "a physio", "player": "a player"}.get(acc.role.value, "a member")
    notify.queue(
        db,
        acc.email,
        "invite",
        f"You're invited to {club} on PathToPro",
        f"{_greeting(db, acc)}\n\n{club} added you to {team} on PathToPro as {who}. "
        f"Choose your password to get started (the link works for 14 days):\n\n{notify.link('/set-password?token=' + raw)}",
    )


def send_guardian_invite(db: Session, guardian: Guardian, child: str, club: str | None = None) -> None:
    """A parent links with their child's account using the invite code (consent under 16)."""
    where = f"{club} uses" if club else "Your child signed up for"
    notify.queue(
        db,
        guardian.email,
        "guardian_invite",
        f"{child} needs your consent on PathToPro",
        f"Hello,\n\n{where} PathToPro, a training planner for young footballers, for {child}. "
        "Because they are under 16, PathToPro stores their check-ins, sleep, growth and test results only "
        "after a parent agrees, separately for each kind of data.\n\n"
        f"Create your parent account and choose what may be stored:\n\n"
        f"{notify.link('/register/guardian?code=' + (guardian.invite_code or ''))}\n\n"
        f"Your invite code: {guardian.invite_code}",
    )


def delete_player(db: Session, player: Player) -> None:
    """Remove a player and everything stored about them (GDPR Art. 17). Most rows go with
    the player by ON DELETE CASCADE; agent runs, plans and personal sessions reference each
    other without one, so they are removed first. A self-guided player's own squad (their
    club fixtures) goes too."""
    pid, squad_id = player.id, player.squad_id
    own_squad = player.pathway == Pathway.AMATEUR.value
    db.execute(delete(Proposal).where(Proposal.player_id == pid))
    db.execute(delete(WeeklyPlan).where(WeeklyPlan.player_id == pid))
    db.execute(delete(AgentRun).where(AgentRun.player_id == pid))
    db.execute(delete(SessionLoad).where(SessionLoad.player_id == pid))
    db.execute(delete(TeamSession).where(TeamSession.player_id == pid))
    db.execute(delete(Player).where(Player.id == pid))
    if own_squad and db.scalars(select(Player.id).where(Player.squad_id == squad_id)).first() is None:
        match_ids = select(Match.id).where(Match.squad_id == squad_id)
        db.execute(delete(SessionLoad).where(SessionLoad.match_id.in_(match_ids)))
        db.execute(delete(Match).where(Match.squad_id == squad_id))
        db.execute(delete(TeamSession).where(TeamSession.squad_id == squad_id))
        db.execute(delete(Squad).where(Squad.id == squad_id))
    db.expunge_all()  # Core deletes bypass the identity map: drop stale objects
