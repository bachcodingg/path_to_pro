import pytest

from agents.coordinator import ActionKind, Decision, Proposal, decide
from analytics.flags import FlagKind, PlayerSnapshot, evaluate
from analytics.readiness import Band


def kinds(snapshot):
    return {f.kind for f in evaluate(snapshot)}


def test_plan_example_loop_emits_three_flags_plus_growth():
    # Thursday 23:00: sleep < 6 h x 3, HRV 1 SD under baseline, ACWR spike after a cup match
    s = PlayerSnapshot(
        daily_loads=[300.0] * 35 + [900.0, 0.0, 1000.0, 800.0, 0.0, 1200.0, 1100.0],
        recent_sleep_hours=[7.5, 5.5, 5.8, 5.6],
        hrv_z=-1.0,
        in_phv_window=True,
        maturity_offset=-0.3,
    )
    assert kinds(s) == {FlagKind.LOAD_SPIKE, FlagKind.SHORT_SLEEP, FlagKind.LOW_HRV, FlagKind.PHV_WINDOW}


def test_quiet_player_has_no_flags():
    s = PlayerSnapshot(
        daily_loads=[500, 400, 0, 600, 300, 700, 0] * 5,
        recent_sleep_hours=[8, 8.5, 7.9],
        hrv_z=0.2,
        readiness_band=Band.GREEN,
    )
    assert evaluate(s) == []


def test_two_short_nights_are_not_enough():
    assert FlagKind.SHORT_SLEEP not in kinds(PlayerSnapshot(recent_sleep_hours=[8, 5, 5]))


def test_missed_checkins_need_red_readiness():
    assert FlagKind.MISSED_CHECKINS not in kinds(PlayerSnapshot(missed_checkins_in_row=2, readiness_band=Band.AMBER))
    assert FlagKind.MISSED_CHECKINS in kinds(PlayerSnapshot(missed_checkins_in_row=2, readiness_band=Band.RED))


@pytest.mark.parametrize(
    "proposal,expected",
    [
        (Proposal("P01", ActionKind.REMINDER), Decision.AUTO_APPLY),
        (Proposal("P01", ActionKind.SLEEP_TASK), Decision.AUTO_APPLY),
        (Proposal("P01", ActionKind.DRILL_SUGGESTION), Decision.AUTO_APPLY),
        (Proposal("P01", ActionKind.INTENSITY_CHANGE, rpe_delta=-1), Decision.AUTO_APPLY_NOTIFY_COACH),
        (Proposal("P01", ActionKind.INTENSITY_CHANGE, rpe_delta=2), Decision.COACH_APPROVAL),
        (Proposal("P01", ActionKind.SESSION_SWAP), Decision.COACH_APPROVAL),
        (Proposal("P01", ActionKind.LOAD_CUT, load_cut_pct=25), Decision.COACH_APPROVAL),
        (Proposal("P01", ActionKind.LOAD_CUT, load_cut_pct=10), Decision.COACH_APPROVAL),
        (Proposal("P01", ActionKind.NEW_GOAL), Decision.COACH_APPROVAL),
    ],
)
def test_autonomy_policy_table(proposal, expected):
    assert decide(proposal).decision == expected


@pytest.mark.parametrize(
    "snapshot",
    [
        PlayerSnapshot(pain_reported=True),
        PlayerSnapshot(mood_red=True),
        PlayerSnapshot(missed_checkins_in_row=2, readiness_band=Band.RED),
    ],
)
def test_safety_flags_always_escalate(snapshot):
    flags = evaluate(snapshot)
    # Even an otherwise auto-applied reminder must not go ahead.
    assert decide(Proposal("P01", ActionKind.REMINDER), flags).decision == Decision.ESCALATE
