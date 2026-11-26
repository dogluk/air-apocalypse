"""Ranking the measures of one place: life-years per crore of the funder's rupees, curve by curve.

Nothing about health is computed here. Every number is read from score.city / score.region
(which run simulate.run); this module only orders them.

The ranking rule, within one place and one curve:
  - A measure with status "scored" and an expected life-years per crore is ranked by it, highest
    first (rank 1); ties are broken by measure id. rank_if_works is the same order on life-years
    per crore if it works.
  - no_cost and pays_for_itself measures are listed apart, after the ranked ones, with their
    life-years and no rank. not_applicable and not_scored measures follow, by id, with why.
  - "Not ranked" is not last. An exposure measure for one age group on a curve that starts above
    that group (e.g. children on a curve for ages 25 and up) gets 0 life-years there for want of
    a curve, not for want of effect: it is not ranked on that curve, and says why (curve_gap).
  - A measure whose cost leaves out part of what it would take (flag partial_cost) is ranked,
    with the flag beside its ratio; `comparable` is False for it, and rank_comparable gives the
    order among the comparable measures only, so the order can be read with those set aside.

A crore is 1,00,00,000 rupees (ten million). Ranks on different curves are columns side by side:
nothing here averages ranks or ratios across curves, studies or maps; the spread across curves is
shown as best, worst and the curves where a measure is not ranked.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

import numpy as np

from . import causes, measures, score, simulate

CRORE = 1e7            # rupees in a crore (1,00,00,000)
FLIP_PLACES = 3        # a measure whose rank moves by this many places or more between curves is marked
RANK_ASSUMPTIONS = ("Measures are ranked one at a time; their benefits do not add up.",
                    "A regional measure's ratio in a city table is its whole reach's: its cost is "
                    "taken to be shared in proportion to where its life-years fall.")

LISTED_APART = ("no_cost", "pays_for_itself")
CURVE_GAP = "this curve does not cover the ages this measure reaches"


@dataclass(frozen=True)
class Row:
    measure: str
    name: str
    kind: str
    scope: str
    status: str
    reason: str
    who_reaches: str
    reach: str                                    # "Bengaluru" | "scored in 3 of 50 cities" | "region: 412 districts"
    p_success: float
    p_success_basis: str
    flags: tuple[str, ...]                        # flag codes, in Score order, deduplicated
    life_years: dict | None                       # if it works: median, p5, p95
    mean_life_years: float | None                 # if it works, mean over draws
    expected_life_years: float | None
    mean_cost_inr: float | None                   # if it works, mean over draws
    cost_share_only_on_success: float
    society_net_inr: float | None
    ly_per_crore_if_works: float | None
    expected_ly_per_crore: float | None
    rank: int | None                              # by expected_ly_per_crore; None unless ranked
    rank_if_works: int | None
    study: str | None
    trail: dict
    curve_gap: str = ""                           # why it is not ranked on this curve although scored
    comparable: bool = True                       # False when its cost is partial (flag partial_cost)
    rank_comparable: int | None = None            # rank among comparable rows only
    rank_if_works_comparable: int | None = None


@dataclass(frozen=True)
class Table:
    curve: str
    curve_label: str
    rows: tuple[Row, ...]       # ranked rows in rank order, then no_cost, pays_for_itself, then the rest by id


@dataclass(frozen=True)
class Ranking:
    place: str
    tables: dict[str, Table]                      # curve name -> Table, curves in run order
    spread: dict[str, dict]                       # measure -> ranks per curve, best, worst, ...
    context: dict                                 # map, study, deaths, discount, n, seed, curves
    parts: dict[str, "Ranking"] = field(default_factory=dict)   # India only: city -> Ranking


def _rankable(r: Row) -> bool:
    return r.status == "scored" and r.expected_ly_per_crore is not None and not r.curve_gap


def _order(rows: list[Row], key: str) -> dict[str, int]:
    """measure -> rank on `key` (highest first, ties by id), over rows with that value set."""
    have = [r for r in rows if getattr(r, key) is not None]
    have.sort(key=lambda r: (-getattr(r, key), r.measure))
    return {r.measure: i for i, r in enumerate(have, 1)}


def rank_rows(rows: list[Row]) -> list[Row]:
    """The ranking rule (module docstring) applied to one place's rows on one curve. Pure."""
    ranked = [r for r in rows if _rankable(r)]
    comparable = [r for r in ranked if r.comparable]
    by_e, by_w = _order(ranked, "expected_ly_per_crore"), _order(ranked, "ly_per_crore_if_works")
    by_ec = _order(comparable, "expected_ly_per_crore")
    by_wc = _order(comparable, "ly_per_crore_if_works")
    out = []
    for r in rows:
        m = r.measure
        out.append(replace(r, rank=by_e.get(m), rank_if_works=by_w.get(m),
                           rank_comparable=by_ec.get(m), rank_if_works_comparable=by_wc.get(m)))

    def place(r: Row):
        if r.rank is not None:
            return (0, r.rank, r.measure)
        if r.status in LISTED_APART:
            return (1 + LISTED_APART.index(r.status), 0, r.measure)
        return (3, 0, r.measure)
    return sorted(out, key=place)


def _codes(*flag_lists) -> tuple[str, ...]:
    seen = []
    for flags in flag_lists:
        for f in flags:
            code = f.code if isinstance(f, score.Flag) else f
            if code not in seen:
                seen.append(code)
    return tuple(seen)


def _curve_run(s: score.Score, curve: str):
    return None if s.run is None else s.run.per_curve.get(curve)


def _curve_gap(s: score.Score, curve: str) -> str:
    """Non-empty when the measure reaches one age group and the curve starts above it."""
    ages = (s.trail.get("exposure") or {}).get("ages")
    cr = _curve_run(s, curve)
    if not ages or cr is None:
        return ""
    min_age = cr.curve.min_age
    if ages[1] < min_age:
        return (f"{CURVE_GAP}: it starts at age {min_age}, and the measure reaches ages "
                f"{ages[0]}-{ages[1]}")
    return ""


def _row(s: score.Score, curve: str, reach: str, regional: score.Score | None = None,
         regional_missing: str = "") -> Row:
    """One measure's row on one curve, read from its Score (and, for a regional measure scored
    in the city, from its whole-reach Score for the cost and ratio figures)."""
    summary = s.per_curve.get(curve)
    status, reason = s.status, s.reason
    flags = _codes(s.flags)
    net = s.society_net_inr
    cost_from = summary
    cr_cost = _curve_run(s, curve)
    if s.scope == "region" and s.status == "scored":
        if regional is None:
            status, reason, cost_from = "not_scored", regional_missing or (
                "its whole reach was not scored, so it has no ratio to rank by"), None
        else:
            reach_summary = regional.per_curve.get(curve)
            flags = _codes(s.flags, regional.flags)
            net = regional.society_net_inr
            if regional.status != "scored":
                status, reason = regional.status, regional.reason
            else:
                reason = ("its life-years are the part that reaches this place; its cost and "
                          "ratio are its whole reach's (see the assumptions)")
            if reach_summary is None:
                status = "not_scored"
                reason = f"its whole reach was not scored on the curve {curve}"
            cost_from, cr_cost = reach_summary, _curve_run(regional, curve)
            districts = (regional.trail.get("region") or {}).get("districts")
            if districts is not None:
                reach = f"{reach} (part of a region: {districts} districts)"
    if summary is None and status in ("scored", *LISTED_APART):
        status, reason = "not_scored", f"it was not run on the curve {curve}"

    def get(d, *keys):
        for k in keys:
            if d is None:
                return None
            d = d.get(k)
        return d

    ly = get(summary, "life_years")
    gap = _curve_gap(s, curve) if status == "scored" else ""
    ratios = cost_from if status == "scored" and not gap else None
    return Row(
        measure=s.measure, name=s.name, kind=s.kind, scope=s.scope, status=status,
        reason=reason, who_reaches=s.who_reaches, reach=reach, p_success=s.p_success,
        p_success_basis=s.p_success_basis, flags=flags,
        life_years=None if ly is None else {k: ly[k] for k in ("median", "p5", "p95")},
        mean_life_years=get(ly, "mean"),
        expected_life_years=get(summary, "expected_life_years"),
        mean_cost_inr=get(cost_from, "cost_inr", "mean"),
        cost_share_only_on_success=(cr_cost.cost_share_only_on_success if cr_cost is not None
                                    else 0.0),
        society_net_inr=net,
        ly_per_crore_if_works=get(ratios, "life_years_per_crore_if_works"),
        expected_ly_per_crore=get(ratios, "expected_life_years_per_crore"),
        rank=None, rank_if_works=None, study=s.study, trail=s.trail, curve_gap=gap,
        comparable="partial_cost" not in flags)


def _curves(scores: list[score.Score]) -> list[str]:
    out = []
    for s in scores:
        for c in s.per_curve:
            if c not in out:
                out.append(c)
    return out


def _label(scores: list[score.Score], curve: str, regional: dict | None) -> str:
    for s in [*scores, *(regional or {}).values()]:
        cr = _curve_run(s, curve)
        if cr is not None:
            return cr.curve.label
    return curve


def table(scores: list[score.Score], curve: str, regional: dict[str, score.Score] | None = None,
          *, regional_missing: dict[str, str] | None = None) -> Table:
    """One curve's table for one place. regional: measure -> whole-reach Score (score.region)
    for the regional measures scored in this place; regional_missing: measure -> why its whole
    reach has no Score."""
    regional, regional_missing = regional or {}, regional_missing or {}
    rows = [_row(s, curve, s.place, regional.get(s.measure), regional_missing.get(s.measure, ""))
            for s in scores]
    return Table(curve, _label(scores, curve, regional), tuple(rank_rows(rows)))


def _spread_of(tables: dict[str, Table], rank_key: str) -> dict[str, dict]:
    ids = []
    for t in tables.values():
        ids += [r.measure for r in t.rows if r.measure not in ids]
    out = {}
    for m in ids:
        ranks = {}
        for c, t in tables.items():
            row = next((r for r in t.rows if r.measure == m), None)
            if row is not None:
                ranks[c] = getattr(row, rank_key)
        got = [v for v in ranks.values() if v is not None]
        best, worst = (min(got), max(got)) if got else (None, None)
        out[m] = {"ranks": ranks, "best": best, "worst": worst,
                  "unranked_on": [c for c, v in ranks.items() if v is None],
                  "disagree": bool(got) and worst - best >= FLIP_PLACES}
    return out


def spread(tables: dict[str, Table]) -> dict[str, dict]:
    """measure -> {"ranks": {curve: rank or None}, "best", "worst", "unranked_on", "disagree",
    "comparable", "comparable_ranks", "comparable_best", "comparable_worst",
    "comparable_disagree"}. best/worst are over the curves where it is ranked; disagree is
    worst - best >= FLIP_PLACES. The comparable_* keys are the same over ranks among measures
    whose cost is not partial (None for a partial-cost measure). Never an average."""
    out = _spread_of(tables, "rank")
    comp = _spread_of(tables, "rank_comparable")
    for m, d in out.items():
        rows = [r for t in tables.values() for r in t.rows if r.measure == m]
        d["comparable"] = all(r.comparable for r in rows)
        c = comp[m]
        d.update(comparable_ranks=c["ranks"], comparable_best=c["best"],
                 comparable_worst=c["worst"], comparable_disagree=c["disagree"])
    return out


def from_scores(scores: list[score.Score], place: str, context: dict,
                regional: dict[str, score.Score] | None = None, *,
                regional_missing: dict[str, str] | None = None) -> Ranking:
    """Tables for every curve present in the scores, plus their spread. Pure: nothing is run."""
    tables = {c: table(scores, c, regional, regional_missing=regional_missing)
              for c in _curves(scores)}
    return Ranking(place=place, tables=tables, spread=spread(tables), context=dict(context))


def city(city: str, *, study=None, map_name="acag_total", curves=None, n=2000, seed=0,
         discount=simulate.DISCOUNT, deaths=None, folder=measures.LIBRARY,
         regional: dict[str, score.Score] | None = None, monthly_curves: bool = False) -> Ranking:
    """score.city for one city, then from_scores. A regional measure scored in the city takes its
    ratio from its whole reach: score.region with the same settings, unless given in
    `regional`."""
    if monthly_curves:
        raise NotImplementedError("month-by-month curves are not built yet (plan D Task 6)")
    folder = Path(folder)
    scores = score.city(city, study=study, map_name=map_name, curves=curves, n=n, seed=seed,
                        discount=discount, deaths=deaths, folder=folder)
    wanted = [s.measure for s in scores if s.scope == "region" and s.status == "scored"]
    reach, missing = _reaches(wanted, regional, map_name=map_name, curves=curves, n=n, seed=seed,
                              discount=discount, deaths=deaths, folder=folder)
    context = _context(scores, study, map_name=map_name, curves=curves, n=n, seed=seed,
                       discount=discount, deaths=deaths)
    return from_scores(scores, city, context, reach, regional_missing=missing)


def _reaches(wanted, given, *, map_name, curves, n, seed, discount, deaths, folder):
    """Whole-reach Scores (score.region) for the regional measures in `wanted` not already in
    `given`; and measure -> why, for those whose reach could not be scored."""
    reach, missing = dict(given or {}), {}
    for m in wanted:
        if m in reach or m in missing:
            continue
        try:
            reach[m] = score.region(m, map_name=map_name, curves=curves, n=n, seed=seed,
                                    discount=discount, deaths=deaths, folder=folder)
        except (ValueError, KeyError) as e:
            missing[m] = f"its whole reach could not be scored: {e}"
    return reach, missing


def _context(scores, study, *, map_name, curves, n, seed, discount, deaths) -> dict:
    used_study = study if study is not None else next((s.study for s in scores if s.study), None)
    first = next((s.run for s in scores if s.run is not None), None)
    context = {"map": map_name, "study": used_study,
               "deaths": deaths if isinstance(deaths, (str, type(None))) else str(deaths),
               "discount": discount, "n": n, "seed": seed,
               "curves": list(curves) if curves is not None else _curves(scores)}
    if first is not None and first.unavailable:
        context["curves_unavailable"] = dict(first.unavailable)
    return context


# --- all India ---------------------------------------------------------------------------------

INDIA = "India: the fifty cities, and each regional measure's whole reach"
CROSS_CITY = "pays_for_itself_in_some"     # flag: pays for itself in some cities, ranked on the rest
_REACH_WORDS = (("not_applicable", "not applicable in"), ("not_scored", "not scored in"),
                ("no_cost", "no cost given in"), ("pays_for_itself", "pays for itself in"))


def _city_parts(rows: dict[str, score.Score], curve: str, status: str):
    """The cities where the measure has `status` and a summary on `curve`: [(city, Score)]."""
    return [(c, s) for c, s in rows.items() if s.status == status and curve in s.per_curve]


def _summed(parts, curve: str) -> dict | None:
    """Life-years (if it works) over the cities in `parts`, added draw by draw: every run shares
    the seed, so draw i is the same quantile in every city. median, p5, p95, mean."""
    runs = [_curve_run(s, curve) for _, s in parts]
    if runs and all(r is not None and hasattr(r, "life_years") for r in runs):
        a = sum(np.asarray(r.life_years, dtype=float) for r in runs)
        return dict(median=float(np.median(a)), p5=float(np.percentile(a, 5)),
                    p95=float(np.percentile(a, 95)), mean=float(np.mean(a)))
    if len(parts) == 1:                      # one city: its own summary is the sum
        return dict(parts[0][1].per_curve[curve].get("life_years") or {}) or None
    return None


def _study_summary(parts) -> str | None:
    counts: dict[str, int] = {}
    for _, s in parts:
        if s.study:
            counts[s.study] = counts.get(s.study, 0) + 1
    if not counts:
        return None
    return "; ".join(f"{k} ({v} {'city' if v == 1 else 'cities'})" for k, v in sorted(counts.items()))


def _india_city_row(mid: str, by_city: dict[str, score.Score], curve: str) -> Row:
    """One city-scope measure's all-India row on one curve: the cities where it is scored, added."""
    first = next(iter(by_city.values()))
    n_cities = len(by_city)
    statuses = {c: s.status for c, s in by_city.items()}
    scored = _city_parts(by_city, curve, "scored")
    pays_some = scored and any(v == "pays_for_itself" for v in statuses.values())
    if scored:
        status, reason, counted = "scored", "", scored
    elif any(v == "scored" for v in statuses.values()):
        status, reason, counted = "not_scored", f"it was not run on the curve {curve}", []
    elif any(v == "no_cost" for v in statuses.values()):
        no_cost = [(c, s) for c, s in by_city.items() if s.status == "no_cost"]
        status, reason, counted = "no_cost", no_cost[0][1].reason, _city_parts(by_city, curve,
                                                                                "no_cost")
    elif any(v == "pays_for_itself" for v in statuses.values()):
        pays = [(c, s) for c, s in by_city.items() if s.status == "pays_for_itself"]
        status, counted = "pays_for_itself", _city_parts(by_city, curve, "pays_for_itself")
        reason = f"pays for itself in every city where it ran ({len(pays)}): {pays[0][1].reason}"
    else:
        tally: dict[str, int] = {}
        for v in statuses.values():
            tally[v] = tally.get(v, 0) + 1
        status = max(tally, key=lambda k: tally[k])          # ties: the first city's order
        why = next(s.reason for s in by_city.values() if s.status == status)
        reason, counted = f"not scored in any city: {why}", []

    k = sum(1 for v in statuses.values() if v == "scored")
    reach = f"scored in {k} of {n_cities} {'city' if n_cities == 1 else 'cities'}"
    for st, words in _REACH_WORDS:
        j = sum(1 for v in statuses.values() if v == st)
        if j:
            reach += f"; {words} {j}"

    flags = _codes(*(s.flags for s in by_city.values()))
    if pays_some:
        flags = _codes(flags, [CROSS_CITY])
    ref = counted[0][1] if counted else first
    cr = _curve_run(ref, curve) if counted else None
    s_share = cr.cost_share_only_on_success if cr is not None else 0.0
    p = ref.p_success
    ly = _summed(counted, curve) if counted else None
    mean_ly = None if ly is None else ly.get("mean")
    if counted and mean_ly is None:
        mean_ly = sum(s.per_curve[curve]["life_years"]["mean"] for _, s in counted)
    costs = [(s.per_curve[curve].get("cost_inr") or {}).get("mean") for _, s in counted]
    mean_cost = sum(costs) if counted and None not in costs else None
    nets = [s.society_net_inr for _, s in counted if s.society_net_inr is not None]
    gap = _curve_gap(ref, curve) if status == "scored" else ""
    expected_ly = None if mean_ly is None else p * mean_ly
    if_works = expected = None
    if status == "scored" and not gap and mean_cost:
        expected_cost = mean_cost * (1 - s_share + s_share * p)
        if_works = mean_ly * CRORE / mean_cost if mean_cost > 0 else None
        expected = expected_ly * CRORE / expected_cost if expected_cost > 0 else None

    def part_mean(s, key):
        if s.status not in ("scored", *LISTED_APART) or curve not in s.per_curve:
            return None
        return (s.per_curve[curve].get(key) or {}).get("mean")
    trail = {"cities": [{"city": c, "status": s.status, "study": s.study,
                         "mean_life_years": part_mean(s, "life_years"),
                         "mean_cost_inr": part_mean(s, "cost_inr")}
                        for c, s in by_city.items()],
             "evidence": (scored[0][1] if scored else first).trail.get("evidence")}
    return Row(
        measure=mid, name=first.name, kind=first.kind, scope=first.scope, status=status,
        reason=reason, who_reaches=first.who_reaches, reach=reach, p_success=p,
        p_success_basis=first.p_success_basis, flags=flags,
        life_years=None if ly is None else {q: ly[q] for q in ("median", "p5", "p95")},
        mean_life_years=mean_ly, expected_life_years=expected_ly, mean_cost_inr=mean_cost,
        cost_share_only_on_success=s_share, society_net_inr=sum(nets) if nets else None,
        ly_per_crore_if_works=if_works, expected_ly_per_crore=expected,
        rank=None, rank_if_works=None,
        study=_study_summary(counted or [(c, s) for c, s in by_city.items() if s.study]),
        trail=trail, curve_gap=gap, comparable="partial_cost" not in flags)


def _india_region_row(s: score.Score, curve: str) -> Row:
    """A regional measure's all-India row: its whole-reach Score as it stands."""
    places = getattr(getattr(s.run, "intervention", None), "places", None)
    districts = len(places) if places is not None else (s.trail.get("region") or {}).get("districts")
    reach = f"region: {districts} districts"
    row = _row(s, curve, reach, regional=s)
    reason = row.reason if row.status != "scored" else ""
    return replace(row, reach=reach, reason=reason, flags=_codes(row.flags, ["regional"]))


def _not_scored_row(s: score.Score, reach: str, reason: str) -> Row:
    return Row(measure=s.measure, name=s.name, kind=s.kind, scope=s.scope, status="not_scored",
               reason=reason, who_reaches=s.who_reaches, reach=reach, p_success=s.p_success,
               p_success_basis=s.p_success_basis, flags=_codes(s.flags, ["regional"]),
               life_years=None, mean_life_years=None, expected_life_years=None,
               mean_cost_inr=None, cost_share_only_on_success=0.0, society_net_inr=None,
               ly_per_crore_if_works=None, expected_ly_per_crore=None, rank=None,
               rank_if_works=None, study=None, trail=s.trail)


def india_from_scores(city_scores: dict[str, list[score.Score]],
                      regional: dict[str, score.Score], context: dict, *,
                      regional_missing: dict[str, str] | None = None) -> Ranking:
    """The all-India Ranking from scores already run. Pure: nothing is run.

    city_scores: city -> its score.city list; regional: measure -> its whole-reach Score
    (score.region), the same one used in every city table; regional_missing: measure -> why its
    whole reach has no Score.

    A city-scope measure's row adds up the cities where it is scored on that curve (never a zero
    for the others): life-year draws added draw by draw, mean life-years and mean cost the sums
    of the city means, expected life-years = p x the sum, expected cost = the summed cost x
    (1 - s + s p), the ratios from those sums. Its reach says in how many cities it is scored,
    not applicable, not scored, without a cost, or paying for itself. A regional measure's row is
    its whole reach. parts = each city's own Ranking, from the same Scores.
    """
    regional, regional_missing = dict(regional or {}), dict(regional_missing or {})
    cities = list(city_scores)
    parts = {}
    for c in cities:
        ctx = {k: v for k, v in context.items() if k not in ("cities", "scored_in")}
        ctx["study"] = next((s.study for s in city_scores[c] if s.study), None)
        parts[c] = from_scores(city_scores[c], c, ctx, regional, regional_missing=regional_missing)

    order: list[str] = []
    by_measure: dict[str, dict[str, score.Score]] = {}
    for c in cities:
        for s in city_scores[c]:
            if s.measure not in by_measure:
                order.append(s.measure)
                by_measure[s.measure] = {}
            by_measure[s.measure][c] = s
    for m in regional:
        if m not in by_measure:
            order.append(m)
            by_measure[m] = {}
    all_scores = [s for c in cities for s in city_scores[c]] + list(regional.values())
    curves = _curves(all_scores)

    tables = {}
    for curve in curves:
        rows = []
        for m in order:
            if m in regional:
                rows.append(_india_region_row(regional[m], curve))
            elif by_measure[m] and next(iter(by_measure[m].values())).scope == "region":
                s = next(iter(by_measure[m].values()))
                rows.append(_not_scored_row(s, "region", regional_missing.get(
                    m, "its whole reach was not scored, so it has no ratio to rank by")))
            else:
                rows.append(_india_city_row(m, by_measure[m], curve))
        tables[curve] = Table(curve, _label(all_scores, curve, None), tuple(rank_rows(rows)))
    ctx = dict(context)
    ctx.setdefault("cities", cities)
    ctx.setdefault("scored_in", {m: sum(1 for s in by_measure[m].values() if s.status == "scored")
                                 for m in order if m not in regional})
    return Ranking(place=INDIA, tables=tables, spread=spread(tables), context=ctx, parts=parts)


def india(*, map_name="acag_total", curves=None, n=2000, seed=0, discount=simulate.DISCOUNT,
          deaths=None, folder=measures.LIBRARY, cities: Sequence[str] | None = None,
          monthly_curves: bool = False, progress: Callable[[str], None] | None = None) -> Ranking:
    """Score every city once (score.city, each on its own APnA study) and every regional measure
    once over its whole reach (score.region), then india_from_scores. cities=None: every city in
    causes.known_cities(), sorted. progress(city) is called before each city is scored.

    Speed: timed 2026-11-27 on the maintainer's laptop, india(n=500) over all 50 cities and the
    real library (21 measures, 4 regional), the eight curves open with IHME files present:
    564 s. 518 s of it is the four whole-reach runs (score.region, once each); the 50 cities
    take 45 s together. The sensitivity reruns should reuse the reaches, not rerun them.
    """
    if monthly_curves:
        raise NotImplementedError("month-by-month curves are not built yet (plan D Task 6)")
    folder = Path(folder)
    names = sorted(causes.known_cities()) if cities is None else list(cities)
    settings = dict(map_name=map_name, curves=curves, n=n, seed=seed, discount=discount,
                    deaths=deaths)
    lib = measures.library(folder)
    reach, missing = _reaches([m for m, x in lib.items() if x.scope == "region"], None,
                              folder=folder, **settings)
    city_scores = {}
    for c in names:
        if progress is not None:
            progress(c)
        city_scores[c] = score.city(c, folder=folder, **settings)
    context = _context([s for c in names for s in city_scores[c]], None, **settings)
    context["study"] = "each city's own APnA study (each row names the studies it used)"
    context["cities"] = names
    return india_from_scores(city_scores, reach, context, regional_missing=missing)


def to_json(r: Ranking) -> dict:
    """JSON-safe view (NaN -> None): place, context, assumptions, spread, tables, parts."""
    out = {
        "place": r.place,
        "context": r.context,
        "assumptions": list(score.ASSUMPTIONS + RANK_ASSUMPTIONS),
        "spread": [{"measure": m, **d} for m, d in r.spread.items()],
        "tables": {c: {"label": t.curve_label, "rows": [asdict(x) for x in t.rows]}
                   for c, t in r.tables.items()},
        "parts": {k: {f: v for f, v in to_json(p).items() if f != "parts"}
                  for k, p in r.parts.items()},
    }
    return score._clean(out)
