"""Season-level process metrics (plan section 9).

Primary results are process metrics (spikes, monotony, constraints held), which do
not depend on the injury model. Injuries are reported as a secondary result.
"""

from __future__ import annotations

import statistics
from collections import defaultdict

from analytics.load import ACWR_FLAG_THRESHOLD, MONOTONY_FLAG_THRESHOLD, monotony
from analytics.maturation import maturity_offset
from simulator.season import SeasonResult


def season_metrics(res: SeasonResult) -> dict[str, float]:
    weeks: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for row in res.daily:
        weeks[(row["player_id"], row["week"])].append(row)

    spike_weeks = mono_weeks = 0
    weekly_loads = []
    for rows in weeks.values():
        loads = [r["load"] for r in rows]
        weekly_loads.append(sum(loads))
        if max(r["acwr"] for r in rows) > ACWR_FLAG_THRESHOLD:
            spike_weeks += 1
        m = monotony(loads) if len(loads) == 7 else None
        if m is not None and m > MONOTONY_FLAG_THRESHOLD:
            mono_weeks += 1

    scores = [r["readiness"] for r in res.daily if r["readiness"] is not None]
    sleep = [c["sleep_hours"] for c in res.checkins]
    hrv = [c["ln_rmssd"] for c in res.checkins]
    n_pw = len(weeks)
    return {
        "player_weeks": n_pw,
        "acwr_spike_weeks": spike_weeks,
        "acwr_spike_pct": 100 * spike_weeks / n_pw,
        "monotony_weeks": mono_weeks,
        "monotony_pct": 100 * mono_weeks / n_pw,
        "weekly_load_mean": statistics.fmean(weekly_loads),
        "weekly_load_sd": statistics.pstdev(weekly_loads),
        "sleep_mean": statistics.fmean(sleep),
        "sleep_sd": statistics.pstdev(sleep),
        "ln_rmssd_mean": statistics.fmean(hrv),
        "readiness_mean": statistics.fmean(scores),
        "readiness_red_pct": 100 * sum(s < 50 for s in scores) / len(scores),
        "readiness_green_pct": 100 * sum(s >= 70 for s in scores) / len(scores),
        "checkin_compliance_pct": 100 * sum(c["completed"] for c in res.checkins) / len(res.checkins),
        "injuries": len(res.injuries),
        "injuries_in_phv": sum(i["in_phv_window"] for i in res.injuries),
        "pain_reports": sum(c["pain_reported"] for c in res.checkins),
        "red_mood_checkins": sum(c["mood_red"] for c in res.checkins),
    }


def mirwald_error(res: SeasonResult) -> dict[str, float]:
    """How well Mirwald on the simulated anthropometrics recovers the true offset,
    within the +/-2.5 years of PHV where the estimate is actually used."""
    phv = {p["player_id"]: p["phv_age"] for p in res.players}
    errors = []
    for a in res.anthropometrics:
        true = a["age"] - phv[a["player_id"]]
        if abs(true) > 2.5:
            continue
        est = maturity_offset(a["age"], a["height_cm"], a["sitting_height_cm"], a["weight_kg"])
        errors.append(est - true)
    return {"bias": statistics.fmean(errors), "mae": statistics.fmean(abs(e) for e in errors)}
