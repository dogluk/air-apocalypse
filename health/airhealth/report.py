"""Tables and JSON for impact results, one row per curve.

Every table ends with one line naming the exposure map and year, how the death counts were
scaled to the SRS crude death rate (or that they were not), the states that fell back to
all-India death rates, and the curves that were asked for but could not run, with why.
run_table() and run_json() do the same for an intervention run (simulate.Run).
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import TYPE_CHECKING

import numpy as np

from . import baseline, curves, exposure
from .curves import IHME_REASON, NOT_BUILT  # noqa: F401  (re-exported for callers)
from .impact import Impact
from .months import MONTHS

if TYPE_CHECKING:
    from .simulate import Run

select_curves = curves.select     # the selection lives with the curves; kept here by name


def place_label(impact: Impact) -> str:
    return impact.place.label


def _row(i: Impact) -> dict:
    return dict(
        curve=i.curve.name, label=i.curve.label, map=i.map_name, year=i.year,
        pm25_before=round(i.pm25_before, 2), pm25_after=round(i.pm25_after, 2),
        share_of_deaths_averted=i.deaths_averted / i.deaths_baseline,
        deaths_averted=i.deaths_averted, life_expectancy_gain=i.e0_after - i.e0_before,
        e0_before=i.e0_before, e0_after=i.e0_after, life_years_averted=i.yll_averted,
        deaths_derived=i.derived, floor=i.curve.floor, below_floor=_below_floor(i))


def _below_floor(i: Impact) -> bool:
    """Part of the move lies below the curve's floor, where it counts no further benefit."""
    return min(i.pm25_before, i.pm25_after) < i.curve.floor - 1e-9


def population_note(population_year: int, year: int, places: list[str]) -> str | None:
    """Cities carry their Census population in every year; say so when that is in use."""
    if population_year == year:
        return None
    return (f"Population of {', '.join(places)}: Census {population_year} urban agglomeration, "
            f"not updated to {year}; deaths and life-years are low by however much the city "
            f"has grown since")


def sources_note(src) -> str:
    """Which source each demographic input came from, and whether bodies are mixed."""
    text = src.text
    if len(src.bodies) > 1:
        text += ("; this run mixes the Indian government's and the United Nations' figures "
                 "(allowed; see airhealth list inputs)")
    return text


def deaths_note(recs, deaths: float, deaths_model: float, un=None) -> str:
    """How the death counts were scaled: `recs` are the states' Reconciliations (none when
    the counts are not scaled to the SRS), `un` the UN scaling if that was used, deaths the
    count used and deaths_model the unscaled one."""
    if un is not None:
        return (f"{un.text[0].upper()}{un.text[1:]}, the same factors in every state: "
                f"×{deaths / deaths_model:.2f} overall here; life expectancy is not scaled")
    if not recs:
        return ("Deaths are population × life-table death rates, not reconciled to the SRS "
                "crude death rate (--deaths model)")
    early = any(r.period != baseline.PERIOD_TEXT for r in recs)
    tail = "the scaling does not touch life expectancy" if early else \
        "life expectancy is from the unscaled life table"
    if len(recs) == 1:
        text = recs[0].text
        return f"{text[0].upper()}{text[1:]}; {tail}"
    factors = [r.factor for r in recs]
    return (f"Deaths scaled to each state's SRS crude death rate for {_years(recs)}: "
            f"×{deaths / deaths_model:.2f} overall, ×{min(factors):.2f} to ×{max(factors):.2f} "
            f"by state (data/{_recon_file(recs)}); {tail}{'' if early else 's'}")


def _recon_file(recs) -> str:
    early = any(r.period != baseline.PERIOD_TEXT for r in recs)
    return "death_reconciliation_by_year.csv" if early else "death_reconciliation.csv"


def _years(recs) -> str:
    """The years the scaling's SRS rates are for: one label, or the year and its exceptions.
    States with no SRS life table (from_age 0) are listed elsewhere in the footer, so they
    are counted here, not named."""
    periods = dict.fromkeys(r.period for r in recs)
    if len(periods) == 1:
        return next(iter(periods))
    main = max(periods, key=lambda p: sum(r.period == p for r in recs))
    rest = []
    for p in periods:
        if p == main:
            continue
        named = [r.state for r in recs if r.period == p and r.from_age]
        unnamed = sum(1 for r in recs if r.period == p and not r.from_age)
        who = named + ([f"the {unnamed} without an SRS life table"] if unnamed else [])
        rest.append(f"{p} for {', '.join(who)}")
    return f"{main} ({'; '.join(rest)}: no SRS rate for {main})"


def rates_note(adjs, fallback=()) -> str | None:
    """An early year's death rates by age: whose SRS rates moved them, and over which years."""
    if not adjs:
        return None
    a = adjs[0]
    if len(adjs) == 1:
        return (f"Death rates by age for {a.state} are the {baseline.PERIOD_TEXT} life table "
                f"moved band by band by {a.text} against {baseline.PERIOD_TEXT}; life expectancy "
                f"moves with them")
    borrowed = [x.state for x in adjs
                if x.unit == "India" and x.state != "India" and x.state not in fallback]
    tail = (f"; India's used for {', '.join(borrowed)}" if borrowed else "")
    return (f"Death rates by age are the {baseline.PERIOD_TEXT} life tables moved band by band "
            f"by each state's own SRS rates by age for {a.years[0]}-{a.years[1] % 100} against "
            f"{baseline.PERIOD_TEXT}{tail}; life expectancy moves with them")


def period_note(year: int, src) -> str | None:
    """After the life-table period no SRS rate checks the counts; say what they rest on.
    (Early years carry their own rates and scaling, named by rates_note and deaths_note.)"""
    if year <= baseline.LIFE_TABLE_PERIOD[1]:
        return None
    if src.deaths == "unwpp":
        return (f"Death counts for {year} are the UN's projection (WPP 2024, Medium variant), "
                f"not an observed figure")
    rates = ("the UN's projected death rates" if src.death_rates == "unwpp"
             else f"{baseline.PERIOD_TEXT} death rates")
    if src.deaths == "model":
        return f"Death rates for {year}: {rates}, not checked against any observed figure"
    return (f"Death counts for {year} are not checked against that year's SRS crude death "
            f"rate: they are projected, {rates} and the {baseline.PERIOD_TEXT} scaling on "
            f"{year}'s population")


def ihme_note(curves_: list, year: int) -> str | None:
    """Where a cause-specific curve's deaths come from (ihme_curves): IHME's, not the SRS's."""
    cause = [c for c in curves_ if c.death_scope == "causes"]
    if not cause:
        return None
    from . import ihme
    text = (f"Deaths for {', '.join(c.name for c in cause)}: the GBD 2023 round's death rates by "
            f"state, cause and age for {ihme.rates_text(year)} × this tool's population, not "
            f"scaled to the SRS; their share of deaths is of the all-cause count above. "
            f"Ladakh takes GBD's Jammu & Kashmir and Ladakh, and Andaman & Nicobar, Chandigarh, "
            f"Dadra & Nagar Haveli, Daman & Diu, Lakshadweep and Puducherry GBD's pooled Other "
            f"Union Territories")
    extra = [f"{c.name}: {c._note}" for c in cause if getattr(c, "_note", "")]
    return text + "".join(f"; {e}" for e in extra)


def _auto_notes(impacts: list[Impact]) -> list[str]:
    if not impacts:
        return []
    i = impacts[0]
    notes = [ihme_note([x.curve for x in impacts], i.year),
             population_note(i.population_year, i.year, [i.place.name]),
             deaths_note(i.reconciliations, i.deaths_baseline, i.deaths_model, i.un_scaling),
             rates_note(i.rate_adjustments, i.fallback_states),
             period_note(i.year, i.sources),
             sources_note(i.sources)]
    return [n for n in notes if n]


def footer(impacts: list[Impact], unavailable: dict[str, str] | None = None,
           notes: tuple[str, ...] = ()) -> str:
    if unavailable is None:
        unavailable = select_curves()[1]
    maps = dict.fromkeys((i.map_name, i.year) for i in impacts)
    fallback = sorted({s for i in impacts for s in i.fallback_states})
    return _footer(maps, fallback, unavailable, [*notes, *_auto_notes(impacts)])


def _deaths_text(deaths: float, population: float) -> str:
    return f"all-cause deaths {deaths:,.0f} a year ({1000 * deaths / population:.1f} per 1,000)"


def _footer(maps, fallback: list[str], unavailable: dict[str, str], notes=()) -> str:
    parts = ["Map: " + "; ".join(f"{m} {y} ({exposure.LABELS[m]})" for m, y in maps) + "."] if maps else []
    parts += [n.rstrip(".") + "." for n in notes]
    if fallback:
        parts.append(f"All-India death rates used for {', '.join(fallback)} (no SRS life table).")
    by_reason = defaultdict(list)
    for name, reason in unavailable.items():
        by_reason[reason].append(name)
    for reason, names in by_reason.items():
        parts.append(f"Not run: {', '.join(names)}: {reason}.")
    return " ".join(parts)


def table(impacts: list[Impact], unavailable: dict[str, str] | None = None,
          heading: str = "", notes: tuple[str, ...] = ()) -> str:
    """Rows across curves, a key to the curves, and the footer line last."""
    if not impacts:
        return footer(impacts, unavailable, notes)
    first = impacts[0]
    lines = [heading or place_label(first),
             f"Population {first.population / 1e6:,.1f} M; "
             f"{_deaths_text(first.deaths_baseline, first.population)}. Steady state, per year.",
             ""]
    head = ("curve", "PM2.5 µg/m³", "% of deaths", "deaths/yr", "life exp. yrs", "life-years/yr")
    rows = []
    for i in impacts:
        name = i.curve.name + (" *" if i.derived else "") + (" †" if _below_floor(i) else "")
        rows.append((name, f"{i.pm25_before:.1f} → {i.pm25_after:.1f}",
                     f"{100 * i.deaths_averted / i.deaths_baseline:.1f}%",
                     f"{i.deaths_averted:,.0f}", f"{i.e0_after - i.e0_before:+.2f}",
                     f"{i.yll_averted:,.0f}"))
    widths = [max(len(r[k]) for r in [head, *rows]) for k in range(len(head))]
    fmt = lambda r: "  ".join(r[0].ljust(widths[0]) if k == 0 else r[k].rjust(widths[k])  # noqa: E731
                              for k in range(len(r)))
    lines += [fmt(head), "  ".join("-" * w for w in widths), *map(fmt, rows), ""]
    lines += [f"  {i.curve.name}: {i.curve.label}" for i in impacts]
    if any(i.derived for i in impacts):
        lines.append("  * deaths derived from the life-expectancy change, not a relative risk")
    low = [i for i in impacts if _below_floor(i)]
    if low:
        lines.append("  † part of this move is below the curve's floor, where the curve counts no "
                     "further benefit (floor, µg/m³: "
                     + ", ".join(f"{i.curve.name} {i.curve.floor:g}" for i in low) + ")")
    lines += ["", footer(impacts, unavailable, notes)]
    return "\n".join(lines)


def to_json(impacts: list[Impact], unavailable: dict[str, str] | None = None,
            heading: str = "", notes: tuple[str, ...] = ()) -> dict:
    if unavailable is None:
        unavailable = select_curves()[1]
    first = impacts[0] if impacts else None
    return dict(
        heading=heading or (place_label(first) if first else ""),
        place=dict(name=first.place.name, kind=first.place.kind, state=first.place.state) if first else None,
        population=first.population if first else None,
        population_year=first.population_year if first else None,
        deaths_baseline=first.deaths_baseline if first else None,
        deaths_basis=first.sources.deaths if first else None,
        sources=_sources_json(first.sources) if first else None,
        deaths_unscaled=first.deaths_model if first else None,
        death_scaling=_scaling_json(first.reconciliations) if first else [],
        rows=[_row(i) for i in impacts],
        fallback_states=sorted({s for i in impacts for s in i.fallback_states}),
        unavailable=unavailable, notes=list(notes),
        footer=footer(impacts, unavailable, notes))


def _sources_json(src) -> dict:
    return {i.name: s.name for i, s in src.items()}


def _scaling_json(recs) -> list[dict]:
    return [dict(state=r.state, factor=r.factor, from_age=r.from_age,
                 srs_crude_death_rate_per_1000=r.srs_cdr, srs_unit=r.srs_unit,
                 period=r.period) for r in recs]


# --- intervention runs ----------------------------------------------------------------------

NO_INTERVAL = "no published interval"


def _sig(x: float) -> str:
    """Three significant figures, with thousands separators."""
    if x == 0 or not math.isfinite(x):
        return f"{x:g}"
    r = round(x, 2 - math.floor(math.log10(abs(x))))
    return f"{r:,.0f}" if abs(r) >= 100 else f"{r:#.3g}"


def _usd(x: float) -> str:
    sign, a = ("-" if x < 0 else ""), abs(x)
    for size, unit in ((1e9, " bn"), (1e6, " M")):
        if a >= size:
            return f"{sign}${a / size:.3g}{unit}"
    return f"{sign}${_sig(a)}"


PM25_ONLY = "PM2.5 change only"


def _range(d: dict, fmt=_sig, interval: str = "published") -> str:
    """median (5-95% range). A curve with no published interval has no range of its own:
    with a fixed PM2.5 change the value stands alone, and with a sampled one the range is
    labelled as covering the PM2.5 change only. A zero-width range is never printed."""
    if interval == "none" or d["p5"] == d["p95"]:
        return fmt(d["median"]) + (f" ({NO_INTERVAL})" if interval == "none" else "")
    tail = f"; {PM25_ONLY}" if interval == "pm25_change_only" else ""
    return f"{fmt(d['median'])} ({fmt(d['p5'])} to {fmt(d['p95'])}{tail})"


def _interval(r) -> str:
    """published: the curve's own uncertainty is in the range. pm25_change_only: the curve
    publishes no interval, so the range reflects the sampled PM2.5 change alone. none: no
    published interval and a fixed change, so there is no range at all."""
    if r.widths["curve_parameters"] > 0 or r.spread["curve_parameters"] > 0:
        return "published"
    return "pm25_change_only" if r.widths["pm25_change"] > 0 else "none"


def _without_range(d: dict) -> dict:
    return dict(d, p5=None, p95=None)


def _dist_text(d, unit: str) -> str:
    if d.kind == "fixed":
        return f"{d.p5:+g}{unit}"
    return f"{d.kind}, 5-95% {d.p5:g} to {d.p95:g}{unit}"


def change_text(iv) -> str:
    """The intervention's change in PM2.5 as written in its file."""
    unit = "%" if iv.change_kind == "pct" else " µg/m³"
    if iv.monthly is not None:
        moved = [f"{m} {_dist_text(d, unit)}" for m, d in zip(MONTHS, iv.monthly)
                 if not (d.kind == "fixed" and d.p5 == 0)]
        return f"monthly {iv.change_kind}: {', '.join(moved) or 'none'}; other months 0"
    if iv.change_kind == "to":
        return f"to {_dist_text(iv.change, unit).lstrip('+')}"
    return f"{iv.change_kind} {_dist_text(iv.change, unit)}"


def _timing(iv, shares) -> str:
    ramp = f"ramp {iv.ramp_years} years" if iv.ramp_years else "no ramp"
    return (f"{iv.start_year}-{iv.start_year + iv.duration_years - 1}: {iv.duration_years} years, "
            f"{ramp}, lag {iv.lag}; these deliver {shares.sum():.1f} years of the full effect")


def _cost_text(run: Run, cost: dict) -> str:
    iv = run.intervention
    if cost["p95"] == 0:
        return "No cost given."
    rate = ("" if iv.cost_currency == "USD"
            else f", ₹{1 / run.usd_per_unit:.2f} per $ (World Bank {iv.cost_year} average)")
    s = iv.cost_share_only_on_success
    spent = ("all of it spent whether or not it works" if s == 0
             else f"{100 * s:.0f}% of it spent only if it works")
    return (f"Cost if it works: {_range(cost, _usd)}, {iv.cost_year} prices{rate}, no inflation "
            f"adjustment; {spent}.")


def run_rows(run: Run) -> list[dict]:
    rows = []
    for name, r in run.per_curve.items():
        s = r.summary()
        interval = _interval(r)
        if interval == "none":      # no range to report: p5 and p95 are null, not the median
            for key in ("life_years", "deaths_postponed", "e0_change_years"):
                s[key] = _without_range(s[key])
        rows.append(dict(
            curve=name, label=r.curve.label, deaths_derived=r.curve.kind == "life_expectancy",
            published_interval=interval == "published", interval=interval,
            life_years=s["life_years"], deaths_postponed=s["deaths_postponed"],
            e0_change_years=s["e0_change_years"], cost_usd=s["cost_usd"],
            expected_life_years=s["expected_life_years"], expected_cost_usd=s["expected_cost_usd"],
            cost_per_life_year_if_works=s["cost_per_life_year_if_works"],
            expected_cost_per_expected_life_year=s["expected_cost_per_expected_life_year"],
            spread=r.spread, spread_widths=r.widths))
    return rows


def _columns(head: tuple, rows: list[tuple]) -> list[str]:
    widths = [max(len(r[k]) for r in [head, *rows]) for k in range(len(head))]
    fmt = lambda r: "  ".join(r[0].ljust(widths[0]) if k == 0 else r[k].rjust(widths[k])  # noqa: E731
                              for k in range(len(r)))
    return [fmt(head), "  ".join("-" * w for w in widths), *map(fmt, rows)]


def _run_heading(run: Run) -> list[str]:
    iv = run.intervention
    first = next(iter(run.per_curve.values()))
    after = float(np.median(first.pm25_after))
    where = "; ".join(f"{p.name} ({p.kind})" if p.kind in ("country", "state")
                      else f"{p.name}, {p.state} ({p.kind})" for p in iv.places)
    start = (f"every unit set to {iv.from_level:g} µg/m³ (from_level), the map supplying "
             "population only" if iv.from_level is not None else "population-weighted")
    return [
        iv.name,
        f"{where}. {_timing(iv, run.shares)}. Probability it works: {100 * iv.p_success:g}%.",
        f"Change: {change_text(iv)}; annual-mean change {after - run.pm25_before:+.2f} µg/m³ "
        f"(PM2.5 {run.pm25_before:.1f} → {after:.1f}, {start}; median draw).",
        f"Population {run.population / 1e6:,.1f} M; "
        f"{_deaths_text(run.deaths_baseline, run.population)}. {run.n:,} draws, seed {run.seed}.",
    ]


def run_footer(run: Run) -> str:
    notes = ["Life-years = deaths postponed by age × remaining life expectancy at the age of "
             "death, at the map year's population and age structure, summed over the "
             "intervention's years",
             ihme_note([c.curve for c in run.per_curve.values()], run.year),
             population_note(run.population_year, run.year, run.census_places),
             deaths_note(run.reconciliations, run.deaths_baseline, run.deaths_model,
                         run.un_scaling),
             rates_note(run.rate_adjustments, run.fallback_states),
             period_note(run.year, run.sources),
             sources_note(run.sources)]
    iv = run.intervention
    if iv.monthly is not None and iv.change_kind == "pct":
        shape_notes = [f"monthly_pct weights each month by the PM2.5 shape of {label} (CPCB monthly "
                       f"means): {sh.basis}"
                       + ("; borrowed, not this place's own monitors"
                          if sh.borrowed and not sh.basis.startswith("borrowed") else "")
                       for label, sh in run.shapes.items()]
        notes = shape_notes + notes
    notes = [n for n in notes if n]
    return _footer({(run.map_name, run.year): None}, run.fallback_states, run.unavailable, notes)


def run_table(run: Run) -> str:
    """The run as text: results if it works, expected results and cost, what drives the
    spread, a key to the curves, and the footer line last."""
    from .simulate import across_curve_spread
    rows = run_rows(run)
    star = lambda r: r["curve"] + (" *" if r["deaths_derived"] else "")  # noqa: E731
    lines = [*_run_heading(run), "",
             "If it works, totals over the run (median, 5-95% range):"]
    lines += _columns(("curve", "life-years", "deaths postponed", "life exp. at full effect, yrs"),
                      [(star(r), _range(r["life_years"], interval=r["interval"]),
                        _range(r["deaths_postponed"], interval=r["interval"]),
                        _range(r["e0_change_years"], lambda v: f"{v:+.2f}", r["interval"]))
                       for r in rows])

    cost = rows[0]["cost_usd"]
    lines += ["", f"Expected = mean if it works × probability it works "
              f"({run.intervention.p_success:g}). {_cost_text(run, cost)}"]
    per_ly = lambda v: "no life-years gained" if v is None else _usd(v)  # noqa: E731
    if cost["p95"] == 0:
        lines += _columns(("curve", "expected life-years"),
                          [(star(r), _sig(r["expected_life_years"])) for r in rows])
    else:
        lines += _columns(("curve", "expected life-years", "cost per life-year if it works",
                           "expected cost per expected life-year"),
                          [(star(r), _sig(r["expected_life_years"]),
                            per_ly(r["cost_per_life_year_if_works"]),
                            per_ly(r["expected_cost_per_expected_life_year"])) for r in rows])
        lines.append("  (costs per life-year are ratios of means over the draws)")

    lines += ["", "What drives the spread in life-years within each curve (share of variance, "
              "each part sampled alone):"]
    lines += _columns(("curve", "PM2.5 change", "curve parameters"),
                      [(star(r), f"{100 * r['spread']['pm25_change']:.0f}%",
                        f"{100 * r['spread']['curve_parameters']:.0f}%" if r["published_interval"]
                        else NO_INTERVAL) for r in rows])
    if len(rows) > 1:
        lines.append(f"Across curves, the largest median life-years is "
                     f"{across_curve_spread(run):.1f}× the smallest.")
    lines.append("")
    lines += [f"  {r['curve']}: {r['label']}" for r in rows]
    if any(r["deaths_derived"] for r in rows):
        lines.append("  * deaths derived from the life-expectancy change, not a relative risk")
    lines += ["", run_footer(run)]
    return "\n".join(lines)


def run_json(run: Run) -> dict:
    from .simulate import across_curve_spread
    iv = run.intervention
    first = next(iter(run.per_curve.values()))
    return dict(
        name=iv.name, places=[dict(name=p.name, kind=p.kind, state=p.state) for p in iv.places],
        map=run.map_name, year=run.year, n=run.n, seed=run.seed, p_success=iv.p_success,
        change=change_text(iv), pm25_before=run.pm25_before,
        annual_mean_change_median=float(np.median(first.pm25_after)) - run.pm25_before,
        population=run.population, deaths_baseline=run.deaths_baseline,
        deaths_basis=run.sources.deaths, sources=_sources_json(run.sources),
        deaths_unscaled=run.deaths_model, death_scaling=_scaling_json(run.reconciliations),
        population_year=run.population_year,
        start_year=iv.start_year, duration_years=iv.duration_years, ramp_years=iv.ramp_years,
        lag=iv.lag, realised_share_by_year=[float(x) for x in run.shares],
        cost_currency=iv.cost_currency, cost_year=iv.cost_year, usd_per_unit=run.usd_per_unit,
        cost_share_only_on_success=iv.cost_share_only_on_success,
        rows=run_rows(run), across_curve_spread=across_curve_spread(run),
        fallback_states=run.fallback_states, unavailable=run.unavailable,
        footer=run_footer(run))
