from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL", "sqlite:///./pathtopro.db")
    # Hosts such as Render hand out postgres:// URLs; SQLAlchemy needs the driver named.
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


def _env_date(name: str) -> date | None:
    v = os.environ.get(name)
    return date.fromisoformat(v) if v else None


@dataclass(frozen=True)
class Settings:
    database_url: str = field(default_factory=_database_url)
    jwt_secret: str = field(default_factory=lambda: os.environ.get("PATHTOPRO_JWT_SECRET", "dev-only-change-me-this-is-not-a-secret-key"))
    jwt_minutes: int = int(os.environ.get("PATHTOPRO_JWT_MINUTES", "720"))
    env: str = os.environ.get("PATHTOPRO_ENV", "development")
    # Demo data is a simulated season, so "today" is a fixed date inside it.
    demo_today: date | None = field(default_factory=lambda: _env_date("PATHTOPRO_TODAY"))
    # Age of digital consent (GDPR Art. 8; 16 in Germany). Below it, a guardian consents.
    digital_consent_age: int = int(os.environ.get("PATHTOPRO_CONSENT_AGE", "16"))
    cors_origins: tuple[str, ...] = tuple(
        os.environ.get("PATHTOPRO_CORS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    )
    scheduler: bool = os.environ.get("PATHTOPRO_SCHEDULER", "on") == "on"
    # Built website to serve from the API (single-container deployment); unset in development.
    static_dir: str | None = os.environ.get("PATHTOPRO_STATIC_DIR")
    # Load the synthetic demo season when the database is empty (demo deployments).
    autoseed: bool = os.environ.get("PATHTOPRO_AUTOSEED", "off") == "on"
    # Self sign-up for the self-guided pathway (players 13+, parents by invite code).
    # Off by default on demo deployments: their demo accounts share a published password
    # and "today" is pinned inside the synthetic season, so real players must not join.
    registration: bool = (
        os.environ.get("PATHTOPRO_REGISTRATION", "off" if os.environ.get("PATHTOPRO_AUTOSEED") == "on" else "on")
        == "on"
    )
    # Where people open the website; links in emails (password reset, invitations) point here.
    public_url: str = os.environ.get("PATHTOPRO_PUBLIC_URL", "http://localhost:5173").rstrip("/")
    # Email: "smtp" sends through PATHTOPRO_SMTP_*, "log" writes each email to the server log
    # (development), "memory" keeps them in a list (tests). Default: smtp when a host is set.
    mail: str = os.environ.get("PATHTOPRO_MAIL", "smtp" if os.environ.get("PATHTOPRO_SMTP_HOST") else "log")
    smtp_host: str | None = os.environ.get("PATHTOPRO_SMTP_HOST")
    smtp_port: int = int(os.environ.get("PATHTOPRO_SMTP_PORT", "587"))
    smtp_user: str | None = os.environ.get("PATHTOPRO_SMTP_USER")
    smtp_password: str | None = os.environ.get("PATHTOPRO_SMTP_PASSWORD")
    smtp_tls: str = os.environ.get("PATHTOPRO_SMTP_TLS", "starttls")  # starttls | ssl | none
    mail_from: str = os.environ.get("PATHTOPRO_MAIL_FROM", "PathToPro <no-reply@localhost>")
    # The club administrator, created on start if no account has this email (real deployments).
    admin_email: str | None = os.environ.get("PATHTOPRO_ADMIN_EMAIL")
    # The club's local time: check-in reminders go out at the hour each player picked.
    timezone: str = os.environ.get("PATHTOPRO_TIMEZONE", "Europe/Berlin")
    # Web push (PWA notifications); keys from `python -m api.jobs vapid`. Unset = push off.
    vapid_public_key: str | None = os.environ.get("PATHTOPRO_VAPID_PUBLIC_KEY")
    vapid_private_key: str | None = os.environ.get("PATHTOPRO_VAPID_PRIVATE_KEY")
    vapid_subject: str = os.environ.get("PATHTOPRO_VAPID_SUBJECT", "mailto:admin@localhost")

    def __post_init__(self):
        if self.mail not in ("smtp", "log", "memory"):
            raise RuntimeError("PATHTOPRO_MAIL must be smtp, log or memory")
        if self.mail == "smtp" and not self.smtp_host:
            raise RuntimeError("PATHTOPRO_MAIL=smtp needs PATHTOPRO_SMTP_HOST")
        if self.env == "production" and self.jwt_secret == "dev-only-change-me-this-is-not-a-secret-key":
            raise RuntimeError("PATHTOPRO_JWT_SECRET must be set in production")
        if self.env == "production" and self.autoseed and self.registration:
            raise RuntimeError(
                "PATHTOPRO_AUTOSEED=on (public demo accounts) and PATHTOPRO_REGISTRATION=on (real players) "
                "can't be combined in production: run the demo and the real service as separate deployments"
            )


settings = Settings()
