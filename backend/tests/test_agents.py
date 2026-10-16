from datetime import date

import pytest
from pydantic import BaseModel

from agents import dev_coach, planner_agent
from agents.coordinator import ActionKind, Decision
from agents.llm import CachedBackend, Call, LLMError, LLMValidationError, complete_with_retry
from agents.monitor import Measurements, PlayerHistory, assess
from agents.orchestrator import diff, run_cycle, to_proposal
from agents.rules import DevGoal, default_constraints
from analytics.flags import FlagKind
from analytics.maturation import MaturityStatus
from domain.enums import SessionType
from planner.schema import ConstraintSet, MinSessions, PlanDay, PlannerInput

MON = date(2026, 10, 19)


class FakeLLM:
    """Returns queued answers per agent; an Exception in the queue is raised."""

    name = "fake"

    def __init__(self, **queues):
        self.queues = {k: list(v) for k, v in queues.items()}
        self.calls: list[Call] = []

    def complete(self, call: Call) -> BaseModel:
        self.calls.append(call)
        q = self.queues.get(call.agent)
        if not q:
            raise LLMError("nothing queued")
        item = q.pop(0)
        if isinstance(item, Exception):
            raise item
        if callable(item):
            return item(call)
        return item


def tired_history(**kw) -> PlayerHistory:
    base = dict(
        player_id="P01",
        day=MON,
        daily_loads=[300.0] * 35 + [900, 0, 1000, 800, 0, 1200, 1100],
        sleep_hours=[8, 8, 5.5, 5.8, 5.6],
        ln_rmssd=[4.2, 4.25, 4.15, 4.2, 4.22, 4.18, 4.2, 3.9],
        hooper_today=(5, 5, 4, 5),
        measurements=Measurements(14.0, 165, 85, 55),
    )
    base.update(kw)
    return PlayerHistory(**base)


# --------------------------------------------------------------------------- monitor


def test_monitor_plan_example_flags_and_chips():
    a = assess(tired_history())
    kinds = {f.kind for f in a.flags}
    assert {FlagKind.LOAD_SPIKE, FlagKind.SHORT_SLEEP, FlagKind.LOW_HRV, FlagKind.PHV_WINDOW} <= kinds
    assert a.readiness is not None and a.readiness.band.value == "red"
    assert "Growth zone" in a.chips
    assert any(c.startswith("Sleep") for c in a.chips)


def test_monitor_without_measurements_has_no_growth_status():
    a = assess(tired_history(measurements=None))
    assert a.growth is None


# --------------------------------------------------------------------------- llm plumbing


def test_retry_once_on_invalid_output_then_succeeds():
    good = ConstraintSet(load_factor=0.8)
    llm = FakeLLM(planner=[LLMValidationError("load_factor too high"), good])
    out, source = complete_with_retry(llm, Call("planner", "s", "u", ConstraintSet))
    assert out == good and source == "llm_retry"
    assert "load_factor too high" in llm.calls[1].retry_feedback


def test_two_invalid_outputs_give_up():
    llm = FakeLLM(planner=[LLMValidationError("x"), LLMValidationError("y")])
    assert complete_with_retry(llm, Call("planner", "s", "u", ConstraintSet)) == (None, "invalid")


def test_api_down_is_unavailable_without_retry():
    llm = FakeLLM(planner=[LLMError("connection")])
    assert complete_with_retry(llm, Call("planner", "s", "u", ConstraintSet)) == (None, "unavailable")
    assert len(llm.calls) == 1


def test_no_backend_is_unavailable():
    assert complete_with_retry(None, Call("planner", "s", "u", ConstraintSet)) == (None, "unavailable")


def test_cache_stores_and_replays(tmp_path):
    answer = ConstraintSet(load_factor=0.9, rationale="cached")
    inner = FakeLLM(planner=[answer])
    cached = CachedBackend(inner, cache_dir=tmp_path)
    call = Call("planner", "sys", "user", ConstraintSet)
    assert cached.complete(call) == answer
    offline = CachedBackend(None, cache_dir=tmp_path)
    assert offline.complete(Call("planner", "sys", "user", ConstraintSet)).rationale == "cached"
    with pytest.raises(LLMError):
        offline.complete(Call("planner", "sys", "other user", ConstraintSet))


# --------------------------------------------------------------------------- planner agent


def planner_input(**kw):
    return PlannerInput(player_id="P01", start=MON, match_days=[5], exam_days=[2], **kw)


def test_planner_agent_uses_llm_constraints():
    cs = ConstraintSet(soft=[MinSessions(session="speed", count=2, weight=6, why="goal")], rationale="llm")
    llm = FakeLLM(planner=[cs], explainer=[planner_agent.Explanation(player="a. b. c.", coach="line")])
    out = planner_agent.run(planner_input(), assess(tired_history(measurements=None)), [], llm)
    assert out.constraint_source == "llm"
    assert out.explanation_source == "llm"
    assert out.hard_violations == []
    assert [d.kind for d in out.result.days].count(SessionType.SPEED) == 2


def test_planner_agent_falls_back_to_rules_when_llm_down():
    a = assess(tired_history())
    out = planner_agent.run(planner_input(acwr=a.acwr, in_phv_window=True), a, [DevGoal("sprint_10m")], None)
    assert out.constraint_source == "rules"
    assert out.explanation_source == "rules"
    assert out.hard_violations == []
    assert out.constraints.load_factor < 1.0  # load spike
    assert out.explanation_player.count(".") >= 3
    assert "growth spurt" in out.explanation_player


def test_rule_constraints_for_goals_and_spike():
    a = assess(tired_history())
    cs = default_constraints(a.planning_flags, [DevGoal("cmj", 2)], planner_input())
    assert cs.load_factor == pytest.approx(0.8)
    assert any(isinstance(c, MinSessions) and c.session == SessionType.STRENGTH for c in cs.soft)


# --------------------------------------------------------------------------- development coach


TESTS_SLOW_SPRINT = {"sprint_10m": 2.15, "sprint_30m": 4.9, "cmj": 33.0, "yoyo_ir1": 1500}


def test_dev_coach_picks_weakest_bio_banded_kpi():
    plan = dev_coach.run("P01", TESTS_SLOW_SPRINT, 14.2, MaturityStatus.CIRCA_PHV, None)
    assert plan.goals[0].kpi in {"sprint_10m", "sprint_30m"}
    assert plan.source == "rules"
    assert plan.drills and all(d.kpi == plan.goals[0].kpi or d.kpi in {g.kpi for g in plan.goals} for d in plan.drills)


def test_dev_coach_never_gives_plyometrics_in_growth_zone():
    for status in MaturityStatus:
        allowed = dev_coach.allowed_drills(dev_coach.load_drills(), 16, status == MaturityStatus.CIRCA_PHV)
        if status == MaturityStatus.CIRCA_PHV:
            assert not any(d.plyometric for d in allowed)


def test_dev_coach_rejects_llm_drill_outside_safe_library():
    bad = dev_coach.DrillChoice(drill_ids=["spd-bounding"], feedback="Jump!")  # plyometric
    plan = dev_coach.run("P01", TESTS_SLOW_SPRINT, 14.2, MaturityStatus.CIRCA_PHV, FakeLLM(dev_coach=[bad]))
    assert plan.source == "rules"
    assert plan.rejected_drills == ["spd-bounding"]
    assert not any(d.plyometric for d in plan.drills)


def test_dev_coach_tool_is_offered_and_llm_pick_used():
    def answer(call: Call):
        tool = call.tools[0]
        ids = [d["id"] for d in tool.fn({"kpi": "sprint_10m"})]
        return dev_coach.DrillChoice(drill_ids=ids[:2], feedback="Work on your first steps.")

    plan = dev_coach.run("P01", TESTS_SLOW_SPRINT, 14.2, MaturityStatus.PRE_PHV, FakeLLM(dev_coach=[answer]))
    assert plan.source == "llm"
    assert len(plan.drills) == 2


# --------------------------------------------------------------------------- orchestrator


def day(d, kind, rpe, minutes=60):
    return PlanDay(day=d, date=date.fromordinal(MON.toordinal() + d), kind=kind, rpe=rpe, minutes=minutes)


def test_diff_classifies_changes():
    cur = [day(0, SessionType.TECHNICAL, 5), day(1, SessionType.SPEED, 7), day(5, SessionType.MATCH, 8, 90)]
    assert to_proposal("P", diff(cur, cur), "").kind == ActionKind.INTENSITY_CHANGE
    small = [day(0, SessionType.TECHNICAL, 4), day(1, SessionType.SPEED, 7), day(5, SessionType.MATCH, 8, 90)]
    p = to_proposal("P", diff(cur, small), "")
    assert p.kind == ActionKind.INTENSITY_CHANGE and p.rpe_delta == 1
    swap = [day(0, SessionType.RECOVERY, 3), day(1, SessionType.SPEED, 7), day(5, SessionType.MATCH, 8, 90)]
    assert to_proposal("P", diff(cur, swap), "").kind == ActionKind.SESSION_SWAP
    minutes = [day(0, SessionType.TECHNICAL, 5), day(1, SessionType.SPEED, 7), day(5, SessionType.MATCH, 8, 45)]
    assert to_proposal("P", diff(cur, minutes), "").kind == ActionKind.MATCH_MINUTES


def test_cycle_escalates_red_mood_without_planning():
    r = run_cycle(tired_history(mood_red=True), planner_input(), [], None, None)
    assert r.escalate
    assert r.outcome is None
    assert r.ruling.decision == Decision.ESCALATE


def test_cycle_sends_session_swap_to_coach():
    current = [day(d, SessionType.TECHNICAL, 6, 75) for d in range(5)] + [
        day(5, SessionType.MATCH, 8, 90),
        day(6, SessionType.REST, 0, 0),
    ]
    r = run_cycle(tired_history(), planner_input(), [], current, None)
    assert not r.escalate
    assert r.proposal is not None
    assert r.ruling.decision == Decision.COACH_APPROVAL
    assert r.outcome.hard_violations == []
