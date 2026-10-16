"""Runs the real agents (Monitor, Development Coach, Planner, Coordinator) inside
the simulator, so they can be evaluated against the fixed-template baseline.

Only what staff could observe is used: recorded loads, sleep, HRV, check-ins,
measured anthropometrics and test results, never the simulator's hidden truth.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

import numpy as np

from agents import dev_coach, planner_agent
from agents.coordinator import Decision, decide
from agents.llm import LLMBackend
from agents.monitor import Assessment, Measurements, PlayerHistory, assess
from agents.orchestrator import diff, to_proposal
from agents.rules import DevGoal
from analytics.flags import FlagKind
from analytics.maturation import MaturityStatus
from analytics.norms import NormTable
from domain.enums import SessionType
from planner.schema import PlanDay, PlannerInput
from simulator.policies import BaselinePolicy, PlannedSession, WeekContext, WeekPlan
from simulator.season import PRESEASON_DAILY_LOAD, PlayerState

REPLAN_FLAGS = {FlagKind.SHORT_SLEEP, FlagKind.LOW_HRV, FlagKind.READINESS_RED, FlagKind.LOAD_SPIKE}


class AgentPolicy:
    name = "agents"

    def __init__(self, llm: LLMBackend | None = None, coach_approves: bool = True, daily_replan: bool = True):
        self.llm = llm
        self.coach_approves = coach_approves
        self.daily_replan = daily_replan
        self.norms = NormTable.load()
        self.drills = dev_coach.load_drills()
        self.baseline = BaselinePolicy()
        self.goals: dict[str, list[DevGoal]] = {}
        self.goal_log: dict[tuple[str, int], list[DevGoal]] = {}
        self.outcomes: list[dict] = []  # one row per planner run, for the evaluation
        self.decisions: dict[str, int] = defaultdict(int)
        self._last_flags: dict[str, set] = {}
        self._bands: dict[str, object] = {}  # yesterday's readiness band, for the colour buffer

    # ------------------------------------------------------------------ helpers

    def _history(self, ps: PlayerState, day: date, include_today_checkin: bool) -> PlayerHistory:
        m = ps.latest_measure
        chk = ps.today_checkin if include_today_checkin else None
        return PlayerHistory(
            player_id=ps.profile.player_id,
            day=day,
            daily_loads=list(ps.daily_loads),
            sleep_hours=list(ps.sleep_hours),
            ln_rmssd=list(ps.ln_rmssd),
            hooper_today=chk["hooper"] if chk else None,
            mood_red=bool(chk and chk["mood_red"]),
            pain_reported=bool(chk and chk["pain"]),
            missed_checkins_in_row=ps.missed_in_row,
            measurements=None
            if m is None
            else Measurements(m["age"], m["height_cm"], m["sitting_height_cm"], m["weight_kg"]),
            preseason_daily_load=PRESEASON_DAILY_LOAD,
            previous_band=self._bands.get(ps.profile.player_id),
        )

    def _status(self, a: Assessment) -> MaturityStatus:
        return a.growth.status if a.growth else MaturityStatus.CIRCA_PHV

    def _update_goals(self, ps: PlayerState, a: Assessment, ctx: WeekContext) -> list[DevGoal]:
        pid = ps.profile.player_id
        # Development Coach runs after each test day (every 4 weeks).
        if ps.latest_tests and (pid not in self.goals or ctx.week % 4 == 1):
            plan = dev_coach.run(pid, ps.latest_tests, ps.age, self._status(a), self.llm, self.norms, self.drills)
            self.goals[pid] = plan.goals
        return self.goals.get(pid, [])

    def _plan(self, ps, ctx, a, goals, start_wd: int, kind: str, ceiling: list[int] | None = None) -> list[PlanDay]:
        inp = PlannerInput(
            player_id=ps.profile.player_id,
            start=ctx.dates[start_wd],
            match_days=[d - start_wd for d in ctx.match_days if d >= start_wd],
            exam_days=[d - start_wd for d in ctx.exam_days if d >= start_wd],
            in_phv_window=bool(a.growth and a.growth.in_phv_window),
            acwr=a.acwr,
            chronic_daily_load=a.chronic_daily_load or PRESEASON_DAILY_LOAD,
            acute_daily_load=a.acute_daily_load if a.chronic_daily_load else None,
            min_training_sessions=max(1, round(3 * (7 - start_wd) / 7)),
            days=7 - start_wd,
            rpe_ceiling=ceiling,
        )
        out = planner_agent.run(inp, a, goals, self.llm)
        self.outcomes.append(
            {
                "player_id": ps.profile.player_id,
                "week": ctx.week,
                "kind": kind,
                "status": out.result.status,
                "solve_seconds": out.result.solve_seconds,
                "hard_violations": len(out.hard_violations),
                "constraint_source": out.constraint_source,
                "flags": [f.kind.value for f in a.planning_flags],
            }
        )
        return out.result.days

    @staticmethod
    def _to_week_plan(days: list[PlanDay], offset: int = 0, base: WeekPlan | None = None) -> WeekPlan:
        plan: WeekPlan = dict(base or {})
        for d in days:
            wd = d.day + offset
            if d.kind == SessionType.MATCH and d.minutes < 90:
                plan[wd] = PlannedSession(d.kind, float(d.rpe), float(d.minutes))
            elif d.kind in (SessionType.MATCH, SessionType.REST):
                plan.pop(wd, None)
            else:
                plan[wd] = PlannedSession(d.kind, float(d.rpe), float(d.minutes))
        return plan

    # ------------------------------------------------------------------ Policy

    def plan_week(self, ps: PlayerState, ctx: WeekContext, rng: np.random.Generator) -> WeekPlan:
        day = ctx.dates[0]
        a = assess(self._history(ps, day, include_today_checkin=False))
        goals = self._update_goals(ps, a, ctx)
        self.goal_log[(ps.profile.player_id, ctx.week)] = list(goals)
        self._last_flags[ps.profile.player_id] = {f.kind for f in a.planning_flags}
        if a.safety_flags:
            # Staff handle it; the team template stands, minus what hard rules never allow.
            self.decisions["escalate"] += 1
            plan = self.baseline.plan_week(ps, ctx, rng)
            return {d: s for d, s in plan.items() if d not in ctx.exam_days}
        days = self._plan(ps, ctx, a, goals, 0, "weekly")
        self.decisions["weekly_plan"] += 1
        return self._to_week_plan(days)

    def adjust_day(self, ps: PlayerState, ctx: WeekContext, wd: int, plan: WeekPlan, rng) -> WeekPlan:
        """Morning check-in arrived: re-plan the rest of the week if new flags appeared."""
        if not self.daily_replan:
            return plan
        pid = ps.profile.player_id
        a = assess(self._history(ps, ctx.dates[wd], include_today_checkin=True))
        self._bands[pid] = a.readiness.band if a.readiness else None
        if a.safety_flags:
            self.decisions["escalate"] += 1
            return plan  # named staff handle it; no agent action
        new = {f.kind for f in a.planning_flags} & REPLAN_FLAGS
        if not new - self._last_flags.get(pid, set()):
            return plan
        self._last_flags[pid] = {f.kind for f in a.planning_flags}
        current = [
            PlanDay(
                day=d - wd,
                date=ctx.dates[d],
                kind=SessionType.MATCH if d in ctx.match_days else (plan[d].kind if d in plan else SessionType.REST),
                rpe=8 if d in ctx.match_days else (round(plan[d].rpe) if d in plan else 0),
                minutes=90 if d in ctx.match_days else (int(plan[d].minutes) if d in plan else 0),
            )
            for d in range(wd, 7)
        ]
        ceiling = [d.rpe for d in current]
        days = self._plan(ps, ctx, a, self.goals.get(pid, []), wd, "replan", ceiling)
        d = diff(current, days)
        if d.is_empty:
            return plan
        ruling = decide(to_proposal(pid, d, "replan"), a.flags)
        self.decisions[ruling.decision.value] += 1
        if ruling.decision == Decision.COACH_APPROVAL and not self.coach_approves:
            return plan
        return self._to_week_plan(days, offset=wd, base={k: v for k, v in plan.items() if k < wd})
