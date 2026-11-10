"""Cut the national CPCB 15-minute parquet files down to hourly, station-level data for
the cities in config, Sep 15 - Dec 20, 2016-2025. Timestamps are IST: the source parquet stamps
CPCB's IST wall-clock times as UTC without shifting them (checked: ozone peaks at 13-14h only if read this way).

QC (per station-hour, applied on 15-min values before averaging):
- PM2.5 >= 999 is the BAM ceiling. Kept as 999 (right-censored, so peaks are understated) when the
  same station's PM10 is >= 600; otherwise treated as a fault -> null. Matters for Delhi's Diwali
  night, where dozens of station-readings saturate.
- PM2.5 <= 0, PM10 <= 0 or > 2000 -> null
- runs of >= 8 identical consecutive 15-min PM2.5 values (stuck sensor) -> null, except saturated ones
- PM2.5 > PM10 by more than 10% when both present -> both null (physically impossible), except saturated
"""
import duckdb

from config import CITIES, DATA, RAW

cities = sorted({c for v in CITIES.values() for c in v["cpcb_city"]})
city_list = ", ".join(f"'{c}'" for c in cities)

con = duckdb.connect()
con.execute(f"""
CREATE TABLE q AS
SELECT
  "Station ID" AS station_id, City AS city, "Station Name" AS station,
  timezone('UTC', "Timestamp") AS ts,  -- source labels IST wall-clock as UTC (parse.py replace_time_zone), so UTC wall-clock IS IST
  "PM2.5 (µg/m³)" AS pm25, "PM10 (µg/m³)" AS pm10, "NO2 (µg/m³)" AS no2, "SO2 (µg/m³)" AS so2,
  "CO (mg/m³)" AS co, "Ozone (µg/m³)" AS o3, "NH3 (µg/m³)" AS nh3,
  "WS (m/s)" AS ws, "WD (deg)" AS wd, "RF (mm)" AS rf, "RH (%)" AS rh, "AT (°C)" AS temp_c
FROM read_parquet('{RAW}/cpcb-air-quality-*.parquet', union_by_name=true)
WHERE City IN ({city_list})
  AND (month(timezone('UTC', "Timestamp")) BETWEEN 9 AND 12)
""")
print("15-min rows:", con.execute("SELECT count(*) FROM q").fetchone()[0])

con.execute("""
CREATE TABLE q2 AS
WITH cityhr AS (
  -- city-wide median of unsaturated PM2.5 readings in the same clock hour
  SELECT city, date_trunc('hour', ts) AS hr, median(pm25) AS city_med
  FROM q WHERE pm25 > 0 AND pm25 < 999 GROUP BY 1, 2
), c0 AS (
  SELECT q.*,
    -- saturated BAM: PM2.5 at the ~1000 ceiling while the rest of the city is also heavily polluted
    -- (PM10 is usually missing at those moments, so it can't be the check)
    (q.pm25 >= 999 AND cityhr.city_med >= 250) AS sat
  FROM q LEFT JOIN cityhr ON q.city = cityhr.city AND date_trunc('hour', q.ts) = cityhr.hr
), c AS (
  SELECT *,
    CASE WHEN sat THEN 999 WHEN pm25 <= 0 OR pm25 >= 999 THEN NULL ELSE pm25 END AS p25,
    CASE WHEN pm10 <= 0 OR pm10 > 2000 THEN NULL ELSE pm10 END AS p10
  FROM c0
), runs AS (
  SELECT *,
    row_number() OVER (PARTITION BY station_id ORDER BY ts)
      - row_number() OVER (PARTITION BY station_id, p25 ORDER BY ts) AS grp
  FROM c
), runlen AS (
  SELECT *, count(*) OVER (PARTITION BY station_id, p25, grp) AS rl FROM runs
)
SELECT station_id, city, station, ts,
  CASE WHEN sat THEN p25 WHEN rl >= 8 OR (p10 IS NOT NULL AND p25 > 1.1 * p10) THEN NULL ELSE p25 END AS pm25,
  CASE WHEN NOT sat AND (p25 IS NOT NULL AND p25 > 1.1 * p10) THEN NULL ELSE p10 END AS pm10,
  sat, no2, so2, co, o3, nh3, ws, wd, rf, rh, temp_c
FROM runlen
""")

con.execute(f"""
COPY (
  SELECT station_id, city, any_value(station) AS station, date_trunc('hour', ts) AS hour,
    avg(pm25) pm25, avg(pm10) pm10, avg(no2) no2, avg(so2) so2, avg(co) co, avg(o3) o3, avg(nh3) nh3,
    sum(sat::INT) n_sat, avg(ws) ws, avg(wd) wd, sum(rf) rf, avg(rh) rh, avg(temp_c) temp_c, count(pm25) n_pm25
  FROM q2
  WHERE (month(ts) = 9 AND day(ts) >= 15) OR month(ts) IN (10, 11) OR (month(ts) = 12 AND day(ts) <= 20)
  GROUP BY 1, 2, 4
) TO '{DATA}/hourly.parquet' (FORMAT parquet)
""")

print(con.execute(f"""
SELECT city, year(hour) y, count(DISTINCT station_id) stations,
  round(avg((pm25 IS NOT NULL)::INT), 2) pm25_cov, round(avg((so2 IS NOT NULL)::INT), 2) so2_cov
FROM '{DATA}/hourly.parquet' GROUP BY 1, 2 ORDER BY 1, 2
""").df().to_string())
