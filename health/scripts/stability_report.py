"""Is a city's top of the table the same on every curve, map and causes study?

    cd health && PYTHONPATH=. ../.venv/bin/python scripts/stability_report.py Bengaluru [--n 500]
        [--seed 0] [--top 3] [--jobs 10] [--out out/]

Prints the report and writes stability_<city>.json and .txt to health/out/ (git-ignored). See
airhealth/stability.py for what it checks.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from airhealth import stability


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("city")
    ap.add_argument("--n", type=int, default=500, help="Monte Carlo draws (default 500)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--top", type=int, default=stability.TOP)
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 1,
                    help="processes for the whole-reach runs of regional measures")
    ap.add_argument("--out", type=Path, default=stability.OUT)
    a = ap.parse_args(argv)
    rep = stability.report(a.city, n=a.n, seed=a.seed, top=a.top, jobs=a.jobs,
                           progress=lambda t: print(f"stability: {t}", file=sys.stderr))
    print(stability.text(rep))
    for p in stability.write(rep, a.out):
        print(f"stability: wrote {p}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
