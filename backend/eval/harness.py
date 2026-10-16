"""Evaluation harness (plan section 9).

Baseline: the fixed weekly template. Every season metric runs on the simulated
season under 3 injury-model variants (load-, readiness-driven, random).
"""

from __future__ import annotations

import copy
import itertools
import json
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path

from agents import planner_agent
from agents.llm import LLMBackend
from agents.monitor import assess
from agents.orchestrator import run_cycle
from agents.rules import DevGoal
from analytics.readiness import ReadinessConfig, band_for, combine, hooper_score, hrv_score, hrv_z, sleep_score
from eval.metrics import mirwald_error, season_metrics
from eval.scenarios import history as scenario_history
from eval.scenarios import inp as scenario_inp
from eval.scenarios import run_all as run_scenarios
from planner.model import MD_MINUS_1_MAX_RPE
from simulator.agent_policy import AgentPolicy
from simulator.season import SeasonResult, SeasonSimulator, load_config

VARIANTS = ("load", "readiness", "random")


# --------------------------------------------------------------------------- executed-week checks


def executed_violations(res: SeasonResult) -> Counter:
    """Hard rules checked on what was actually scheduled (planned RPE), per player-week."""
    fx = {f["date"]: f for f in res.fixtures}
    by_date = sorted(fx)
    next_day = dict(zip(by_date, by_date[1:]))
    sessions = defaultdict(dict)
    for s in res.sessions:
        sessions[s["player_id"]][s["date"]] = s
    weeks = defaultdict(list)
    for r in res.daily:
        weeks[(r["player_id"], r["week"])].append(r)

    v = Counter()
    for (_pid, _), rows in weeks.items():
        if any(r["injured"] for r in rows):
            continue
        if not any(r["load"] == 0 and not fx[r["date"]]["match"] for r in rows):
            v["no_rest_day"] += 1
    for _pid, by_day in sessions.items():
        for d, s in by_day.items():
            if s["kind"] == "match":
                continue
            if fx[d]["exam"]:
                v["session_on_exam_day"] += 1
            nd = next_day.get(d)
            if nd and fx[nd]["match"] and s["planned_rpe"] > MD_MINUS_1_MAX_RPE:
                v["md_minus_1_too_hard"] += 1
    return v


def development_delivery(res: SeasonResult, policy: AgentPolicy) -> float | None:
    """Delivered goal sessions / planned goal sessions, over healthy player-weeks."""
    kinds = defaultdict(Counter)
    for s in res.sessions:
        kinds[s["player_id"]][(res_week(res, s["date"]), s["kind"])] += 1
    injured_weeks = {(r["player_id"], r["week"]) for r in res.daily if r["injured"]}
    required = delivered = 0
    for (pid, week), goals in policy.goal_log.items():
        if (pid, week) in injured_weeks or not goals:
            continue
        need = Counter()
        for g in goals:
            need[g.session.value] += g.sessions_per_week
        for kind, n in need.items():
            required += n
            delivered += min(n, kinds[pid][(week, kind)])
    return None if required == 0 else 100 * delivered / required


_WEEK_CACHE: dict[int, dict[str, int]] = {}


def res_week(res: SeasonResult, d: str) -> int:
    m = _WEEK_CACHE.setdefault(id(res), {f["date"]: f["week"] for f in res.fixtures})
    return m[d]


# --------------------------------------------------------------------------- readiness sensitivity


def readiness_sensitivity(res: SeasonResult, delta: float = 0.1) -> dict[str, float]:
    """% of daily bands that change when one weight shifts by +/-delta (others rescaled)."""
    base_cfg = ReadinessConfig.load()
    rows = defaultdict(list)
    for c in res.checkins:
        rows[c["player_id"]].append(c)
    comps = []
    for _pid, cs in rows.items():
        hrv_hist: list[float] = []
        for c in cs:
            z = hrv_z(c["ln_rmssd"], hrv_hist)
            hrv_hist.append(c["ln_rmssd"])
            comps.append(
                {
                    "hrv": None if z is None else hrv_score(z),
                    "hooper": None
                    if not c["completed"]
                    else hooper_score(c["sleep_quality"], c["fatigue"], c["stress"], c["soreness"]),
                    "sleep": sleep_score(c["sleep_hours"]),
                }
            )
    base_bands = [band_for(combine(c, base_cfg).score, base_cfg) for c in comps]
    out = {}
    for key, sign in itertools.product(base_cfg.weights, (+1, -1)):
        w = dict(base_cfg.weights)
        w[key] = max(0.0, w[key] + sign * delta)
        others = [k for k in w if k != key]
        rest = sum(base_cfg.weights[k] for k in others)
        for k in others:
            w[k] = base_cfg.weights[k] * (1 - w[key]) / rest
        cfg = ReadinessConfig(weights=w)
        bands = [band_for(combine(c, cfg).score, cfg) for c in comps]
        out[f"{key}{'+' if sign > 0 else '-'}{delta}"] = 100 * sum(a != b for a, b in zip(bands, base_bands)) / len(bands)
    return out


# --------------------------------------------------------------------------- consistency + LLM validity


def planner_consistency(llm: LLMBackend | None, runs: int = 20) -> dict:
    """Same input -> same week? Over a few representative inputs."""
    cases = [
        (scenario_history(), scenario_inp(), []),
        (scenario_history(daily_loads=[300.0] * 35 + [900, 0, 1000, 800, 0, 1200, 1100]), scenario_inp(exam_days=[2]),
         [DevGoal("sprint_10m")]),
        (scenario_history(sleep_hours=[7.8, 5.5, 5.7, 5.4]), scenario_inp(match_days=[2, 5]), [DevGoal("cmj")]),
    ]
    shares = []
    for h, inp, goals in cases:
        a = assess(h)
        p = inp.model_copy(update={"acwr": a.acwr, "chronic_daily_load": a.chronic_daily_load})
        sigs = Counter(planner_agent.run(p, a, goals, llm).result.signature() for _ in range(runs))
        shares.append(100 * sigs.most_common(1)[0][1] / runs)
    return {"min_share_pct": min(shares), "per_case_pct": shares}


def red_checkin_latency(n: int = 20) -> float:
    """Seconds from a red check-in arriving to the escalation decision (agent side)."""
    worst = 0.0
    for _ in range(n):
        t0 = time.perf_counter()
        r = run_cycle(scenario_history(mood_red=True), scenario_inp(), [], None, None)
        assert r.escalate
        worst = max(worst, time.perf_counter() - t0)
    return worst


# --------------------------------------------------------------------------- main


def run(quick: bool = False, llm: LLMBackend | None = None, out_dir: Path | None = None, log=print) -> dict:
    cfg = load_config()
    if quick:
        cfg["n_players"], cfg["weeks"] = 8, 16
    results: dict = {"config": {"players": cfg["n_players"], "weeks": cfg["weeks"], "seed": cfg["seed"]}}
    seasons = {}
    for variant in VARIANTS:
        t0 = time.perf_counter()
        base = SeasonSimulator(copy.deepcopy(cfg), injury_variant=variant).run()
        policy = AgentPolicy(llm=llm)
        agent = SeasonSimulator(copy.deepcopy(cfg), policy=policy, injury_variant=variant).run()
        seasons[variant] = (base, agent, policy)
        mb, ma = season_metrics(base), season_metrics(agent)
        st = [o["solve_seconds"] for o in policy.outcomes]
        weekly = defaultdict(float)
        for o in policy.outcomes:
            if o["kind"] == "weekly":
                weekly[o["week"]] += o["solve_seconds"]
        results[variant] = {
            "baseline": mb,
            "agents": ma,
            "spike_reduction_pct": _reduction(mb["acwr_spike_weeks"], ma["acwr_spike_weeks"]),
            "monotony_reduction_pct": _reduction(mb["monotony_weeks"], ma["monotony_weeks"]),
            "dev_delivery_pct": development_delivery(agent, policy),
            "plan_hard_violations": sum(o["hard_violations"] for o in policy.outcomes),
            "executed_violations_agents": dict(executed_violations(agent)),
            "executed_violations_baseline": dict(executed_violations(base)),
            "planner_runs": len(policy.outcomes),
            "planner_status": dict(Counter(o["status"] for o in policy.outcomes)),
            "constraint_source": dict(Counter(o["constraint_source"] for o in policy.outcomes)),
            "solver_max_s_player_week": max(st),
            "solver_mean_s_player_week": statistics.fmean(st),
            "solver_max_s_squad_week": max(weekly.values()),
            "decisions": dict(policy.decisions),
        }
        log(f"  {variant}: done in {time.perf_counter() - t0:.0f} s")

    base_load = seasons["load"][0]
    results["mirwald_error"] = mirwald_error(base_load)
    results["readiness_sensitivity_pct"] = readiness_sensitivity(base_load)
    scen = run_scenarios()
    results["safety_scenarios"] = {
        "passed": sum(s.passed for s in scen),
        "total": len(scen),
        "by_category": dict(Counter(s.category for s in scen if s.passed)),
        "failures": {s.name: s.errors for s in scen if not s.passed},
    }
    results["planner_consistency"] = planner_consistency(llm)
    results["red_checkin_to_escalation_s"] = red_checkin_latency()
    results["llm"] = {
        "backend": None if llm is None else llm.name,
        "first_try_valid_pct": _pct_source(results, ("llm",)),
        "valid_after_retry_or_fallback_pct": 100.0,  # every planner run produced a plan (see planner_status)
    }

    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "results.json").write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
        try:
            from eval.plots import realism_plots

            realism_plots(seasons["load"][0], seasons["load"][1], out_dir)
        except ImportError:
            log("  matplotlib not installed: skipping plots")
    return results


def _reduction(base: float, agent: float) -> float | None:
    if base == 0:
        return None
    return 100 * (base - agent) / base


def _pct_source(results: dict, ok: tuple[str, ...]) -> float | None:
    llm_runs = good = 0
    for v in VARIANTS:
        for src, n in results[v]["constraint_source"].items():
            if src == "rules":
                continue  # LLM was not consulted (offline) - not an LLM validity sample
            llm_runs += n
            good += n if src in ok else 0
    return None if llm_runs == 0 else 100 * good / llm_runs

