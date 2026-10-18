"""League ladder (config/competitions.yaml): names, levels and minutes weighted by level."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

CONFIG = Path(__file__).resolve().parent.parent / "config" / "competitions.yaml"


@lru_cache(maxsize=1)
def _data() -> dict:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


def all_competitions() -> dict[str, dict]:
    return _data()["competitions"]


def get(key: str | None) -> dict | None:
    return all_competitions().get(key or "")


def label(key: str | None) -> str:
    c = get(key)
    return c["name"] if c else (key or "Unknown")


def level(key: str | None) -> int:
    c = get(key)
    return int(c["level"]) if c else 0


def academy_competition(age: float) -> str:
    """The national youth league for an academy player's age group."""
    by_age = {int(k): v for k, v in _data()["academy_by_age"].items()}
    for limit in sorted(by_age):
        if age < limit:
            return by_age[limit]
    return by_age[max(by_age)]


def exposure(minutes: float, key: str | None) -> float:
    """Minutes weighted by competition level, in "full matches at the top level"."""
    return minutes * level(key) / 100 / 90
