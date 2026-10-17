"""CP-SAT model for one player's next 7 days.

Hard rules (always enforced, never from the LLM):
  H1 fixtures fixed; matches only on match days
  H2 at least one rest day (full weeks; a short mid-week re-plan keeps the week's rest day)
  H3 match day minus 1 at RPE <= 4
  H4 in the PHV window, no speed session above RPE 6
  H5 when ACWR > 1.5, weekly load <= cap
  H6 no session on exam evenings
  H7 each session type stays inside its RPE range

Soft constraints are weighted penalties. LLM constraints with weight >= 8 are first
imposed as hard; if that is infeasible they are dropped lowest weight first, and if
the hard rules alone are infeasible a safe template is returned.
"""

from __future__ import annotations

import time
from datetime import timedelta

from ortools.sat.python import cp_model

from analytics.load import ACUTE_DAYS as ACWR_ACUTE_DAYS
from analytics.load import CHRONIC_DAYS as ACWR_CHRONIC_DAYS
from domain.enums import SessionType
from planner.schema import (
    MATCH_RPE,
    RPE_RANGE,
    SESSION_MINUTES,
    ConstraintSet,
    MaxRpeOnDay,
    MaxSessions,
    MinSessions,
    NoHardBackToBack,
    PlanDay,
    PlannerInput,
    PlanResult,
    RestOnDay,
    SoftConstraint,
)

TIME_LIMIT_S = 2.0
MIN_DAYS_FOR_REST_RULE = 4
ACWR_CAP_THRESHOLD = 1.5
ACWR_CAP_FACTOR = 1.0  # cap = chronic weekly load when ACWR is high
MD_MINUS_1_MAX_RPE = 4
PHV_SPEED_MAX_RPE = 6
ENFORCE_WEIGHT = 8  # LLM constraints at or above this weight start as hard
TYPES = list(SessionType)
TRAINING = [t for t in TYPES if t not in (SessionType.REST, SessionType.MATCH)]

LOAD_UNIT_AU = 25
PENALTY_SCALE = 100 // LOAD_UNIT_AU  # 1 penalty point = 100 AU of target-load deviation

# Built-in soft weights (penalty points)
W_MIN_TRAINING = 6
W_BACK_TO_BACK = 3
W_NON_PREFERRED = 1
W_MD_PLUS_1 = 4
W_SECOND_REST = 3  # academies usually give two days off a week
W_MATCH_MINUTES = 2  # per 15 match minutes below 90
W_PROJECTED_ACWR = 4  # per 25 AU of projected acute load above the limit (~100 AU of session load)
PROJECTED_ACWR_LIMIT = 1.4  # margin under the 1.5 flag for RPE noise and match-minute variation
EWMA_SCALE = 1000  # integer scaling of the EWMA coefficients for CP-SAT
MATCH_MINUTE_OPTIONS = [0, 30, 45, 60, 90]  # 0 = in the squad but not playing (return to play)
W_SAME_TYPE = 2  # per session of one type beyond MAX_SAME_TYPE
MAX_SAME_TYPE = 2
W_FOOTBALL = 3  # academy weeks are built around technical and tactical work
MIN_FOOTBALL_SESSIONS = 2
MD_PLUS_1_MAX_RPE = 3
W_TEAM_DAY = 8  # per club training night without a football session (self-guided players)
W_TEAM_RPE = 2  # per RPE point a club session is planned below TEAM_MIN_RPE (the club sets the intensity)
TEAM_MIN_RPE = 5


def weekly_cap(inp: PlannerInput) -> int | None:
    if inp.acwr is not None and inp.acwr > ACWR_CAP_THRESHOLD:
        return round(inp.chronic_daily_load * inp.days * ACWR_CAP_FACTOR)
    return None


def _label(c: SoftConstraint) -> str:
    fields = c.model_dump(exclude={"why", "weight", "type"})
    args = ", ".join(f"{k}={v.value if hasattr(v, 'value') else v}" for k, v in fields.items())
    return f"{c.type}({args}) w={c.weight}"


class _Model:
    def __init__(self, inp: PlannerInput, cs: ConstraintSet, enforced: list[SoftConstraint]):
        self.inp, self.cs = inp, cs
        m = self.m = cp_model.CpModel()
        self.n = n = inp.days
        D = range(n)
        self.x = {(d, t): m.NewBoolVar(f"x_{d}_{t.value}") for d in D for t in TYPES}
        self.rpe = {d: m.NewIntVar(0, 10, f"rpe_{d}") for d in D}
        rpe_t = {(d, t): m.NewIntVar(0, 10, f"rpe_{d}_{t.value}") for d in D for t in TYPES}
        for d in D:
            m.AddExactlyOne(self.x[d, t] for t in TYPES)
            for t in TYPES:
                lo, hi = RPE_RANGE[t]
                m.Add(rpe_t[d, t] == self.rpe[d]).OnlyEnforceIf(self.x[d, t])
                m.Add(rpe_t[d, t] == 0).OnlyEnforceIf(self.x[d, t].Not())
                m.Add(self.rpe[d] >= lo).OnlyEnforceIf(self.x[d, t])  # H7
                m.Add(self.rpe[d] <= hi).OnlyEnforceIf(self.x[d, t])
        matches = set(inp.match_days)
        # Match minutes are a decision (return-to-play limits); the fixture itself is fixed.
        self.match_min = {
            d: m.NewIntVarFromDomain(cp_model.Domain.FromValues(MATCH_MINUTE_OPTIONS), f"mm_{d}") for d in matches
        }
        self.load = {
            d: MATCH_RPE * self.match_min[d]
            if d in matches
            else sum(SESSION_MINUTES[t] * rpe_t[d, t] for t in TYPES if t != SessionType.MATCH)
            for d in D
        }
        self.week_load = sum(self.load.values())
        self.is_rest = {d: self.x[d, SessionType.REST] for d in D}

        for d in D:  # H1
            if d in matches:
                m.Add(self.x[d, SessionType.MATCH] == 1)
                m.Add(self.rpe[d] == MATCH_RPE)
            else:
                m.Add(self.x[d, SessionType.MATCH] == 0)
        if n >= MIN_DAYS_FOR_REST_RULE:  # H2
            m.Add(sum(self.is_rest[d] for d in D if d not in matches) >= 1)
        for d in matches:  # H3
            if d - 1 >= 0 and d - 1 not in matches:
                m.Add(self.rpe[d - 1] <= MD_MINUS_1_MAX_RPE)
        if inp.in_phv_window:  # H4
            for d in D:
                m.Add(self.rpe[d] <= PHV_SPEED_MAX_RPE).OnlyEnforceIf(self.x[d, SessionType.SPEED])
        self.cap = weekly_cap(inp)
        if self.cap is not None:  # H5
            m.Add(self.week_load <= self.cap)
        for d in inp.exam_days:  # H6
            if d not in matches:
                m.Add(self.is_rest[d] == 1)
        if inp.rpe_ceiling is not None:  # a re-plan never adds load to a day
            for d, ceiling in enumerate(inp.rpe_ceiling[:n]):
                if d not in matches:
                    m.Add(self.rpe[d] <= ceiling)

        # ---- soft constraints
        penalties = []
        target = inp.target_load(cs.load_factor)
        if self.cap is not None:
            target = min(target, self.cap)
        # Deviation from the target load in coarse units: nobody can tell 10 AU apart,
        # and the coarse objective lets the solver prove optimality much faster.
        dev = m.NewIntVar(0, 100_000 // LOAD_UNIT_AU, "dev")
        m.Add(LOAD_UNIT_AU * dev >= self.week_load - target)
        m.Add(LOAD_UNIT_AU * dev >= target - self.week_load)
        self.target = target

        n_training = sum(self.x[d, t] for d in D for t in TRAINING)
        short = m.NewIntVar(0, 7, "short_training")
        m.Add(short >= inp.min_training_sessions - n_training)
        penalties.append(W_MIN_TRAINING * short)

        if n == 7:
            one_rest = m.NewBoolVar("only_one_rest")
            m.Add(sum(self.is_rest[d] for d in D) >= 2).OnlyEnforceIf(one_rest.Not())
            penalties.append(W_SECOND_REST * one_rest)

        penalties.extend(self._projected_acwr(inp))
        for d in matches:
            cut = m.NewIntVar(0, 6, f"mmcut_{d}")
            m.Add(15 * cut == 90 - self.match_min[d])
            penalties.append(W_MATCH_MINUTES * cut)

        penalties.append(W_BACK_TO_BACK * self._hard_pairs(7))  # threshold RPE 7

        for t in TRAINING:
            if t == SessionType.RECOVERY:
                continue
            extra = m.NewIntVar(0, 7, f"extra_{t.value}")
            m.Add(extra >= sum(self.x[d, t] for d in D) - MAX_SAME_TYPE)
            penalties.append(W_SAME_TYPE * extra)
        football = sum(self.x[d, t] for d in D for t in (SessionType.TECHNICAL, SessionType.TACTICAL))
        few = m.NewIntVar(0, 7, "few_football")
        m.Add(few >= MIN_FOOTBALL_SESSIONS - football)
        penalties.append(W_FOOTBALL * few)

        for d in matches:  # day after a match: recovery or rest
            if d + 1 < n and d + 1 not in matches:
                over = m.NewIntVar(0, 10, f"md1_{d}")
                m.Add(over >= self.rpe[d + 1] - MD_PLUS_1_MAX_RPE)
                penalties.append(W_MD_PLUS_1 * over)

        for d in inp.team_days:
            if d < n and d not in matches:
                penalties.append(
                    W_TEAM_DAY * (1 - self.x[d, SessionType.TECHNICAL] - self.x[d, SessionType.TACTICAL])
                )
                if d + 1 not in matches:  # the day before a match stays easy (H3)
                    low = m.NewIntVar(0, 10, f"team_low_{d}")
                    m.Add(low >= TEAM_MIN_RPE - self.rpe[d])
                    penalties.append(W_TEAM_RPE * low)

        if inp.preferred_days:
            off = [d for d in D if d not in inp.preferred_days and d not in matches]
            penalties.append(W_NON_PREFERRED * sum(1 - self.is_rest[d] for d in off))

        enforced_ids = {id(c) for c in enforced}
        for c in cs.soft:
            v = self._violation(c)
            if v is None:
                continue
            if id(c) in enforced_ids:
                m.Add(v == 0)
            else:
                penalties.append(c.weight * v)

        m.Minimize(PENALTY_SCALE * sum(penalties) + dev)

    def _projected_acwr(self, inp: PlannerInput) -> list:
        """Penalise days whose projected EWMA ACWR would exceed the limit.

        With today's acute A0 and chronic C0, the acute and chronic load on plan day d are
        linear in the planned loads:  X_d = (1-l)^(d+1) X0 + sum_k<=d l (1-l)^(d-k) load_k.
        So acute_d <= limit * chronic_d is a linear constraint on the plan.
        """
        m, n = self.m, self.n
        la, lc = 2 / (ACWR_ACUTE_DAYS + 1), 2 / (ACWR_CHRONIC_DAYS + 1)
        a0 = inp.acute_daily_load if inp.acute_daily_load is not None else inp.chronic_daily_load
        c0 = inp.chronic_daily_load
        if c0 <= 0:
            return []
        out = []
        for d in range(n):
            coef = {
                k: round(EWMA_SCALE * (la * (1 - la) ** (d - k) - PROJECTED_ACWR_LIMIT * lc * (1 - lc) ** (d - k)))
                for k in range(d + 1)
            }
            rhs = EWMA_SCALE * (PROJECTED_ACWR_LIMIT * c0 * (1 - lc) ** (d + 1) - a0 * (1 - la) ** (d + 1))
            excess = m.NewIntVar(0, 10_000, f"acwr_excess_{d}")
            m.Add(EWMA_SCALE * LOAD_UNIT_AU * excess >= sum(coef[k] * self.load[k] for k in coef) - round(rhs))
            out.append(W_PROJECTED_ACWR * excess)
        return out

    def _hard_pairs(self, threshold: int):
        m = self.m
        hard = {}
        for d in range(self.n):
            b = m.NewBoolVar(f"hard_{d}_{threshold}")
            m.Add(self.rpe[d] >= threshold).OnlyEnforceIf(b)
            m.Add(self.rpe[d] < threshold).OnlyEnforceIf(b.Not())
            hard[d] = b
        pairs = []
        for d in range(self.n - 1):
            p = m.NewBoolVar(f"pair_{d}_{threshold}")
            m.AddBoolAnd([hard[d], hard[d + 1]]).OnlyEnforceIf(p)
            m.AddBoolOr([hard[d].Not(), hard[d + 1].Not()]).OnlyEnforceIf(p.Not())
            pairs.append(p)
        return sum(pairs)

    def _violation(self, c: SoftConstraint):
        m, D = self.m, range(self.n)
        if isinstance(c, MinSessions):
            v = m.NewIntVar(0, 7, "")
            m.Add(v >= c.count - sum(self.x[d, c.session] for d in D))
            return v
        if isinstance(c, MaxSessions):
            v = m.NewIntVar(0, 7, "")
            m.Add(v >= sum(self.x[d, c.session] for d in D) - c.count)
            return v
        if isinstance(c, MaxRpeOnDay):
            if c.day in self.inp.match_days or c.day >= self.n:
                return None
            v = m.NewIntVar(0, 10, "")
            m.Add(v >= self.rpe[c.day] - c.rpe)
            return v
        if isinstance(c, RestOnDay):
            if c.day in self.inp.match_days or c.day >= self.n:
                return None
            return 1 - self.is_rest[c.day]
        if isinstance(c, NoHardBackToBack):
            return self._hard_pairs(c.rpe_threshold)
        raise TypeError(c)


def _solve(inp: PlannerInput, cs: ConstraintSet, enforced: list[SoftConstraint]):
    model = _Model(inp, cs, enforced)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = TIME_LIMIT_S
    solver.parameters.num_workers = 1  # deterministic: same input, same week
    solver.parameters.random_seed = 7
    status = solver.Solve(model.m)
    return model, solver, status


def safe_template(inp: PlannerInput) -> list[PlanDay]:
    """Conservative week used when no feasible plan exists."""
    days = []
    matches, exams = set(inp.match_days), set(inp.exam_days)
    toggle = True
    for d in range(inp.days):
        dt = inp.start + timedelta(days=d)
        if d in matches:
            kind, rpe = SessionType.MATCH, MATCH_RPE
        elif d in exams or d + 1 in matches or d == 6 or (inp.rpe_ceiling and inp.rpe_ceiling[d] < 3):
            kind, rpe = SessionType.REST, 0
        else:
            kind, rpe = (SessionType.TECHNICAL, 4) if toggle else (SessionType.RECOVERY, 3)
            toggle = not toggle
        days.append(PlanDay(day=d, date=dt, kind=kind, rpe=rpe, minutes=SESSION_MINUTES[kind]))
    cap = weekly_cap(inp)
    if cap is not None:
        for pd in days:
            if sum(x.load for x in days) <= cap:
                break
            if pd.kind not in (SessionType.MATCH, SessionType.REST):
                pd.kind, pd.rpe, pd.minutes = SessionType.REST, 0, 0
    return days


def plan_week(inp: PlannerInput, cs: ConstraintSet | None = None) -> PlanResult:
    cs = cs or ConstraintSet()
    t0 = time.perf_counter()
    enforced = sorted((c for c in cs.soft if c.weight >= ENFORCE_WEIGHT), key=lambda c: -c.weight)
    dropped: list[str] = []
    while True:
        model, solver, status = _solve(inp, cs, enforced)
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            days = []
            for d in range(inp.days):
                kind = next(t for t in TYPES if solver.Value(model.x[d, t]))
                rpe = solver.Value(model.rpe[d])
                minutes = solver.Value(model.match_min[d]) if d in model.match_min else SESSION_MINUTES[kind]
                days.append(PlanDay(day=d, date=inp.start + timedelta(days=d), kind=kind, rpe=rpe, minutes=minutes))
            if dropped:
                label = "relaxed"
            else:
                label = "optimal" if status == cp_model.OPTIMAL else "feasible"
            return PlanResult(
                player_id=inp.player_id,
                days=days,
                status=label,
                dropped=dropped,
                penalty=int(solver.ObjectiveValue()),
                solve_seconds=time.perf_counter() - t0,
                weekly_load_cap=model.cap,
            )
        if not enforced:
            break
        weakest = enforced.pop()  # lowest weight last
        dropped.append(_label(weakest))
    return PlanResult(
        player_id=inp.player_id,
        days=safe_template(inp),
        status="template",
        dropped=dropped,
        solve_seconds=time.perf_counter() - t0,
        weekly_load_cap=weekly_cap(inp),
    )


def hard_violations(result: PlanResult, inp: PlannerInput) -> list[str]:
    """Independent check of H1-H7, used by tests and the evaluation harness.

    The template may exceed the ACWR cap only when the fixtures alone exceed it.
    """
    out = []
    days = {d.day: d for d in result.days}
    matches = set(inp.match_days)
    for d, pd in days.items():
        if (pd.kind == SessionType.MATCH) != (d in matches):
            out.append(f"H1 day {d}")
        lo, hi = RPE_RANGE[pd.kind]
        if not lo <= pd.rpe <= hi:
            out.append(f"H7 day {d} {pd.kind.value} rpe {pd.rpe}")
        if d + 1 in matches and d not in matches and pd.rpe > MD_MINUS_1_MAX_RPE:
            out.append(f"H3 day {d}")
        if inp.in_phv_window and pd.kind == SessionType.SPEED and pd.rpe > PHV_SPEED_MAX_RPE:
            out.append(f"H4 day {d}")
        if d in inp.exam_days and d not in matches and pd.kind != SessionType.REST:
            out.append(f"H6 day {d}")
    no_rest = not any(pd.kind == SessionType.REST for d, pd in days.items() if d not in matches)
    if inp.days >= MIN_DAYS_FOR_REST_RULE and no_rest:
        out.append("H2 no rest day")
    cap = weekly_cap(inp)
    if cap is not None and result.weekly_load > cap:
        fixture_load = sum(pd.load for pd in result.days if pd.kind == SessionType.MATCH)
        if fixture_load <= cap:
            out.append(f"H5 weekly load {result.weekly_load} > cap {cap}")
    return out
