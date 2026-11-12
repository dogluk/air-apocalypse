"""Build data/exposure_cpcb.csv (annual PM2.5 by city from CPCB monitors) and data/cities.csv.

    python scripts/build_exposure_cpcb.py [DOWNLOAD_DIR]

Needs the `build` extra (duckdb, openpyxl) and the CPCB parquet files the Diwali track
downloads (diwali/download.sh: github.com/Vonter/india-cpcb-aqi releases, ODbL). Those files
hold every station's 15-minute readings for whole calendar years (checked: 1 Jan 00:00 to
31 Dec 23:45 in every year 2016-2025).

Cities are the CITIES table below: Delhi plus the 49 APnA airsheds, each with its CPCB city
names (none for airsheds CPCB has no station in). Per station,
15-minute PM2.5 gets the Diwali track's QC (diwali/extract.py): readings >= 999 kept as 999
only when the city's hourly median of unsaturated readings is >= 250, otherwise dropped;
<= 0 dropped; runs of >= 8 identical values dropped; PM2.5 > 1.1 x PM10 dropped. Station
readings are averaged to hours; the city value for an hour is the median across its stations;
the annual mean is the mean of those hourly medians. Timestamps are read as IST wall-clock
(see diwali/extract.py). A city-year is kept only if at least 75% of its hours have a value.

monthly_cpcb.csv: city, year, month, pm25, hours_share, from the same hourly city values grouped by
calendar month (the month's real number of hours, so February has 29 days in 2016, 2020, 2024). A
month-year is kept only if at least 75% of that month's hours have a value.

exposure_cpcb.csv: city, state, year, pm25, stations (stations with any valid hour that
year), hours_share (share of the year's hours with a city value).

cities.csv: city, state, population, census_name, aqli_units, acag_units, apna_airshed,
cpcb_cities. Population is the sum of the Census 2011 figures of the Class I entries (urban
agglomerations, or the city where the census lists no UA) in census_name, from Census table
A-04 (I), downloaded here. aqli_units and acag_units name the district(s) holding the city in
each satellite map, ';'-separated; a satellite map's value for a city is the population-weighted
mean over those districts. apna_airshed is the airshed's name in the APnA table (empty for Delhi);
cpcb_cities the CPCB city names whose stations make up the city (empty if there are none).
census_name and cpcb_cities are ';'-separated.
"""
import calendar
import re
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

# City -> (state, Census A-04 (I) entries, AQLI gadm2 districts, geoBoundaries ADM2 districts,
#          APnA airshed, CPCB city names). The first 11 are the original cities and keep their
# values. The others are the other 39 APnA airsheds (Zenodo 6919069, data/apna_source_apportionment.csv).
# state: the state of the city's first town. A satellite map's district units must lie in it, so an
# airshed that crosses a state line (Chandigarh-Patiala-Ambala, Puducherry-Cuddalore) lists only the
# units of its home state. Units are the districts of the towns counted in the population.
# Census entries are summed; a listed town that is not Class I is left out
# (see sources.toml). cpcb_cities is empty where CPCB has no station in the airshed.
CITIES = {
    "Delhi": ("Delhi", ["Delhi U.A."], ["NCT of Delhi"],
              ["Central", "East", "New Delhi", "North", "North East", "North West", "Shahdara",
               "South", "South East", "South West", "West"], None, ["Delhi"]),
    "Mumbai": ("Maharashtra", ["Greater Mumbai U.A."], ["Mumbai City", "Mumbai Suburban"],
               ["Mumbai", "Mumbai Suburban"], "Mumbai", ["Mumbai"]),
    "Kolkata": ("West Bengal", ["Kolkata U.A."], ["Kolkata"], ["Kolkata"], "Kolkata-Howarh", ["Kolkata"]),
    "Bengaluru": ("Karnataka", ["Bruhat Bangalore U.A."], ["Bangalore"], ["Bangalore"], "Bengaluru", ["Bengaluru"]),
    "Chennai": ("Tamil Nadu", ["Chennai U.A."], ["Chennai"], ["Chennai"], "Chennai", ["Chennai"]),
    "Hyderabad": ("Telangana", ["Hyderabad U.A."], ["Hyderabad"], ["Hyderabad"], "Hyderabad", ["Hyderabad"]),
    "Ahmedabad": ("Gujarat", ["Ahmadabad U.A."], ["Ahmadabad"], ["Ahmadabad"], "Ahmedabad-Gandhi-Nagar", ["Ahmedabad"]),
    "Pune": ("Maharashtra", ["Pune U.A."], ["Pune"], ["Pune"], "Pune-Pimpri-Chinchwad", ["Pune"]),
    "Surat": ("Gujarat", ["Surat U.A."], ["Surat"], ["Surat"], "Surat", ["Surat"]),
    "Jaipur": ("Rajasthan", ["Jaipur"], ["Jaipur"], ["Jaipur"], "Jaipur", ["Jaipur"]),
    "Lucknow": ("Uttar Pradesh", ["Lucknow U.A."], ["Lucknow"], ["Lucknow"], "Lucknow", ["Lucknow"]),
    "Agartala": ("Tripura", ["Agartala"], ["West Tripura"], ["West Tripura"], "Agartala", ["Agartala"]),
    "Allahabad": ("Uttar Pradesh", ["Allahabad U.A."], ["Prayagraj"], ["Allahabad"], "Allahabad", ["Prayagraj"]),
    "Asansol-Durgapur": ("West Bengal", ["Asansol U.A.", "Durgapur U.A."], ["Barddhaman"],
                         ["Paschim Barddhaman"], "Asansol-Durgapur", ["Asansol", "Durgapur"]),
    "Aurangabad": ("Maharashtra", ["Aurangabad U.A."], ["Aurangabad"], ["Aurangabad"], "Aurangabad", []),
    "Hubli-Dharwad": ("Karnataka", ["Hubli-Dharwad"], ["Dharwad"], ["Dharwad"], "Dharwad-Hubli",
                      ["Hubballi", "Dharwad"]),
    "Dhanbad-Bokaro": ("Jharkhand", ["Dhanbad U.A.", "Bokaro Steel City U.A."], ["Dhanbad", "Bokaro"],
                       ["Dhanbad", "Bokaro"], "Dhanbad-Bokaro", ["Dhanbad"]),
    "Gaya": ("Bihar", ["Gaya U.A."], ["Gaya"], ["Gaya"], "Gaya", ["Gaya"]),
    "Guwahati": ("Assam", ["Guwahati U.A."], ["Kamrup Metropolitan"], ["Kamrup Metropolitan"],
                 "Guwahati-Dispur", ["Guwahati"]),
    "Gwalior": ("Madhya Pradesh", ["Gwalior U.A."], ["Gwalior"], ["Gwalior"], "Gwalior", ["Gwalior"]),
    "Jamshedpur": ("Jharkhand", ["Jamshedpur U.A."], ["Purbi Singhbhum"], ["Purbi Singhbhum"], "Jamshedpur", []),
    "Jodhpur": ("Rajasthan", ["Jodhpur U.A."], ["Jodhpur"], ["Jodhpur"], "Jodhpur", ["Jodhpur"]),
    "Kota": ("Rajasthan", ["Kota"], ["Kota"], ["Kota"], "Kota", ["Kota"]),
    "Madurai": ("Tamil Nadu", ["Madurai U.A."], ["Madurai"], ["Madurai"], "Madurai", ["Madurai"]),
    "Nashik": ("Maharashtra", ["Nashik U.A."], ["Nashik"], ["Nashik"], "Nashik", ["Nashik"]),
    "Panaji": ("Goa", ["Panaji U.A.", "Mormugao U.A.", "Margao U.A."], ["North Goa", "South Goa"],
               ["North Goa", "South Goa"], "Panjim-Vasco-Margao", []),
    "Puducherry": ("Puducherry", ["Puducherry U.A.", "Cuddalore"], ["Puducherry"], ["Puducherry"],
                   "Puducherry-Cuddalore", ["Puducherry", "Cuddalore"]),
    "Rajkot": ("Gujarat", ["Rajkot U.A."], ["Rajkot"], ["Rajkot"], "Rajkot", []),
    "Shimla": ("Himachal Pradesh", ["Shimla U.A."], ["Shimla"], ["Shimla"], "Shimla", []),
    "Srinagar": ("Jammu & Kashmir", ["Srinagar U.A."], ["Srinagar"], ["Srinagar"], "Srinagar", ["Srinagar"]),
    "Thiruvananthapuram": ("Kerala", ["Thiruvananthapuram U.A."], ["Thiruvananthapuram"],
                           ["Thiruvananthapuram"], "Thiruvananthapuram", ["Thiruvananthapuram"]),
    "Tiruchirappalli": ("Tamil Nadu", ["Tiruchirappalli U.A."], ["Tiruchirappalli"], ["Tiruchirappalli"],
                        "Tiruchirapalli", ["Tiruchirappalli"]),
    "Vadodara": ("Gujarat", ["Vadodara U.A."], ["Vadodara"], ["Vadodara"], "Vadodara", []),
    "Vijayawada": ("Andhra Pradesh", ["Vijayawada U.A.", "Guntur U.A.", "Tenali"], ["Krishna", "Guntur"],
                   ["Krishna", "Guntur"], "Vijayawada-Guntur-Tenali", ["Vijayawada"]),
    "Visakhapatnam": ("Andhra Pradesh", ["Visakhapatnam"], ["Visakhapatnam"], ["Visakhapatnam"],
                      "Visakhapatnam", ["Visakhapatnam"]),
    "Agra": ("Uttar Pradesh", ["Agra U.A."], ["Agra"], ["Agra"], "Agra", ["Agra"]),
    "Amritsar": ("Punjab", ["Amritsar U.A."], ["Amritsar"], ["Amritsar"],
                 "Amritsar-Tarn Taran", ["Amritsar"]),
    "Bhopal": ("Madhya Pradesh", ["Bhopal U.A."], ["Bhopal"], ["Bhopal"], "Bhopal", ["Bhopal"]),
    "Bhubaneswar": ("Odisha", ["Bhubaneswar U.A."], ["Khordha"], ["Khordha"], "Bhubaneswar", ["Bhubaneswar"]),
    "Chandigarh": ("Chandigarh", ["Chandigarh U.A.", "Patiala U.A.", "Ambala U.A."], ["Chandigarh"],
                   ["Chandigarh"], "Chandigarh-Patiala-Ambala", ["Chandigarh", "Patiala", "Ambala"]),
    "Coimbatore": ("Tamil Nadu", ["Coimbatore U.A."], ["Coimbatore"], ["Coimbatore"], "Coimbatore", ["Coimbatore"]),
    "Dehradun": ("Uttarakhand", ["Dehradun U.A."], ["Dehradun"], ["Dehradun"], "Dehradun", ["Dehradun"]),
    "Indore": ("Madhya Pradesh", ["Indore U.A."], ["Indore"], ["Indore"], "Indore", ["Indore"]),
    "Kanpur": ("Uttar Pradesh", ["Kanpur U.A."], ["Kanpur Nagar"], ["Kanpur Nagar"], "Kanpur", ["Kanpur"]),
    "Kochi": ("Kerala", ["Kochi U.A."], ["Ernakulam"], ["Ernakulam"], "Kochi", ["Kochi"]),
    "Ludhiana": ("Punjab", ["Ludhiana"], ["Ludhiana"], ["Ludhiana"],
                 "Ludhiana-Phillaur", ["Ludhiana"]),
    "Nagpur": ("Maharashtra", ["Nagpur U.A."], ["Nagpur"], ["Nagpur"], "Nagpur", ["Nagpur"]),
    "Patna": ("Bihar", ["Patna U.A."], ["Patna"], ["Patna"], "Patna", ["Patna"]),
    "Raipur-Durg-Bhilai": ("Chhattisgarh", ["Raipur U.A.", "Durg-Bhilainagar U.A."], ["Raipur", "Durg"],
                           ["Raipur", "Durg"], "Raipur-Durg-Bhillai", ["Raipur", "Bhilai"]),
    "Ranchi": ("Jharkhand", ["Ranchi U.A."], ["Ranchi"], ["Ranchi"], "Ranchi", []),
}
# CPCB cities of an airshed that crosses a state line may be in these states too.
CPCB_OTHER_STATES = {"Chandigarh": {"Punjab", "Haryana"}, "Puducherry": {"Tamil Nadu"}}

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


def census_populations(xlsx: Path) -> dict[str, tuple[str, int]]:
    """Normalised name -> (entry as printed, 2011 persons) for each Census entry the table uses."""
    d = pd.read_excel(xlsx, sheet_name=0, header=None)
    heads = d[pd.to_numeric(d[0], errors="coerce").notna()]
    wanted = {norm(e) for _, entries, *_ in CITIES.values() for e in entries}
    found = {}
    for i, r in heads.iterrows():
        key = norm(str(r[1]))
        if key in wanted:
            block = d.loc[i:i + 12]
            # the year cell is '2011', or '!!2011' / '!! 2011' where the census footnotes it
            row = block[block[3].map(lambda y: re.sub(r"\D", "", str(y))) == "2011"]
            assert len(row), r[1]      # the first is the entry's own; sub-entries (i), (ii) follow
            assert key not in found, f"{r[1]} appears twice"
            found[key] = (str(r[1]).strip(), int(row[6].iloc[0]))
    assert set(found) == wanted, wanted - set(found)
    return found


def check_cpcb_names(con: duckdb.DuckDBPyConnection) -> None:
    """Every CPCB name is a city in some year's file (2016-2025), in the city's state (or a
    neighbour's for an airshed across a state line); a CPCB name serves one city only."""
    have = {}
    for path in sorted((DIWALI / "data" / "raw").glob("cpcb-air-quality-*.parquet")):
        have.update(con.execute(f"SELECT City, mode(State) FROM read_parquet('{path}') GROUP BY 1").fetchall())
    seen = {}
    for city, (state, _, _, _, _, names) in CITIES.items():
        for n in names:
            assert n in have, (city, n, "not in any year of the CPCB files")
            ok = {state} | CPCB_OTHER_STATES.get(city, set())
            assert canonical_state(have[n]) in ok, (city, n, have[n])
            assert n not in seen, (n, city, seen[n])
            seen[n] = city


def main() -> None:
    folder = workdir(sys.argv, "cpcb")
    xlsx = fetch(CENSUS, folder, "PC11_A04-I_CLASS_I.xlsx")
    names = [c for c, v in CITIES.items() if not v[5]]
    print("no CPCB station:", ", ".join(names))
    assert len({v[4] for v in CITIES.values()}) == len(CITIES)
    cpcb_names = {n: city for city, v in CITIES.items() for n in v[5]}
    city_list = ", ".join(f"'{n}'" for n in cpcb_names)

    con = duckdb.connect()
    check_cpcb_names(con)
    con.register("cmap", pd.DataFrame({"cpcb_city": list(cpcb_names), "airshed_city": list(cpcb_names.values())}))
    rows, months = [], []
    for path in sorted((DIWALI / "data" / "raw").glob("cpcb-air-quality-*.parquet")):
        year = int(path.stem.rsplit("-", 1)[1])
        first, last = con.execute(f"""SELECT min(timezone('UTC', "Timestamp")),
            max(timezone('UTC', "Timestamp")) FROM read_parquet('{path}')""").fetchone()
        assert (first.month, first.day, last.month, last.day) == (1, 1, 12, 31), (path, first, last)
        con.execute(QC_SQL.format(path=path, cities=city_list, year=year))
        hours_in_year = pd.Timestamp(year=year, month=12, day=31).day_of_year * 24
        con.execute("""
            CREATE OR REPLACE TABLE valid AS
            SELECT m.airshed_city AS city, h.station_id, h.hour, h.pm25
            FROM hourly h JOIN cmap m ON h.city = m.cpcb_city WHERE h.pm25 IS NOT NULL;
            CREATE OR REPLACE TABLE cityhour AS
            SELECT city, hour, median(pm25) AS pm25 FROM valid GROUP BY 1, 2""")
        mo = con.execute("""SELECT city, month(hour) AS month, avg(pm25) AS pm25, count(*) AS n
                            FROM cityhour GROUP BY 1, 2""").df()
        mo["year"] = year
        mo["hours_share"] = mo.n / [calendar.monthrange(year, m)[1] * 24 for m in mo.month]
        months.append(mo.drop(columns="n"))
        df = con.execute(f"""
            WITH annual AS (SELECT city, avg(pm25) AS pm25, count(*) / {hours_in_year} AS hours_share
                       FROM cityhour GROUP BY 1),
            meta AS (SELECT city, count(DISTINCT station_id) AS stations FROM valid GROUP BY 1)
            SELECT a.city, a.pm25, a.hours_share, m.stations
            FROM annual a JOIN meta m USING (city)""").df()
        df["year"] = year
        rows.append(df)
        print(year, ", ".join(f"{r.city} {r.pm25:.0f} ({r.stations}, {r.hours_share:.0%})"
                              for r in df.sort_values("city").itertuples()))
    out = pd.concat(rows)
    out["state"] = out.city.map({c: v[0] for c, v in CITIES.items()})
    dropped = out[out.hours_share < MIN_HOURS_SHARE]
    print("dropped for coverage:", ", ".join(f"{r.city} {r.year} ({r.hours_share:.0%})"
                                             for r in dropped.itertuples()) or "none")
    out = out[out.hours_share >= MIN_HOURS_SHARE]
    out["pm25"] = out.pm25.round(1)
    out["hours_share"] = out.hours_share.round(3)
    out = out[["city", "state", "year", "pm25", "stations", "hours_share"]].sort_values(["city", "year"])
    out.to_csv(DATA / "exposure_cpcb.csv", index=False)

    monthly = pd.concat(months)
    mdrop = monthly[monthly.hours_share < MIN_HOURS_SHARE]
    print("city-months dropped for coverage:", mdrop.groupby("city").size().to_dict())
    monthly = monthly[monthly.hours_share >= MIN_HOURS_SHARE].copy()
    monthly["pm25"] = monthly.pm25.round(1)
    monthly["hours_share"] = monthly.hours_share.round(3)
    monthly[["city", "year", "month", "pm25", "hours_share"]].sort_values(
        ["city", "year", "month"]).to_csv(DATA / "monthly_cpcb.csv", index=False)

    census = census_populations(xlsx)
    cities = pd.DataFrame([{
        "city": city, "state": state,
        "population": sum(census[norm(e)][1] for e in entries),
        "census_name": ";".join(census[norm(e)][0] for e in entries),
        "aqli_units": ";".join(aqli), "acag_units": ";".join(acag),
        "apna_airshed": airshed, "cpcb_cities": ";".join(cpcb),
    } for city, (state, entries, aqli, acag, airshed, cpcb) in CITIES.items()])
    for col, f in (("aqli_units", "exposure_aqli.csv"), ("acag_units", "exposure_acag_total.csv")):
        t = pd.read_csv(DATA / f, usecols=["state", "unit"]).drop_duplicates()
        have = set(zip(t.state, t.unit))
        for c in cities.itertuples():
            for unit in getattr(c, col).split(";"):
                assert (c.state, unit) in have, (f, c.state, unit)
    apna = pd.read_csv(DATA / "apna_source_apportionment.csv").City
    assert sorted(cities.apna_airshed.dropna()) == sorted(apna), "cities must cover the APnA airsheds"
    cities.to_csv(DATA / "cities.csv", index=False)
    print(cities.to_string())


if __name__ == "__main__":
    main()
