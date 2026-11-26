"""Scoring measures for one city: a library measure becomes an ordinary Intervention and is run.

compile() turns one measure (measures.py) and one city into an intervention.Intervention, with
a status, the flags every result carries, and a trail of what went in; city() runs each one
through simulate.run on every curve asked for and returns one Score per measure. Nothing
bypasses simulate.run.

An air measure in a city cuts causes of PM2.5 (dust, transport, ...). Its change in month m is

    pct_m = sum over the causes it targets in m of  -share_k(m) x cut_k

(share in percent of the city's PM2.5, cut a fraction): cutting a cause by x% cuts its share of
PM2.5 by x% ("share x cut", spec part 4). The twelve months are weighted by how dirty each one
is in the city (months.py), so a winter cut counts for more than a monsoon one. Shares come
from one source study (causes.py), never an average of several:
  - Only complete splits of concentration (covers = "all", metric = "concentration_share").
  - A study with shares of sources inside the city (origin = "inside", e.g. APnA) is scored on
    those alone; air blown in from outside is never cut.
  - A study whose shares count every origin (origin = "all_origins", e.g. CSTEP's receptor
    model for Bengaluru) is scored on those too, flagged upper_bound_all_origins: part of each
    share blew in from elsewhere, which a city measure cannot cut, so the result is an upper
    bound. Callers score each study separately rather than letting one win quietly.
  - A study that only splits by where the air comes from (origin = "region") is not scored.
  - For each month the study's seasonal group holding it wins over its whole-year group.
  - A cause the study does not report is NaN, never 0: a measure that targets only such
    causes is not scored; one that targets some is scored on the rest and flagged.

An exposure measure cuts what people breathe, not the outdoor air: in its months the change
is -100 x hours x cut percent, for the covered share of people only (simulate.run's covered).
With [exposure] ages, covered is a share of that age group, the run counts only its age bands
(Intervention.covered_ages), and a per-person cost counts only its people (impact.age_share).

A regional measure (scope = "region") removes a fraction (region.cut) of a source spread over
several states (crop burning, coal power). How much each district's PM2.5 falls when the whole
source goes is read from a source-receptor table (measures.receptor, data/receptor_<name>.csv);
the change in a district is cut x that full change, an ordinary "delta" run with a per-place
scale. Two views, never mixed:
  - region(): the whole reach, every district whose full change is not 0, with the measure's
    whole cost: the ratio figures belong here (airhealth score --region ID).
  - city(): the part that reaches one city, its scale the population-weighted mean full change
    over the city's map units. Life-years only: the cost belongs to the whole reach, so cost and
    ratio figures are None and the reason points to the region view. A city with a map unit the
    table does not cover is not_scored; one whose units all change by 0 is not_applicable.

Costs are per driver unit (a person, a household, the city, or `units` of something) and are
multiplied out here; an exposure measure's cost is then multiplied by the covered share in the
run (cost_per_covered). A measure with no [cost] is status no_cost; one whose society-wide net
cost over the horizon is below zero is pays_for_itself. Both are shown with their life-years
and with the ratio figures set to None: they are not ranked by a ratio.
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from . import causes, exposure, impact, measures, months, places, prices, simulate
from .intervention import Dist, Intervention, Linear, MonthlyMean, Product
from .measures import ALL_MONTHS, Measure
from .months import MONTH_DAYS

STATUSES = ("scored", "no_cost", "pays_for_itself", "not_applicable", "not_scored")

ASSUMPTIONS = (
    "Share times cut: cutting a cause of PM2.5 by a given percent is taken to cut its share of "
    "the city's PM2.5 by the same percent.",
    "No chemistry: real air is not additive (particles formed in the air from gases, limits set "
    "by ammonia, the dome over a city), and none of that is modelled.",
    "Health only: benefits to the climate, crops or time saved are not counted, and nothing is "
    "valued in money.",
    "Life-years and costs are counted over the measure's years plus the years in which its "
    "effect on deaths keeps arriving (20 under the default lag), discounted at 3% a year; "
    "deaths postponed are not discounted.",
    "Cost is what a government or funder would spend (the funder's rupees), in 2025 rupees; "
    "a measure that saves society money overall is listed apart, not ranked.",
)

RATIO_KEYS = ("cost_per_life_year_if_works", "expected_cost_per_expected_life_year",
              "inr_per_life_year_if_works", "expected_inr_per_expected_life_year",
              "life_years_per_crore_if_works", "expected_life_years_per_crore")

COST_KEYS = ("cost_usd", "cost_inr", "expected_cost_usd", "expected_cost_inr")

UPPER_BOUND_TEXT = ("This study's shares include air blown in from outside the city, so a city "
                    "measure scored on them is an upper bound.")


@dataclass(frozen=True)
class Flag:
    """A caveat printed with a result. code is stable, one of: "placeholder", "evidence_S",
    "evidence_R", "odds_judgement", "long_shot", "not_reported", "annual_share_flat",
    "borrowed_shape", "covered_only", "regional", "receptor_basis", "receptor_fallback",
    "upper_bound_all_origins", "partial_cost", "age_group". age_group: an exposure measure that
    reaches one age group, whose deaths and life-years use that group's own death rates and
    whose per-person cost counts only that group. receptor_fallback: the measure's source-receptor
    table is a stand-in built because no published source-receptor result could be used (its
    data/sources.toml entry has a `fallback` sentence saying how far off it may be)."""
    code: str
    text: str     # one plain sentence


@dataclass(frozen=True)
class Score:
    measure: str                 # Measure.id
    name: str
    kind: str                    # "air" | "exposure"
    scope: str                   # "city" | "region"
    place: str                   # the city's name; for region(), "region reached by <receptor>"
    study: str | None            # the causes study used (air/city), else None
    status: str                  # one of STATUSES
    reason: str                  # why, when status is not "scored"; "" otherwise
    who_reaches: str
    p_success: float
    p_success_basis: str
    flags: tuple[Flag, ...]
    pm25_change: dict | None     # annual µg/m³ if it works, population-weighted: median, p5, p95
                                 # (for an exposure measure: what the covered people breathe)
    per_curve: dict[str, dict]   # curve name -> CurveRun.summary()
    trail: dict
    run: simulate.Run | None     # not in JSON


def _dist(d) -> dict | None:
    return None if d is None else asdict(d)


def _months_of(text: str) -> tuple[int, ...]:
    return ALL_MONTHS if text == "1-12" else tuple(sorted(int(m) for m in text.split(",")))


def _fixed_flags(m: Measure, place: places.Place | None) -> list[Flag]:
    """The flags that depend on the measure and the place, not on the study (place None: a
    region's whole reach, which has no month-by-month shape)."""
    out = [Flag("placeholder", f"{name} is a placeholder: a stand-in, not an estimate.")
           for name in m.placeholders]
    for e in m.evidence:
        if e.key in ("S", "R"):
            how = ("was seen only in a snippet or summary of" if e.key == "S"
                   else "is recalled from")
            out += [Flag(f"evidence_{e.key}", f"{name} {how} {e.source}, not read at the source.")
                    for name in e.fields]
    basis = m.p_success_basis.lower()
    if not any(e.source.lower() in basis or e.url.lower() in basis for e in m.evidence):
        out.append(Flag("odds_judgement", f"The odds that it works ({m.p_success:.0%}) are a "
                                          "judgement, not a figure from a cited source."))
    if m.long_shot:
        out.append(Flag("long_shot", "This is a long shot: a large effect if it works, but "
                                     "unlikely to work."))
    if m.scope == "region":
        out.append(Flag("regional", "This measure acts on a source spread over several states; "
                                    "how much each district gains is read from a source-receptor "
                                    "table, and its cost belongs to the whole region it reaches."))
        basis = receptor_basis(m.region.receptor)
        if basis:
            out.append(Flag("receptor_basis", basis))
        fallback = receptor_basis(m.region.receptor, key="fallback")
        if fallback:
            out.append(Flag("receptor_fallback", fallback))
    elif m.kind == "exposure":
        out.append(Flag("covered_only", "Only the people it reaches breathe less; the outdoor "
                                        "air and everyone else are unchanged."))
        if m.exposure.ages is not None:
            lo, hi = m.exposure.ages
            out.append(Flag("age_group", f"Only people aged {lo}-{hi} are reached, and their own "
                                         "death rates are used."))
    if m.cost is not None and m.cost.partial:
        out.append(Flag("partial_cost", m.cost.partial))
    shape = months.shape(place) if place is not None else None
    if shape is not None and shape.borrowed:
        out.append(Flag("borrowed_shape", f"{place.name} has no month-by-month PM2.5 record of "
                                          f"its own, so the shape is {shape.basis}."))
    return out


def _empty_trail(shape_basis: str, m: Measure) -> dict:
    return {"shares": {}, "share_basis": {}, "cuts": [], "exposure": None, "region": None,
            "cost": None, "evidence": [asdict(e) for e in m.evidence], "shape": shape_basis}


def receptor_basis(name: str, key: str = "caveat") -> str:
    """A sentence from a receptor file's data/sources.toml entry ("" if none). key "caveat": what
    the table stands for (e.g. a sector from every origin, not only the named states); key
    "fallback": present only when the table is a stand-in for a published source-receptor
    result, saying so and how far off it may be."""
    import tomllib

    from . import paths
    entry = tomllib.loads((paths.DATA / "sources.toml").read_text()).get(name, {})
    return " ".join(str(entry.get(key, "")).split())


def _region_city(m: Measure, place: places.Place, map_name: str, folder: Path, trail: dict):
    """(scale for the city, status, reason): the population-weighted mean full change over the
    city's map units, from the measure's receptor table."""
    column = exposure.DISTRICT_MAPS.get(map_name)
    if column is None:
        return None, "not_scored", (f"the map {map_name} is not by district, so the source-"
                                    "receptor table cannot be read for this city; use acag_total "
                                    "or aqli")
    table = measures.receptor(m.region.receptor, folder)
    full = dict(zip(table.label, table.delta_pm25_full))
    units = exposure._cities().loc[place.name, column].split(";")
    state = exposure.cells(places.resolve(place.state, kind="state"), map_name)
    state = state[state.unit.isin(units)]
    labels, missing = [], []
    for u in state.unit:
        try:
            label = measures.district(u, place.state).label
        except KeyError:
            label = None
        if label not in full:
            missing.append(u)
        labels.append(label)
    trail["region"] = {"receptor": m.region.receptor, "cut": _dist(m.region.cut),
                       "units": list(state.unit), "population": list(state.population),
                       "delta_pm25_full": [full.get(x) for x in labels]}
    if missing:
        return None, "not_scored", (f"outside the source-receptor study's area: "
                                    f"{m.region.receptor} has no row for {', '.join(missing)}")
    deltas = np.array([full[x] for x in labels])
    if not deltas.any():
        return None, "not_applicable", (f"the source-receptor study gives no change in "
                                        f"{place.name}'s PM2.5 ({m.region.receptor})")
    scale = float(np.average(deltas, weights=state.population.to_numpy(float)))
    trail["region"]["city_delta_pm25_full"] = scale
    return scale, "scored", (f"this is the part that reaches {place.name}; the cost belongs to "
                             "the whole region the measure reaches, so the ratio figures are "
                             f"given only by airhealth score --region {m.id}")


def _study_shares(city: str, study: str):
    """(shares {cause: twelve monthly % with NaN}, basis {month: "study/season" or None},
    upper_bound, whole_year_months) for a study, or a reason string if it cannot be used."""
    rows = causes.for_city(city, study)
    if rows.empty:
        return f"there are no rows for study {study!r} in {city} in data/causes.csv"
    rows = rows[(rows.covers == "all") & (rows.metric == "concentration_share")]
    upper = False
    used = rows[rows.origin == "inside"]
    if used.empty:
        used, upper = rows[rows.origin == "all_origins"], True
    if used.empty:
        if (rows.origin == "region").any():
            return ("this study splits the air by where it comes from (the city's own sources "
                    "against air blown in), not by cause, so a city measure cannot be scored "
                    "on it")
        return ("this study gives no complete split of PM2.5 by cause (only partial pieces or "
                "shares of emissions), so a city measure cannot be scored on it")
    groups = {season: (_months_of(g.months.iloc[0]),
                       g.groupby("source_harmonised").share_pct.sum(min_count=1))
              for season, g in used.groupby("season", sort=True)}
    shares = {c: np.full(12, np.nan) for c in sorted(set(used.source_harmonised))}
    basis, whole_year = {}, set()
    for m in ALL_MONTHS:
        holding = [(s, ms, v) for s, (ms, v) in groups.items() if m in ms]
        seasonal = [h for h in holding if h[1] != ALL_MONTHS]
        pick = (seasonal or holding or [None])[0]
        if pick is None:
            basis[m] = None
            continue
        season, ms, values = pick
        basis[m] = f"{study}/{season}"
        if ms == ALL_MONTHS:
            whole_year.add(m)
        for cause, v in values.items():
            shares[cause][m - 1] = v
    return shares, basis, upper, whole_year


def _air(m: Measure, city: str, study: str, flags: list[Flag], trail: dict):
    """(monthly changes, status, reason) for an air measure in a city."""
    got = _study_shares(city, study)
    if isinstance(got, str):
        return None, "not_scored", got
    shares, basis, upper, whole_year = got
    trail["share_basis"] = basis
    nan = np.full(12, np.nan)
    trail["shares"] = {c: [None if math.isnan(x) else float(x) for x in v]
                       for c, v in shares.items()}
    trail["cuts"] = [{"cause": t.cause, "months": list(t.months), "p5": t.cut.p5,
                      "p95": t.cut.p95, "kind": t.cut.kind} for t in m.targets]
    if upper:
        flags.append(Flag("upper_bound_all_origins", UPPER_BOUND_TEXT))

    reported, missing = [], []
    for t in m.targets:
        v = shares.get(t.cause, nan)
        if t.cause not in trail["shares"]:
            trail["shares"][t.cause] = None
        gaps = [mo for mo in t.months if math.isnan(v[mo - 1])]
        if len(gaps) == len(t.months):
            missing.append(t.cause)
            continue
        reported.append(t)
        if gaps:
            flags.append(Flag("not_reported", f"The study reports no share of {t.cause} for "
                                              f"months {', '.join(map(str, gaps))}, so those "
                                              "months get no credit (not reported is not zero)."))
        if t.months != ALL_MONTHS and whole_year & set(t.months):
            flags.append(Flag("annual_share_flat", f"{t.cause} is cut only in some months, but "
                                                   "the study gives one share for the whole "
                                                   "year, so that share is used for each of "
                                                   "them."))
    if not reported:
        return None, "not_scored", (f"the study does not report {', '.join(missing)}; not "
                                    "reported is not zero, so the measure gets no credit from it")
    for cause in missing:
        flags.append(Flag("not_reported", f"The study does not report {cause}, so cutting it gets "
                                          "no credit here (not reported is not zero)."))

    if m.min_share_pct is not None:
        annual = sum(float(np.dot(MONTH_DAYS, np.nan_to_num(shares[t.cause]))) / MONTH_DAYS.sum()
                     for t in reported)
        if annual < m.min_share_pct:
            where = "all of its PM2.5" if upper else "PM2.5 from inside the city"
            names = ", ".join(t.cause for t in reported)
            return None, "not_applicable", (
                f"the causes it targets ({names}) make up {annual:.1f}% of {where} in {study}, "
                f"below the measure's threshold of {m.min_share_pct:g}%")

    monthly = []
    for mo in ALL_MONTHS:
        terms = tuple((-float(shares[t.cause][mo - 1]), t.cut) for t in reported
                      if mo in t.months and not math.isnan(shares[t.cause][mo - 1]))
        monthly.append(Linear(terms) if terms else Dist.fixed(0.0))
    return monthly, "scored", ""


def _exposure_change(m: Measure, trail: dict) -> list:
    e = m.exposure
    trail["exposure"] = {"covered": _dist(e.covered), "hours": _dist(e.hours),
                         "cut": _dist(e.cut), "months": list(e.months),
                         "ages": list(e.ages) if e.ages is not None else None}
    step = Linear(((-100.0, Product((e.hours, e.cut))),))
    return [step if mo in e.months else Dist.fixed(0.0) for mo in ALL_MONTHS]


def _rupees_basis(currency: str, year: int) -> str:
    factor = prices.to_base_inr(1.0, "INR", year)
    text = (f"{year} rupees times {factor:.4f}, the rise in India's GDP deflator (World Bank) "
            f"from {year} to {prices.BASE_YEAR}")
    if currency == "USD":
        rate = prices.to_base_inr(1.0, "USD", year) / factor
        text = f"dollars at the {year} rate of {rate:.2f} rupees each, then " + text
    return text


def _count(m: Measure, place: places.Place, city: str, map_name: str) -> float:
    people = float(exposure.cells(place, map_name).population.sum())
    driver = m.cost.driver
    if driver == "person":
        if m.kind == "exposure" and m.exposure.ages is not None:
            return people * impact.age_share(place, map_name, m.exposure.ages)
        return people
    if driver == "household":
        return people / measures.persons_per_household(city)
    if driver == "city":
        return 1.0
    return m.cost.units.median


def _times(c, d: Dist, count: float):
    return Product((c.units, d)) if c.driver == "unit" else d.scaled(count)


def compile(measure: Measure, city: str, *, study: str | None = None,
            map_name: str = "acag_total", folder: Path = measures.LIBRARY
            ) -> tuple[Intervention | None, str, str, tuple[Flag, ...], dict]:
    """(intervention or None, status, reason, flags, trail) for one measure in one city; what
    city() runs. study: the causes study for an air measure in a city (None: the city's APnA
    study). Status here is one of not_applicable, not_scored, no_cost or scored; city() turns
    scored into pays_for_itself when society's net cost is below zero. A regional measure gives
    the part that reaches the city (no cost; see the module docstring); folder is where its
    receptor file may sit beside the measure files (else data/)."""
    m = measure
    place = places.resolve(city, kind="city")
    flags = _fixed_flags(m, place)
    trail = _empty_trail(months.shape(place).basis, m)

    def stop(status, reason):
        return None, status, reason, tuple(flags), trail

    if m.scope == "region":
        scale, status, reason = _region_city(m, place, map_name, folder, trail)
        if scale is None:
            return stop(status, reason)
        iv = Intervention(
            name=m.name, places=[place], change_kind="delta", change=m.region.cut, monthly=None,
            start_year=m.start_year, ramp_years=m.ramp_years, duration_years=m.duration_years,
            p_success=m.p_success, lag=m.lag, notes=m.notes, cost_once=Dist.fixed(0.0),
            cost_annual=Dist.fixed(0.0), cost_currency="INR", cost_year=prices.BASE_YEAR,
            scale={place.label: scale})
        return iv, status, reason, tuple(flags), trail
    if m.cities is not None and city not in m.cities:
        return stop("not_applicable", f"this measure is written for {', '.join(m.cities)}, "
                                      f"not {city}")
    if m.kind == "air":
        if study is None:
            study = _default_study(city)
            if study is None:
                return stop("not_scored", f"there is no APnA study of {city}'s causes of PM2.5 "
                                          "(the default); give a study to score it on")
        monthly, status, reason = _air(m, city, study, flags, trail)
        if monthly is None:
            return stop(status, reason)
    else:
        monthly = _exposure_change(m, trail)

    c = m.cost
    if c is None:
        cost = dict(cost_once=Dist.fixed(0.0), cost_annual=Dist.fixed(0.0), cost_currency="INR",
                    cost_year=prices.BASE_YEAR, cost_share_only_on_success=0.0)
        status, reason = "no_cost", "it has no cost given, so it is shown but not ranked"
    else:
        count = _count(m, place, city, map_name)
        cost = dict(cost_once=_times(c, c.once, count), cost_annual=_times(c, c.annual, count),
                    cost_currency=c.currency, cost_year=c.year,
                    cost_share_only_on_success=c.share_only_on_success)
        trail["cost"] = {"driver": c.driver, "units_count": count, "once": _dist(c.once),
                         "annual": _dist(c.annual), "currency": c.currency, "year": c.year,
                         "cost_in_2025_rupees_basis": _rupees_basis(c.currency, c.year),
                         "unit": c.unit, "units": _dist(c.units),
                         "society_net_once": _dist(c.society_net_once),
                         "society_net_annual": _dist(c.society_net_annual)}
        status, reason = "scored", ""

    iv = Intervention(
        name=m.name, places=[place], change_kind="pct", change=MonthlyMean(tuple(monthly)),
        monthly=list(monthly), start_year=m.start_year, ramp_years=m.ramp_years,
        duration_years=m.duration_years, p_success=m.p_success, lag=m.lag, notes=m.notes,
        covered=m.exposure.covered if m.kind == "exposure" else None,
        covered_ages=m.exposure.ages if m.kind == "exposure" else None,
        cost_per_covered=m.kind == "exposure", **cost)
    return iv, status, reason, tuple(flags), trail


def _default_study(city: str) -> str | None:
    found = [s for s in causes.studies(city) if s.startswith("apna")]
    return found[0] if found else None


def _society_net(m: Measure, iv: Intervention, count: float, discount: float) -> float | None:
    """Median society-wide net cost over the duration, discounted, in 2025 rupees; None if the
    file gives none. Once and annual are drawn together (the same quantile)."""
    c = m.cost
    if c is None or (c.society_net_once is None and c.society_net_annual is None):
        return None
    paid = float(simulate.discount_factors(m.duration_years, discount).sum())
    terms = []
    for d, k in ((c.society_net_once, 1.0), (c.society_net_annual, paid)):
        if d is not None:
            terms.append((k, Product((c.units, d)) if c.driver == "unit" else d))
    total = Linear(tuple(terms)).median * (1.0 if c.driver == "unit" else count)
    if iv.covered is not None:
        total *= iv.covered.median
    return float(prices.to_base_inr(total, c.currency, c.year))


def city(city: str, measures: Sequence[str] | None = None, *, study: str | None = None,
         map_name: str = "acag_total", curves: list[str] | None = None, n: int = 2000,
         seed: int = 0, discount: float = simulate.DISCOUNT, deaths=None,
         folder: Path = measures.LIBRARY) -> list[Score]:
    """One Score per library measure in `folder` (or per id asked for), in library order (file
    name). study=None scores air measures on the city's APnA study; a city without one gets
    not_scored for them. Callers that want every study call once per study."""
    from . import measures as library_
    lib = library_.library(folder)
    ids = list(lib) if measures is None else [i for i in lib if i in set(measures)]
    unknown = sorted(set(measures or ()) - set(lib))
    if unknown:
        raise KeyError(f"no measure {unknown[0]!r} in {folder}")
    out = []
    for mid in ids:
        m = lib[mid]
        used = None
        if m.kind == "air" and m.scope == "city":
            used = study if study is not None else _default_study(city)
        iv, status, reason, flags, trail = compile(m, city, study=used, map_name=map_name,
                                                   folder=folder)
        per_curve, pm25, run = {}, None, None
        if iv is not None:
            run = simulate.run(iv, map_name=map_name, curves=curves, n=n, seed=seed,
                               deaths=deaths, discount=discount)
            per_curve = {k: r.summary() for k, r in run.per_curve.items()}
            first = next(iter(run.per_curve.values()))
            d = first.pm25_after - run.pm25_before
            pm25 = {"median": float(np.median(d)), "p5": float(np.percentile(d, 5)),
                    "p95": float(np.percentile(d, 95))}
            if m.scope == "region":
                for summary in per_curve.values():
                    summary.update({k: None for k in (*RATIO_KEYS, *COST_KEYS)})
            elif status == "scored":
                count = trail["cost"]["units_count"]
                net = _society_net(m, iv, count, discount)
                if net is not None and net < 0:
                    status = "pays_for_itself"
                    reason = (f"society as a whole saves money overall (about "
                              f"{-net:,.0f} rupees over its years, net), so it is listed apart, "
                              "not ranked by a ratio")
            if status in ("no_cost", "pays_for_itself"):
                for summary in per_curve.values():
                    summary.update({k: None for k in RATIO_KEYS})
        out.append(Score(
            measure=mid, name=m.name, kind=m.kind, scope=m.scope, place=city, study=used,
            status=status, reason=reason, who_reaches=m.who_reaches, p_success=m.p_success,
            p_success_basis=m.p_success_basis, flags=flags, pm25_change=pm25,
            per_curve=per_curve, trail=trail, run=run))
    return out


def region(measure: str, *, map_name: str = "acag_total", curves: list[str] | None = None,
           n: int = 2000, seed: int = 0, discount: float = simulate.DISCOUNT, deaths=None,
           folder: Path = measures.LIBRARY) -> Score:
    """A regional measure scored over its whole reach: every district of its receptor table whose
    full change is not 0, each changed by region.cut x its own full change (one "delta" run,
    scale per district), with the measure's whole cost (driver "unit", "city" as one total for
    the region, or "person" over everyone reached). The ratio figures for a regional measure
    come from here, never from a city's part.

    Speed: one run is one steady-state calculation per district per curve (three per curve for
    the spread). Timed 2026-11-27 on the maintainer's laptop: receptor_stubble.csv (735 districts),
    n = 1000, the eight curves open with IHME files present: 136 s, over the two minutes the plan
    allowed (n = 100 took 128 s, so the time is per-district work, not draws). Left for plan D to
    decide; no district is dropped to make it faster."""
    from . import measures as library_
    lib = library_.library(folder)
    if measure not in lib:
        raise KeyError(f"no measure {measure!r} in {folder}")
    m = lib[measure]
    if m.scope != "region":
        raise ValueError(f"{measure} is a city measure; score it with airhealth score CITY")
    if map_name not in exposure.DISTRICT_MAPS:
        raise ValueError("a regional measure needs a district map "
                         f"({', '.join(exposure.DISTRICT_MAPS)}), not {map_name}")
    table = measures.receptor(m.region.receptor, folder)
    reach = table[table.delta_pm25_full != 0]
    if reach.empty:
        raise ValueError(f"{m.region.receptor} gives no change in any district")
    reached = [measures.district(r.district, r.state)
               for r in reach.itertuples()]
    people, off_map = 0.0, []
    for p in reached:
        try:
            people += float(exposure.cells(p, map_name).population.sum())
        except KeyError:
            off_map.append(p.label)
    if off_map:
        raise ValueError(f"{len(off_map)} districts of {m.region.receptor} are not on the map "
                         f"{map_name} (e.g. {off_map[0]}); use acag_total, the map the table "
                         "was built on")
    flags = _fixed_flags(m, None)
    trail = _empty_trail("not used: a regional change is one annual figure per district", m)
    trail["region"] = {"receptor": m.region.receptor, "cut": _dist(m.region.cut),
                       "districts": len(reached), "districts_in_table": len(table),
                       "population": people}
    c = m.cost
    if c is None:
        cost = dict(cost_once=Dist.fixed(0.0), cost_annual=Dist.fixed(0.0), cost_currency="INR",
                    cost_year=prices.BASE_YEAR, cost_share_only_on_success=0.0)
        status, reason, count = "no_cost", "it has no cost given, so it is shown but not ranked", 1.0
    else:
        count = people if c.driver == "person" else (1.0 if c.driver == "city" else c.units.median)
        cost = dict(cost_once=_times(c, c.once, count), cost_annual=_times(c, c.annual, count),
                    cost_currency=c.currency, cost_year=c.year,
                    cost_share_only_on_success=c.share_only_on_success)
        trail["cost"] = {"driver": c.driver, "units_count": count, "once": _dist(c.once),
                         "annual": _dist(c.annual), "currency": c.currency, "year": c.year,
                         "cost_in_2025_rupees_basis": _rupees_basis(c.currency, c.year),
                         "unit": c.unit, "units": _dist(c.units),
                         "society_net_once": _dist(c.society_net_once),
                         "society_net_annual": _dist(c.society_net_annual)}
        status, reason = "scored", ""
    iv = Intervention(
        name=m.name, places=reached, change_kind="delta", change=m.region.cut, monthly=None,
        start_year=m.start_year, ramp_years=m.ramp_years, duration_years=m.duration_years,
        p_success=m.p_success, lag=m.lag, notes=m.notes,
        scale=dict(zip((p.label for p in reached), reach.delta_pm25_full)), **cost)
    run = simulate.run(iv, map_name=map_name, curves=curves, n=n, seed=seed, deaths=deaths,
                       discount=discount)
    per_curve = {k: r.summary() for k, r in run.per_curve.items()}
    d = next(iter(run.per_curve.values())).pm25_after - run.pm25_before
    pm25 = {"median": float(np.median(d)), "p5": float(np.percentile(d, 5)),
            "p95": float(np.percentile(d, 95))}
    if status == "scored":
        net = _society_net(m, iv, count, discount)
        if net is not None and net < 0:
            status = "pays_for_itself"
            reason = (f"society as a whole saves money overall (about {-net:,.0f} rupees over "
                      "its years, net), so it is listed apart, not ranked by a ratio")
    if status in ("no_cost", "pays_for_itself"):
        for summary in per_curve.values():
            summary.update({k: None for k in RATIO_KEYS})
    return Score(
        measure=m.id, name=m.name, kind=m.kind, scope=m.scope,
        place=f"the region {m.region.receptor} reaches ({len(reached)} districts)", study=None,
        status=status, reason=reason, who_reaches=m.who_reaches, p_success=m.p_success,
        p_success_basis=m.p_success_basis, flags=tuple(flags), pm25_change=pm25,
        per_curve=per_curve, trail=trail, run=run)


def _clean(x):
    """JSON-safe: numpy numbers as Python ones, NaN and infinity as None, dataclasses as dicts."""
    if isinstance(x, dict):
        return {(k if isinstance(k, str) else str(k)): _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, (Dist, Flag)):
        return _clean(asdict(x))
    if isinstance(x, np.ndarray):
        return _clean(x.tolist())
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, (int, np.integer)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        return None if not math.isfinite(float(x)) else float(x)
    return x


def to_json(scores: list[Score], **context) -> dict:
    """The page's view of a city() result: context (place, study, map, discount, n, seed; any
    not given is taken from the scores), the assumptions, and every Score field except run."""
    runs = [s.run for s in scores if s.run is not None]
    first = runs[0] if runs else None
    out = {
        "place": context.get("place", scores[0].place if scores else None),
        "study": context.get("study", next((s.study for s in scores if s.study), None)),
        "map": context.get("map", first.map_name if first else None),
        "discount": context.get("discount", first.discount if first else None),
        "n": context.get("n", first.n if first else None),
        "seed": context.get("seed", first.seed if first else None),
        "assumptions": list(ASSUMPTIONS),
        "measures": [{f: getattr(s, f) for f in Score.__dataclass_fields__ if f != "run"}
                     for s in scores],
    }
    for m in out["measures"]:
        m["flags"] = [{"code": f.code, "text": f.text} for f in m["flags"]]
    return _clean(out)
