"""Build data/cpcb_city_month_hour.csv and data/cpcb_station_month.csv: a city's air year-round,
hour of day by month, for six pollutants, and each station's coverage.

    python scripts/build_cpcb_city_detail.py [--raw DIR] [--city NAME ...]

Needs the `build` extra (duckdb) and the CPCB parquet files the Diwali track downloads
(diwali/download.sh: github.com/Vonter/india-cpcb-aqi releases, ODbL). --raw defaults to
<repo>/diwali/data/raw, or the environment variable AIRHEALTH_CPCB_RAW. --city is a city of
data/cities.csv (default Bengaluru) and may be repeated; a rebuild replaces both files with
exactly the cities named. Each year file must run 1 Jan to 31 Dec, as build_exposure_cpcb.py checks.

Method. A city's stations are those of its CPCB city names (cities.csv, column cpcb_cities).
Timestamps are read as IST wall-clock (see diwali/extract.py).
PM2.5 gets exactly the annual table's QC: build_exposure_cpcb.QC_SQL is imported and run, so the
station-hours are the ones exposure_cpcb.csv averages. PM10, NO2, SO2, CO and ozone get light
cleaning, a modelling call not yet reviewed: values <= 0 are dropped, runs of >= 8 identical
consecutive 15-minute values at one station are dropped (the PM2.5 stuck-sensor rule), and PM10 > 2000
is dropped (the existing PM10 rule). Nothing else (no cross-checks between pollutants, no limit
on the other gases), so a sensor fault that is not stuck and not <= 0 stays in.
Readings are averaged to station-hours; the city's value for an hour is the median across its
stations of those (the method of exposure_cpcb.csv).

cpcb_city_month_hour.csv: city, year, month, hour (0-23, IST), then for each pollutant X in
pm25, pm10, no2, so2, co, o3: X = mean over the days of the month of the city's value for that
clock hour, n_X = the number of days that hour had a city value (X is empty where n_X is 0).
Units are CPCB's: ug/m3, except co in mg/m3. Weighting X by n_X reproduces monthly_cpcb.csv.

cpcb_station_month.csv: city, station_id, station, year, month, pm25 (the station's mean over
its valid station-hours that month), share_X = share of the month's calendar hours with a valid
station-hour of X (0-1). One row per station-month with a reading of any pollutant.
"""
import argparse
import calendar
import os
import re
import sys
from collections.abc import Iterable
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_exposure_cpcb import QC_SQL  # noqa: E402

HEALTH = Path(__file__).resolve().parents[1]
DATA = HEALTH / "data"
DEFAULT_RAW = HEALTH.parent / "diwali" / "data" / "raw"
POLLUTANTS = ["pm25", "pm10", "no2", "so2", "co", "o3"]
GASES = {  # name -> (parquet column, extra condition that drops a value)
    "pm10": ("PM10 (µg/m³)", "x > 2000"),
    "no2": ("NO2 (µg/m³)", "FALSE"),
    "so2": ("SO2 (µg/m³)", "FALSE"),
    "co": ("CO (mg/m³)", "FALSE"),
    "o3": ("Ozone (µg/m³)", "FALSE"),
}
GAS_SQL = """
CREATE OR REPLACE TABLE gas_{p} AS
WITH c AS (
  SELECT station_id, cpcb_city, ts, CASE WHEN x <= 0 OR {extra} THEN NULL ELSE x END AS v
  FROM (SELECT "Station ID" AS station_id, City AS cpcb_city, timezone('UTC', "Timestamp") AS ts,
               "{col}" AS x FROM read_parquet('{path}') WHERE City IN ({names})) t
), runs AS (
  SELECT *, row_number() OVER (PARTITION BY station_id ORDER BY ts)
          - row_number() OVER (PARTITION BY station_id, v ORDER BY ts) AS grp FROM c
), runlen AS (
  SELECT *, count(*) OVER (PARTITION BY station_id, v, grp) AS rl FROM runs
)
SELECT station_id, cpcb_city, date_trunc('hour', ts) AS hour, avg(v) AS val
FROM runlen WHERE v IS NOT NULL AND rl < 8 AND year(ts) = {year} GROUP BY 1, 2, 3;
"""


def _q(names: Iterable[str]) -> str:
    return ", ".join("'" + n.replace("'", "''") + "'" for n in names)


def build(raw: Path, cpcb_names: dict[str, list[str]], years: Iterable[int]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(city_month_hour, station_month) for the cities in cpcb_names (city -> its CPCB city
    names) and the given years, from raw/cpcb-air-quality-{year}.parquet. Writes nothing."""
    owner = {n: city for city, ns in cpcb_names.items() for n in ns}
    assert len(owner) == sum(map(len, cpcb_names.values())), "a CPCB name serves one city only"
    names = _q(owner)
    con = duckdb.connect()
    con.register("cmap", pd.DataFrame({"cpcb_city": list(owner), "city": list(owner.values())}))
    cmh, stm = [], []
    for year in years:
        path = raw / f"cpcb-air-quality-{year}.parquet"
        con.execute(QC_SQL.format(path=path, year=year, group="City", join="", where=f"City IN ({names})"))
        parts = ["SELECT station_id, city AS cpcb_city, hour, 'pm25' AS pol, pm25 AS val "
                 "FROM hourly WHERE pm25 IS NOT NULL"]
        for p, (col, extra) in GASES.items():
            con.execute(GAS_SQL.format(p=p, col=col, extra=extra, path=path, names=names, year=year))
            parts.append(f"SELECT station_id, cpcb_city, hour, '{p}' AS pol, val FROM gas_{p}")
        con.execute("CREATE OR REPLACE TABLE sh AS SELECT m.city, s.station_id, s.hour, s.pol, s.val "
                    "FROM (" + " UNION ALL ".join(parts) + ") s JOIN cmap m USING (cpcb_city)")
        a = con.execute("""
            WITH ch AS (SELECT city, hour, pol, median(val) AS val FROM sh GROUP BY 1, 2, 3)
            SELECT city, month(hour) AS month, hour(hour) AS hour, pol, avg(val) AS x, count(*) AS n
            FROM ch GROUP BY 1, 2, 3, 4""").df()
        a["year"] = year
        cmh.append(a)
        station_names = con.execute(f"""SELECT "Station ID" AS station_id, mode("Station Name") AS station
                                        FROM read_parquet('{path}') WHERE City IN ({names}) GROUP BY 1""").df()
        b = con.execute("""SELECT city, station_id, month(hour) AS month, pol, avg(val) AS x, count(*) AS n
                           FROM sh GROUP BY 1, 2, 3, 4""").df()
        b = b.merge(station_names, on="station_id", how="left")
        b["year"] = year
        stm.append(b)

    long = pd.concat(cmh, ignore_index=True)
    keys = ["city", "year", "month", "hour"]
    val = long.pivot(index=keys, columns="pol", values="x").reindex(columns=POLLUTANTS)
    cnt = long.pivot(index=keys, columns="pol", values="n").reindex(columns=POLLUTANTS)
    # one row per hour of day for every city-month that has any value
    months = long[["city", "year", "month"]].drop_duplicates()
    grid = pd.MultiIndex.from_frame(months.merge(pd.DataFrame({"hour": range(24)}), how="cross")[keys])
    val, cnt = val.reindex(grid), cnt.reindex(grid).fillna(0).astype(int)
    out = pd.DataFrame(index=grid)
    for p in POLLUTANTS:
        out[p] = val[p].round(2)
        out[f"n_{p}"] = cnt[p]
    out = out.reset_index().sort_values(keys).reset_index(drop=True)

    long = pd.concat(stm, ignore_index=True)
    keys = ["city", "station_id", "station", "year", "month"]
    long["station"] = long.station.fillna("")
    cnt = long.pivot(index=keys, columns="pol", values="n").reindex(columns=POLLUTANTS).fillna(0)
    hours = pd.Series([calendar.monthrange(y, m)[1] * 24 for y, m in zip(
        cnt.index.get_level_values("year"), cnt.index.get_level_values("month"))], index=cnt.index)
    st = pd.DataFrame(index=cnt.index)
    st["pm25"] = long[long.pol == "pm25"].set_index(keys).x.reindex(cnt.index).round(2)
    for p in POLLUTANTS:
        st[f"share_{p}"] = (cnt[p] / hours).round(3)
    st = st.reset_index().sort_values(keys).reset_index(drop=True)
    return out, st


def _years(raw: Path) -> list[int]:
    found = sorted(int(m.group(1)) for f in raw.glob("cpcb-air-quality-*.parquet")
                   if (m := re.fullmatch(r"cpcb-air-quality-(\d{4})\.parquet", f.name)))
    assert found, f"no cpcb-air-quality-YYYY.parquet files in {raw}"
    return found


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--raw", type=Path, default=Path(os.environ.get("AIRHEALTH_CPCB_RAW", DEFAULT_RAW)))
    ap.add_argument("--city", action="append", help="a city of cities.csv (repeatable; default Bengaluru)")
    args = ap.parse_args()
    cities = pd.read_csv(DATA / "cities.csv").set_index("city")
    wanted = args.city or ["Bengaluru"]
    cpcb_names = {}
    for c in wanted:
        assert c in cities.index, f"{c} is not in cities.csv"
        ns = cities.loc[c, "cpcb_cities"]
        assert isinstance(ns, str) and ns, f"{c} has no CPCB station"
        cpcb_names[c] = ns.split(";")
    years = _years(args.raw)
    con = duckdb.connect()
    for y in years:
        first, last = con.execute(f"""SELECT min(timezone('UTC', "Timestamp"))::VARCHAR,
            max(timezone('UTC', "Timestamp"))::VARCHAR
            FROM read_parquet('{args.raw}/cpcb-air-quality-{y}.parquet')""").fetchone()
        assert (first[5:10], last[5:10]) == ("01-01", "12-31"), (y, first, last)
    cmh, sm = build(args.raw, cpcb_names, years)
    cmh.to_csv(DATA / "cpcb_city_month_hour.csv", index=False)
    sm.to_csv(DATA / "cpcb_station_month.csv", index=False)
    print(f"{len(cmh)} city-month-hour rows, {len(sm)} station-month rows; "
          f"cities: {', '.join(wanted)}; years {years[0]}-{years[-1]}")


if __name__ == "__main__":
    main()
