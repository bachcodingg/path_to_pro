"""Generate a synthetic season: python -m simulator [--config F] [--out DIR] [--variant V]."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from eval.metrics import mirwald_error, season_metrics
from simulator.season import DEFAULT_CONFIG, SeasonSimulator, load_config


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    ap.add_argument("--out", type=Path, default=Path("data/season"))
    ap.add_argument("--variant", choices=["load", "readiness", "random"], default=None)
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    if args.seed is not None:
        cfg["seed"] = args.seed
    t0 = time.perf_counter()
    res = SeasonSimulator(cfg, injury_variant=args.variant).run()
    elapsed = time.perf_counter() - t0
    paths = res.to_csv(args.out)

    print(f"Season: {cfg['n_players']} players x {cfg['weeks']} weeks, policy={res.policy}, "
          f"injury model={res.variant}, seed={res.seed} ({elapsed:.1f} s)")
    for k, v in season_metrics(res).items():
        print(f"  {k:24s} {v:10.2f}" if isinstance(v, float) else f"  {k:24s} {v:10d}")
    err = mirwald_error(res)
    print(f"  {'mirwald_bias_years':24s} {err['bias']:10.2f}")
    print(f"  {'mirwald_mae_years':24s} {err['mae']:10.2f}")
    print(f"Wrote {len(paths)} CSV files to {args.out}")


if __name__ == "__main__":
    main()
