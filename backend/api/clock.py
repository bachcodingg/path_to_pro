"""The app's notion of today. Demo data is a simulated season, so the demo pins
'today' to a date inside it (PATHTOPRO_TODAY, or the date stored by the seeder)."""

from __future__ import annotations

from datetime import date

from api.settings import settings

_override: date | None = None


def set_today(day: date | None) -> None:
    global _override
    _override = day


def today() -> date:
    if _override is not None:
        return _override
    if settings.demo_today is not None:
        return settings.demo_today
    return date.today()
