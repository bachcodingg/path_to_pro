"""Calibrate the readiness weights against staff ratings.

Staff (coach or physio) rate how ready a player looks on a day: green, amber or
red. Each rating is paired with that day's component scores (HRV, Hooper, sleep).
`fit_weights` searches the weight simplex for the weights whose bands agree best
with the staff, measured by quadratic-weighted Cohen's kappa (ordinal agreement
corrected for chance). Every weight stays >= MIN_WEIGHT so no input is switched
off, and ties go to the weights closest to the current ones.

Safety constraint: kappa rewards the common green/amber days, so an unconstrained
fit can trade away red days. Candidate weights must keep red recall (share of
staff-red days the score also calls red) at least as high as the current weights.

`cross_validate` refits on all players but one group at a time and scores the
held-out group, so the reported agreement is not flattered by fitting and testing
on the same players. A club applies new weights only after a coach reviews them.
"""

from __future__ import annotations

import itertools
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from analytics.readiness import Band, ReadinessConfig, band_for, combine

KEYS = ("hrv", "hooper", "sleep")
STEP = 0.05
MIN_WEIGHT = 0.10
MIN_SAMPLES = 60
MIN_CV_GAIN = 0.01  # held-out kappa must improve by more than this (and twice its noise)
_RANK = {Band.RED: 0, Band.AMBER: 1, Band.GREEN: 2}


@dataclass(frozen=True)
class RatedDay:
    player_id: str
    components: Mapping[str, float | None]
    staff_band: Band


@dataclass(frozen=True)
class Agreement:
    n: int
    accuracy: float
    kappa: float  # quadratic-weighted Cohen's kappa
    red_recall: float | None  # share of staff-red days the score also calls red


@dataclass(frozen=True)
class Calibration:
    weights: dict[str, float]
    before: Agreement
    after: Agreement
    cv_before: float | None = None  # held-out kappa, current weights
    cv_after: float | None = None  # held-out kappa, refitted weights
    enough_data: bool = True
    cv_gain_folds: tuple[float, ...] = ()  # per held-out group: kappa(refitted) - kappa(current)

    @property
    def cv_noise(self) -> float | None:
        """Standard error of the held-out gain across groups (fold-to-fold spread)."""
        g = self.cv_gain_folds
        if len(g) < 2:
            return None
        mean = sum(g) / len(g)
        sd = (sum((x - mean) ** 2 for x in g) / (len(g) - 1)) ** 0.5
        return sd / len(g) ** 0.5

    @property
    def recommended(self) -> bool:
        """Suggest applying only if the held-out gain is clearly above the noise."""
        if not self.enough_data or self.cv_before is None or self.cv_after is None:
            return False
        if self.after.red_recall is not None and self.before.red_recall is not None:
            if self.after.red_recall < self.before.red_recall:
                return False
        noise = self.cv_noise or 0.0
        return self.cv_after - self.cv_before > max(MIN_CV_GAIN, 2 * noise)


def weighted_kappa(a: Sequence[int], b: Sequence[int], k: int = 3) -> float:
    n = len(a)
    if n == 0:
        return 0.0
    obs = [[0.0] * k for _ in range(k)]
    for x, y in zip(a, b):
        obs[x][y] += 1
    ra = [sum(obs[i]) for i in range(k)]
    rb = [sum(obs[i][j] for i in range(k)) for j in range(k)]
    num = den = 0.0
    for i in range(k):
        for j in range(k):
            w = (i - j) ** 2 / (k - 1) ** 2
            num += w * obs[i][j]
            den += w * ra[i] * rb[j] / n
    return 1.0 if den == 0 else 1 - num / den


def agreement(samples: Sequence[RatedDay], config: ReadinessConfig) -> Agreement:
    pred, true = [], []
    for s in samples:
        r = combine(s.components, config)
        if r is None:
            continue
        pred.append(_RANK[band_for(r.score, config)])
        true.append(_RANK[s.staff_band])
    if not pred:
        return Agreement(0, 0.0, 0.0, None)
    reds = [p for p, t in zip(pred, true) if t == 0]
    return Agreement(
        n=len(pred),
        accuracy=sum(p == t for p, t in zip(pred, true)) / len(pred),
        kappa=weighted_kappa(true, pred),
        red_recall=None if not reds else sum(p == 0 for p in reds) / len(reds),
    )


def _grid(step: float = STEP, floor: float = MIN_WEIGHT) -> list[dict[str, float]]:
    units, lo = round(1 / step), round(floor / step)
    out = []
    for a, b in itertools.product(range(lo, units + 1), repeat=2):
        c = units - a - b
        if c >= lo:
            out.append({"hrv": a * step, "hooper": b * step, "sleep": round(c * step, 10)})
    return out


def _fit(samples: Sequence[RatedDay], base: ReadinessConfig) -> tuple[dict[str, float], Agreement]:
    current = agreement(samples, base)
    floor = current.red_recall or 0.0
    best, best_key = (dict(base.weights), current), (round(current.kappa, 4), 0.0)
    for w in _grid():
        ag = agreement(samples, base.with_weights(w))
        if ag.red_recall is not None and ag.red_recall < floor:
            continue  # never detect fewer red days than today
        dist = sum((w[k] - base.weights[k]) ** 2 for k in KEYS)
        key = (round(ag.kappa, 4), -dist)  # best kappa, then closest to current weights
        if best_key is None or key > best_key:
            best, best_key = (w, ag), key
    return best


def cross_validate(samples: Sequence[RatedDay], base: ReadinessConfig, folds: int = 5, seed: int = 7, detail: bool = False):
    """Held-out kappa (current weights, refitted weights), grouping folds by player.

    With `detail`, also returns each held-out group's gain (refitted minus current kappa).
    """
    players = sorted({s.player_id for s in samples})
    if len(players) < folds:
        return (None, None, ()) if detail else (None, None)
    random.Random(seed).shuffle(players)
    groups = [set(players[i::folds]) for i in range(folds)]
    true, cur, fit, gains = [], [], [], []
    for g in groups:
        train = [s for s in samples if s.player_id not in g]
        test = [s for s in samples if s.player_id in g]
        w, _ = _fit(train, base)
        f_true, f_cur, f_fit = [], [], []
        for s in test:
            r0 = combine(s.components, base)
            if r0 is None:
                continue
            cfg = base.with_weights(w)
            r1 = combine(s.components, cfg)
            f_true.append(_RANK[s.staff_band])
            f_cur.append(_RANK[band_for(r0.score, base)])
            f_fit.append(_RANK[band_for(r1.score, cfg)] if r1 is not None else f_cur[-1])
        true += f_true
        cur += f_cur
        fit += f_fit
        if f_true:
            gains.append(weighted_kappa(f_true, f_fit) - weighted_kappa(f_true, f_cur))
    out = (weighted_kappa(true, cur), weighted_kappa(true, fit))
    return (*out, tuple(gains)) if detail else out


def fit_weights(samples: Sequence[RatedDay], base: ReadinessConfig | None = None, cv: bool = True) -> Calibration:
    base = base or ReadinessConfig.load()
    before = agreement(samples, base)
    if len(samples) < MIN_SAMPLES:
        return Calibration(dict(base.weights), before, before, enough_data=False)
    w, after = _fit(samples, base)
    cv_before, cv_after, gains = cross_validate(samples, base, detail=True) if cv else (None, None, ())
    return Calibration(w, before, after, cv_before, cv_after, cv_gain_folds=tuple(gains))
