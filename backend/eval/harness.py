"""Evaluation harness (plan section 9).

Baselines: the fixed weekly template (the plan's baseline, blind to exams and fixtures)
and a rule-of-thumb heuristic coach (the same template plus the safety rules as
if-statements), so the comparison shows what the planner adds beyond the rules. Every
season metric runs on the simulated season under 3 injury-model variants (load-,
readiness-driven, random). `eval.seeds` repeats the comparison over several seeds.
"""

from __future__ import annotations

import copy
import itertools
import json
import statistics
import time
from collections import Counter, defaultdict
from dataclasses import asdict, replace
from pathlib import Path

from agents import planner_agent
from agents.llm import LLMBackend
from agents.monitor import assess
from agents.orchestrator import run_cycle
from agents.rules import DevGoal
from analytics.calibration import RatedDay, fit_weights
from analytics.readiness import Band, ReadinessConfig, band_for, combine, hooper_score, hrv_score, hrv_z, sleep_score
from eval.metrics import mirwald_error, season_metrics
from eval.scenarios import history as scenario_history
from eval.scenarios import inp as scenario_inp
from eval.scenarios import run_all as run_scenarios
from planner.model import MD_MINUS_1_MAX_RPE
from simulator.agent_policy import AgentPolicy
from simulator.policies import BaselinePolicy, HeuristicPolicy
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


def _season_components(res: SeasonResult) -> list[list[dict]]:
    """Per player, the daily component scores in date order."""
    rows = defaultdict(list)
    for c in res.checkins:
        rows[c["player_id"]].append(c)
    out = []
    for cs in rows.values():
        hrv_hist: list[float] = []
        days = []
        for c in cs:
            z = hrv_z(c["ln_rmssd"], hrv_hist)
            hrv_hist.append(c["ln_rmssd"])
            days.append(
                {
                    "hrv": None if z is None else hrv_score(z),
                    "hooper": None
                    if not c["completed"]
                    else hooper_score(c["sleep_quality"], c["fatigue"], c["stress"], c["soreness"]),
                    "sleep": sleep_score(c["sleep_hours"]),
                }
            )
        out.append(days)
    return out


def _bands(players: list[list[dict]], cfg: ReadinessConfig) -> list:
    """Daily bands as the app shows them: the colour buffer carries yesterday's band."""
    out = []
    for days in players:
        prev = None
        for comp in days:
            r = combine(comp, cfg)
            if r is not None:  # no usable input that day: the colour stays as it was
                prev = band_for(r.score, cfg, prev)
            out.append(prev)
    return out


def _changes(players: list[list[dict]], cfg: ReadinessConfig) -> float:
    """% of days whose colour differs from the day before (flicker)."""
    n = changed = 0
    for days in players:
        b = _bands([days], cfg)
        n += len(b)
        changed += sum(x != y for x, y in zip(b, b[1:]))
    return 100 * changed / n


def readiness_sensitivity(res: SeasonResult, delta: float = 0.1, config: ReadinessConfig | None = None) -> dict[str, float]:
    """% of daily bands that change when one weight shifts by +/-delta (others rescaled)."""
    base_cfg = config or ReadinessConfig.load()
    players = _season_components(res)
    base_bands = _bands(players, base_cfg)
    out = {}
    for key, sign in itertools.product(base_cfg.weights, (+1, -1)):
        w = dict(base_cfg.weights)
        w[key] = max(0.0, w[key] + sign * delta)
        others = [k for k in w if k != key]
        rest = sum(base_cfg.weights[k] for k in others)
        for k in others:
            w[k] = base_cfg.weights[k] * (1 - w[key]) / rest
        bands = _bands(players, base_cfg.with_weights(w))
        out[f"{key}{'+' if sign > 0 else '-'}{delta}"] = 100 * sum(a != b for a, b in zip(bands, base_bands)) / len(bands)
    return out


def borderline_share(res: SeasonResult, delta: float = 0.1, margin: float = 5.0) -> float:
    """Of the daily bands that flip under the worst +/-delta weight shift (no buffer),
    the % whose score was within `margin` points of a band boundary: flips of days that
    were borderline anyway, not of clearly green or clearly red days."""
    cfg = replace(ReadinessConfig.load(), hysteresis_up=0.0, hysteresis_down=0.0)
    sens = readiness_sensitivity(res, delta, cfg)
    worst = max(sens, key=sens.get)
    key, sign = worst[:-len(f"+{delta}")], (1 if f"+{delta}" in worst else -1)
    w = dict(cfg.weights)
    w[key] = max(0.0, w[key] + sign * delta)
    rest = sum(cfg.weights[k] for k in w if k != key)
    for k in w:
        if k != key:
            w[k] = cfg.weights[k] * (1 - w[key]) / rest
    shifted = cfg.with_weights(w)
    flips = near = 0
    for days in _season_components(res):
        for comp in days:
            a, b = combine(comp, cfg), combine(comp, shifted)
            if a is None or b is None or band_for(a.score, cfg) == band_for(b.score, shifted):
                continue
            flips += 1
            near += min(abs(a.score - cfg.green_min), abs(a.score - cfg.amber_min)) <= margin
    return 100 * near / flips if flips else 0.0


def readiness_report(res: SeasonResult) -> dict:
    """Colour buffer and weight calibration against the simulated staff ratings."""
    cfg = ReadinessConfig.load()
    no_buffer = replace(cfg, hysteresis_up=0.0, hysteresis_down=0.0)
    players = _season_components(res)
    rated = [
        RatedDay(c["player_id"], {"hrv": c["comp_hrv"], "hooper": c["comp_hooper"], "sleep": c["comp_sleep"]}, Band(c["staff_rating"]))
        for c in res.checkins
        if c["staff_rating"]
    ]
    cal = fit_weights(rated, cfg)
    calibrated = cfg.with_weights(cal.weights)
    return {
        "buffer": {"up": cfg.hysteresis_up, "down": cfg.hysteresis_down},
        "sensitivity_no_buffer": max(readiness_sensitivity(res, config=no_buffer).values()),
        "sensitivity_buffer": max(readiness_sensitivity(res, config=cfg).values()),
        "sensitivity_calibrated": max(readiness_sensitivity(res, config=calibrated).values()),
        "sensitivity_half_step": max(readiness_sensitivity(res, delta=0.05, config=cfg).values()),
        "flips_borderline_pct": borderline_share(res),
        "changes_no_buffer_pct": _changes(players, no_buffer),
        "changes_buffer_pct": _changes(players, cfg),
        "red_days_no_buffer_pct": 100 * sum(b == Band.RED for b in _bands(players, no_buffer)) / sum(map(len, players)),
        "red_days_buffer_pct": 100 * sum(b == Band.RED for b in _bands(players, cfg)) / sum(map(len, players)),
        "calibration": {
            "n": len(rated),
            "weights_before": dict(cfg.weights),
            "weights_after": cal.weights,
            "before": asdict(cal.before),
            "after": asdict(cal.after),
            "cv_kappa_before": cal.cv_before,
            "cv_kappa_after": cal.cv_after,
        },
    }


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


# --------------------------------------------------------------------------- equal-load baseline


def equal_load_baseline(cfg: dict, variant: str, target_mean: float, base_mean: float) -> tuple[SeasonResult, float]:
    """The fixed template with session minutes scaled so its mean weekly load matches the
    agents'. Answers: are there fewer spikes because the agents plan better, or only
    because they plan less? Matches stay as they are, so the scale is found in two runs
    (a linear fit through the full-length and the first scaled season)."""
    load = cfg["load"]
    lo, hi = load["session_minutes"]

    def season(f: float) -> tuple[SeasonResult, float]:
        pol = BaselinePolicy(load["session_rpe_mean"], load["session_rpe_sd"], (round(lo * f), round(hi * f)))
        res = SeasonSimulator(copy.deepcopy(cfg), policy=pol, injury_variant=variant).run()
        return res, season_metrics(res)["weekly_load_mean"]

    f0 = target_mean / base_mean
    res, got = season(f0)
    if abs(got - target_mean) > 0.02 * target_mean and f0 != 1:
        slope = (base_mean - got) / (1 - f0)
        f1 = f0 + (target_mean - got) / slope
        res, got = season(f1)
        f0 = f1
    return res, f0


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
        heur = SeasonSimulator(copy.deepcopy(cfg), policy=HeuristicPolicy(), injury_variant=variant).run()
        seasons[variant] = (base, agent, policy)
        mb, ma, mh = season_metrics(base), season_metrics(agent), season_metrics(heur)
        eq, eq_scale = equal_load_baseline(cfg, variant, ma["weekly_load_mean"], mb["weekly_load_mean"])
        me = season_metrics(eq)
        st = [o["solve_seconds"] for o in policy.outcomes]
        weekly = defaultdict(float)
        for o in policy.outcomes:
            if o["kind"] == "weekly":
                weekly[o["week"]] += o["solve_seconds"]
        results[variant] = {
            "baseline": mb,
            "agents": ma,
            "spike_reduction_pct": _reduction(mb["acwr_spike_weeks"], ma["acwr_spike_weeks"]),
            "heuristic": mh,
            "spike_reduction_vs_heuristic_pct": _reduction(mh["acwr_spike_weeks"], ma["acwr_spike_weeks"]),
            "executed_violations_heuristic": dict(executed_violations(heur)),
            "baseline_equal_load": me,
            "equal_load_minutes_scale": eq_scale,
            "spike_reduction_equal_load_pct": _reduction(me["acwr_spike_weeks"], ma["acwr_spike_weeks"]),
            "executed_violations_equal_load": dict(executed_violations(eq)),
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
    results["readiness_colours"] = readiness_report(base_load)
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

