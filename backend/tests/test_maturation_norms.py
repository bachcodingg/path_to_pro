import pytest

from analytics.maturation import MaturityStatus, Sex, growth_status, maturity_offset
from analytics.norms import Norm, NormTable, age_group, percentile
from simulator.season import sitting_height_for_offset


def test_mirwald_male_hand_calculation():
    # leg 80 cm; terms: 1.84144 - 1.86256 + 8.58704 + 0.76400 - 9.236
    assert maturity_offset(14, 165, 85, 55) == pytest.approx(0.0939, abs=1e-3)


def test_mirwald_female_runs():
    assert -4 < maturity_offset(12, 150, 78, 40, Sex.FEMALE) < 4


def test_mirwald_rejects_impossible_sitting_height():
    with pytest.raises(ValueError):
        maturity_offset(14, 165, 170, 55)


def test_growth_status_window():
    s = growth_status(14, 165, 85, 55)
    assert s.status == MaturityStatus.CIRCA_PHV
    assert s.in_phv_window
    assert s.age_at_phv == pytest.approx(14 - s.maturity_offset)


@pytest.mark.parametrize(
    "age,height,weight,target",
    [(12.5, 150, 40, -1.5), (14.0, 165, 55, -0.3), (14.0, 165, 55, 0.0), (17.0, 178, 68, 2.5)],
)
def test_sitting_height_inverse_round_trips(age, height, weight, target):
    sh = sitting_height_for_offset(age, height, weight, target)
    assert maturity_offset(age, height, sh, weight) == pytest.approx(target, abs=1e-6)


def test_sitting_height_clamped_to_plausible_ratio():
    sh = sitting_height_for_offset(14.0, 165.0, 55.0, -4.0)
    assert sh == pytest.approx(0.47 * 165)


def test_plan_sprint_example_is_72nd_percentile():
    norms = NormTable.load()
    assert norms.age_percentile("sprint_30m", 4.35, 16.4) == pytest.approx(72, abs=1)


def test_percentile_direction():
    fast = Norm(mean=4.5, sd=0.2, lower_is_better=True)
    high = Norm(mean=30, sd=4, lower_is_better=False)
    assert percentile(4.3, fast) > 50
    assert percentile(34, high) > 50
    assert percentile(4.5, fast) == pytest.approx(50)


def test_age_group():
    assert age_group(16.4) == "U17"
    assert age_group(13.0) == "U14"


def test_bio_banded_norms_exist_for_every_test():
    norms = NormTable.load()
    for t in norms.tests():
        for s in MaturityStatus:
            norms.bio_banded_percentile(t, norms.norm(t, s.value).mean, s)
