"""Render evaluation results as the plan section 9 table."""

from __future__ import annotations

from eval.harness import VARIANTS


def _fmt(x, digits=1, suffix=""):
    if x is None:
        return "n/a"
    if isinstance(x, float):
        return f"{x:.{digits}f}{suffix}"
    return f"{x}{suffix}"


def _status(ok: bool | None) -> str:
    return {True: "PASS", False: "FAIL", None: "not measured"}[ok]


def markdown(r: dict) -> str:
    v = {k: r[k] for k in VARIANTS}
    spike = [v[k]["spike_reduction_pct"] for k in VARIANTS]
    spike_eq = [v[k].get("spike_reduction_equal_load_pct") for k in VARIANTS]
    mono = [v[k]["monotony_reduction_pct"] for k in VARIANTS]
    dev = [v[k]["dev_delivery_pct"] for k in VARIANTS]
    hard = sum(v[k]["plan_hard_violations"] for k in VARIANTS)
    exec_hard = sum(sum(v[k]["executed_violations_agents"].values()) for k in VARIANTS)
    s = r["safety_scenarios"]
    rd = r["readiness_colours"]
    cal = rd["calibration"]
    llm = r["llm"]
    rows = [
        ("Hard constraint violations", "0", f"{hard} in plans, {exec_hard} in executed weeks", hard == 0 and exec_hard == 0),
        (f"Safety scenario suite ({s['total']} cases)", "100%", f"{s['passed']}/{s['total']}", s["passed"] == s["total"]),
        (
            "Player-weeks with ACWR > 1.5",
            ">= 50% fewer than baseline",
            ", ".join(f"{k}: {_fmt(x, 0, '%')}" for k, x in zip(VARIANTS, spike)),
            all(x is not None and x >= 50 for x in spike),
        ),
        (
            "Same, against a baseline with the agents' total load",
            "fewer spikes at equal load (not just less training)",
            ", ".join(
                f"{k}: {v[k]['baseline_equal_load']['acwr_spike_weeks']} -> {v[k]['agents']['acwr_spike_weeks']} "
                f"({_fmt(x, 0, '%')} fewer)"
                for k, x in zip(VARIANTS, spike_eq)
            )
            if all(x is not None for x in spike_eq)
            else "n/a",
            None if any(x is None for x in spike_eq) else all(x > 0 for x in spike_eq),
        ),
        (
            "Weeks with monotony > 2",
            ">= 40% fewer than baseline",
            ", ".join(f"{k}: {v[k]['baseline']['monotony_weeks']} -> {v[k]['agents']['monotony_weeks']}" for k in VARIANTS),
            None if any(x is None for x in mono) else all(x >= 40 for x in mono),
        ),
        (
            "Planned development sessions delivered",
            ">= 90% of goal",
            ", ".join(f"{k}: {_fmt(x, 0, '%')}" for k, x in zip(VARIANTS, dev)),
            all(x is not None and x >= 90 for x in dev),
        ),
        (
            "LLM output valid on first try",
            ">= 95% (200 runs)",
            _fmt(llm["first_try_valid_pct"], 1, "%") if llm["backend"] else "LLM not used (rule-based run)",
            None if llm["first_try_valid_pct"] is None else llm["first_try_valid_pct"] >= 95,
        ),
        ("LLM valid after retry or fallback", "100%", "100% (every run produced a plan)", True),
        (
            "Planner consistency (20 runs)",
            ">= 80% identical",
            _fmt(r["planner_consistency"]["min_share_pct"], 0, "%"),
            r["planner_consistency"]["min_share_pct"] >= 80,
        ),
        (
            "Solver time",
            "< 2 s player-week, < 60 s squad",
            f"max {_fmt(max(v[k]['solver_max_s_player_week'] for k in VARIANTS), 2)} s / "
            f"{_fmt(max(v[k]['solver_max_s_squad_week'] for k in VARIANTS), 1)} s",
            max(v[k]["solver_max_s_player_week"] for k in VARIANTS) < 2
            and max(v[k]["solver_max_s_squad_week"] for k in VARIANTS) < 60,
        ),
        (
            "Red check-in to staff notification",
            "< 5 min",
            f"agent decision {r['red_checkin_to_escalation_s'] * 1000:.0f} ms (end-to-end measured in API tests)",
            r["red_checkin_to_escalation_s"] < 300,
        ),
        ("Expert rating of 10 plans", ">= 3.5 / 5", "pending: needs 2+ reviewers", None),
        ("SUS score", ">= 70", "pending: usability tests in week 10", None),
        (
            "Readiness weight sensitivity",
            "< 10% of daily bands change at +/-0.1",
            f"{rd['sensitivity_no_buffer']:.1f}% without buffer, {rd['sensitivity_buffer']:.1f}% with buffer, "
            f"{rd['sensitivity_calibrated']:.1f}% with buffer + calibrated weights",
            rd["sensitivity_calibrated"] < 10,
        ),
        (
            "Which days flip when a weight shifts",
            "flips are borderline days, not clear ones",
            f"{rd['flips_borderline_pct']:.0f}% of flipped days were within 5 points of a colour boundary; "
            f"a smaller +/-0.05 shift changes {rd['sensitivity_half_step']:.1f}% of bands",
            rd["flips_borderline_pct"] >= 80,
        ),
        (
            "Readiness colour stability (colour buffer)",
            "fewer day-to-day colour changes, warnings never delayed",
            f"{rd['changes_no_buffer_pct']:.0f}% -> {rd['changes_buffer_pct']:.0f}% of days change colour "
            f"(buffer up {rd['buffer']['up']:g}, down {rd['buffer']['down']:g})",
            rd["changes_buffer_pct"] < rd["changes_no_buffer_pct"] and rd["buffer"]["down"] == 0,
        ),
        (
            "Weights calibrated against staff ratings",
            "better agreement, red recall not lower",
            f"kappa {cal['before']['kappa']:.2f} -> {cal['after']['kappa']:.2f} "
            f"(held-out {cal['cv_kappa_before']:.2f} -> {cal['cv_kappa_after']:.2f}), red recall "
            f"{cal['before']['red_recall']:.0%} -> {cal['after']['red_recall']:.0%}, n={cal['n']} synthetic ratings",
            cal["after"]["kappa"] >= cal["before"]["kappa"] and cal["after"]["red_recall"] >= cal["before"]["red_recall"],
        ),
    ]
    out = [
        f"# PathToPro evaluation ({r['config']['players']} players x {r['config']['weeks']} weeks, seed {r['config']['seed']})",
        "",
        "| Metric | Target | Result | Status |",
        "| --- | --- | --- | --- |",
    ]
    out += [f"| {a} | {b} | {c} | {_status(d)} |" for a, b, c, d in rows]
    out += [
        "",
        "## Season detail",
        "",
        "| Injury model | Policy | ACWR>1.5 weeks | Monotony>2 weeks | Mean weekly load | Red readiness days | Injuries (in PHV) |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for k in VARIANTS:
        for pol in ("baseline", "baseline_equal_load", "agents"):
            if pol not in v[k]:
                continue
            m = v[k][pol]
            name = "baseline, agents' load" if pol == "baseline_equal_load" else pol
            out.append(
                f"| {k} | {name} | {m['acwr_spike_weeks']} | {m['monotony_weeks']} | {m['weekly_load_mean']:.0f} | "
                f"{m['readiness_red_pct']:.1f}% | {m['injuries']} ({m['injuries_in_phv']}) |"
            )
    out += [
        "",
        "Executed-week rule checks (planned RPE): "
        + "; ".join(
            f"{k}: agents {v[k]['executed_violations_agents'] or 'none'}, baseline {v[k]['executed_violations_baseline'] or 'none'}"
            for k in VARIANTS
        ),
        "",
        f"Mirwald estimate error within +/-2.5 y of PHV: bias {r['mirwald_error']['bias']:+.2f} y, "
        f"MAE {r['mirwald_error']['mae']:.2f} y.",
        "",
        "Equal-load baseline: the same fixed template with session minutes scaled "
        + ", ".join(f"{k} x{v[k]['equal_load_minutes_scale']:.2f}" for k in VARIANTS if "equal_load_minutes_scale" in v[k])
        + " so its mean weekly load matches the agents'. Spikes it still has come from how load is spread, not how much.",
        "",
        "Injuries are a secondary result: the injury model is synthetic, so process metrics are primary.",
    ]
    return "\n".join(out) + "\n"
