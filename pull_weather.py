"""Hourly ERA5 weather (Open-Meteo archive, no key) for each city, Sep 15 - Dec 20, 2016-2025.

Adds what CPCB stations don't measure well: boundary layer height (mixing depth) and
gridded precipitation, plus wind and humidity as a cross-check on station met.
"""
import time

import pandas as pd
import requests

from config import CITIES, DATA, DIWALI, SEASON

VARS = "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,wind_direction_10m,boundary_layer_height"

frames = []
for city, c in CITIES.items():
    for y in DIWALI:
        for attempt in range(5):
            try:
                r = requests.get(
                    "https://archive-api.open-meteo.com/v1/archive",
                    params=dict(latitude=c["lat"], longitude=c["lon"], hourly=VARS,
                                start_date=f"{y}-{SEASON[0]}", end_date=f"{y}-{SEASON[1]}",
                                timezone="Asia/Kolkata"),
                    timeout=90,
                )
                r.raise_for_status()
                break
            except requests.RequestException as e:
                print(f"{city} {y} attempt {attempt}: {e.__class__.__name__}")
                time.sleep(5 * (attempt + 1))
        else:
            raise SystemExit(f"failed {city} {y}")
        df = pd.DataFrame(r.json()["hourly"])
        df["city"] = city
        frames.append(df)
        time.sleep(0.5)

out = pd.concat(frames)
out["time"] = pd.to_datetime(out["time"])  # local IST
out.to_parquet(DATA / "weather_era5.parquet", index=False)
print(out.groupby("city").size(), out.isna().mean().round(3), sep="\n")
