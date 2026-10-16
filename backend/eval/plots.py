"""Realism check plots: simulated distributions next to typical published ranges."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from simulator.season import SeasonResult  # noqa: E402

# Typical ranges reported for academy / adolescent players. Used as a visual sanity
# check only; see docs/evaluation.md for the caveats.
RANGES = {
    "weekly_load": (1500, 3000, "Weekly sRPE load (AU)"),
    "sleep": (7.0, 9.0, "Sleep per night (h)"),
    "ln_rmssd": (3.5, 4.8, "Morning lnRMSSD"),
}


def _weekly_loads(res: SeasonResult) -> list[float]:
    w = defaultdict(float)
    injured = {(r["player_id"], r["week"]) for r in res.daily if r["injured"]}
    for r in res.daily:
        if (r["player_id"], r["week"]) not in injured:
            w[(r["player_id"], r["week"])] += r["load"]
    return list(w.values())


def realism_plots(baseline: SeasonResult, agents: SeasonResult, out_dir: Path) -> Path:
    data = {
        "weekly_load": (_weekly_loads(baseline), _weekly_loads(agents)),
        "sleep": ([c["sleep_hours"] for c in baseline.checkins], None),
        "ln_rmssd": ([c["ln_rmssd"] for c in baseline.checkins], None),
    }
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.6))
    for ax, (key, (base, agent)) in zip(axes, data.items()):
        lo, hi, title = RANGES[key]
        ax.axvspan(lo, hi, color="#2e7d32", alpha=0.12, label="typical range")
        ax.hist(base, bins=30, color="#546e7a", alpha=0.75, label="baseline")
        if agent is not None:
            ax.hist(agent, bins=30, color="#1565c0", alpha=0.55, label="agents")
        ax.set_title(title, fontsize=10)
        ax.spines[["top", "right"]].set_visible(False)
        ax.legend(fontsize=8, frameon=False)
    fig.tight_layout()
    path = out_dir / "realism.png"
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path
