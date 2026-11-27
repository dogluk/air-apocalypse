"""Ranking benchmarks: run each case in rank_cases.toml, print published vs ours, write RANKING.md.

Run from health/:  python benchmarks/rank_run.py

Each case scores one library measure (or two, or several) the way a published cost ranking did
and compares one figure: cost per death postponed (per_life), cost per µg/m³ (per_ugm3), the
ratio of two measures' cost per death (ratio_of_measures) or the share of pairs in the paper's
order (order). Regional measures are scored over their whole reach (score.region) on the case's
one curve only; the whole file ran in 46 s on 2026-11-27 (eight curves would take minutes). A case
that cannot be computed here (measure not in the library, not scored in the place, IHME files
missing) is listed as skipped with the reason, and the rest still run.
"""
import tomllib
from functools import cache
from itertools import combinations
from pathlib import Path

import numpy as np

from airhealth import curves, ihme, measures, prices, score

HERE = Path(__file__).resolve().parent
RANK_CASES = HERE / "rank_cases.toml"
RANKING = HERE / "RANKING.md"
N = 1000          # draws per run; the cases compare means and medians of uniform ranges

NOT_COMPARED = (
    ("World Bank, Striving for Clean Air (2022/23), GAINS", "dollars per life saved for its "
     "South Asia scenarios", "a scenario of many measures chosen together by an "
     "optimisation model; no single library measure matches it"),
    ("CREA, creahia", "health impacts of a change in PM2.5", "needs the R package, and it is a "
     "burden calculation, not a cost ranking: a case for cases.toml, not this file"),
    ("UNDP and CCDC/PGIMER/Krea, Investment case: Amritsar and Gurugram (2025)", "returns on "
     "investment for city measures", "its ROI table was seen only in a search summary [S] "
     "(lit/prior-rankings.md), never read at source"),
)

DELHI_NO_COUNTERPART = (
    ("home_purifiers", "no purifier or exposure row in TERI's Table 36"),
    ("school_purifiers_india", "no purifier or exposure row in TERI's Table 36"),
    ("winter_cloud_seeding", "no cloud-seeding row in TERI's Table 36"),
    ("stubble_pes_upfront, happy_seeder_subsidy, punjab_out_of_rice",
     "regional: their part in Delhi carries no cost of its own, and TERI's crop-residue options "
     "are not in Table 36 (TERI calls residue use in power plants a no-regret measure)"),
)


class Skip(Exception):
    """A case (or one of its measures) that cannot be computed here; the message says why."""


def load_cases(path: Path = RANK_CASES) -> list[dict]:
    with open(path, "rb") as f:
        return tomllib.load(f)["case"]


def _folder(case: dict) -> Path:
    return Path(case.get("folder", measures.LIBRARY))


def needs_region(case: dict) -> bool:
    """True when the case scores a regional measure over its whole reach (minutes, not seconds)."""
    return case["place"] == "region"


@cache
def _score(measure: str, place: str, causes_study: str | None, curve: str, map_name: str,
           discount: float, folder: str, n: int) -> score.Score:
    lib = measures.library(Path(folder))
    if measure not in lib:
        raise Skip(f"{measure} is not in the library ({folder})")
    if curve in curves.IHME and ihme.missing(list(curves.ihme_files(curve))):
        raise Skip(f"the curve {curve} needs IHME files that are not in data_local/")
    if place == "region":
        if lib[measure].scope != "region":
            raise Skip(f"{measure} is a city measure; it has no whole reach to score")
        s = score.region(measure, map_name=map_name, curves=[curve], n=n, discount=discount,
                         folder=Path(folder))
    else:
        s = score.city(place, [measure], study=causes_study, map_name=map_name, curves=[curve],
                       n=n, discount=discount, folder=Path(folder))[0]
        if s.status == "scored" and s.scope == "region":
            raise Skip(f"{measure} is regional: its part in {place} carries no cost, which belongs "
                       "to the whole reach")
    if s.status != "scored":
        raise Skip(f"{measure} is {s.status} in {place}: {s.reason}")
    if curve not in s.run.per_curve:
        raise Skip(f"the curve {curve} could not run: {s.run.unavailable.get(curve, '')}")
    return s


def _get(case: dict, measure: str) -> score.Score:
    return _score(measure, case["place"], case.get("causes_study"), case["curve"], case["map"],
                  float(case["discount"]), str(_folder(case)), int(case.get("n", N)))


def _per_life(case: dict, measure: str) -> float:
    r = _get(case, measure).run.per_curve[case["curve"]]
    return float(np.mean(r.cost_inr) / np.mean(r.deaths_postponed))


def _per_ugm3(case: dict, measure: str) -> float:
    s = _get(case, measure)
    r = s.run.per_curve[case["curve"]]
    change = abs(float(np.median(r.pm25_after - s.run.pm25_before)))
    if case.get("cost_basis", "total") == "annual":
        iv = s.run.intervention
        cost = prices.to_base_inr(iv.cost_annual.median + iv.cost_once.median / iv.duration_years,
                                  iv.cost_currency, iv.cost_year)
        if iv.covered is not None and iv.cost_per_covered:
            cost *= iv.covered.median
    else:
        cost = float(np.median(r.cost_inr))
    return float(cost / change)


def _per_ugm3_or_reason(case: dict, measure: str) -> float | str:
    try:
        return _per_ugm3(case, measure)
    except Skip as e:
        return str(e)


def _order(case: dict) -> float:
    published = case["published_values"]
    ours = {m: _per_ugm3_or_reason(case, m) for m in published}
    usable = [m for m, v in ours.items() if not isinstance(v, str)]
    if len(usable) < 2:
        why = "; ".join(f"{m}: {v}" for m, v in ours.items() if isinstance(v, str))
        raise Skip(f"fewer than two of its measures can be computed here ({why})")
    pairs = list(combinations(sorted(usable), 2))
    agree = sum((published[a] < published[b]) == (ours[a] < ours[b]) for a, b in pairs)
    return agree / len(pairs)


METRICS = {
    "per_life": lambda case: _per_life(case, case["measure"]),
    "per_ugm3": lambda case: _per_ugm3(case, case["measure"]),
    "ratio_of_measures": lambda case: (_per_life(case, case["measure"])
                                       / _per_life(case, case["other_measure"])),
    "order": _order,
}

UNITS = {"per_life": "₹ per death postponed", "per_ugm3": "₹ per µg/m³",
         "ratio_of_measures": "ratio", "order": "share of pairs"}


def published_base(case: dict) -> float:
    """The published figure in the unit ours is in: 2025 rupees for per_life and per_ugm3
    (per_ugm3 published in billions), as printed for a ratio or an order."""
    if case["kind"] == "per_life":
        return float(prices.to_base_inr(case["published"], case["published_currency"],
                                        case["published_year"]))
    if case["kind"] == "per_ugm3":
        return float(prices.to_base_inr(case["published"] * 1e9, case["published_currency"],
                                        case["published_year"]))
    return float(case["published"])


def judge(case: dict, ours: float, published: float) -> dict:
    ratio = ours / published
    return dict(case, ours=ours, published_inr=published, ratio=ratio,
                within=abs(ratio / case["expected_ratio"] - 1) <= case["tolerance"])


def evaluate(case: dict) -> dict:
    """The case with ours, ratio and within (within is judged for every case; only tested ones
    are held to it). Raises Skip when a measure cannot be computed."""
    return judge(case, METRICS[case["kind"]](case), published_base(case))


def evaluate_or_skip(case: dict) -> dict:
    try:
        return evaluate(case)
    except Skip as e:
        return dict(case, skipped=True, reason=str(e))


def _fmt(kind: str, v: float) -> str:
    if kind in ("per_life", "per_ugm3"):
        return f"₹{v / 1e9:,.2f} bn" if abs(v) >= 1e9 else f"₹{v:,.0f}"
    return f"{v:.4g}"


def _status(r: dict) -> str:
    if r.get("skipped"):
        return "skipped"
    if not r["tested"]:
        return "shown, not tested" + ("" if r["within"] else " (gap unexplained)")
    return "ok" if r["within"] else "OUTSIDE"


def table(results: list[dict]) -> str:
    head = ("case", "published", "ours", "ratio", "expected", "")
    rows = [(r["id"], _fmt(r["kind"], published_base(r)),
             "skipped" if r.get("skipped") else _fmt(r["kind"], r["ours"]),
             "" if r.get("skipped") else f"{r['ratio']:.4g}",
             f"{r['expected_ratio']:.4g} ±{r['tolerance']:.0%}", _status(r)) for r in results]
    w = [max(len(x[k]) for x in [head, *rows]) for k in range(len(head))]
    return "\n".join("  ".join(x[k].ljust(w[k]) if k == 0 else x[k].rjust(w[k]) for k in range(len(x)))
                     for x in [head, *rows])


def _setting(r: dict) -> str:
    where = ("the measure's whole reach (score.region)" if r["place"] == "region"
             else f"{r['place']} (score.city" + (f", study {r['causes_study']}" if
                                                 r.get("causes_study") else "") + ")")
    measure = r["measure"] + (f" ÷ {r['other_measure']}" if r.get("other_measure") else "")
    if r["kind"] == "order":
        measure = ", ".join(r["published_values"])
    return (f"`{measure}` over {where}, curve `{r['curve']}`, map `{r['map']}`, discount "
            f"{r['discount']:g}" + (f", cost basis {r['cost_basis']}" if r["kind"] == "per_ugm3" else ""))


def ranking_md(results: list[dict]) -> str:
    out = ["# Ranking benchmarks", "",
           "Generated by `benchmarks/rank_run.py` from `rank_cases.toml`; do not edit by hand. "
           "Run `python benchmarks/rank_run.py` from `health/` to refresh it (about a minute on one "
           "curve: the regional cases score a measure over every district it reaches).", "",
           "Each case scores library measures the way a published cost ranking did and compares "
           "one figure with the paper's: cost per death postponed, cost per µg/m³ of PM2.5, the "
           "ratio of two measures' cost per death, or the order of several. Costs are in 2025 "
           "rupees (the paper's figure is moved to 2025 rupees from its own price year). As in "
           "the reproduction benchmarks (`README.md`), each case states the ratio it expects "
           "(ours ÷ published), worked out from the known differences in inputs before it was "
           "run, and a tested case passes only within a narrow band of that expectation. "
           "Nothing is tuned to close a gap: a case whose expectation cannot be worked out from "
           "inputs is shown but not tested, and its gap is written down as unexplained.", "",
           "| Case | Kind | Published | Ours | Ratio | Expected | |", "|---|---|---|---|---|---|---|"]
    for r in results:
        ours = "skipped" if r.get("skipped") else _fmt(r["kind"], r["ours"])
        ratio = "" if r.get("skipped") else f"{r['ratio']:.4g}"
        out.append(f"| {r['id']} | {r['kind']} | {_fmt(r['kind'], published_base(r))} | {ours} | "
                   f"{ratio} | {r['expected_ratio']:.4g} ±{r['tolerance']:.0%} | {_status(r)} |")
    out += ["", "## The cases", ""]
    for r in results:
        if r.get("skipped"):
            ours = f"skipped here: {r['reason']}"
        else:
            ours = (f"{_fmt(r['kind'], r['ours'])} ({UNITS[r['kind']]}), from {_setting(r)}; "
                    f"ratio {r['ratio']:.4g}")
        out += [f"### {r['id']}: {r['study']}", "",
                f"**Published:** {r['published_text']}. Source: <{r['source_url']}>, {r['locator']}", "",
                f"**Ours:** {ours}.", "",
                " ".join(r["in_short"].split()), ""]
        if r.get("expected_why"):
            out += [f"**Expected ratio {r['expected_ratio']:.4g}:** "
                    + " ".join(r["expected_why"].split()), ""]
        if r["tested"]:
            out += [f"**Band ±{r['tolerance']:.0%}:** " + " ".join(r["band_why"].split()), ""]
        else:
            gap = ""
            if not r.get("skipped"):
                gap = (f" The ratio, {r['ratio']:.4g}, is " + (
                    "near that expectation, but that is not evidence of a match."
                    if r["within"] else
                    f"{r['ratio'] / r['expected_ratio']:.3g} times the expectation; that gap is "
                    "unexplained."))
            out += ["**Not tested:** " + " ".join(r["why_untested"].split()) + gap, ""]
    out += ["## Library measures that run in Delhi with no row in TERI's Table 36", ""]
    out += [f"- `{m}`: {why}." for m, why in DELHI_NO_COUNTERPART]
    out += ["", "## Not compared", ""]
    out += [f"- **{who}** ({what}): {why}." for who, what, why in NOT_COMPARED]
    out += ["", "Every measure is scored one at a time; benefits of two measures do not add.", ""]
    return "\n".join(out)


def main() -> int:
    results = [evaluate_or_skip(c) for c in load_cases()]
    print(table(results))
    RANKING.write_text(ranking_md(results))
    print(f"\nwrote {RANKING}")
    bad = [r for r in results if r["tested"] and not r.get("skipped") and not r["within"]]
    for r in bad:
        print(f"{r['id']} is outside its band.")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
