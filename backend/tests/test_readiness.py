import math

import pytest

from analytics.readiness import (
    Band,
    ReadinessConfig,
    band_for,
    combine,
    hooper_score,
    hrv_score,
    hrv_z,
    readiness,
    sleep_score,
)


def test_plan_worked_example_is_red():
    # HRV z = -1.0 -> 25, Hooper 16 -> 50, sleep 6.5 h -> 72.2
    r = combine({"hrv": hrv_score(-1.0), "hooper": hooper_score(4, 4, 4, 4), "sleep": sleep_score(6.5)})
    assert hrv_score(-1.0) == 25
    assert hooper_score(4, 4, 4, 4) == 50
    assert sleep_score(6.5) == pytest.approx(72.22, abs=0.01)
    assert r.score == pytest.approx(10 + 17.5 + 18.06, abs=0.01)
    assert r.band == Band.RED


def test_missing_hrv_rescales_weights():
    r = combine({"hrv": None, "hooper": 80.0, "sleep": 100.0})
    assert r.weights_used["hooper"] == pytest.approx(0.583, abs=1e-3)
    assert r.weights_used["sleep"] == pytest.approx(0.417, abs=1e-3)
    assert "hrv" not in r.weights_used


def test_no_inputs_gives_none():
    assert combine({"hrv": None, "hooper": None, "sleep": None}) is None


def test_hrv_needs_seven_day_baseline():
    assert hrv_z(4.0, [4.1] * 6) is None
    assert hrv_z(4.1, [4.0, 4.2] * 4) is not None


def test_hrv_uses_last_seven_days_only():
    baseline = [10.0] * 5 + [4.0, 4.2, 4.0, 4.2, 4.0, 4.2, 4.0]
    assert hrv_z(4.1, baseline) == pytest.approx(hrv_z(4.1, baseline[-7:]))


def test_hrv_score_clamped():
    assert hrv_score(-5) == 0
    assert hrv_score(5) == 100


def test_hooper_bounds():
    assert hooper_score(1, 1, 1, 1) == 100
    assert hooper_score(7, 7, 7, 7) == 0
    with pytest.raises(ValueError):
        hooper_score(0, 3, 3, 3)


def test_sleep_caps_at_target():
    assert sleep_score(10) == 100


@pytest.mark.parametrize("score,band", [(70, Band.GREEN), (69.9, Band.AMBER), (50, Band.AMBER), (49.9, Band.RED)])
def test_band_edges(score, band):
    assert band_for(score, ReadinessConfig()) == band


def test_config_file_matches_defaults():
    loaded = ReadinessConfig.load()
    default = ReadinessConfig()
    assert dict(loaded.weights) == dict(default.weights)
    assert math.isclose(sum(loaded.weights.values()), 1.0)


def test_wrapper_without_hrv_baseline_drops_hrv():
    r = readiness(hooper=(2, 2, 2, 2), sleep_hours=9, ln_rmssd=4.2, hrv_baseline=[4.2] * 3)
    assert "hrv" not in r.components
    assert r.band == Band.GREEN
