"""Multi-seed evaluation: the season comparison repeated over independent seeds.

One seed gives one number per metric and no idea of its spread. Here every seed is a
new squad, fixture list and noise draw; within a seed all three policies face the same
world (common random numbers), so differences are paired. Reported: mean +/- SD over
seeds and a 95% confidence interval (t distribution) for the paired differences.

    python -m eval.seeds --seeds 10 --out ../docs/evaluation
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
import statistics
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from eval.harness import VARIANTS, executed_violations
from eval.metrics import season_metrics

POLICIES = ("baseline", "heuristic", "agents")
METRICS = ("acwr_spike_weeks", "monotony_weeks", "weekly_load_mean", "injuries", "injuries_in_phv")
# Two-sided 95% t quantiles for n - 1 degrees of freedom (n = number of seeds).
_T95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
        11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131, 19: 2.093, 24: 2.064, 29: 2.045}  # fmt: skip


def _t95(df: int) -> float:
    return _T95.get(df) or _T95[max(k for k in _T95 if k <= df)]


def one_season(args: tuple[int, str, bool]) -> dict:
    """All three policies on one seed and injury model (runs in a worker process)."""
    from simulator.agent_policy import AgentPolicy
    from simulator.policies import HeuristicPolicy
    from simulator.season import SeasonSimulator, load_config

    seed, variant, quick = args
    cfg = load_config()
    cfg["seed"] = seed
    if quick:
        cfg["n_players"], cfg["weeks"] = 8, 16
    out: dict = {"seed": seed, "variant": variant}
    for name, policy in (("baseline", None), ("heuristic", HeuristicPolicy()), ("agents", AgentPolicy())):
        res = SeasonSimulator(copy.deepcopy(cfg), policy=policy, injury_variant=variant).run()
        m = season_metrics(res)
        out[name] = {k: m[k] for k in METRICS} | {"rule_violations": sum(executed_violations(res).values())}
    return out


def _ci(xs: list[float]) -> dict:
    n = len(xs)
    mean = statistics.fmean(xs)
    sd = statistics.stdev(xs) if n > 1 else 0.0
    half = _t95(n - 1) * sd / math.sqrt(n) if n > 1 else float("nan")
    return {"mean": mean, "sd": sd, "lo": mean - half, "hi": mean + half, "n": n}


def summarise(rows: list[dict]) -> dict:
    out: dict = {}
    for variant in VARIANTS:
        vr = [r for r in rows if r["variant"] == variant]
        s: dict = {
            p: {k: _ci([r[p][k] for r in vr]) for k in (*METRICS, "rule_violations")} for p in POLICIES
        }
        for ref in ("baseline", "heuristic"):
            # Paired: per seed, % fewer spike weeks and the injury difference vs the reference.
            red = [
                100 * (r[ref]["acwr_spike_weeks"] - r["agents"]["acwr_spike_weeks"]) / r[ref]["acwr_spike_weeks"]
                for r in vr
                if r[ref]["acwr_spike_weeks"] > 0
            ]
            s[f"spike_reduction_vs_{ref}_pct"] = _ci(red) if red else None
            s[f"injury_diff_vs_{ref}"] = _ci([r["agents"]["injuries"] - r[ref]["injuries"] for r in vr])
            s[f"monotony_diff_vs_{ref}"] = _ci([r["agents"]["monotony_weeks"] - r[ref]["monotony_weeks"] for r in vr])
        out[variant] = s
    return out


def _f(c: dict | None, digits: int = 0) -> str:
    if c is None:
        return "n/a"
    return f"{c['mean']:.{digits}f} [{c['lo']:.{digits}f}, {c['hi']:.{digits}f}]"


def markdown(summary: dict, seeds: list[int], players: int, weeks: int) -> str:
    out = [
        f"# Multi-seed evaluation ({len(seeds)} seeds, {players} players x {weeks} weeks)",
        "",
        f"Seeds {seeds[0]}-{seeds[-1]}. Each seed is a new squad, fixture list and noise draw; within a seed the "
        "three policies face the same world, so differences are paired. Values: mean [95% CI] over seeds.",
        "",
        "- **baseline**: fixed weekly template with random RPE, blind to exams and fixtures (the plan's baseline).",
        "- **heuristic**: the same template plus a coach's rules of thumb as if-statements: no session on exam "
        "days, easy day before and rest after a match, speed capped in the growth window, minutes cut 10-20% when "
        "ACWR is high, recovery on pain / red mood / red readiness. No solver, no LLM.",
        "- **agents**: Monitor + CP-SAT planner + Coordinator, rule-based (no LLM).",
        "",
        "## Load spikes (player-weeks with ACWR > 1.5)",
        "",
        "| Injury model | Baseline | Heuristic | Agents | Agents vs baseline (% fewer) | Agents vs heuristic (% fewer) |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for v in VARIANTS:
        s = summary[v]
        out.append(
            f"| {v} | {_f(s['baseline']['acwr_spike_weeks'])} | {_f(s['heuristic']['acwr_spike_weeks'])} | "
            f"{_f(s['agents']['acwr_spike_weeks'])} | {_f(s['spike_reduction_vs_baseline_pct'])} | "
            f"{_f(s['spike_reduction_vs_heuristic_pct'])} |"
        )
    out += [
        "",
        "## Secondary: injuries, monotony, load, rule violations",
        "",
        "| Injury model | Policy | Injuries | Monotony > 2 weeks | Mean weekly load (AU) | Executed rule violations |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for v in VARIANTS:
        for p in POLICIES:
            m = summary[v][p]
            out.append(
                f"| {v} | {p} | {_f(m['injuries'], 1)} | {_f(m['monotony_weeks'], 1)} | "
                f"{_f(m['weekly_load_mean'])} | {_f(m['rule_violations'])} |"
            )
    out += [
        "",
        "## Paired differences, agents minus reference (negative = agents lower)",
        "",
        "| Injury model | Injuries vs baseline | Injuries vs heuristic | Monotony weeks vs baseline | Monotony weeks vs heuristic |",
        "| --- | --- | --- | --- | --- |",
    ]
    for v in VARIANTS:
        s = summary[v]
        out.append(
            f"| {v} | {_f(s['injury_diff_vs_baseline'], 1)} | {_f(s['injury_diff_vs_heuristic'], 1)} | "
            f"{_f(s['monotony_diff_vs_baseline'], 1)} | {_f(s['monotony_diff_vs_heuristic'], 1)} |"
        )
    out += [
        "",
        "A confidence interval that contains 0 means the difference is not distinguishable from seed-to-seed "
        "noise. Injuries come from a synthetic injury model, so they are a secondary result; and the agents' "
        "planner penalises projected ACWR directly, so fewer ACWR spikes is partly the objective being met, "
        "not independent evidence of benefit.",
    ]
    return "\n".join(out) + "\n"


def run(n_seeds: int = 10, first_seed: int = 2026, quick: bool = False, workers: int | None = None, log=print) -> dict:
    from simulator.season import load_config

    seeds = list(range(first_seed, first_seed + n_seeds))
    tasks = [(s, v, quick) for s in seeds for v in VARIANTS]
    workers = workers or max(1, min(len(tasks), (os.cpu_count() or 2) - 2))
    t0 = time.perf_counter()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        rows = list(pool.map(one_season, tasks))
    log(f"  {len(tasks)} seasons x 3 policies in {time.perf_counter() - t0:.0f} s ({workers} workers)")
    cfg = load_config()
    players, weeks = (8, 16) if quick else (cfg["n_players"], cfg["weeks"])
    return {"seeds": seeds, "players": players, "weeks": weeks, "rows": rows, "summary": summarise(rows)}


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", type=int, default=10)
    ap.add_argument("--first-seed", type=int, default=2026)
    ap.add_argument("--quick", action="store_true", help="8 players x 16 weeks")
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--out", type=Path, default=Path("eval_results"))
    args = ap.parse_args(argv)
    r = run(args.seeds, args.first_seed, args.quick, args.workers)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "seeds.json").write_text(json.dumps(r, indent=2), encoding="utf-8")
    md = markdown(r["summary"], r["seeds"], r["players"], r["weeks"])
    (args.out / "seeds.md").write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
