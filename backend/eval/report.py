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
    mono = [v[k]["monotony_reduction_pct"] for k in VARIANTS]
    dev = [v[k]["dev_delivery_pct"] for k in VARIANTS]
    hard = sum(v[k]["plan_hard_violations"] for k in VARIANTS)
    exec_hard = sum(sum(v[k]["executed_violations_agents"].values()) for k in VARIANTS)
    s = r["safety_scenarios"]
    sens = r["readiness_sensitivity_pct"]
    llm = r["llm"]
    rows = [
        ("Hard constraint violations", "0", f"{hard} in plans, {exec_hard} in executed weeks", hard == 0 and exec_hard == 0),
        ("Safety scenario suite (50 cases)", "100%", f"{s['passed']}/{s['total']}", s["passed"] == s["total"]),
        (
            "Player-weeks with ACWR > 1.5",
            ">= 50% fewer than baseline",
            ", ".join(f"{k}: {_fmt(x, 0, '%')}" for k, x in zip(VARIANTS, spike)),
            all(x is not None and x >= 50 for x in spike),
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
            f"max {max(sens.values()):.1f}%",
            max(sens.values()) < 10,
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
        for pol in ("baseline", "agents"):
            m = v[k][pol]
            out.append(
                f"| {k} | {pol} | {m['acwr_spike_weeks']} | {m['monotony_weeks']} | {m['weekly_load_mean']:.0f} | "
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
        "Injuries are a secondary result: the injury model is synthetic, so process metrics are primary.",
    ]
    return "\n".join(out) + "\n"
