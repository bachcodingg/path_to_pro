"""Day-by-day synthetic season for a squad of academy players.

The world (fixtures, exams, physiology, injuries) is driven by the config and
seed; what players train is decided by a `Policy`. Running two policies with the
same seed gives the same fixtures and players, so their results are comparable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, ClassVar

import numpy as np
import yaml

from analytics.load import ewma_lambda, session_load
from analytics.maturation import PHV_WINDOW
from analytics.norms import NormTable
from analytics.readiness import ReadinessConfig, readiness
from domain.enums import SessionType
from simulator.policies import BaselinePolicy, Policy, WeekContext

DEFAULT_CONFIG = Path(__file__).resolve().parent / "config.yaml"
PRESEASON_DAILY_LOAD = 300.0  # seeds the EWMA so ACWR is meaningful from day 1
MIRWALD_VALID_YEARS = 3.0
SITTING_RATIO_BOUNDS = (0.47, 0.58)
TESTS = ("sprint_10m", "sprint_30m", "cmj", "yoyo_ir1")


def load_config(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def _logit(p: float) -> float:
    return math.log(p / (1 - p))


# --------------------------------------------------------------------------- players


@dataclass
class PlayerProfile:
    index: int
    player_id: str
    name: str
    age_at_start: float
    phv_age: float
    adult_height: float
    mirwald_bias: float  # Mirwald's error is systematic per person (SE ~0.5 y)
    bmi_offset: float
    sleep_mean: float
    ln_rmssd_base: float


@dataclass
class PlayerState:
    profile: PlayerProfile
    age: float
    daily_loads: list[float] = field(default_factory=list)
    sleep_hours: list[float] = field(default_factory=list)
    ln_rmssd: list[float] = field(default_factory=list)
    readiness_scores: list[float | None] = field(default_factory=list)
    fatigue: float = 0.0  # residual load in 1000 AU
    acute: float = PRESEASON_DAILY_LOAD
    chronic: float = PRESEASON_DAILY_LOAD
    injured_until: date | None = None
    pain_pending: bool = False
    missed_in_row: int = 0
    ability_z: dict[str, float] = field(default_factory=dict)

    @property
    def true_maturity_offset(self) -> float:
        return self.age - self.profile.phv_age

    @property
    def in_phv_window(self) -> bool:
        lo, hi = PHV_WINDOW
        return lo <= self.true_maturity_offset <= hi

    @property
    def acwr(self) -> float:
        return self.acute / self.chronic if self.chronic > 0 else 1.0

    def is_injured(self, d: date) -> bool:
        return self.injured_until is not None and d < self.injured_until


# --------------------------------------------------------------------------- anthropometrics


def height_at(p: PlayerProfile, age: float, cfg: dict) -> float:
    g = cfg["growth"]
    amp, s = g["growth_amplitude_cm"], g["logistic_scale_years"]
    return p.adult_height - amp + amp * _sigmoid((age - p.phv_age) / s)


def weight_at(p: PlayerProfile, age: float, height_cm: float) -> float:
    bmi = 16.5 + 0.35 * (age - 10) + p.bmi_offset
    return bmi * (height_cm / 100) ** 2


def sitting_height_for_offset(age: float, height: float, weight: float, target_offset: float) -> float:
    """Sitting height that makes Mirwald's (male) equation return `target_offset`.

    Mirwald is quadratic in sitting height once age, height and weight are fixed,
    so generating sitting height this way keeps the simulated anthropometrics
    consistent with the true PHV age plus a realistic estimation error.
    """
    a = -0.0002708
    b = 0.0002708 * height + 0.001663 * age + 0.007216 * age
    c = -9.236 - 0.001663 * age * height + 0.02292 * weight / height * 100 - target_offset
    disc = b * b - 4 * a * c
    guess = 0.52 * height
    if disc < 0:
        return guess
    roots = [(-b + s * math.sqrt(disc)) / (2 * a) for s in (1, -1)]
    best = min(roots, key=lambda r: abs(r - guess))
    lo, hi = SITTING_RATIO_BOUNDS
    return float(np.clip(best, lo * height, hi * height))


# --------------------------------------------------------------------------- tests


def _norm_value(norms: NormTable, test: str, age: float, z: float) -> float:
    """Value at ability z, interpolating norms between age groups (U13 centred on 12.5 y)."""
    lo_age = min(max(age, 12.5), 18.5)
    g0 = math.floor(lo_age - 0.5) + 1  # U-number of the group below
    g0 = min(max(g0, 13), 18)
    frac = min(max(lo_age - (g0 - 0.5), 0.0), 1.0)
    n0, n1 = norms.norm(test, f"U{g0}"), norms.norm(test, f"U{g0 + 1}")
    mean = n0.mean + frac * (n1.mean - n0.mean)
    sd = n0.sd + frac * (n1.sd - n0.sd)
    return mean - z * sd if n0.lower_is_better else mean + z * sd


# --------------------------------------------------------------------------- season


@dataclass
class SeasonResult:
    policy: str
    seed: int
    variant: str
    players: list[dict] = field(default_factory=list)
    daily: list[dict] = field(default_factory=list)
    sessions: list[dict] = field(default_factory=list)
    checkins: list[dict] = field(default_factory=list)
    anthropometrics: list[dict] = field(default_factory=list)
    tests: list[dict] = field(default_factory=list)
    injuries: list[dict] = field(default_factory=list)

    TABLES = ("players", "daily", "sessions", "checkins", "anthropometrics", "tests", "injuries")

    def to_csv(self, out_dir: Path) -> list[Path]:
        import csv

        out_dir.mkdir(parents=True, exist_ok=True)
        written = []
        for name in self.TABLES:
            rows = getattr(self, name)
            path = out_dir / f"{name}.csv"
            with path.open("w", newline="", encoding="utf-8") as f:
                if rows:
                    w = csv.DictWriter(f, fieldnames=list(rows[0]))
                    w.writeheader()
                    w.writerows(rows)
            written.append(path)
        return written


class SeasonSimulator:
    def __init__(self, cfg: dict | None = None, policy: Policy | None = None, injury_variant: str | None = None):
        self.cfg = cfg or load_config()
        load = self.cfg["load"]
        self.policy = policy or BaselinePolicy(
            load["session_rpe_mean"], load["session_rpe_sd"], tuple(load["session_minutes"])
        )
        self.variant = injury_variant or self.cfg["injury"]["variant"]
        if self.variant not in ("load", "readiness", "random"):
            raise ValueError(f"unknown injury variant {self.variant!r}")
        self.norms = NormTable.load()
        self.readiness_cfg = ReadinessConfig.load()
        seed = self.cfg["seed"]
        # Independent streams: changing the policy never changes the world.
        # World draws are keyed by (player, day, purpose), so a policy that trains
        # differently still gets the same sleep noise, injury dice, etc.
        self.rng_fixtures = np.random.default_rng([seed, 1])
        self.rng_policy = np.random.default_rng([seed, 2])

    _STREAMS: ClassVar[dict[str, int]] = {"morning": 0, "train": 1, "injury": 2, "test": 3, "measure": 4}

    def _rng(self, ps: PlayerState, d: date, purpose: str) -> np.random.Generator:
        return np.random.default_rng([self.cfg["seed"], 10, ps.profile.index, d.toordinal(), self._STREAMS[purpose]])

    # ------------------------------------------------------------------ setup

    def _make_players(self) -> list[PlayerState]:
        c, rng = self.cfg, np.random.default_rng([self.cfg["seed"], 3])
        g = c["growth"]
        players = []
        for i in range(c["n_players"]):
            age = float(rng.uniform(*c["age_range"]))
            p = PlayerProfile(
                index=i,
                player_id=f"P{i + 1:02d}",
                name=f"Player {i + 1:02d}",
                age_at_start=age,
                phv_age=float(rng.normal(g["phv_age_mean"], g["phv_age_sd"])),
                adult_height=float(rng.normal(g["adult_height_mean"], g["adult_height_sd"])),
                mirwald_bias=float(rng.normal(0, 0.4)),
                bmi_offset=float(rng.normal(0, 1.2)),
                sleep_mean=float(rng.normal(c["sleep"]["mean"], c["sleep"]["person_sd"])),
                ln_rmssd_base=float(rng.normal(c["hrv"]["ln_rmssd_mean"], c["hrv"]["ln_rmssd_person_sd"])),
            )
            general = rng.normal()
            # Early maturers look better against age-group norms (the bias bio-banding removes).
            maturity_edge = -0.4 * (p.phv_age - g["phv_age_mean"])
            ability = {t: 0.6 * general + 0.8 * rng.normal() + maturity_edge for t in TESTS}
            ability["sprint_30m"] = 0.7 * ability["sprint_10m"] + 0.3 * ability["sprint_30m"]
            players.append(PlayerState(profile=p, age=age, ability_z=ability))
        return players

    def _fixtures(self) -> list[WeekContext]:
        c, rng = self.cfg, self.rng_fixtures
        s, t = c["schedule"], c["tests"]
        start = c["start_date"]
        start = start if isinstance(start, date) else date.fromisoformat(str(start))
        weeks = []
        for w in range(c["weeks"]):
            dates = tuple(start + timedelta(days=7 * w + d) for d in range(7))
            match_days = {s["match_weekday"]}
            evening = set()
            if rng.random() < s["second_match_prob"]:
                match_days.add(s["second_match_weekday"])
                evening.add(s["second_match_weekday"])
            exams = set(s["exam_weekdays"]) if w in s["exam_weeks"] else set()
            test_day = t["weekday"] if w % t["every_weeks"] == 0 else None
            weeks.append(WeekContext(w, dates, frozenset(match_days), frozenset(evening), frozenset(exams), test_day))
        return weeks

    # ------------------------------------------------------------------ run

    def run(self) -> SeasonResult:
        c = self.cfg
        res = SeasonResult(policy=self.policy.name, seed=c["seed"], variant=self.variant)
        players = self._make_players()
        for ps in players:
            p = ps.profile
            res.players.append(
                {
                    "player_id": p.player_id,
                    "name": p.name,
                    "age_at_start": round(p.age_at_start, 2),
                    "phv_age": round(p.phv_age, 2),
                    "adult_height": round(p.adult_height, 1),
                }
            )
        prev_evening_match: dict[str, bool] = {ps.profile.player_id: False for ps in players}

        for ctx in self._fixtures():
            plans = {ps.profile.player_id: self.policy.plan_week(ps, ctx, self.rng_policy) for ps in players}
            exam_week = bool(ctx.exam_days)
            for wd, d in enumerate(ctx.dates):
                for ps in players:
                    pid = ps.profile.player_id
                    self._morning(ps, d, exam_week, prev_evening_match[pid], res, ctx)
                    load, evening = self._train(ps, d, wd, ctx, plans[pid], res)
                    prev_evening_match[pid] = evening
                    if ctx.test_day == wd and not ps.is_injured(d):
                        self._test_day(ps, d, res)
                    if (d - ctx.dates[0]).days == 0 and ctx.week * 7 % c["growth"]["measure_every_days"] == 0:
                        self._measure(ps, d, res)
                    res.daily.append(
                        {
                            "player_id": pid,
                            "date": d.isoformat(),
                            "week": ctx.week,
                            "load": round(load, 1),
                            "acwr": round(ps.acwr, 3),
                            "readiness": None if ps.readiness_scores[-1] is None else round(ps.readiness_scores[-1], 1),
                            "true_maturity_offset": round(ps.true_maturity_offset, 2),
                            "in_phv_window": ps.in_phv_window,
                            "injured": ps.is_injured(d),
                            "exam_day": wd in ctx.exam_days,
                        }
                    )
                    ps.age += 1 / 365.25
        return res

    # ------------------------------------------------------------------ daily steps

    def _morning(self, ps: PlayerState, d: date, exam_week: bool, after_evening_match: bool, res, ctx) -> None:
        c, rng = self.cfg, self._rng(ps, d, "morning")
        sc, hc, wc = c["sleep"], c["hrv"], c["wellness"]

        sleep = rng.normal(ps.profile.sleep_mean, sc["sd"])
        if exam_week:
            sleep -= rng.uniform(*sc["exam_drop"])
        if after_evening_match:
            sleep -= rng.uniform(*sc["evening_match_drop"])
        sleep = float(np.clip(sleep, 3.0, 11.0))

        ln = (
            ps.profile.ln_rmssd_base
            - hc["fatigue_coef"] * ps.fatigue
            - hc["sleep_coef"] * max(0.0, 7.5 - sleep)
            + rng.normal(0, hc["daily_noise_sd"])
        )
        baseline = list(ps.ln_rmssd[-7:])
        ps.sleep_hours.append(sleep)
        ps.ln_rmssd.append(ln)

        completed = rng.random() < wc["checkin_compliance"]
        hooper = None
        mood_red = False
        pain = False
        if completed:

            def item(x: float) -> int:
                return int(np.clip(round(x + rng.normal(0, 0.7)), 1, 7))

            hooper = (
                item(2.5 + 0.9 * max(0.0, 7.5 - sleep)),
                item(1.8 + 1.5 * ps.fatigue),
                item(2.0 + (2.0 if exam_week else 0.0)),
                item(1.8 + 1.5 * ps.fatigue),
            )
            p_red = wc["red_mood_daily_prob"] * (wc["red_mood_exam_multiplier"] if exam_week else 1.0)
            mood_red = bool(rng.random() < p_red)
            pain = ps.pain_pending
            ps.pain_pending = False
            ps.missed_in_row = 0
        else:
            ps.missed_in_row += 1

        r = readiness(
            hooper=hooper,
            sleep_hours=sleep,
            ln_rmssd=ln,
            hrv_baseline=baseline,
            config=self.readiness_cfg,
        )
        ps.readiness_scores.append(None if r is None else r.score)
        res.checkins.append(
            {
                "player_id": ps.profile.player_id,
                "date": d.isoformat(),
                "completed": completed,
                "sleep_quality": hooper[0] if hooper else None,
                "fatigue": hooper[1] if hooper else None,
                "stress": hooper[2] if hooper else None,
                "soreness": hooper[3] if hooper else None,
                "mood_red": mood_red,
                "pain_reported": pain,
                "sleep_hours": round(sleep, 2),
                "ln_rmssd": round(ln, 3),
                "missed_in_row": ps.missed_in_row,
            }
        )

    def _train(self, ps: PlayerState, d: date, wd: int, ctx: WeekContext, plan, res) -> tuple[float, bool]:
        c, rng = self.cfg, self._rng(ps, d, "train")
        lc = c["load"]
        kind, planned_rpe, rpe, minutes = SessionType.REST, 0.0, 0.0, 0.0
        evening = False
        if not ps.is_injured(d):
            if wd in ctx.match_days:
                kind = SessionType.MATCH
                planned_rpe = rpe = float(np.clip(rng.normal(lc["match_rpe_mean"], lc["match_rpe_sd"]), 1, 10))
                minutes = float(rng.integers(lc["match_minutes"][0], lc["match_minutes"][1] + 1))
                evening = wd in ctx.evening_match_days
            elif wd in plan and plan[wd].kind != SessionType.REST:
                s = plan[wd]
                kind, planned_rpe, minutes = s.kind, s.rpe, s.minutes
                rpe = float(np.clip(s.rpe + rng.normal(0, lc["execution_rpe_noise_sd"]), 1, 10))
        load = session_load(rpe, minutes) if kind != SessionType.REST else 0.0

        la, lch = ewma_lambda(7), ewma_lambda(28)
        ps.acute = la * load + (1 - la) * ps.acute
        ps.chronic = lch * load + (1 - lch) * ps.chronic
        ps.fatigue = c["hrv"]["fatigue_decay"] * ps.fatigue + load / 1000
        ps.daily_loads.append(load)

        if kind != SessionType.REST:
            res.sessions.append(
                {
                    "player_id": ps.profile.player_id,
                    "date": d.isoformat(),
                    "kind": kind.value,
                    "planned_rpe": round(planned_rpe, 1),
                    "rpe": round(rpe, 1),
                    "minutes": minutes,
                    "load": round(load, 1),
                    "exam_day": wd in ctx.exam_days,
                }
            )
            self._train_effect(ps, kind)
            self._maybe_injure(ps, d, res)
        elif ps.is_injured(d):
            for t in TESTS:
                ps.ability_z[t] -= c["tests"]["detraining_z_per_injured_day"]
        return load, evening

    def _train_effect(self, ps: PlayerState, kind: SessionType) -> None:
        for test, gain in self.cfg["tests"]["training_effect_z"].get(kind.value, {}).items():
            ps.ability_z[test] += gain

    def _maybe_injure(self, ps: PlayerState, d: date, res) -> None:
        ic, rng = self.cfg["injury"], self._rng(ps, d, "injury")
        x = _logit(ic["base_daily_prob"])
        phv = 1.0 if ps.in_phv_window else 0.0
        r = ps.readiness_scores[-1]
        if self.variant == "load":
            x += ic["acwr_coef"] * max(0.0, ps.acwr - 1.0) + ic["phv_coef"] * phv
        elif self.variant == "readiness":
            x += ic["readiness_coef"] * max(0.0, 70.0 - (r if r is not None else 70.0)) + ic["phv_coef"] * phv
        if rng.random() < _sigmoid(x):
            out = int(rng.integers(ic["out_days"][0], ic["out_days"][1] + 1))
            ps.injured_until = d + timedelta(days=out + 1)
            ps.pain_pending = True
            res.injuries.append(
                {
                    "player_id": ps.profile.player_id,
                    "date": d.isoformat(),
                    "out_days": out,
                    "acwr": round(ps.acwr, 3),
                    "in_phv_window": ps.in_phv_window,
                    "readiness": None if r is None else round(r, 1),
                }
            )

    def _test_day(self, ps: PlayerState, d: date, res) -> None:
        noise, rng = self.cfg["tests"]["noise_sd_z"], self._rng(ps, d, "test")
        for t in TESTS:
            z = ps.ability_z[t] + rng.normal(0, noise)
            value = _norm_value(self.norms, t, ps.age, z)
            res.tests.append(
                {"player_id": ps.profile.player_id, "date": d.isoformat(), "test": t, "value": round(value, 2)}
            )

    def _measure(self, ps: PlayerState, d: date, res) -> None:
        rng = self._rng(ps, d, "measure")
        h = height_at(ps.profile, ps.age, self.cfg)
        w = weight_at(ps.profile, ps.age, h)
        # Mirwald is only valid within about +/-3 years of PHV and attenuates beyond it.
        target = float(np.clip(ps.true_maturity_offset, -MIRWALD_VALID_YEARS, MIRWALD_VALID_YEARS))
        target += ps.profile.mirwald_bias
        sh = sitting_height_for_offset(ps.age, h, w, target)
        res.anthropometrics.append(
            {
                "player_id": ps.profile.player_id,
                "date": d.isoformat(),
                "age": round(ps.age, 3),
                "height_cm": round(h + rng.normal(0, 0.3), 1),
                "sitting_height_cm": round(sh + rng.normal(0, 0.3), 1),
                "weight_kg": round(w + rng.normal(0, 0.3), 1),
            }
        )
