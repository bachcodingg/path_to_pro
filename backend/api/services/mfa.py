"""Two-step sign-in with an authenticator app: TOTP (RFC 6238, SHA-1, 6 digits, 30 s),
the kind Google Authenticator, Microsoft Authenticator and 1Password read.

After the password, an account with two-step sign-in gets a short-lived "second step"
token, signed with a key of its own, so it can never be used as an access token.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

import jwt

from api.settings import settings

STEP = 30
DIGITS = 6
RECOVERY_CODES = 8


def new_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _code(secret: str, counter: int) -> str:
    key = base64.b32decode(secret + "=" * (-len(secret) % 8))
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(value % 10**DIGITS).zfill(DIGITS)


def code_at(secret: str, at: float) -> str:
    """>>> code_at("GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ", 59)  # RFC 6238 test vector (SHA-1)
    '287082'
    """
    return _code(secret, int(at // STEP))


def verify(secret: str, code: str, at: float | None = None) -> bool:
    """One step either side, for phones whose clock is a little off."""
    code = "".join(c for c in code if c.isdigit())
    if len(code) != DIGITS:
        return False
    now = time.time() if at is None else at
    return any(hmac.compare_digest(code_at(secret, now + d * STEP), code) for d in (-1, 0, 1))


def otpauth_uri(secret: str, email: str) -> str:
    issuer = "PathToPro"
    return f"otpauth://totp/{quote(issuer)}:{quote(email)}?secret={secret}&issuer={quote(issuer)}&digits={DIGITS}&period={STEP}"


def _hash(code: str) -> str:
    return hashlib.sha256(code.replace("-", "").upper().encode()).hexdigest()


def new_recovery_codes() -> tuple[list[str], list[str]]:
    """Codes to show once, and their hashes to store."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    codes = []
    for _ in range(RECOVERY_CODES):
        raw = "".join(secrets.choice(alphabet) for _ in range(10))
        codes.append(f"{raw[:5]}-{raw[5:]}")
    return codes, [_hash(c) for c in codes]


def use_recovery_code(stored: list[str] | None, code: str) -> list[str] | None:
    """The remaining hashes if `code` is one of them (it is used up), else None."""
    h = _hash(code.strip())
    if not stored or h not in stored:
        return None
    return [s for s in stored if s != h]


def _key() -> str:
    return settings.jwt_secret + ":second-step"


def step_token(account_id: str) -> str:
    now = datetime.now(UTC)
    return jwt.encode({"sub": account_id, "iat": now, "exp": now + timedelta(minutes=5)}, _key(), algorithm="HS256")


def read_step_token(token: str) -> str:
    return jwt.decode(token, _key(), algorithms=["HS256"])["sub"]
