"""Daily MODIS fire counts (NASA FIRMS public country archive) per source region.

- punjab_haryana: the stubble-burning belt, upwind of Delhi / Jaipur / Lucknow in Oct-Nov.
- local_<city>: fires within LOCAL_FIRE_KM of each city centre (regional crop/biomass burning).

Only type 0 (presumed vegetation fire), confidence >= 30. Dates converted UTC -> IST.
"""
import numpy as np
import pandas as pd

from config import CITIES, DATA, DIWALI, FIRES, LOCAL_FIRE_KM, PUNJAB_HARYANA_BBOX


def km(lat1, lon1, lat2, lon2):
    p = np.pi / 180
    a = np.sin((lat2 - lat1) * p / 2) ** 2 + np.cos(lat1 * p) * np.cos(lat2 * p) * np.sin((lon2 - lon1) * p / 2) ** 2
    return 12742 * np.arcsin(np.sqrt(a))


rows = []
for y in DIWALI:
    df = pd.read_csv(FIRES / f"modis_{y}_India.csv")
    df = df[(df["type"] == 0) & (df.confidence >= 30)]
    ts = pd.to_datetime(df.acq_date + " " + df.acq_time.astype(str).str.zfill(4), format="%Y-%m-%d %H%M")
    df["date"] = (ts + pd.Timedelta(hours=5, minutes=30)).dt.normalize()
    b = PUNJAB_HARYANA_BBOX
    masks = {"punjab_haryana": df.latitude.between(b["lat_min"], b["lat_max"]) & df.longitude.between(b["lon_min"], b["lon_max"])}
    for city, c in CITIES.items():
        masks[f"local_{city}"] = km(c["lat"], c["lon"], df.latitude.values, df.longitude.values) <= LOCAL_FIRE_KM
    for region, m in masks.items():
        d = df[m].groupby("date").agg(fires=("frp", "size"), frp=("frp", "sum")).reset_index()
        d["region"] = region
        rows.append(d)

out = pd.concat(rows).groupby(["region", "date"], as_index=False)[["fires", "frp"]].sum()  # year files overlap at New Year in IST
idx = pd.date_range(f"{min(DIWALI)}-01-01", f"{max(DIWALI)}-12-31", freq="D")
full = []
for region, g in out.groupby("region"):
    g = g.set_index("date").reindex(idx).fillna({"fires": 0, "frp": 0}).assign(region=region)
    full.append(g.rename_axis("date").reset_index())
out = pd.concat(full).reset_index(drop=True)
out.to_parquet(DATA / "fires_daily.parquet", index=False)

out["m"], out["y"] = out.date.dt.month, out.date.dt.year
print("Mean daily fire detections, Oct-Nov, 2016-25:")
print(out[out.m.isin([10, 11])].groupby("region").fires.mean().round(1).sort_values(ascending=False).to_string())
