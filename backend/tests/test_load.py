import pytest

from analytics.load import ewma_acwr, ewma_acwr_series, monotony, session_load, strain


def test_session_load_plan_example():
    assert session_load(7, 90) == 630


@pytest.mark.parametrize("rpe,minutes", [(11, 60), (-1, 60), (5, -10)])
def test_session_load_rejects_bad_input(rpe, minutes):
    with pytest.raises(ValueError):
        session_load(rpe, minutes)


def test_acwr_is_one_for_constant_load():
    assert ewma_acwr([400.0] * 40) == pytest.approx(1.0)


def test_acwr_needs_28_days():
    assert ewma_acwr([400.0] * 27) is None
    assert ewma_acwr([400.0] * 28) is not None


def test_acwr_flags_a_spike():
    loads = [300.0] * 35 + [900.0] * 7
    assert ewma_acwr(loads) > 1.5


def test_acwr_falls_after_deload():
    loads = [400.0] * 35 + [100.0] * 7
    assert ewma_acwr(loads) < 0.8


def test_series_with_initial_value():
    series = ewma_acwr_series([300.0, 300.0], initial=300.0)
    assert len(series) == 2
    assert series[-1].ratio == pytest.approx(1.0)


def test_monotony_and_strain():
    week = [600, 400, 500, 0, 700, 800, 0]
    m = monotony(week)
    assert m == pytest.approx(428.571 / 296.236, rel=1e-4)
    assert strain(week) == pytest.approx(3000 * m)


def test_monotony_undefined_for_identical_days():
    assert monotony([300] * 7) is None
    assert strain([300] * 7) is None


def test_monotony_needs_seven_days():
    with pytest.raises(ValueError):
        monotony([1, 2, 3])
