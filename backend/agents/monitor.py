"""Monitor agent: computes load, readiness and growth status and emits risk flags.

Deterministic, no LLM. Triggered by a new session, check-in, wearable sync and
nightly at 23:00.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date

from analytics.flags import Flag, PlayerSnapshot, evaluate
from analytics.load import ewma_acwr, ewma_acwr_series, monotony
from analytics.maturation import GrowthStatus, Sex, growth_status
from analytics.readiness import Band, Readiness, ReadinessConfig, active_config, hrv_z, readiness


@dataclass
class Measurements:
    age_years: float
    height_cm: float
    sitting_height_cm: float
    weight_kg: float
    sex: Sex = Sex.MALE


@dataclass
class PlayerHistory:
    """Raw inputs for one player, oldest first. Today's values are last."""

    player_id: str
    day: date
    daily_loads: Sequence[float] = ()
    sleep_hours: Sequence[float] = ()
    ln_rmssd: Sequence[float] = ()
    hooper_today: tuple[int, int, int, int] | None = None
    mood_red: bool = False
    pain_reported: bool = False
    missed_checkins_in_row: int = 0
    measurements: Measurements | None = None
    preseason_daily_load: float | None = None  # seeds the EWMA when history is short
    previous_band: Band | None = None  # yesterday's readiness band, for the colour buffer


@dataclass
class Assessment:
    player_id: str
    day: date
    flags: list[Flag]
    readiness: Readiness | None
    growth: GrowthStatus | None
    acwr: float | None
    chronic_daily_load: float
    acute_daily_load: float
    monotony: float | None
    hrv_z: float | None
    chips: list[str] = field(default_factory=list)  # short data chips for "Why?" cards

    @property
    def safety_flags(self) -> list[Flag]:
        return [f for f in self.flags if f.is_safety]

    @property
    def planning_flags(self) -> list[Flag]:
        return [f for f in self.flags if not f.is_safety]


def assess(h: PlayerHistory, config: ReadinessConfig | None = None) -> Assessment:
    loads = list(h.daily_loads)
    if h.preseason_daily_load is not None:
        series = ewma_acwr_series(loads, initial=h.preseason_daily_load)
        acwr = series[-1].ratio if series else None
        chronic = series[-1].chronic if series else h.preseason_daily_load
        acute = series[-1].acute if series else h.preseason_daily_load
    else:
        acwr = ewma_acwr(loads)
        series = ewma_acwr_series(loads)
        chronic = series[-1].chronic if series else 0.0
        acute = series[-1].acute if series else 0.0
    mono = monotony(loads[-7:]) if len(loads) >= 7 else None

    z = None
    if h.ln_rmssd:
        z = hrv_z(h.ln_rmssd[-1], list(h.ln_rmssd[:-1]))
    r = readiness(
        hooper=h.hooper_today,
        sleep_hours=h.sleep_hours[-1] if h.sleep_hours else None,
        ln_rmssd=h.ln_rmssd[-1] if h.ln_rmssd else None,
        hrv_baseline=list(h.ln_rmssd[:-1]),
        config=config or active_config(),
        previous_band=h.previous_band,
    )
    g = None
    if h.measurements is not None:
        m = h.measurements
        g = growth_status(m.age_years, m.height_cm, m.sitting_height_cm, m.weight_kg, m.sex)

    snap = PlayerSnapshot(
        daily_loads=loads,
        acwr=acwr,
        recent_sleep_hours=list(h.sleep_hours[-3:]),
        hrv_z=z,
        readiness_band=r.band if r else None,
        in_phv_window=bool(g and g.in_phv_window),
        maturity_offset=g.maturity_offset if g else None,
        pain_reported=h.pain_reported,
        mood_red=h.mood_red,
        missed_checkins_in_row=h.missed_checkins_in_row,
    )
    flags = evaluate(snap)
    return Assessment(
        player_id=h.player_id,
        day=h.day,
        flags=flags,
        readiness=r,
        growth=g,
        acwr=acwr,
        chronic_daily_load=chronic,
        acute_daily_load=acute,
        monotony=mono,
        hrv_z=z,
        chips=_chips(h, acwr, z, g, loads),
    )


def _chips(h: PlayerHistory, acwr, z, g, loads) -> list[str]:
    chips = []
    short = [s for s in list(h.sleep_hours)[-3:] if s < 6]
    if len(short) == 3:
        chips.append(f"Sleep {sum(short) / 3:.1f} h x 3")
    if acwr is not None and acwr > 1.3:
        chips.append(f"Load {100 * (acwr - 1):+.0f}%")
    if z is not None and z <= -1:
        chips.append(f"HRV {z:+.1f} SD")
    if g is not None and g.in_phv_window:
        chips.append("Growth zone")
    return chips
