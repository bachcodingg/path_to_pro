"""Match tips: mindset for everyone and how to play each position (config/tips.yaml), and
the tip for today: a match-day tip on match day, the bad-game tip the day after a match,
otherwise a tip for the player's position and an everyday mindset tip on alternate days.

>>> tip_for_day("striker", date(2026, 11, 28), days_to_match=0, match_yesterday=False)["when"]
'match'
>>> tip_for_day("striker", date(2026, 11, 29), days_to_match=6, match_yesterday=True)["id"]
'after-bad-game'
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path

import yaml

CONFIG = Path(__file__).resolve().parent.parent / "config" / "tips.yaml"


@lru_cache(maxsize=1)
def library() -> dict:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


def tip_for_day(position: str, day: date, days_to_match: int | None, match_yesterday: bool) -> dict:
    lib = library()
    mindset = lib["mindset"]
    own = lib["positions"].get(position, lib["positions"]["midfielder"])
    n = day.toordinal()
    if days_to_match == 0:
        pool, reason = [t for t in mindset if t["when"] == "match"], "Match day"
    elif match_yesterday:
        pool, reason = [t for t in mindset if t["when"] == "after_match"], "After yesterday's match"
    elif n % 2:
        pool, reason = own, "For your position"
    else:
        pool, reason = [t for t in mindset if t["when"] == "any"], "Mindset"
    return pool[(n // 2) % len(pool)] | {"reason": reason}
