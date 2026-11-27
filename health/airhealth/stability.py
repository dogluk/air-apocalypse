"""Is a city's top of the table the same whichever way it is computed?

For one city, ranks the measure library once for every exposure map in MAPS (those present) and
every causes study the city has with a complete split, and reports for each combination:

  - whether the top K (default 3) is the same on every curve: the same measures in the same order
    (same_top), or at least the same measures (same_members); among all ranked measures and among
    comparable ones (costs that leave part out, flag partial_cost, set aside);
  - each measure's largest rank move across curves (worst minus best; never an average).

And, as the scale of the problem behind the ranking, the deaths attributable to PM2.5 on the CPCB
monitor map, curve by curve, with the lowest and highest (a spread, not a central figure).

Regional measures are ranked by their whole reach, which needs a district map (acag_total,
aqli); on the other maps they are not scored and drop out of the table. Their reaches are scored
once per map and shared by every study (sensitivity.py's cache).

    PYTHONPATH=. python scripts/stability_report.py Bengaluru [--n 500] [--jobs 10]
"""
from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from pathlib import Path

from . import causes, curves as curves_, exposure, measures, paths, places, rank, score, simulate
from .impact import Change, steady_state
from .inputs import Sources

MAPS = ("acag_total", "aqli", "cpcb", "gbd2023")
BURDEN_MAP = "cpcb"
TOP = 3
OUT = paths.HEALTH / "out"


def _top(r: rank.Ranking, curve: str, k: int, comparable: bool) -> list[str]:
    key = "rank_comparable" if comparable else "rank"
    rows = [x for x in r.tables[curve].rows if getattr(x, key) is not None]
    return [x.measure for x in sorted(rows, key=lambda x: getattr(x, key))[:k]]


def top_check(r: rank.Ranking, k: int = TOP, comparable: bool = False) -> dict:
    """{"top": curve -> first k measure ids, "same_top": the same list on every curve,
    "same_members": the same set on every curve}."""
    top = {c: _top(r, c, k, comparable) for c in r.tables}
    lists = list(top.values())
    return {"top": top, "same_top": all(x == lists[0] for x in lists),
            "same_members": all(set(x) == set(lists[0]) for x in lists)}


def moves(r: rank.Ranking) -> dict[str, dict]:
    """measure -> best, worst, move (worst - best) across curves, and the same among comparable
    measures (None where it is not ranked)."""
    out = {}
    for m, d in r.spread.items():
        def gap(lo, hi):
            return None if lo is None or hi is None else hi - lo
        out[m] = {"best": d["best"], "worst": d["worst"], "move": gap(d["best"], d["worst"]),
                  "comparable_best": d["comparable_best"],
                  "comparable_worst": d["comparable_worst"],
                  "comparable_move": gap(d["comparable_best"], d["comparable_worst"])}
    return out


def burden(city: str, map_name: str = BURDEN_MAP) -> dict:
    """Deaths attributable to PM2.5 above each curve's own floor, per curve, on one map, with the
    curves giving the lowest and highest (no average)."""
    run, missing = curves_.select()
    place = places.resolve(city, kind="city")
    deaths = {c.name: float(steady_state(place, c, map_name, Change(to=c.floor),
                                         deaths=Sources()).deaths_averted) for c in run}
    lo = min(deaths, key=deaths.get)
    hi = max(deaths, key=deaths.get)
    return {"map": map_name, "deaths": deaths, "lowest": {"curve": lo, "deaths": deaths[lo]},
            "highest": {"curve": hi, "deaths": deaths[hi]},
            "ratio_highest_to_lowest": deaths[hi] / deaths[lo] if deaths[lo] else None,
            "curves_not_run": dict(missing)}


def _studies(city: str) -> list[str]:
    return [s for s in causes.studies(city) if not isinstance(score._study_shares(city, s), str)]


def report(city: str, *, maps: Sequence[str] = MAPS, n: int = 500, seed: int = 0,
           curves: list[str] | None = None, folder=measures.LIBRARY, top: int = TOP,
           jobs: int = 1, progress: Callable[[str], None] | None = None) -> dict:
    """The stability report for one city (see the module docstring) as a dict."""
    from . import sensitivity

    folder = Path(folder)
    say = progress or (lambda text: None)
    lib = measures.library(folder)
    studies = _studies(city)
    out = {"city": city, "top": top, "n": n, "seed": seed, "studies": studies,
           "maps": [m for m in maps if exposure.available(m)],
           "maps_unavailable": [m for m in maps if not exposure.available(m)], "combos": []}
    for map_name in out["maps"]:
        s = dict(map_name=map_name, curves=curves, n=n, seed=seed, discount=simulate.DISCOUNT,
                 deaths=None, monthly_curves=False)
        for study in studies:
            say(f"{city}: map {map_name}, study {study}")
            scores = score.city(city, study=study, folder=folder, library=lib, **s)
            wanted = [x.measure for x in scores if x.scope == "region" and x.status == "scored"]
            reach, missing = {}, {}
            if map_name in exposure.DISTRICT_MAPS and wanted:
                keys = {m: sensitivity._key(m, s, None, folder) for m in wanted}
                sensitivity._reaches_many([(keys[m], m, s, lib) for m in wanted], folder, jobs,
                                          say)
                for m in wanted:
                    got = sensitivity._REACHES[keys[m]]
                    if isinstance(got, str):
                        missing[m] = got
                    else:
                        reach[m] = got
            context = rank._context(scores, study, **s)
            r = rank.from_scores(scores, city, context, reach, regional_missing=missing)
            out["combos"].append({"map": map_name, "study": study, "curves": list(r.tables),
                                  "all": top_check(r, top), "comparable": top_check(r, top, True),
                                  "moves": moves(r)})
    largest: dict[str, dict] = {}
    for c in out["combos"]:
        for m, d in c["moves"].items():
            if d["move"] is not None and d["move"] >= largest.get(m, {}).get("move", -1):
                largest[m] = {"move": d["move"], "map": c["map"], "study": c["study"]}
    out["largest_move"] = dict(sorted(largest.items(), key=lambda x: (-x[1]["move"], x[0])))
    out["burden"] = burden(city) if exposure.available(BURDEN_MAP) else None
    return out


def text(rep: dict) -> str:
    k = rep["top"]
    lines = [f"Is the top of {rep['city']}'s table the same whichever way it is computed? "
             f"{rep['n']:,} draws, seed {rep['seed']}. Top {k} on every curve, for each map and "
             "causes study; ranks are never averaged.", ""]
    for c in rep["combos"]:
        for label, part in (("all measures", c["all"]), ("comparable only", c["comparable"])):
            verdict = ("same, same order" if part["same_top"] else
                       "same measures, order differs" if part["same_members"] else "differs")
            lines.append(f"  map {c['map']}, study {c['study']}, {label}: top {k} {verdict}")
            if not part["same_top"]:
                lines += [f"      {cv}: {', '.join(ids) or '—'}" for cv, ids in part["top"].items()]
    lines += ["", "Largest rank move across curves per measure (worst minus best, over every map "
              "and study; where it happens):"]
    lines += [f"  {m}: {d['move']} ({d['map']}, {d['study']})" for m, d in rep["largest_move"].items()]
    b = rep.get("burden")
    if b:
        lines += ["", f"Deaths attributable to PM2.5 a year, {b['map']} map, by curve (a spread, "
                  "not a central figure):"]
        lines += [f"  {cv}: {v:,.0f}" for cv, v in sorted(b["deaths"].items(), key=lambda x: x[1])]
        lines.append(f"  lowest {b['lowest']['deaths']:,.0f} ({b['lowest']['curve']}), highest "
                     f"{b['highest']['deaths']:,.0f} ({b['highest']['curve']})")
    if rep["maps_unavailable"]:
        lines.append(f"\nMaps not present here: {', '.join(rep['maps_unavailable'])}.")
    return "\n".join(lines)


def write(rep: dict, folder: Path = OUT) -> list[Path]:
    """stability_<city>.json and .txt in folder (default health/out/, git-ignored)."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    slug = rep["city"].lower().replace(" ", "_")
    j, t = folder / f"stability_{slug}.json", folder / f"stability_{slug}.txt"
    j.write_text(json.dumps(score._clean(rep), indent=2, ensure_ascii=False, allow_nan=False),
                 encoding="utf-8")
    t.write_text(text(rep) + "\n", encoding="utf-8")
    return [j, t]
