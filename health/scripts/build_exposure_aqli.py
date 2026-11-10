"""Build data/exposure_aqli.csv from the AQLI Annual Update 2025 release (data years 1998-2023).

    python scripts/build_exposure_aqli.py [DOWNLOAD_DIR]

Downloads the gadm0/1/2 wide CSVs from github.com/aqli-epic/aqli-update (pinned commit)
to a folder outside the repo and keeps India's districts (gadm2, name0 == 'India';
GADM files Jammu & Kashmir and Ladakh under iso 'Z01', so the iso code is not used).

Output, one row per district and year:
  state, unit, year, pm25, population, aqli_years_who
pm25 is AQLI's annual mean PM2.5 (dust and sea salt removed), population AQLI's
(one figure per district, the same in every year), aqli_years_who AQLI's life-expectancy
gain if the WHO guideline (5 µg/m³) were met.

Checks: district populations sum to the gadm0 India figure; population-weighted
district means reproduce every gadm1 state value in every year to 0.01.
One Telangana district is named 'NA' in gadm2 (1.5 million people); it is written as
'Unnamed area'.
"""
import io
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from _fetch import fetch, workdir
from airhealth.places import canonical_state

COMMIT = "441f4e2241d9ec92567f080faa99dd3a29f7a90a"  # 2026-10-05, last change to the 2025 folder
BASE = f"https://raw.githubusercontent.com/aqli-epic/aqli-update/{COMMIT}/AQLI%20Annual%20Update%202025%20data"
OUT = Path(__file__).resolve().parents[1] / "data" / "exposure_aqli.csv"


def read(folder, level: int) -> pd.DataFrame:
    z = fetch(f"{BASE}/gadm{level}.zip", folder)
    with zipfile.ZipFile(z) as zf:
        raw = zf.read(f"gadm{level}/gadm{level}_2023_wide.csv")
    # A Telangana district is named 'NA' in gadm2: keep names as text, read NA as missing
    # only in the numeric columns.
    df = pd.read_csv(io.BytesIO(raw), na_values=["NA"], keep_default_na=False)
    for col in ("name", "name0", "name1"):
        if col in df:
            df[col] = pd.read_csv(io.BytesIO(raw), usecols=[col], dtype=str,
                                  keep_default_na=False)[col]
    return df


def main() -> None:
    folder = workdir(sys.argv, "aqli")
    g0, g1, g2 = (read(folder, lvl) for lvl in (0, 1, 2))
    india_total = int(g0.loc[g0.name == "India", "population"].item())
    g1 = g1[g1.name0 == "India"].copy()
    g2 = g2[g2.name0 == "India"].copy()
    years = sorted(int(c[2:]) for c in g2.columns if c.startswith("pm"))

    assert g2.population.sum() == india_total, (g2.population.sum(), india_total)
    for y in years:
        w = g2.groupby("name1").apply(lambda d: np.average(d[f"pm{y}"], weights=d.population))
        diff = (g1.set_index("name")[f"pm{y}"] - w).abs()
        assert diff.max() <= 0.01, (y, diff.idxmax(), diff.max())

    g2["state"] = g2.name1.map(canonical_state)
    g2["name"] = g2.name.str.strip().replace({"NA": "Unnamed area"})  # a Telangana district
    long = g2.melt(id_vars=["state", "name", "population"],
                   value_vars=[f"pm{y}" for y in years], var_name="year", value_name="pm25")
    long["year"] = long.year.str[2:].astype(int)
    who = g2.melt(id_vars=["state", "name"], value_vars=[f"who{y}" for y in years],
                  var_name="year", value_name="aqli_years_who")
    who["year"] = who.year.str[3:].astype(int)
    out = (long.merge(who, on=["state", "name", "year"])
           .rename(columns={"name": "unit"})
           [["state", "unit", "year", "pm25", "population", "aqli_years_who"]]
           .sort_values(["state", "unit", "year"]))
    out["population"] = out.population.astype(int)
    assert not out.isna().any().any()
    assert not out.duplicated(["state", "unit", "year"]).any()
    out.to_csv(OUT, index=False)
    print(f"{len(g2)} districts, {len(years)} years ({years[0]}-{years[-1]}); "
          f"India population {india_total:,}")


if __name__ == "__main__":
    main()
