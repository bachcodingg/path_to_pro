import random
from dataclasses import replace

import pytest

from analytics.calibration import MIN_SAMPLES, RatedDay, agreement, fit_weights, weighted_kappa
from analytics.readiness import Band, ReadinessConfig, band_for, combine

BUFFERED = replace(ReadinessConfig(), hysteresis_up=8.0, hysteresis_down=0.0)


# --------------------------------------------------------------------------- colour buffer


def test_no_previous_band_means_plain_thresholds():
    assert band_for(70, BUFFERED) == Band.GREEN
    assert band_for(69.9, BUFFERED) == Band.AMBER


def test_better_colour_needs_the_margin():
    assert band_for(72, BUFFERED, Band.AMBER) == Band.AMBER  # just past 70: stay amber
    assert band_for(78, BUFFERED, Band.AMBER) == Band.GREEN  # clearly past: green
    assert band_for(55, BUFFERED, Band.RED) == Band.RED
    assert band_for(58, BUFFERED, Band.RED) == Band.AMBER


def test_warnings_are_never_delayed():
    # down margin is 0: a worse colour applies as soon as the score crosses the boundary
    assert band_for(69.9, BUFFERED, Band.GREEN) == Band.AMBER
    assert band_for(49.9, BUFFERED, Band.GREEN) == Band.RED
    assert band_for(49.9, BUFFERED, Band.AMBER) == Band.RED


def test_symmetric_buffer_option():
    cfg = replace(BUFFERED, hysteresis_down=3.0)
    assert band_for(68, cfg, Band.GREEN) == Band.GREEN
    assert band_for(66, cfg, Band.GREEN) == Band.AMBER


def test_buffer_reduces_flicker():
    rng = random.Random(3)
    scores = [70 + rng.gauss(0, 4) for _ in range(300)]
    plain, buffered, prev = [], [], None
    for s in scores:
        plain.append(band_for(s, BUFFERED))
        prev = band_for(s, BUFFERED, prev)
        buffered.append(prev)

    def changes(b):
        return sum(x != y for x, y in zip(b, b[1:]))

    assert changes(buffered) < changes(plain) / 2


def test_config_file_buffer_is_safety_first():
    cfg = ReadinessConfig.load()
    assert cfg.hysteresis_down == 0
    assert cfg.hysteresis_up > 0


# --------------------------------------------------------------------------- calibration


def _synthetic(true_weights, n=600, noise=4.0, seed=1):
    rng = random.Random(seed)
    cfg = ReadinessConfig().with_weights(true_weights)
    out = []
    for i in range(n):
        comp = {"hrv": rng.uniform(0, 100), "hooper": rng.uniform(20, 100), "sleep": rng.uniform(50, 100)}
        score = combine(comp, cfg).score + rng.gauss(0, noise)
        out.append(RatedDay(f"P{i % 20}", comp, band_for(score, cfg)))
    return out


def test_kappa_bounds():
    assert weighted_kappa([0, 1, 2, 2], [0, 1, 2, 2]) == pytest.approx(1.0)
    assert weighted_kappa([0, 0, 2, 2], [2, 2, 0, 0]) < 0


def test_recovers_the_weights_staff_actually_use():
    truth = {"hrv": 0.2, "hooper": 0.6, "sleep": 0.2}
    cal = fit_weights(_synthetic(truth), ReadinessConfig(), cv=False)
    assert cal.after.kappa > cal.before.kappa
    assert all(abs(cal.weights[k] - truth[k]) <= 0.1 for k in truth)


def test_never_lowers_red_recall():
    samples = _synthetic({"hrv": 0.15, "hooper": 0.7, "sleep": 0.15}, seed=5)
    base = ReadinessConfig()
    cal = fit_weights(samples, base, cv=False)
    assert cal.after.red_recall >= agreement(samples, base).red_recall


def test_weights_stay_valid():
    cal = fit_weights(_synthetic({"hrv": 0.1, "hooper": 0.8, "sleep": 0.1}), ReadinessConfig(), cv=False)
    assert sum(cal.weights.values()) == pytest.approx(1.0)
    assert min(cal.weights.values()) >= 0.1 - 1e-9


def test_too_few_ratings_keeps_current_weights():
    base = ReadinessConfig()
    cal = fit_weights(_synthetic({"hrv": 0.2, "hooper": 0.6, "sleep": 0.2}, n=MIN_SAMPLES - 1), base)
    assert not cal.enough_data
    assert cal.weights == dict(base.weights)


def test_cross_validation_reports_held_out_agreement():
    cal = fit_weights(_synthetic({"hrv": 0.2, "hooper": 0.6, "sleep": 0.2}), ReadinessConfig())
    assert cal.cv_before is not None and cal.cv_after is not None
    assert cal.cv_after > cal.cv_before
