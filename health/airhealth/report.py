"""Tables and JSON for impact results, one row per curve.

Every table ends with one line naming the exposure map and year, the states that fell back
to all-India death rates, and the curves that were asked for but could not run, with why.
"""
from collections import defaultdict

from . import curves, exposure
from .curves import Curve, Unavailable
from .impact import Impact

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
    parts = ["Map: " + "; ".join(f"{m} {y} ({exposure.LABELS[m]})" for m, y in maps) + "."] if maps else []
    parts += [n.rstrip(".") + "." for n in notes]
    fallback = sorted({s for i in impacts for s in i.fallback_states})
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
