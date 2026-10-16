"""python -m eval [--quick] [--llm] [--out DIR]: run the full evaluation and print the report."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from agents.llm import default_backend
from eval.harness import VARIANTS, run
from eval.report import markdown


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--quick", action="store_true", help="8 players x 16 weeks (CI smoke run)")
    ap.add_argument("--llm", action="store_true", help="use Claude (cached) for the agents; default is rule-based")
    ap.add_argument("--out", type=Path, default=Path("eval_results"))
    args = ap.parse_args(argv)
    llm = default_backend() if args.llm else None
    t0 = time.perf_counter()
    print(f"Running evaluation ({'quick' if args.quick else 'full'}, variants: {', '.join(VARIANTS)})")
    results = run(quick=args.quick, llm=llm, out_dir=args.out)
    report = markdown(results)
    (args.out / "report.md").write_text(report, encoding="utf-8")
    print(report)
    print(f"Done in {time.perf_counter() - t0:.0f} s. Results in {args.out}/")


if __name__ == "__main__":
    main()
