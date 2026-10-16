from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date


def _env_date(name: str) -> date | None:
    v = os.environ.get(name)
    return date.fromisoformat(v) if v else None


@dataclass(frozen=True)
class Settings:
    database_url: str = field(default_factory=lambda: os.environ.get("DATABASE_URL", "sqlite:///./pathtopro.db"))
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

    def __post_init__(self):
        if self.env == "production" and self.jwt_secret == "dev-only-change-me-this-is-not-a-secret-key":
            raise RuntimeError("PATHTOPRO_JWT_SECRET must be set in production")


settings = Settings()
