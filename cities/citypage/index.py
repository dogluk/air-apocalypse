"""The cities index: one row per city, every number computed from the same functions the city
pages use (ground.annual, burden.level, findings.toll_ends, causes.studies, measures.applicability),
so a row and its page cannot disagree. Rows follow the order of the Diwali track's city list;
nothing is ranked or averaged across cities.
"""
from __future__ import annotations

from pathlib import Path

from airhealth import causes

from . import burden, findings, ground, measures
from .page import esc, fmt

# diwali/config.py CITIES, in its order (a test checks they match): the ten biggest metros and Lucknow.
CITIES: tuple[str, ...] = ("Delhi", "Mumbai", "Kolkata", "Bengaluru", "Chennai", "Hyderabad",
                           "Ahmedabad", "Pune", "Surat", "Jaipur", "Lucknow")
ACAG = "acag_total"


def slug(city: str) -> str:
    return city.lower().replace(" ", "-")


def rows(folder: Path | None = None) -> list[dict]:
    """One dict per city. A value that does not exist for a city is None, never 0."""
    out = []
    for c in CITIES:
        ann = ground.annual(c)
        r: dict = {"city": c, "slug": slug(c), "pm25": None, "pm25_year": None, "monitors": None,
                   "hours_share": None, "years_of_monitors": len(ann), "acag": None,
                   "acag_year": None, "deaths_low": None, "deaths_high": None,
                   "derived": False, "n_curves": 0, "n_maps": 0}
        if len(ann):
            last = ann.loc[ann.year.idxmax()]
            r.update(pm25=float(last.pm25), pm25_year=int(last.year), monitors=int(last.stations),
                     hours_share=float(last.hours_share))
        if burden._maps() and ACAG in burden._maps():
            r["acag"], r["acag_year"] = burden.level(c, ACAG)
        ends = findings.toll_ends(c)
        if ends is not None:
            lo, hi, n_curves, n_maps = ends
            r.update(deaths_low=float(lo[0]), deaths_high=float(hi[0]), n_curves=n_curves,
                     n_maps=n_maps, derived=bool(lo[3] or hi[3]))
        k, total, _ = measures.applicability(c, folder)
        r.update(studies=len(causes.studies(c)), measures=k, measures_total=total)
        out.append(r)
    return out


def _cell(r: dict) -> list[str]:
    star = " *" if r["derived"] else ""
    pm = "no data" if r["pm25"] is None else f"{fmt(r['pm25'], '1dp')} ({r['pm25_year']})"
    sat = "no data" if r["acag"] is None else f"{fmt(r['acag'], '1dp')} ({r['acag_year']})"
    toll = ("no curve gave one" if r["deaths_low"] is None
            else f"{fmt(r['deaths_low'])} to {fmt(r['deaths_high'])}{star}")
    return [f'<a href="{esc(r["slug"])}/index.html">{esc(r["city"])}</a>', esc(pm),
            "no data" if r["monitors"] is None else str(r["monitors"]),
            str(r["years_of_monitors"]), esc(sat), esc(toll), str(r["studies"]),
            f"{r['measures']} of {r['measures_total']}"]


HEAD = ("City (its page)", "PM2.5 on CPCB monitors, latest year (µg/m³)", "Monitors that year",
        "Years of monitor data", "PM2.5 on the ACAG satellite map (µg/m³)",
        "Range of deaths a year attributable to PM2.5, over every curve and map",
        "Source studies", "Library measures that apply")


def _span(values) -> str:
    v = sorted(set(values))
    return str(v[0]) if len(v) == 1 else f"{v[0]} to {v[-1]}"


def body(rs: list[dict] | None = None) -> str:
    rs = rs if rs is not None else rows()
    head = "".join(f'<th{" class=num" if i else ""}>{esc(h)}</th>' for i, h in enumerate(HEAD))
    trs = "".join(
        "<tr>" + "".join(f'<td{" class=num" if i else ""}>{v}</td>' for i, v in enumerate(_cell(r)))
        + "</tr>" for r in rs)
    n_years = max(r["years_of_monitors"] for r in rs)
    thin = [f"{r['city']} ({r['years_of_monitors']})" for r in rs if r["years_of_monitors"] < n_years]
    star = f'<p class="note">{esc(burden.STAR)}</p>' if any(r["derived"] for r in rs) else ""
    return (
        "<p>One row for each of the eleven cities the Diwali track follows. Each city has its own "
        "page that goes from the air to health to what could be done about it; this table gives "
        "the headline numbers from those pages side by side. It is <b>not a ranking</b>: the rows "
        "follow the order of the repository's city list, nothing is averaged across cities, and "
        "no column is a score.</p>"
        f'<div class="tablewrap"><table><caption>The eleven cities, as the pages find them'
        f"</caption><thead><tr>{head}</tr></thead><tbody>{trs}</tbody></table></div>{star}"
        "<h2>How to read the columns</h2>"
        "<ul>"
        "<li><b>PM2.5 on CPCB monitors</b>: the yearly mean of PM2.5, the fine particles (under 2.5 "
        "micrometres across) that do most of the harm, in micrograms per cubic metre of air "
        "(µg/m³), as read by the Central Pollution Control Board's ground monitors in the latest "
        "year the city has enough data for (at least 75% of that year's hours). The year is in "
        "brackets. <b>Years of monitor data</b> counts the years the city has such a reading"
        + (f"; the eleven cities have up to {n_years}, and {esc(', '.join(thin))} fewer, so "
           "their latest year rests on a shorter record" if thin else "") + ".</li>"
        "<li><b>PM2.5 on the ACAG satellite map</b>: the same yearly mean estimated from space, "
        "weighted by where people live, for the satellite map's own latest year. It is a "
        "different instrument and often a different year; the two columns are side by side, not "
        "averaged.</li>"
        "<li><b>Range of deaths a year</b>: the deaths a year that PM2.5 above each risk curve's "
        "floor accounts for, from the lowest to the highest answer over "
        f"{_span(r['n_curves'] for r in rs)} risk curves and "
        f"{_span(r['n_maps'] for r in rs)} exposure maps. The published curves and maps "
        "disagree several-fold and no one of them is preferred, so a range is all that is given. "
        "The city pages say which curve and map sit at each end.</li>"
        "<li><b>Source studies</b>: the studies in <code>health/data/causes.csv</code> that "
        "say where the city's PM2.5 comes from, counted by study id. A study with several parts "
        "(a model run for different years, a receptor study next to a model) counts once for each "
        "part, so this is a count of rows of evidence, not of research teams.</li>"
        "<li><b>Library measures that apply</b>: how many of the "
        f"{_span(r['measures_total'] for r in rs)} measures in the measure library apply to the city. The "
        "library is written from single-city evidence, so a measure applies only where its file "
        "names the city (or says it fits every city), or where it acts on a whole region. Each "
        "city page lists which apply and why the rest do not.</li>"
        "</ul>")
