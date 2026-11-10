"""Build data/exposure_cpcb.csv (annual PM2.5 by city from CPCB monitors) and data/cities.csv.

    python scripts/build_exposure_cpcb.py [DOWNLOAD_DIR]

Needs the `build` extra (duckdb, openpyxl) and the CPCB parquet files the Diwali track
downloads (diwali/download.sh: github.com/Vonter/india-cpcb-aqi releases, ODbL). Those files
hold every station's 15-minute readings for whole calendar years (checked: 1 Jan 00:00 to
31 Dec 23:45 in every year 2016-2025).

Cities are those in diwali/config.py (CITIES, with their CPCB city names). Per station,
15-minute PM2.5 gets the Diwali track's QC (diwali/extract.py): readings >= 999 kept as 999
only when the city's hourly median of unsaturated readings is >= 250, otherwise dropped;
<= 0 dropped; runs of >= 8 identical values dropped; PM2.5 > 1.1 x PM10 dropped. Station
readings are averaged to hours; the city value for an hour is the median across its stations;
the annual mean is the mean of those hourly medians. Timestamps are read as IST wall-clock
(see diwali/extract.py). A city-year is kept only if at least 75% of its hours have a value.

exposure_cpcb.csv: city, state, year, pm25, stations (stations with any valid hour that
year), hours_share (share of the year's hours with a city value).

cities.csv: city, state, population, census_name, aqli_units, acag_units. Population is the
Census 2011 figure for the urban agglomeration (Jaipur: the city, which the census does not
list as a UA), from Census table A-04 (I), downloaded here. aqli_units and acag_units name the
district(s) holding the city core in each satellite map, ';'-separated; a satellite map's
value for a city is the population-weighted mean over those districts.
"""
import importlib.util
import sys
from pathlib import Path

import duckdb
import pandas as pd

from _fetch import fetch, workdir
from airhealth.places import canonical_state, norm

HEALTH = Path(__file__).resolve().parents[1]
DATA = HEALTH / "data"
DIWALI = HEALTH.parent / "diwali"
CENSUS = "https://censusindia.gov.in/nada/index.php/catalog/42876/download/46544"
MIN_HOURS_SHARE = 0.75

# City -> (Census A-04 (I) entry, AQLI gadm2 districts, geoBoundaries ADM2 districts)
CITIES = {
    "Delhi": ("Delhi U.A.", ["NCT of Delhi"],
              ["Central", "East", "New Delhi", "North", "North East", "North West", "Shahdara",
               "South", "South East", "South West", "West"]),
    "Mumbai": ("Greater Mumbai U.A.", ["Mumbai City", "Mumbai Suburban"], ["Mumbai", "Mumbai Suburban"]),
    "Kolkata": ("Kolkata U.A.", ["Kolkata"], ["Kolkata"]),
    "Bengaluru": ("Bruhat Bangalore U.A.", ["Bangalore"], ["Bangalore"]),
    "Chennai": ("Chennai U.A.", ["Chennai"], ["Chennai"]),
    "Hyderabad": ("Hyderabad U.A.", ["Hyderabad"], ["Hyderabad"]),
    "Ahmedabad": ("Ahmadabad U.A.", ["Ahmadabad"], ["Ahmadabad"]),
    "Pune": ("Pune U.A.", ["Pune"], ["Pune"]),
    "Surat": ("Surat U.A.", ["Surat"], ["Surat"]),
    "Jaipur": ("Jaipur", ["Jaipur"], ["Jaipur"]),
    "Lucknow": ("Lucknow U.A.", ["Lucknow"], ["Lucknow"]),
}

QC_SQL = """
CREATE OR REPLACE TABLE q AS
SELECT "Station ID" AS station_id, City AS city, State AS state,
  timezone('UTC', "Timestamp") AS ts, "PM2.5 (µg/m³)" AS pm25, "PM10 (µg/m³)" AS pm10
FROM read_parquet('{path}') WHERE City IN ({cities});

CREATE OR REPLACE TABLE hourly AS
WITH cityhr AS (
  SELECT city, date_trunc('hour', ts) AS hr, median(pm25) AS city_med
  FROM q WHERE pm25 > 0 AND pm25 < 999 GROUP BY 1, 2
), c AS (
  SELECT q.*, (q.pm25 >= 999 AND cityhr.city_med >= 250) AS sat
  FROM q LEFT JOIN cityhr ON q.city = cityhr.city AND date_trunc('hour', q.ts) = cityhr.hr
), c2 AS (
  SELECT *,
    CASE WHEN sat THEN 999 WHEN pm25 <= 0 OR pm25 >= 999 THEN NULL ELSE pm25 END AS p25,
    CASE WHEN pm10 <= 0 OR pm10 > 2000 THEN NULL ELSE pm10 END AS p10
  FROM c
), runs AS (
  SELECT *, row_number() OVER (PARTITION BY station_id ORDER BY ts)
          - row_number() OVER (PARTITION BY station_id, p25 ORDER BY ts) AS grp
  FROM c2
), runlen AS (
  SELECT *, count(*) OVER (PARTITION BY station_id, p25, grp) AS rl FROM runs
), clean AS (
  SELECT station_id, city, state, ts,
    CASE WHEN sat THEN p25 WHEN rl >= 8 OR (p10 IS NOT NULL AND p25 > 1.1 * p10) THEN NULL
         ELSE p25 END AS pm25
  FROM runlen
)
SELECT station_id, city, any_value(state) AS state, date_trunc('hour', ts) AS hour, avg(pm25) AS pm25
FROM clean WHERE year(ts) = {year} GROUP BY 1, 2, 4;
"""


def diwali_cities() -> dict:
    spec = importlib.util.spec_from_file_location("diwali_config", DIWALI / "config.py")
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    return config.CITIES


def census_populations(xlsx: Path) -> dict[str, tuple[str, int]]:
    """2011 persons for each city's entry in Census table A-04 (I)."""
    d = pd.read_excel(xlsx, sheet_name=0, header=None)
    heads = d[pd.to_numeric(d[0], errors="coerce").notna()]
    found = {}
    for i, r in heads.iterrows():
        name = norm(str(r[1]))
        for city, (entry, _, _) in CITIES.items():
            if name == norm(entry):
                block = d.loc[i:i + 12]
                row = block[block[3].astype(str).str.strip() == "2011"]
                assert len(row) == 1, (city, entry)
                assert city not in found, f"{entry} appears twice"
                found[city] = (" ".join(str(r[1]).split()), int(row[6].item()))
    assert set(found) == set(CITIES), set(CITIES) - set(found)
    return found


def main() -> None:
    folder = workdir(sys.argv, "cpcb")
    xlsx = fetch(CENSUS, folder, "PC11_A04-I_CLASS_I.xlsx")
    config = diwali_cities()
    assert set(config) == set(CITIES), set(config) ^ set(CITIES)
    cpcb_names = {n: city for city, v in config.items() for n in v["cpcb_city"]}
    city_list = ", ".join(f"'{n}'" for n in cpcb_names)

    con = duckdb.connect()
    rows = []
    for path in sorted((DIWALI / "data" / "raw").glob("cpcb-air-quality-*.parquet")):
        year = int(path.stem.rsplit("-", 1)[1])
        first, last = con.execute(f"""SELECT min(timezone('UTC', "Timestamp")),
            max(timezone('UTC', "Timestamp")) FROM read_parquet('{path}')""").fetchone()
        assert (first.month, first.day, last.month, last.day) == (1, 1, 12, 31), (path, first, last)
        con.execute(QC_SQL.format(path=path, cities=city_list, year=year))
        hours_in_year = pd.Timestamp(year=year, month=12, day=31).day_of_year * 24
        df = con.execute(f"""
            WITH valid AS (SELECT * FROM hourly WHERE pm25 IS NOT NULL),
            cityhour AS (SELECT city, hour, median(pm25) AS pm25 FROM valid GROUP BY 1, 2),
            annual AS (SELECT city, avg(pm25) AS pm25, count(*) / {hours_in_year} AS hours_share
                       FROM cityhour GROUP BY 1),
            meta AS (SELECT city, mode(state) AS state, count(DISTINCT station_id) AS stations
                     FROM valid GROUP BY 1)
            SELECT a.city, m.state, a.pm25, a.hours_share, m.stations
            FROM annual a JOIN meta m USING (city)""").df()
        df["year"] = year
        rows.append(df)
        print(year, ", ".join(f"{r.city} {r.pm25:.0f} ({r.stations}, {r.hours_share:.0%})"
                              for r in df.sort_values("city").itertuples()))
    out = pd.concat(rows)
    out["city"] = out.city.map(cpcb_names)
    out["state"] = out.state.map(canonical_state)
    dropped = out[out.hours_share < MIN_HOURS_SHARE]
    print("dropped for coverage:", ", ".join(f"{r.city} {r.year} ({r.hours_share:.0%})"
                                             for r in dropped.itertuples()) or "none")
    out = out[out.hours_share >= MIN_HOURS_SHARE]
    out["pm25"] = out.pm25.round(1)
    out["hours_share"] = out.hours_share.round(3)
    out = out[["city", "state", "year", "pm25", "stations", "hours_share"]].sort_values(["city", "year"])
    out.to_csv(DATA / "exposure_cpcb.csv", index=False)

    census = census_populations(xlsx)
    states = out.groupby("city").state.agg(lambda s: s.mode().item())
    cities = pd.DataFrame([{
        "city": city, "state": states[city], "population": census[city][1],
        "census_name": census[city][0], "aqli_units": ";".join(aqli), "acag_units": ";".join(acag),
    } for city, (_, aqli, acag) in CITIES.items()])
    for col, f in (("aqli_units", "exposure_aqli.csv"), ("acag_units", "exposure_acag_total.csv")):
        t = pd.read_csv(DATA / f, usecols=["state", "unit"]).drop_duplicates()
        have = set(zip(t.state, t.unit))
        for c in cities.itertuples():
            for unit in getattr(c, col).split(";"):
                assert (c.state, unit) in have, (f, c.state, unit)
    cities.to_csv(DATA / "cities.csv", index=False)
    print(cities.to_string())


if __name__ == "__main__":
    main()
