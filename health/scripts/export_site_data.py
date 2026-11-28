"""Write compact JSON for the website, so the landing page can read results without running the
model.

    python scripts/export_site_data.py [--city NAME ...] [--out DIR] [--rank-dir DIR]
                                       [--with-regions] [--n N] [--skip-score]

Writes, into health/out/site/ (git ignores health/out/; nothing here is committed):

    index.json                 what was written, and when
    ranking/<city>.json        the ranking of the measure library in one city: one table per curve
    score/bengaluru.json       the Bengaluru score: every measure on every curve (airhealth score)
    sensitivity/<place>.json   the research lists (which inputs reorder the ranking), when a
                               sensitivity run exists (airhealth rank PLACE --sensitivity --write)

Every file is {"generated", "commit", "sources", "data"}: when it was written, the commit of the
code, a plain sentence saying what it was made from, and the content. The ranking is read from
health/out/rank/rank_<city>.json when that exists (write it with airhealth rank PLACE --write).
If a city has none, this runs the ranking for that city alone, scoring only the city measures:
the regional measures (stubble, power plants) get no ratio, because that needs a whole-region
run that takes minutes. Pass --with-regions to do that run. Cities: every city with a rank
output, or --city (repeatable); with neither, Bengaluru. The per-measure "trail" (the long
audit record behind each row) is left out to keep the files small; the rank outputs keep it.

Repository script, not part of the installed package: the commit it records comes from
`git rev-parse` run in the checkout, so run it from a clone.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from airhealth import paths, places, rank, score, simulate

DEFAULT_OUT = paths.HEALTH / "out" / "site"
DEFAULT_RANK_DIR = paths.HEALTH / "out" / "rank"
NOT_CITY_FILES = ("india",)
SENSITIVITY_KEEP = ("place", "top", "notes", "research", "research_comparable", "noise_sets",
                    "noise_sets_comparable", "whatifs")
NO_REGION_RUN = ("its whole reach was not scored: export_site_data.py ran this city alone "
                 "(pass --with-regions to score it)")


def slug(name: str) -> str:
    return name.lower().replace(" ", "_")


def commit() -> str:
    """The code's commit, with -dirty if files differ from it; 'unknown' outside a checkout."""
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=paths.REPO, capture_output=True,
                             text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"],
                               cwd=paths.REPO, capture_output=True, text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return sha + ("-dirty" if dirty else "")


def wrap(data, *, sources: str) -> dict:
    return {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "commit": commit(), "sources": sources, "data": data}


def write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":"), allow_nan=False))


def cities_with_output(rank_dir: Path) -> list[str]:
    """Place names of the rank_<city>.json files (not India's), sorted."""
    names = []
    for f in sorted(rank_dir.glob("rank_*.json")):
        if f.stem[len("rank_"):] in NOT_CITY_FILES:
            continue
        names.append(json.loads(f.read_text())["place"])
    return sorted(names)


def _lean(ranking: dict) -> dict:
    """The ranking without each row's trail."""
    out = dict(ranking)
    out["tables"] = {c: {**t, "rows": [{k: v for k, v in r.items() if k != "trail"}
                                       for r in t["rows"]]}
                     for c, t in ranking["tables"].items()}
    out["parts"] = {k: _lean(v) for k, v in ranking.get("parts", {}).items()}
    return out


def ranking_for(city: str, rank_dir: Path, *, with_regions: bool, n: int) -> dict:
    path = rank_dir / f"rank_{slug(city)}.json"
    if path.exists():
        data = json.loads(path.read_text())
        when = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).strftime("%Y-%m-%d")
        ctx = data.get("context", {})
        note = (f"Read from {path.name}, written {when} by airhealth rank (map {ctx.get('map')}, "
                f"study {ctx.get('study')}, n {ctx.get('n')}, seed {ctx.get('seed')}). "
                "Inputs and their sources: health/data/sources.toml.")
        return wrap(_lean(data), sources=note)
    if with_regions:
        ranking = rank.city(city, n=n)
        note = (f"Ran airhealth rank {city} (n {n}, seed 0), with the whole-region run for the "
                "regional measures.")
    else:
        scores = score.city(city, n=n)
        wanted = [s.measure for s in scores if s.scope == "region" and s.status == "scored"]
        context = rank._context(scores, None, map_name="acag_total", curves=None, n=n, seed=0,
                                discount=simulate.DISCOUNT, deaths=None)
        ranking = rank.from_scores(scores, city, context,
                                   regional_missing={m: NO_REGION_RUN for m in wanted})
        note = (f"Ran airhealth rank {city} (n {n}, seed 0) for this city alone, city measures "
                "only: no whole-region run, so regional measures have no ratio.")
    return wrap(_lean(rank.to_json(ranking)),
                sources=note + " Inputs and their sources: health/data/sources.toml.")


def score_for(city: str, n: int) -> dict:
    scores = score.city(city, n=n)
    return wrap(score.to_json(scores),
                sources=f"Ran airhealth score {city} (n {n}, seed 0, default map and study). "
                        "Inputs and their sources: health/data/sources.toml.")


def sensitivity_for(name: str, rank_dir: Path) -> dict | None:
    path = rank_dir / f"sensitivity_{slug(name)}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    when = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).strftime("%Y-%m-%d")
    return wrap({k: data[k] for k in SENSITIVITY_KEEP if k in data},
                sources=f"The research lists of {path.name}, written {when} by airhealth rank "
                        f"{data.get('place', name)} --sensitivity; the rest of that file "
                        "(every setting's ranks) is left out.")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--city", action="append", help="a city to write (repeatable)")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--rank-dir", type=Path, default=DEFAULT_RANK_DIR)
    ap.add_argument("--with-regions", action="store_true",
                    help="for a city with no rank output, also score the regional measures' "
                         "whole reach (minutes)")
    ap.add_argument("--n", type=int, default=2000, help="draws when a run is needed")
    ap.add_argument("--skip-score", action="store_true", help="leave out the Bengaluru score")
    args = ap.parse_args(argv)

    if args.city:
        cities = []
        for c in args.city:
            try:
                cities.append(places.resolve(c, kind="city").name)
            except KeyError:
                sys.exit(f"export_site_data: unknown city {c!r}; see airhealth list places")
    else:
        cities = cities_with_output(args.rank_dir) or ["Bengaluru"]

    written = {"cities": [], "score": [], "sensitivity": []}
    for city in cities:
        doc = ranking_for(city, args.rank_dir, with_regions=args.with_regions, n=args.n)
        write(args.out / "ranking" / f"{slug(city)}.json", doc)
        written["cities"].append({"city": city, "file": f"ranking/{slug(city)}.json",
                                  "sources": doc["sources"]})
        print(f"export_site_data: ranking/{slug(city)}.json", file=sys.stderr)
    if not args.skip_score:
        doc = score_for("Bengaluru", args.n)
        write(args.out / "score" / "bengaluru.json", doc)
        written["score"].append({"city": "Bengaluru", "file": "score/bengaluru.json"})
        print("export_site_data: score/bengaluru.json", file=sys.stderr)
    for name in [*cities, "India"]:
        doc = sensitivity_for(name, args.rank_dir)
        if doc is not None:
            write(args.out / "sensitivity" / f"{slug(name)}.json", doc)
            written["sensitivity"].append({"place": name, "file": f"sensitivity/{slug(name)}.json"})
            print(f"export_site_data: sensitivity/{slug(name)}.json", file=sys.stderr)
    write(args.out / "index.json",
          wrap(written, sources="List of the files written by export_site_data.py in this run."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
