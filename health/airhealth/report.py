"""Tables and JSON for impact results, one row per curve.

Every table ends with one line naming the exposure map and year, the states that fell back
to all-India death rates, and the curves that were asked for but could not run, with why.
run_table() and run_json() do the same for an intervention run (simulate.Run).
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import TYPE_CHECKING

import numpy as np

from . import curves, exposure
from .curves import Curve, Unavailable
from .impact import Impact

if TYPE_CHECKING:
    from .simulate import Run

IHME_REASON = "need IHME files in health/data_local/ (see health/IHME_DOWNLOADS.md)"
NOT_BUILT = "IHME files present, but the curve is not built yet"


def select_curves(names: list[str] | None = None) -> tuple[list[Curve], dict[str, str]]:
    """The curves that can run, and the reason each of the rest cannot. names=None means
    every registered curve. An unknown name raises KeyError."""
    names = names or [*(c.name for c in curves.available()), *curves.IHME]
    run, unavailable = [], {}
    for name in dict.fromkeys(names):
        try:
            run.append(curves.get(name))
        except Unavailable:
            unavailable[name] = IHME_REASON
        except NotImplementedError:
            unavailable[name] = NOT_BUILT
    return run, unavailable


def place_label(impact: Impact) -> str:
    p = impact.place
    return f"{p.name} ({p.kind})" if p.kind in ("country", "state") else f"{p.name}, {p.state} ({p.kind})"


def _row(i: Impact) -> dict:
    return dict(
        curve=i.curve.name, label=i.curve.label, map=i.map_name, year=i.year,
        pm25_before=round(i.pm25_before, 2), pm25_after=round(i.pm25_after, 2),
        share_of_deaths_averted=i.deaths_averted / i.deaths_baseline,
        deaths_averted=i.deaths_averted, life_expectancy_gain=i.e0_after - i.e0_before,
        e0_before=i.e0_before, e0_after=i.e0_after, life_years_averted=i.yll_averted,
        deaths_derived=i.derived)


def footer(impacts: list[Impact], unavailable: dict[str, str] | None = None,
           notes: tuple[str, ...] = ()) -> str:
    if unavailable is None:
        unavailable = select_curves()[1]
    maps = dict.fromkeys((i.map_name, i.year) for i in impacts)
    fallback = sorted({s for i in impacts for s in i.fallback_states})
    return _footer(maps, fallback, unavailable, notes)


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
             f"Population {first.population / 1e6:,.1f} M; all-cause deaths "
             f"{first.deaths_baseline:,.0f} a year. Steady state, per year.", ""]
    head = ("curve", "PM2.5 µg/m³", "% of deaths", "deaths/yr", "life exp. yrs", "life-years/yr")
    rows = []
    for i in impacts:
        name = i.curve.name + (" *" if i.derived else "")
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
        deaths_baseline=first.deaths_baseline if first else None,
        rows=[_row(i) for i in impacts],
        fallback_states=sorted({s for i in impacts for s in i.fallback_states}),
        unavailable=unavailable, notes=list(notes),
        footer=footer(impacts, unavailable, notes))


# --- intervention runs ----------------------------------------------------------------------

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
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


def _range(d: dict, fmt=_sig) -> str:
    return f"{fmt(d['median'])} ({fmt(d['p5'])} to {fmt(d['p95'])})"


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
        rows.append(dict(
            curve=name, label=r.curve.label, deaths_derived=r.curve.kind == "life_expectancy",
            published_interval=r.widths["curve_parameters"] > 0 or r.spread["curve_parameters"] > 0,
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
        f"Population {run.population / 1e6:,.1f} M; all-cause deaths {run.deaths_baseline:,.0f} "
        f"a year. {run.n:,} draws, seed {run.seed}.",
    ]


def run_footer(run: Run) -> str:
    notes = ["Life-years = deaths postponed by age × remaining life expectancy, at the map "
             "year's population and age structure, summed over the intervention's years"]
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
                      [(star(r), _range(r["life_years"]), _range(r["deaths_postponed"]),
                        _range(r["e0_change_years"], lambda v: f"{v:+.2f}")) for r in rows])

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
        start_year=iv.start_year, duration_years=iv.duration_years, ramp_years=iv.ramp_years,
        lag=iv.lag, realised_share_by_year=[float(x) for x in run.shares],
        cost_currency=iv.cost_currency, cost_year=iv.cost_year, usd_per_unit=run.usd_per_unit,
        cost_share_only_on_success=iv.cost_share_only_on_success,
        rows=run_rows(run), across_curve_spread=across_curve_spread(run),
        fallback_states=run.fallback_states, unavailable=run.unavailable,
        footer=run_footer(run))
