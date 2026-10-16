import itertools
import random
from datetime import date

import pytest
from pydantic import ValidationError

from domain.enums import SessionType
from planner.model import TIME_LIMIT_S, hard_violations, plan_week, safe_template, weekly_cap
from planner.schema import ConstraintSet, MaxRpeOnDay, MinSessions, PlannerInput, RestOnDay

MON = date(2026, 10, 19)


def inp(**kw):
    return PlannerInput(player_id="P01", start=MON, **kw)


def test_plan_worked_example():
    """Match Saturday, exam Wednesday, ACWR 1.6, goal: improve 10 m sprint."""
    i = inp(match_days=[5], exam_days=[2], acwr=1.6, in_phv_window=True)
    cs = ConstraintSet(load_factor=0.9, soft=[MinSessions(session="speed", count=2, weight=6, why="sprint goal")])
    r = plan_week(i, cs)
    kinds = [d.kind for d in r.days]
    assert hard_violations(r, i) == []
    assert kinds[5] == SessionType.MATCH
    assert kinds[2] == SessionType.REST  # exam
    assert r.days[4].rpe <= 4  # MD-1
    assert kinds.count(SessionType.SPEED) == 2
    assert all(d.rpe <= 6 for d in r.days if d.kind == SessionType.SPEED)  # PHV
    assert r.weekly_load <= r.weekly_load_cap
    assert r.status == "optimal"


def test_cap_only_when_acwr_high():
    assert weekly_cap(inp(acwr=1.4)) is None
    assert weekly_cap(inp(acwr=1.6, chronic_daily_load=300)) == 2100


def test_same_input_same_week():
    i = inp(match_days=[2, 5], acwr=1.2)
    sigs = {plan_week(i).signature() for _ in range(5)}
    assert len(sigs) == 1


def test_infeasible_hard_rules_fall_back_to_template():
    # Cap below even a 30-minute match: nothing feasible, so the safe template is used.
    i = inp(match_days=[5], acwr=1.8, chronic_daily_load=30)
    r = plan_week(i)
    assert r.status == "template"
    assert hard_violations(r, i) == []


def test_return_to_play_limits_match_minutes():
    # Back from injury: chronic load has dropped, so a full match would be a spike.
    i = inp(match_days=[5], acwr=1.8, chronic_daily_load=90)  # cap 630 < 720 AU full match
    r = plan_week(i)
    assert r.status == "optimal"
    assert r.days[5].kind == SessionType.MATCH
    assert r.days[5].minutes < 90
    assert r.weekly_load <= r.weekly_load_cap


def test_full_match_in_a_normal_week():
    assert plan_week(inp(match_days=[5])).days[5].minutes == 90


def test_conflicting_llm_constraints_are_dropped_lowest_weight_first():
    # Weight >= 8 starts hard. Resting every non-match day conflicts with 2 speed sessions.
    soft = [RestOnDay(day=d, weight=9, why="rest") for d in range(5)]
    soft.append(MinSessions(session="speed", count=2, weight=8, why="goal"))
    r = plan_week(inp(match_days=[5]), ConstraintSet(soft=soft))
    assert r.status == "relaxed"
    assert r.dropped[0].startswith("min_sessions")
    assert hard_violations(r, inp(match_days=[5])) == []


def test_soft_max_rpe_respected_when_cheap():
    cs = ConstraintSet(soft=[MaxRpeOnDay(day=1, rpe=3, weight=5, why="low readiness")])
    r = plan_week(inp(match_days=[5]), cs)
    assert r.days[1].rpe <= 3


def test_llm_schema_rejects_bad_output():
    with pytest.raises(ValidationError):
        ConstraintSet.model_validate({"load_factor": 3.0})
    with pytest.raises(ValidationError):
        ConstraintSet.model_validate({"soft": [{"type": "delete_rest_days", "weight": 5, "why": "x"}]})
    with pytest.raises(ValidationError):
        ConstraintSet.model_validate({"soft": [], "turn_off_safety": True})


def test_template_is_safe_everywhere():
    for matches in ([5], [2, 5], [0, 6]):
        for phv in (False, True):
            i = inp(match_days=matches, exam_days=[1], in_phv_window=phv, acwr=1.7)
            r = plan_week(i, ConstraintSet())
            r.days = safe_template(i)
            r.status = "template"
            assert hard_violations(r, i) == []


def test_randomised_inputs_never_break_hard_rules():
    rng = random.Random(11)
    for _ in range(60):
        matches = sorted(rng.sample(range(7), rng.choice([1, 1, 2])))
        free = [d for d in range(7) if d not in matches]
        exams = sorted(rng.sample(free, rng.choice([0, 0, 1, 2])))
        i = inp(
            match_days=matches,
            exam_days=exams,
            in_phv_window=rng.random() < 0.3,
            acwr=rng.choice([None, 0.9, 1.3, 1.6, 2.0]),
            chronic_daily_load=rng.uniform(150, 450),
        )
        soft = [MinSessions(session=rng.choice(["speed", "strength"]), count=2, weight=rng.randint(1, 10), why="g")]
        r = plan_week(i, ConstraintSet(soft=soft, load_factor=rng.uniform(0.6, 1.1)))
        assert hard_violations(r, i) == [], (i, r)
        assert r.solve_seconds < TIME_LIMIT_S * 2


@pytest.mark.parametrize("matches", [[5], [2, 5]])
def test_md_plus_1_is_easy(matches):
    r = plan_week(inp(match_days=matches))
    for d, _ in itertools.groupby(matches):
        if d + 1 < 7 and d + 1 not in matches:
            assert r.days[d + 1].rpe <= 3
