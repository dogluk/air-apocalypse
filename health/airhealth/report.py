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


def _timing(iv, run) -> str:
    ramp = f"ramp {iv.ramp_years} years" if iv.ramp_years else "no ramp"
    rate = f"discounted at {100 * run.discount:g}% a year" if run.discount else "not discounted"
    return (f"{iv.start_year}-{iv.start_year + iv.duration_years - 1}: {iv.duration_years} years, "
            f"{ramp}, lag {iv.lag}, counted over {run.horizon_years} years, {rate}; "
            f"these deliver {run.shares.sum():.1f} years of the full effect, undiscounted")


def _cost_text(run: Run, cost: dict) -> str:
    iv = run.intervention
    if cost["p95"] == 0:
        return "No cost given."
    origin = ("" if (iv.cost_currency, iv.cost_year) == ("INR", 2025)
              else f" (given as {iv.cost_currency} in {iv.cost_year} prices)")
    rate = f", ₹{1 / run.usd_per_unit:.2f} per $ (World Bank 2025 average)"
    s = iv.cost_share_only_on_success
    spent = ("all of it spent whether or not it works" if s == 0
             else f"{100 * s:.0f}% of it spent only if it works")
    return (f"Cost if it works: {_range(cost, _usd)}, in 2025 rupees{origin}{rate}; {spent}.")


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
            e0_change_years=s["e0_change_years"], cost_usd=s["cost_usd"], cost_inr=s["cost_inr"],
            expected_cost_inr=s["expected_cost_inr"],
            inr_per_life_year_if_works=s["inr_per_life_year_if_works"],
            expected_inr_per_expected_life_year=s["expected_inr_per_expected_life_year"],
            life_years_per_crore_if_works=s["life_years_per_crore_if_works"],
            expected_life_years_per_crore=s["expected_life_years_per_crore"],
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
        f"{where}. {_timing(iv, run)}. Probability it works: {100 * iv.p_success:g}%.",
        f"Change: {change_text(iv)}; annual-mean change {after - run.pm25_before:+.2f} µg/m³ "
        f"(PM2.5 {run.pm25_before:.1f} → {after:.1f}, {start}; median draw).",
        f"Population {run.population / 1e6:,.1f} M; "
        f"{_deaths_text(run.deaths_baseline, run.population)}. {run.n:,} draws, seed {run.seed}.",
    ]


def run_footer(run: Run) -> str:
    notes = ["Life-years = deaths postponed by age × remaining life expectancy at the age of "
             "death, at the map year's population and age structure, summed over the "
             f"{run.horizon_years}-year horizon (the intervention's years and the tail of the lag), "
             + (f"discounted at {100 * run.discount:g}% a year" if run.discount else "not discounted"),
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
        discount=run.discount, horizon_years=run.horizon_years,
        monthly_curves=run.monthly_curves,
        cost_currency=iv.cost_currency, cost_year=iv.cost_year, usd_per_unit=run.usd_per_unit,
        cost_share_only_on_success=iv.cost_share_only_on_success,
        rows=run_rows(run), across_curve_spread=across_curve_spread(run),
        fallback_states=run.fallback_states, unavailable=run.unavailable,
        footer=run_footer(run))


# ---- airhealth causes: every study's split of a city's PM2.5, side by side ----

_MON = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def months_text(months: str) -> str:
    """'10,11' -> 'Oct-Nov'; '1-12' -> 'annual'; '12,1,2' -> 'Dec-Feb'; gaps are listed."""
    if months == "1-12":
        return "annual"
    ms = [int(m) for m in str(months).split(",")]
    if all((b - a) % 12 == 1 for a, b in zip(ms, ms[1:])):
        return _MON[ms[0] - 1] if len(ms) == 1 else f"{_MON[ms[0] - 1]}-{_MON[ms[-1] - 1]}"
    return ",".join(_MON[m - 1] for m in ms)


def _pct(x: float) -> str:
    return f"{x:.1f}".rstrip("0").rstrip(".")


def _groups(df):
    """One entry per (study, season): its rows, in the order studies() gives (APnA first)."""
    order = list(dict.fromkeys(df.study))
    order.sort(key=lambda s: (not s.startswith("apna"), s))
    out = []
    for s in order:
        sub = df[df.study == s]
        for season in sorted(sub.season.unique(), key=lambda x: (x != "annual", x)):
            out.append((s, season, sub[sub.season == season]))
    return out


def _evidence(keys) -> str:
    return ", ".join(sorted(set(keys))) + (" (press only)" if set(keys) == {"S"} else "")


def _cols_ruled(head, rows, header_rows: int) -> list[str]:
    """_columns with the rule moved under `header_rows` extra header lines."""
    out = _columns(head, rows)
    return [out[0], *out[2:2 + header_rows], out[1], *out[2 + header_rows:]]


def _year(y) -> str:
    return "year not stated" if y != y else f"sampled {int(y)}"


def causes_table(city: str, df, show_all: bool, harmonised: tuple) -> str:
    """The city's causes rows as one table: a column per (study, season) group whose
    covers = all (every group with show_all), a row per harmonised cause, a total row."""
    groups = _groups(df)
    whole = [g for g in groups if set(g[2].covers) == {"all"}]
    partial = [g for g in groups if set(g[2].covers) != {"all"}]
    cols = groups if show_all else whole
    def split(study):       # a long id wraps at its last underscore: arai_teri_delhi2018 / receptor
        a, _, b = study.rpartition("_")
        return (a, b) if len(study) > 14 and a else (study, "")
    head = ("", *(split(s)[0] for s, _, _ in cols))
    second = ("", *(split(s)[1] for s, _, _ in cols))
    season = ("season", *(f"{se}" + ("".join(
        f" [{m}]" for m, on in (("P", set(g.covers) != {"all"}),
                               ("E", "emission_share" in set(g.metric))) if on))
                         for _, se, g in cols))
    present = [c for c in harmonised if c in set(df.source_harmonised)]
    rows = [second, season]
    for c in present:
        rows.append((c, *(_pct(g[g.source_harmonised == c].share_pct.sum())
                          if (g.source_harmonised == c).any() else "—" for _, _, g in cols)))
    rows.append(("total", *(_pct(g.share_pct.sum()) if set(g.covers) == {"all"} else "—"
                            for _, _, g in cols)))
    lines = [f"{city}: PM2.5 by source, each column one study and season; % of the study's own "
             f"total, — = not reported",
             *(_cols_ruled(head, rows, 2) if cols else ["(no complete split matches)"])]
    if cols and any("emission_share" in set(g.metric) for _, _, g in cols):
        lines.append("[E] = share of emissions, not of PM2.5 concentration; do not compare it with "
                     "the other columns")
    if show_all and partial:
        lines.append("[P] = partial: one piece of a split (not the whole split); the total is not "
                     "shown and it can overlap an `outside` row")
    if partial and not show_all:
        lines.append(f"{len(partial)} partial estimate(s) (one piece of a split, not the whole; "
                     f"they can overlap an `outside` row) are not columns; --all shows them. Listed here:")
        listed: dict[tuple, list[str]] = defaultdict(list)
        for s, se, g in partial:
            for c in harmonised:
                sel = g[g.source_harmonised == c]
                if len(sel):
                    listed[(c, months_text(sel.months.iloc[0]))].append(f"{s} {_pct(sel.share_pct.sum())}")
        for (c, m), items in listed.items():
            lines.append(f"  {c}, {m}: " + ", ".join(items))
    lines.append("")
    lines.append("origin: inside = sources inside the airshed only (outside is its own row); all_origins = "
                 "that sector's contribution from everywhere; region = a split by where the pollution comes "
                 "from. Shares with different origins are not the same quantity.")
    lines.append("Studies:")
    for s in dict.fromkeys(g[0] for g in groups):
        r = df[df.study == s]
        uniq = lambda col: ", ".join(dict.fromkeys(str(v) for v in r[col]))  # noqa: E731
        lines.append(f"  {s}: {uniq('method')}, {', '.join(dict.fromkeys(_year(y) for y in r.year_sampled))}, boundary "
                     f"{uniq('boundary')}, origin {uniq('origin')}, evidence {_evidence(r.evidence_key)}")
        lines.append(f"    {uniq('url')}")
    return "\n".join(lines)


def causes_cities(counts: list[tuple[str, int]]) -> str:
    w = max(len(c) for c, _ in counts)
    return "\n".join([*(f"{c.ljust(w)}  {n} {'study' if n == 1 else 'studies'}" for c, n in counts),
                      "", "airhealth causes CITY shows each study's split of a city's PM2.5."])


# ---- airhealth score: the measure library scored in one city ----

FLAG_CODES = {"placeholder": "PH", "evidence_S": "ES", "evidence_R": "ER", "odds_judgement": "OJ",
              "long_shot": "LS", "not_reported": "NR", "annual_share_flat": "AF",
              "borrowed_shape": "BS", "covered_only": "CO", "regional": "RG",
              "upper_bound_all_origins": "UB", "partial_cost": "PC", "receptor_basis": "RB",
              "receptor_fallback": "RF", "age_group": "AG"}
FLAG_LEGEND = {"PH": "a number is a placeholder", "ES": "a number seen only in a snippet or summary",
               "ER": "a number recalled, not read at the source",
               "OJ": "odds are a judgement", "LS": "long shot",
               "NR": "a targeted cause is not reported by the study (not reported is not zero)",
               "AF": "one whole-year share used for a part-year cut",
               "BS": "month-by-month shape borrowed from another place",
               "CO": "only the covered people breathe less",
               "AG": "only one age group is reached, counted with its own death rates",
               "RG": "a source spread over states; a city's part has no cost of its own (the "
                     "cost belongs to the whole region: airhealth score --region ID)",
               "RB": "what the source-receptor table stands for (its data/sources.toml caveat)",
               "RF": "the source-receptor table is a stand-in (no published one could be used), "
                     "so the result may be far off",
               "UB": "shares include air blown in from outside, so an upper bound",
               "PC": "the cost leaves out part of what the measure costs (listed above)"}
EVIDENCE_LEGEND = "O read at the source; S seen in a snippet or summary; R recalled"


def _flag_codes(flags) -> str:
    seen = []
    for f in flags:
        code = FLAG_CODES.get(f.code, f.code)
        if code not in seen:
            seen.append(code)
    return " ".join(seen) or "-"


def _lyr(d: dict) -> str:
    if d["p5"] == d["p95"]:
        return _sig(d["median"])
    return f"{_sig(d['median'])} ({_sig(d['p5'])} to {_sig(d['p95'])})"


def _crore(a, b) -> str:
    return "-" if a is None else f"{_sig(a)} / {_sig(b)}"


def score_table(scores: list, context: dict) -> str:
    """The scored library as text: one block per curve, measures in library order, then the
    PM2.5 each would change, why any were not a plain scored row, and a footer naming the
    study, map, shape basis, assumptions and the legends."""
    from .score import ASSUMPTIONS
    if not scores:
        return f"No measures in the library for {context.get('place', 'this city')}."
    labels = {}
    for s in scores:
        if s.run is not None:
            for name, cr in s.run.per_curve.items():
                labels.setdefault(name, cr.curve.label)
    lines = [f"{context['place']}: {len(scores)} measures. Life-years are counted over each "
             f"measure's years and the tail of the lag, discounted at "
             f"{100 * context['discount']:g}% a year; cost in 2025 rupees (1 crore = 10 million). "
             f"{context['n']:,} draws, seed {context['seed']}."]
    head = ("measure", "status", "life-years if it works", "expected life-years",
            "cost, ₹ crore median", "life-years per crore: works / expected", "odds", "flags")
    for name in labels or [None]:
        lines += ["", f"Curve {name}: {labels[name]}" if name else "No curve was run."]
        rows = []
        for s in scores:
            c = s.per_curve.get(name)
            odds = f"{100 * s.p_success:g}%"
            if c is None:
                rows.append((s.measure, s.status, "-", "-", "-", "-", odds, _flag_codes(s.flags)))
                continue
            rows.append((s.measure, s.status, _lyr(c["life_years"]),
                         _sig(c["expected_life_years"]),
                         "none given" if s.status == "no_cost"
                         else "whole region" if c["cost_inr"] is None
                         else _sig(c["cost_inr"]["median"] / 1e7),
                         _crore(c["life_years_per_crore_if_works"],
                                c["expected_life_years_per_crore"]),
                         odds, _flag_codes(s.flags)))
        lines += _columns(head, rows)

    ran = [s for s in scores if s.pm25_change is not None]
    if ran:
        lines += ["", "PM2.5 change if it works (annual, µg/m³, median and 5-95% range):"]
        for s in ran:
            d = s.pm25_change
            what = ("what the covered people breathe, the rest unchanged" if s.kind == "exposure"
                    else "population-weighted over the city")
            spread = ("" if d["p5"] == d["p95"]
                      else f" ({d['p5']:+.2f} to {d['p95']:+.2f})")
            lines.append(f"  {s.measure}: {d['median']:+.2f}{spread}, {what}")
    other = [s for s in scores if s.reason]
    if other:
        lines += ["", "Why not a plain scored row:"]
        lines += [f"  {s.measure} ({s.status}): {s.reason}" for s in other]
    partial = [(s.measure, f.text) for s in scores for f in s.flags if f.code == "partial_cost"]
    if partial:
        lines += ["", "What the cost leaves out (PC):"]
        lines += [f"  {mid}: {text}" for mid, text in partial]

    study =context.get("study") or next((s.study for s in scores if s.study), None)
    lines += ["", f"Study: {study}." if study else "Study: none used (no air measure was scored).",
              f"Map: {context['map']}.",
              "Shape: " + "; ".join(sorted({s.trail["shape"] for s in scores})) + ".",
              *("Assumption: " + a for a in ASSUMPTIONS), ""]
    codes = sorted({FLAG_CODES.get(f.code, f.code) for s in scores for f in s.flags})
    lines.append("Flags: " + "; ".join(f"{c} {FLAG_LEGEND.get(c, c)}" for c in codes) + "."
                 if codes else "Flags: none.")
    lines.append(f"Evidence keys: {EVIDENCE_LEGEND}.")
    return "\n".join(lines)


# ---- airhealth rank: the measure library ranked by life-years per crore ----

CSV_COLUMNS = ("place", "curve", "rank", "rank_if_works", "measure", "name", "status", "reason", "kind",
               "scope", "reach", "who_reaches", "life_years_median", "life_years_p5", "life_years_p95",
               "expected_life_years", "cost_inr_mean", "society_net_inr", "ly_per_crore_if_works",
               "expected_ly_per_crore", "p_success", "p_success_basis", "flags", "curves_best_rank",
               "curves_worst_rank", "curves_disagree", "map", "study", "share_basis", "cuts", "cost_basis",
               "evidence")
DASH = "—"        # a rank a measure does not have on a curve


def _months_text(months) -> str:
    months = sorted(int(m) for m in months)
    spans = []
    for m in months:
        if spans and m == spans[-1][1] + 1:
            spans[-1][1] = m
        else:
            spans.append([m, m])
    return ",".join(f"{a}-{b}" if a != b else str(a) for a, b in spans)


def _share_basis(trail: dict) -> str:
    """The trail's {month: study/season} collapsed to text: 'apna_2015/annual: months 1-12'."""
    basis = (trail or {}).get("share_basis") or {}
    by: dict[str, list] = {}
    for month, what in basis.items():
        by.setdefault(str(what), []).append(month)
    return "; ".join(f"{what}: months {_months_text(ms)}" for what, ms in by.items())


def _cuts_text(trail: dict) -> str:
    return "; ".join(f"{c['cause']} months {_months_text(c['months'])} {c['p5']:g}-{c['p95']:g}"
                     for c in (trail or {}).get("cuts") or [])


def _cost_basis(trail: dict) -> str:
    c = (trail or {}).get("cost")
    if not c:
        return ""
    return (f"driver {c.get('driver')}; count {c.get('units_count')}; "
            f"2025-rupee basis: {c.get('cost_in_2025_rupees_basis')}")


def _evidence_text(trail: dict) -> str:
    return " ;; ".join(" | ".join(str(e.get(k, "")) for k in ("source", "locator", "url", "key"))
                       for e in (trail or {}).get("evidence") or [])


def rank_csv_rows(r) -> list[dict]:
    """One row per curve x measure, with the sources behind every number on each row."""
    out = []
    for curve, t in r.tables.items():
        for x in t.rows:
            sp = r.spread.get(x.measure, {})
            ly = x.life_years or {}
            out.append({
                "place": r.place, "curve": curve, "rank": x.rank, "rank_if_works": x.rank_if_works,
                "measure": x.measure, "name": x.name, "status": x.status,
                "reason": x.reason or x.curve_gap,
                "kind": x.kind, "scope": x.scope, "reach": x.reach, "who_reaches": x.who_reaches,
                "life_years_median": ly.get("median"), "life_years_p5": ly.get("p5"),
                "life_years_p95": ly.get("p95"), "expected_life_years": x.expected_life_years,
                "cost_inr_mean": x.mean_cost_inr, "society_net_inr": x.society_net_inr,
                "ly_per_crore_if_works": x.ly_per_crore_if_works,
                "expected_ly_per_crore": x.expected_ly_per_crore, "p_success": x.p_success,
                "p_success_basis": x.p_success_basis, "flags": " ".join(x.flags),
                "curves_best_rank": sp.get("best"), "curves_worst_rank": sp.get("worst"),
                "curves_disagree": sp.get("disagree"), "map": r.context.get("map"),
                "study": x.study or r.context.get("study"), "share_basis": _share_basis(x.trail),
                "cuts": _cuts_text(x.trail), "cost_basis": _cost_basis(x.trail),
                "evidence": _evidence_text(x.trail)})
    return out


def _ratio(x) -> str:
    if x.expected_ly_per_crore is None:
        return DASH
    marks = [FLAG_CODES[f] for f in ("partial_cost", "upper_bound_all_origins") if f in x.flags]
    return _sig(x.expected_ly_per_crore) + (" " + "/".join(marks) if marks else "")


def _flag_text(flags) -> str:
    return " ".join(dict.fromkeys(FLAG_CODES.get(f, f) for f in flags)) or "-"


def _rank_grid(r) -> list[str]:
    curves_ = list(r.tables)
    lines = ["Rank on each curve (1 = most life-years per crore; " + DASH + " = not ranked on that "
             "curve; read the curves side by side, no one of them is the answer)"]
    head = ("measure", "reach", *curves_, "best-worst", "comparable", "curves disagree")
    rows = []
    ranked = [(m, d) for m, d in r.spread.items() if d["best"] is not None]
    ranked.sort(key=lambda md: (md[1]["best"], md[1]["worst"], md[0]))
    for m, d in ranked:
        ranks = [DASH if d["ranks"].get(c) is None else str(d["ranks"][c]) for c in curves_]
        row = next(x for t in r.tables.values() for x in t.rows if x.measure == m)
        if not d["comparable"]:
            comp = "PC"
        elif d["comparable_best"] == d["comparable_worst"]:
            comp = str(d["comparable_best"])
        else:
            comp = f"{d['comparable_best']}-{d['comparable_worst']}"
        rows.append((m, row.reach, *ranks, f"{d['best']}-{d['worst']}", comp,
                     "curves disagree" if d["disagree"] else ""))
    if not rows:
        return lines + ["  No measure is ranked on any curve."]
    return lines + _columns(head, rows)


def _curve_table(rows, show_reach: bool) -> list[str]:
    head = ["rank", "measure", *(["reach"] if show_reach else []), "expected life-years per crore",
            "per crore if it works", "rank if works", "life-years if it works (median, p5-p95)",
            "cost, ₹ crore (mean)", "society's net cost, ₹ crore", "odds", "comparable rank", "flags"]
    body = []
    for x in rows:
        body.append((str(x.rank), x.measure, *([x.reach] if show_reach else []), _ratio(x),
                     DASH if x.ly_per_crore_if_works is None else _sig(x.ly_per_crore_if_works),
                     DASH if x.rank_if_works is None else str(x.rank_if_works),
                     _lyr(x.life_years) if x.life_years else DASH,
                     DASH if x.mean_cost_inr is None else _sig(x.mean_cost_inr / 1e7),
                     DASH if x.society_net_inr is None else _sig(x.society_net_inr / 1e7),
                     f"{100 * x.p_success:g}%",
                     "PC" if x.rank_comparable is None else str(x.rank_comparable),
                     _flag_text(x.flags)))
    return _columns(tuple(head), body)


def rank_table(r) -> str:
    """The ranking as text: the grid of ranks on every curve first, then one table per curve,
    the measures listed apart or not ranked (with why), and a footer of settings, assumptions
    and legends."""
    from .rank import INDIA, RANK_ASSUMPTIONS
    from .score import ASSUMPTIONS
    india = r.place == INDIA
    lines = [f"Ranking of measures by life-years per crore: {r.place}. Each measure is ranked on its "
             "own; benefits do not add up. 1 crore = 10 million rupees, 2025 rupees."]
    lines += ["", *_rank_grid(r)]
    legend_gaps = []
    for curve, t in r.tables.items():
        ranked = [x for x in t.rows if x.rank is not None]
        lines += ["", f"Curve {curve}: {t.curve_label}"]
        if not ranked:
            lines.append("  No measure is ranked on this curve.")
        elif india:
            lines += _curve_table(ranked, True)
        else:
            city_rows = [x for x in ranked if x.scope != "region"]
            region_rows = [x for x in ranked if x.scope == "region"]
            lines += _curve_table(city_rows, False) if city_rows else ["  No city measure is ranked."]
            if region_rows:
                lines += ["", "Regional measures. Their ratio is over their whole reach, and most of their "
                          "benefit falls outside this city; their life-years here are only this city's part.",
                          *_curve_table(region_rows, True)]
        legend_gaps += [(curve, x) for x in t.rows if x.curve_gap]

    first = next(iter(r.tables.values()), None)
    rest = [x for x in (first.rows if first else ()) if x.rank is None and not x.curve_gap]
    for status, title in (("pays_for_itself", "Pays for itself (no rank)"),
                          ("no_cost", "No cost given (no rank)")):
        group = [x for x in rest if x.status == status]
        if group:
            lines += ["", title + ":"]
            lines += [f"  {x.measure}: {x.reach}; life-years if it works "
                      f"{_lyr(x.life_years) if x.life_years else DASH}; {x.reason}" for x in group]
    others = [x for x in rest if x.status not in ("pays_for_itself", "no_cost")]
    if others:
        lines += ["", "Not ranked (why):"]
        lines += [f"  {x.measure} ({x.status}): {x.reason}" for x in others]
    if legend_gaps:
        lines += ["", f"{DASH} in the grid means no rank on that curve:"]
        lines += [f"  {x.measure} on {c}: {x.curve_gap}" for c, x in legend_gaps]

    ctx = r.context
    lines += ["", f"Place: {r.place}. Map: {ctx.get('map')}. Study: {ctx.get('study') or 'none'}. "
              f"Deaths: {ctx.get('deaths') or 'default'}. Discount: {100 * ctx.get('discount', 0):g}% a year. "
              f"{ctx.get('n'):,} draws, seed {ctx.get('seed')}.",
              *("Assumption: " + a for a in (*ASSUMPTIONS, *RANK_ASSUMPTIONS))]
    if ctx.get("curves_unavailable"):
        lines.append("Curves not run: " + "; ".join(f"{k}: {v}" for k, v in ctx["curves_unavailable"].items()))
    lines += ["", "PC beside a ratio: the cost leaves out part of what the measure costs, so its ratio is "
              "flattering; the comparable column ranks without such measures. UB: shares include air blown "
              "in from outside, an upper bound."]
    used = sorted({FLAG_CODES.get(f, f) for t in r.tables.values() for x in t.rows for f in x.flags})
    lines.append("Flags: " + "; ".join(f"{c} {FLAG_LEGEND.get(c, c)}" for c in used) + "."
                 if used else "Flags: none.")
    lines.append(f"Evidence keys: {EVIDENCE_LEGEND}.")
    return "\n".join(lines)


# --- sensitivity: what reorders the ranking --------------------------------------------------

def _nan(x) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x))


def _names(xs) -> str:
    return ", ".join(xs) if xs else DASH


def _research_block(s, comparable: bool) -> list[str]:
    res = s.research(comparable)
    n_curves = len(s._curves())
    head = ("research unit", f"curves where the top {s.top} changes", "on curves", "enter", "leave",
            "largest move", "within noise only", "drops out of the top")
    rows, quiet = [], []
    for x in res.itertuples():
        if x.unit != "seed" and not (x.curves_top_changed or x.within_noise or x.drops_out):
            quiet.append(x.unit)
            continue
        unit = x.unit + (" (noise floor)" if x.unit == "seed" else "")
        rows.append((unit, f"{x.curves_top_changed} of {n_curves}", _names(x.curves),
                     _names(x.enter), _names(x.leave),
                     DASH if _nan(x.max_abs_delta) else f"{x.max_abs_delta:g}",
                     str(x.within_noise) if x.within_noise else "", _names(x.drops_out)))
    out = _columns(head, rows) if rows else ["  No setting changes the top."]
    if quiet:
        out.append(f"  No change to the top {s.top} on any curve: {', '.join(sorted(quiet))}.")
    return out


def _spread_block(s, comparable: bool) -> list[str]:
    st = s.stability(comparable)
    curves_ = s._curves()
    cells: dict = {}
    first: dict = {}
    for x in st.itertuples():
        base = DASH if _nan(x.base_rank) else str(int(x.base_rank))
        cell = f"{base} ({x.best}-{x.worst})"
        if x.drops_out:
            cell += f" out{x.drops_out}"
        cells.setdefault(x.measure, {})[x.curve] = cell
        if not _nan(x.base_rank):
            first[x.measure] = min(first.get(x.measure, 10 ** 6), x.base_rank)
    order = sorted(cells, key=lambda m: (first.get(m, 10 ** 6), m))
    rows = [(m, *(cells[m].get(c, DASH) for c in curves_)) for m in order]
    return _columns(("measure", *curves_), rows) if rows else ["  No measure is ranked."]


def _movers_block(s, comparable: bool) -> list[str]:
    mv = s.movers(comparable)
    curves_ = s._curves()
    cells: dict = {}
    for x in mv.itertuples():
        if x.unit is None:
            text = "none"
        else:
            text = f"{x.unit} {x.delta:+g}"
            if x.within_noise:
                text = f"({text})"
        got = cells.setdefault(x.measure, {})
        got[x.curve] = text if x.curve not in got else got[x.curve] + " | " + text
    rows = [(m, *(cells[m].get(c, DASH) for c in curves_)) for m in cells]
    return _columns(("measure", *curves_), rows) if rows else ["  No measure is ranked."]


def _odds_block(s, comparable: bool) -> list[str]:
    be = s.break_even_odds(comparable)
    curves_ = list(s.base.tables)
    cells: dict = {}
    odds: dict = {}
    for x in be.itertuples():
        cells.setdefault(x.measure, {})[x.curve] = (f"{x.pass_above or DASH} / "
                                                    f"{x.fall_below or DASH}")
        odds[x.measure] = x.p_success
    rows = [(m, f"{100 * odds[m]:g}%", *(cells[m].get(c, DASH) for c in curves_)) for m in cells]
    return (_columns(("measure", "odds now", *curves_), rows) if rows
            else ["  No measure is ranked."])


def sensitivity_table(s) -> str:
    """The sensitivity as text: (1) what would reorder the top K, the research list, first;
    (2) each measure's default rank on each curve and its range across all settings; (3) the
    biggest mover per measure per curve, within-noise moves in brackets; (4) break-even odds;
    (5) the settings, defaults and notes. Blocks 1-4 among all measures, then among comparable
    ones."""
    from .sensitivity import CANNOT, notes
    ctx = s.base.context
    lines = [f"What reorders the ranking: {s.place}. {len(s.settings)} settings, each moving one "
             f"input from the defaults; the top of the table is the first {s.top} (a display "
             "choice). Ranks are never averaged."]
    alls = (False, True)

    def among(comparable):
        return ("among comparable measures (costs that leave part out, PC, set aside)"
                if comparable else "among all ranked measures")
    for c in alls:
        lines += ["", f"1. What would reorder the top {s.top}, {among(c)}: the research list. A "
                  "unit is one input, one measure's effect or cost range, or one city's study; a "
                  "curve counts when one of its settings changes which measures make the top by "
                  "more than another random seed does.", *_research_block(s, c)]
    for c in alls:
        lines += ["", f"2. Rank on each curve by default, {among(c)}, and (best-worst) across every "
                  f"setting; outN: not ranked under N settings; {DASH} first: not ranked by default.",
                  *_spread_block(s, c)]
    for c in alls:
        lines += ["", f"3. The input that moves each measure most on each curve, {among(c)} "
                  "(+ down the table, - up; in brackets: no larger than another seed's move, "
                  "within noise).", *_movers_block(s, c)]
    for c in alls:
        lines += ["", f"4. Break-even odds, {among(c)}: the odds that it works at which it would "
                  "pass the measure above it / fall below the one below it, on the default "
                  f"ranking ({DASH} at the ends; '{CANNOT}' as it says).", *_odds_block(s, c)]
    lines += ["", "Settings:", *(f"  {x.id}: {x.label}" for x in s.settings)]
    if s.skipped:
        lines += ["", "Settings that could not be run:",
                  *(f"  {k}: {v}" for k, v in s.skipped.items())]
    lines += ["", f"Defaults: map {ctx.get('map')}; study {ctx.get('study') or 'none'}; deaths "
              f"{ctx.get('deaths') or 'SRS'}; discount {100 * ctx.get('discount', 0):g}% a year; "
              f"{ctx.get('n'):,} draws, seed {ctx.get('seed')}.",
              *("Note: " + t for t in notes(s))]
    return "\n".join(lines)
