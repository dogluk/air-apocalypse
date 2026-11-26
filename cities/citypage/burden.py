"""Chapter 3: what it does to health. Every risk curve on every exposure map, each its own row.

Nothing here is averaged or ranked: up to eight curves and three maps give up to twenty-four
answers and the page shows all of them. Figures come from airhealth (the same code the
`airhealth burden` command runs); this module only arranges them.
"""
from dataclasses import dataclass

import pandas as pd

from airhealth import curves, exposure, paths, places, report
from airhealth.impact import Change, steady_state
from airhealth.inputs import Sources

from . import svg
from .page import Section, esc, fmt, table

MAPS: tuple[str, ...] = ("cpcb", "aqli", "acag_total")
ROUND_TARGET = 20.0          # a chosen round number, not a standard
_TARGETS = paths.DATA / "targets.csv"


@dataclass(frozen=True)
class Target:
    key: str
    label: str
    pm25: float
    url: str | None
    locator: str | None


def targets() -> list[Target]:
    out = [Target("round", "a round number, not a standard", ROUND_TARGET, None, None)]
    if _TARGETS.exists():
        for r in pd.read_csv(_TARGETS).itertuples():
            out.append(Target(r.target, r.label, float(r.pm25_annual), r.url, r.locator))
    return out


def curves_status() -> tuple[list[str], dict[str, str]]:
    run, missing = curves.select()
    return [c.name for c in run], dict(missing)


def _maps() -> list[str]:
    return [m for m in MAPS if exposure.available(m)]


def _place(city: str):
    return places.resolve(city, kind="city")


def _impacts(city: str, map_name: str, change_for):
    run, missing = curves.select()
    place = _place(city)
    imps = [steady_state(place, c, map_name, change_for(c), deaths=Sources()) for c in run]
    return imps, missing


def burden(city: str, map_name: str) -> dict:
    imps, missing = _impacts(city, map_name, lambda c: Change(to=c.floor))
    heading = f"{report.place_label(imps[0])}: deaths attributable to PM2.5 above each curve's own floor"
    return report.to_json(imps, missing, heading, ())


def level(city: str, map_name: str) -> tuple[float, int]:
    c = exposure.cells(_place(city), map_name)
    return exposure.mean(_place(city), map_name), int(c.attrs["year"])


def change_to(city: str, map_name: str, target: float) -> dict | None:
    if level(city, map_name)[0] <= target:
        return None
    imps, missing = _impacts(city, map_name, lambda c: Change(to=target))
    heading = f"{report.place_label(imps[0])}: PM2.5 down to {target:g} µg/m³"
    return report.to_json(imps, missing, heading, ())


def _row_cells(r: dict) -> list[str]:
    star = " *" if r["deaths_derived"] else ""
    dag = " †" if r["below_floor"] else ""
    return [f"{r['label']} ({r['curve']}){star}{dag}",
            f"{r['pm25_before']:.1f} → {r['pm25_after']:.1f}",
            fmt(r["share_of_deaths_averted"], "pct"), fmt(r["deaths_averted"]) + star,
            fmt(r["life_expectancy_gain"], "years"), fmt(r["life_years_averted"])]


HEAD = ["Curve", "PM2.5 µg/m³ before → after", "Share of all deaths", "Deaths a year",
        "Life expectancy gained (years)", "Life-years a year"]
STAR = "* deaths derived from the life-expectancy change, not from a relative risk."
DAGGER = "† part of this move is below the curve's floor, where the curve counts no further benefit."


def _burden_table(d: dict, caption: str) -> str:
    rows = [_row_cells(r) for r in d["rows"]]
    out = [table(HEAD, rows, caption=caption, numeric=(1, 2, 3, 4, 5))]
    if any(r["deaths_derived"] for r in d["rows"]):
        out.append(f'<p class="note">{esc(STAR)}</p>')
    if any(r["below_floor"] for r in d["rows"]):
        out.append(f'<p class="note">{esc(DAGGER)}</p>')
    out.append(f'<p class="note">{esc(d["footer"])}</p>')
    return "".join(out)


def render(city: str) -> Section:
    run, missing = curves_status()
    maps = _maps()
    results = {m: burden(city, m) for m in maps}
    lv = {m: level(city, m) for m in maps}
    h = []

    deaths_all = [r["deaths_averted"] for d in results.values() for r in d["rows"]]
    pm_text = "; ".join(f"{m} {lv[m][0]:.1f} µg/m³ ({lv[m][1]})" for m in maps)
    h.append(
        "<p>This chapter turns the air into health. A <b>risk curve</b> is a published estimate "
        "of how much the chance of dying rises as the yearly PM2.5 level rises. An <b>exposure "
        "map</b> says what level people in a place breathe. Put the two together and you get the "
        "<b>deaths attributable</b> to the air: the deaths a year that would not happen if the air "
        "were clean down to the curve's <b>floor</b>, the level below which the curve counts "
        "no further harm. <b>Life-years</b> add up the years of life those deaths took, each death "
        "counted by the years the person had left. <b>Life expectancy gained</b> is how much "
        "longer the average person would live.</p>")
    if deaths_all:
        h.append(
            f"<p>The curves do not agree, and neither do the maps. The PM2.5 level for "
            f"{esc(city)} is {esc(pm_text)}. Across every curve and map below, the deaths a year "
            f"attributable to the air run from {fmt(min(deaths_all))} to {fmt(max(deaths_all))}. "
            "The gap comes from the curves (each was fitted to different studies, some mostly of "
            "cleaner air than India's) and from the maps (they measure the air differently). "
            "No curve or map is picked here, and nothing is averaged.</p>")
    line = f"Curves used: {', '.join(run)}."
    if missing:
        line += " Not run: " + "; ".join(f"{n} ({why})" for n, why in missing.items()) + "."
    h.append(f'<p class="note">{esc(line)}</p>')

    h.append("<h3>Deaths and life-years attributable, to each curve's own floor</h3>")
    for m in maps:
        h.append(f"<h4>{esc(m)}: {esc(exposure.LABELS[m])}, {lv[m][1]}</h4>")
        h.append(f"<p>Starting level {lv[m][0]:.1f} µg/m³ in {lv[m][1]}.</p>")
        h.append(_burden_table(results[m], f"{city}, map {m}: every curve down to its own floor"))

    names = [r["curve"] for r in results[maps[0]]["rows"]] if maps else []

    def series(key):
        return [(m, [next((r[key] for r in results[m]["rows"] if r["curve"] == n), None)
                     for n in names]) for m in maps]
    if maps:
        h.append(svg.dot_rows(names, series("deaths_averted"),
                              title=f"{city}: deaths a year attributable to PM2.5, one dot per map",
                              x_label="deaths a year"))
        h.append(svg.dot_rows(names, series("life_years_averted"),
                              title=f"{city}: life-years a year lost to PM2.5, one dot per map",
                              x_label="life-years a year"))

    h.append("<h3>Round changes</h3>")
    h.append("<p>What if the air reached a stated level? Only the air above the level is "
             "cleaned. The first level below is a round number chosen for this page, not a "
             "standard; the others are published standards, with their sources.</p>")
    for t in targets():
        if t.url:
            src = f'<a href="{esc(t.url)}">source</a> ({esc(t.locator)})'
        else:
            src = "a round number, not a standard"
        h.append(f'<h4>{t.pm25:g} µg/m³: {esc(t.label)}</h4><p class="note">{src}</p>')
        for m in maps:
            d = change_to(city, m, t.pm25)
            if d is None:
                h.append(f"<p>Map {esc(m)}: already below {t.pm25:g} µg/m³ on this map "
                         f"({lv[m][0]:.1f}).</p>")
            else:
                h.append(f"<p>Map {esc(m)}:</p>")
                h.append(_burden_table(d, f"{city}, map {m}: down to {t.pm25:g} µg/m³"))
    return Section("health", "What it does to health", "".join(h))
