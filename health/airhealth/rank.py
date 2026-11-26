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

from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

from . import measures, score, simulate

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
    reach, missing = dict(regional or {}), {}
    for s in scores:
        if s.scope == "region" and s.status == "scored" and s.measure not in reach:
            try:
                reach[s.measure] = score.region(s.measure, map_name=map_name, curves=curves, n=n,
                                                seed=seed, discount=discount, deaths=deaths,
                                                folder=folder)
            except (ValueError, KeyError) as e:
                missing[s.measure] = f"its whole reach could not be scored: {e}"
    used_study = study if study is not None else next((s.study for s in scores if s.study), None)
    first = next((s.run for s in scores if s.run is not None), None)
    context = {"map": map_name, "study": used_study,
               "deaths": deaths if isinstance(deaths, (str, type(None))) else str(deaths),
               "discount": discount, "n": n, "seed": seed,
               "curves": list(curves) if curves is not None else _curves(scores)}
    if first is not None and first.unavailable:
        context["curves_unavailable"] = dict(first.unavailable)
    return from_scores(scores, city, context, reach, regional_missing=missing)


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
