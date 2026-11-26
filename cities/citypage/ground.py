"""Chapter 1: the air itself. Monitors (CPCB) and satellite maps for one city, each kept apart.

Gases got only light cleaning upstream (readings <= 0 and stuck runs dropped); outliers remain.
They are shown as the monitors report them, and the chapter reads shapes (month, hour, ratios)
rather than absolute levels. Missing is never zero: n_* columns say how many days stand behind
each value, and a cell with no data is None/NaN and drawn as "no data".
"""
import calendar
from functools import cache

import numpy as np
import pandas as pd

from airhealth import exposure, paths, places

from . import svg
from .page import Section, esc, fmt, table

POLLUTANTS: dict[str, tuple[str, str]] = {
    "pm25": ("PM2.5", "µg/m³"), "pm10": ("PM10", "µg/m³"), "no2": ("NO₂", "µg/m³"),
    "so2": ("SO₂", "µg/m³"), "co": ("CO", "mg/m³"), "o3": ("O₃", "µg/m³")}
# A choice made for the charts, not a standard: where the monsoon and the festival season fall.
SEASONS: dict[str, tuple[int, ...]] = {
    "Dec-Feb": (12, 1, 2), "Mar-May": (3, 4, 5), "Jun-Sep": (6, 7, 8, 9), "Oct-Nov": (10, 11)}
MAP_ORDER = ("cpcb", "aqli", "acag_total")
MAP_SHORT = {"cpcb": "CPCB monitors", "aqli": "AQLI", "acag_total": "ACAG"}
AQLI_FIRST_YEAR = 2016      # a choice: the monitors start in 2016, so the satellite line does too
MONTHS = [calendar.month_abbr[m] for m in range(1, 13)]


@cache
def _csv(name: str) -> pd.DataFrame:
    return pd.read_csv(paths.DATA / name)


def _hours(city: str) -> pd.DataFrame:
    t = _csv("cpcb_city_month_hour.csv")
    return t[t.city == city]


def _stations(city: str) -> pd.DataFrame:
    t = _csv("cpcb_station_month.csv")
    return t[t.city == city]


def annual(city: str) -> pd.DataFrame:
    t = _csv("exposure_cpcb.csv")
    return t[t.city == city][["year", "pm25", "stations", "hours_share"]].reset_index(drop=True)


def month_by_year(city: str) -> pd.DataFrame:
    t = _csv("monthly_cpcb.csv")
    t = t[t.city == city]
    out = t.pivot(index="year", columns="month", values="pm25")
    return out.reindex(columns=range(1, 13))


def _weighted(df: pd.DataFrame, p: str, by: str) -> pd.Series:
    n = df[f"n_{p}"].where(df[p].notna(), 0)
    num = (df[p].fillna(0) * n).groupby(df[by]).sum()
    den = n.groupby(df[by]).sum()
    return (num / den.where(den > 0)).rename(p)


def hour_of_day(city: str, pollutant: str = "pm25",
                months: tuple[int, ...] | None = None) -> pd.Series:
    df = _hours(city)
    if months is not None:
        df = df[df.month.isin(months)]
    return _weighted(df, pollutant, "hour").reindex(range(24))


def station_coverage(city: str) -> pd.DataFrame:
    s = _stations(city)
    s = s[s.share_pm25 > 0].copy()      # a zero share means the monitor reports no PM2.5: no data
    s["valid"] = s.share_pm25 * [calendar.monthrange(y, m)[1] * 24 for y, m in zip(s.year, s.month)]
    v = s.pivot_table(index="station", columns="year", values="valid", aggfunc="sum")
    for y in v.columns:
        v[y] = v[y] / sum(calendar.monthrange(int(y), m)[1] * 24 for m in range(1, 13))
    return v


def maps_compared(city: str) -> pd.DataFrame:
    place = places.resolve(city, kind="city")
    rows = []
    for m in MAP_ORDER:
        if not exposure.available(m):
            continue
        if m == "cpcb":
            years = [int(y) for y in annual(city).year]
        elif m == "aqli":
            years = range(AQLI_FIRST_YEAR, 2100)
        else:
            years = [None]
        for y in years:
            try:
                val = exposure.mean(place, m, y)
                yr = y if y is not None else exposure.cells(place, m).attrs["year"]
            except KeyError:
                if m == "aqli":
                    break           # past the map's last year
                continue
            rows.append({"map": m, "year": int(yr), "pm25": val, "label": exposure.LABELS[m]})
    return pd.DataFrame(rows, columns=["map", "year", "pm25", "label"])


def _relative(df: pd.DataFrame, by: str, index) -> pd.DataFrame:
    cols = {}
    for p in POLLUTANTS:
        n = df[f"n_{p}"].where(df[p].notna(), 0)
        overall = (df[p].fillna(0) * n).sum() / n.sum() if n.sum() else np.nan
        cols[p] = _weighted(df, p, by) / overall
    return pd.DataFrame(cols).reindex(index)


def fingerprints(city: str) -> dict[str, pd.DataFrame]:
    df = _hours(city)
    st = _stations(city)
    cov = []
    for p in POLLUTANTS:
        have = st[st[f"share_{p}"] > 0]
        yrs = sorted(have.year.unique())
        cov.append({"pollutant": p, "first_year": yrs[0] if yrs else np.nan,
                    "last_year": yrs[-1] if yrs else np.nan, "years": len(yrs),
                    "stations": have.station_id.nunique()})
    return {"month": _relative(df, "month", range(1, 13)),
            "hour": _relative(df, "hour", range(24)),
            "coverage": pd.DataFrame(cov).set_index("pollutant")}


def _short(name: str, city: str) -> str:
    return name.replace(f", {city} - ", " · ").replace(f", {city}", "")


def _hour_ticks():
    return [(h, f"{h:02d}") for h in range(0, 24, 3)]


def _line(xs, ys, name, colour=0):
    return svg.Series(name, [float(x) for x in xs],
                      [None if pd.isna(v) else float(v) for v in ys], colour=colour)


def _cells(frame: pd.DataFrame, scale: float = 1.0):
    return [[None if pd.isna(v) else float(v) * scale for v in r] for r in frame.to_numpy()]


def render(city: str) -> Section:
    ann = annual(city)
    mby = month_by_year(city)
    st = station_coverage(city)
    maps = maps_compared(city)
    fp = fingerprints(city)
    a = ann.set_index("year")
    hi, lo = a.pm25.idxmax(), a.pm25.idxmin()
    h = []

    h.append(
        "<p>This chapter is about what the air holds, measured two ways. The government's "
        "ground <b>monitors</b> (the Central Pollution Control Board, CPCB, and the state boards "
        "that run them) read the air at a fixed spot every hour. <b>Satellite maps</b> estimate it "
        "everywhere from space. The main pollutant here is <b>PM2.5</b>: particles under 2.5 "
        "micrometres across, small enough to reach deep into the lungs. It is counted in "
        "<b>µg/m³</b>, micrograms of particles in a cubic metre of air. An <b>annual mean</b> "
        "is the average over a whole year.</p>")

    # (a) year by year
    h.append("<h3>Year by year</h3>")
    h.append(svg.line_chart(
        [_line(ann.year, ann.pm25, "PM2.5")],
        title=f"{city}: annual mean PM2.5 at CPCB monitors", x_label="year",
        y_label="µg/m³", x_ticks=[(int(y), str(int(y))) for y in ann.year]))
    h.append(f"<p>The highest year was {hi} at {fmt(a.pm25[hi], '1dp')} µg/m³ and the lowest "
             f"{lo} at {fmt(a.pm25[lo], '1dp')} µg/m³. The number of monitors changed over the "
             f"years (table below), so the line is not one fixed set of places.</p>")
    h.append(table(["Year", "PM2.5 (µg/m³)", "Monitors", "Share of hours with data"],
                   [[int(r.year), fmt(r.pm25, "1dp"), int(r.stations), fmt(r.hours_share, "pct")]
                    for r in ann.itertuples()], numeric=(0, 1, 2, 3)))

    # (b) month by month
    h.append("<h3>Month by month</h3>")
    h.append(svg.heatmap([str(int(y)) for y in mby.index], MONTHS, _cells(mby),
                         title=f"{city}: monthly mean PM2.5, µg/m³",
                         value_label="µg/m³; hatched = no data"))
    flat = mby.stack()
    my, mm = flat.idxmax()
    ly, lm = flat.idxmin()
    gaps = int(mby.isna().sum().sum())
    h.append(f"<p>Darker cells are dirtier months. The dirtiest month on record is "
             f"{calendar.month_name[mm]} {int(my)} ({fmt(flat.max(), '1dp')} µg/m³), the cleanest "
             f"{calendar.month_name[lm]} {int(ly)} ({fmt(flat.min(), '1dp')} µg/m³). "
             f"{gaps} month-year cell{'s' if gaps != 1 else ''} "
             f"{'are' if gaps != 1 else 'is'} hatched: the monitors had data for under 75% of "
             f"that month's hours, or none, so it is shown as no data, not as zero.</p>")

    # (c) hour of day
    h.append("<h3>Hour of day</h3>")
    ser = [_line(range(24), hour_of_day(city, "pm25", m), s, i)
           for i, (s, m) in enumerate(SEASONS.items())]
    h.append(svg.line_chart(ser, title=f"{city}: PM2.5 through the day, by season",
                            x_label="hour of day (IST)", y_label="µg/m³", x_ticks=_hour_ticks()))
    parts = []
    for s, m in SEASONS.items():
        hh = hour_of_day(city, "pm25", m)
        parts.append(f"{s}: highest at {int(hh.idxmax()):02d}:00 ({fmt(hh.max(), '1dp')}), lowest at "
                     f"{int(hh.idxmin()):02d}:00 ({fmt(hh.min(), '1dp')})")
    h.append("<p>Each line averages every monitor-day in the pooled years for the months of that "
             "season. The season groupings are a choice made for this chart, not a standard. "
             + "; ".join(parts) + " (µg/m³).</p>")

    # (d) the monitors
    h.append("<h3>The monitors</h3>")
    h.append(svg.heatmap([_short(n, city) for n in st.index], [str(int(y)) for y in st.columns],
                         _cells(st, 100),
                         title=f"{city}: share of each year's hours with valid PM2.5, by monitor",
                         value_label="% of hours; hatched = no data", fmt_kind="int"))
    n_other = _stations(city).station.nunique() - len(st)
    per_year = ", ".join(f"{int(y)}: {int(st[y].notna().sum())}" for y in st.columns)
    h.append(f"<p>Monitors reporting PM2.5 each year: {per_year}. A monitor that was not yet "
             f"installed, or sent nothing, is hatched; that is not the same as clean air. "
             f"{n_other} further monitor{'s' if n_other != 1 else ''} in the city's file "
             f"report other pollutants but no PM2.5, so {'they are' if n_other != 1 else 'it is'} "
             f"not listed here.</p>")
    h.append(table(["Monitor", "First year", "Last year", "Mean share of hours, years it reported"],
                   [[n, int(r.dropna().index.min()), int(r.dropna().index.max()),
                     fmt(r.mean(), "pct")] for n, r in st.iterrows()], numeric=(1, 2, 3)))

    # (e) satellites against monitors
    h.append("<h3>Satellites against monitors</h3>")
    ser = []
    present = [m for m in MAP_ORDER if m in set(maps['map'])]
    for i, m in enumerate(present):
        d = maps[maps['map'] == m]
        ser.append(svg.Series(MAP_SHORT[m], [float(y) for y in d.year], list(d.pm25),
                              kind="points" if len(d) == 1 else "line", colour=i))
    h.append(svg.line_chart(ser, title=f"{city}: annual mean PM2.5 on each map, µg/m³",
                            x_label="year", y_label="µg/m³",
                            x_ticks=[(y, str(y)) for y in sorted(maps.year.unique())]))
    labels = "".join(f"<li>{esc(exposure.LABELS[m])}</li>" for m in present)
    h.append(f"<p>Each series is its own source, never pooled:</p><ul>{labels}</ul>")
    h.append("<p>AQLI removes mineral dust and sea salt from the satellite estimate; ACAG keeps "
             "them; CPCB is the monitors' median across the city's stations. The GBD (Global "
             "Burden of Disease) maps are state-level only, so they have no city value and are "
             "not drawn here.</p>")
    common = sorted(set.intersection(*[set(maps[maps['map'] == m].year) for m in present]))
    if common:
        y = common[-1]
        vals = ", ".join(f"{MAP_SHORT[m]} "
                         f"{fmt(float(maps[(maps['map'] == m) & (maps.year == y)].pm25.iloc[0]), '1dp')}"
                         for m in present)
        h.append(f"<p>In {y}, the latest year all of them cover, the values were {vals} µg/m³. "
                 f"They are listed, not averaged: the gap between them is itself a finding.</p>")

    # (f) other pollutants
    h.append("<h3>Other pollutants as fingerprints</h3>")
    h.append("<p>The monitors also report four gases. Their readings had only light cleaning "
             "(values at or below zero, and long runs of one stuck value, were dropped), and some "
             "outliers remain, so they are shown as the monitors report them. Each line below is "
             "divided by that pollutant's own average, so 1 means average and the chart shows "
             "<i>shape</i> (when it is high), not level.</p>")
    cols = list(POLLUTANTS)
    h.append(svg.line_chart(
        [_line(fp["month"].index, fp["month"][p], POLLUTANTS[p][0], i) for i, p in enumerate(cols)],
        title=f"{city}: month of year, relative to each pollutant's own mean",
        x_label="month", y_label="1 = own average",
        x_ticks=[(m, MONTHS[m - 1]) for m in range(1, 13)]))
    h.append(svg.line_chart(
        [_line(fp["hour"].index, fp["hour"][p], POLLUTANTS[p][0], i) for i, p in enumerate(cols)],
        title=f"{city}: hour of day, relative to each pollutant's own mean",
        x_label="hour of day (IST)", y_label="1 = own average", x_ticks=_hour_ticks()))
    h.append("<p>What each usually points to: NO₂ and CO come from traffic and burning; SO₂ from "
             "coal, industry and fireworks; O₃ (ozone) is made in sunlight from other gases, so "
             "it peaks in the afternoon. PM10 is the coarser particles (under 10 micrometres), "
             "which include road dust.</p>")
    cv = fp["coverage"]
    h.append(table(["Pollutant", "Unit", "First year", "Last year", "Years with data",
                    "Monitors that measured it"],
                   [[POLLUTANTS[p][0], POLLUTANTS[p][1], str(int(r.first_year)),
                     str(int(r.last_year)), int(r.years), int(r.stations)]
                    for p, r in cv.iterrows()],
                   caption="Coverage of each pollutant", numeric=(2, 3, 4, 5)))
    h.append("<p>A city median of any gas mixes monitors that were added, moved or stopped over "
             "the years, so a change in a city's gas level can come from the line-up of "
             "monitors and not from the air.</p>")
    return Section("ground", "The air itself", "".join(h))
