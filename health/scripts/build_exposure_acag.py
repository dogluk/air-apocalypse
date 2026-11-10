"""Build data/exposure_acag_total.csv: ACAG V6.GL.02.04 total PM2.5, 2023, by district.

    python scripts/build_exposure_acag.py [DOWNLOAD_DIR]

Needs the `build` extra (rasterio, geopandas). Downloads to a folder outside the repo:
  - ACAG V6.GL.02.04 annual mean total PM2.5, 0.1°, Asia crop, 2023 (CC BY 4.0), from the
    ACAG archive bucket s3://satpmdata (archive/V6GL0204/);
  - WorldPop Global2 R2025A, India, 2023, 1 km, constrained, UN-adjusted (CC BY 4.0);
  - geoBoundaries gbOpen IND ADM2 (districts, LGD 2021, ODbL) and ADM1 (states, DataMeet,
    CC BY 2.5 IN), pinned to release commit 9469f09.
and keeps only the derived table.

Method: every populated WorldPop pixel (30 arc-seconds) takes the PM2.5 of the 0.1° ACAG
cell containing its centre and the district containing its centre. A populated pixel whose
centre lies in no district polygon (coastline and border slivers) goes to the nearest
district; one whose ACAG cell is empty (water) takes the nearest non-empty cell. District
PM2.5 is the population-weighted mean over its pixels; population is the pixel sum, so the
districts add up to the WorldPop India total. Districts take the state whose ADM1 polygon
holds their representative point; the merged UT 'Dadra and Nagar Haveli and Daman and Diu'
is split by district into the two UTs the SRS reports. Corrections to geoBoundaries: Yanam is
put in Puducherry (the ADM1 outline leaves it inside Andhra Pradesh; checked by area overlap,
it is the only district whose state differs from its largest overlap other than islands);
'Hydrabad' is spelled Hyderabad; the Ladakh unit named 'DATA NOT AVAILABLE' is 'Unnamed area'.

Output: state, unit, year, pm25, population.
Checks: population kept equals the raster total; the national and state population-weighted
means are printed beside ACAG's own region summaries (tables labelled V6GL0203 in the
V6.GL.02.04 folder, weighted by ACAG's own population), and the national mean must agree
within 10%. (2026-11-10: this table 49.8, ACAG 47.1; at 0.01° instead of 0.1° this table
gives 50.2, so grid resolution is not the gap.)
"""
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from scipy.ndimage import distance_transform_edt

from _fetch import fetch, workdir
from airhealth.places import canonical_state, norm

YEAR = 2023
ACAG = ("https://satpmdata.s3.us-east-1.amazonaws.com/archive/V6GL0204/CNNPM25c0p10/Annual/AS/"
        f"V6GL02.04.CNNPM25.0p10.AS.{YEAR}01-{YEAR}12.nc")
SUMMARIES = "https://satpmdata.s3.us-east-1.amazonaws.com/archive/V6GL0204/RegionSummaries/"
STATE_SUMMARY = "IndiaPM25-V6GL0203-Annual-REGIONAL-1998-2023-wThresFrac.csv"
COUNTRY_SUMMARY = "GlobalPM25-V6GL0203-Annual-1998-2023-wThresFrac.csv"
PW = "Population-Weighted PM2.5 [ug/m3]"
WORLDPOP = ("https://data.worldpop.org/GIS/Population/Global_2015_2030/R2025A/"
            f"{YEAR}/IND/v1/1km_ua/constrained/ind_pop_{YEAR}_CN_1km_R2025A_UA_v1.tif")
GB = "https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/IND/{0}/geoBoundaries-IND-{0}.geojson"
SPLIT_UT = {"dadra and nagar haveli": "Dadra & Nagar Haveli", "daman": "Daman & Diu",
            "diu": "Daman & Diu"}
STATE_FIX = {"Yanam": "Puducherry"}
NAME_FIX = {"Hydrabad": "Hyderabad", "DATA NOT AVAILABLE": "Unnamed area"}
OUT = Path(__file__).resolve().parents[1] / "data" / "exposure_acag_total.csv"


def district_states(adm2: gpd.GeoDataFrame, adm1: gpd.GeoDataFrame) -> pd.Series:
    pts = adm2[["shapeName"]].copy().set_geometry(adm2.geometry.representative_point())
    states = adm1[["shapeName", "geometry"]].rename(columns={"shapeName": "adm1"})
    j = gpd.sjoin(pts, states, how="left", predicate="within")
    j = j[~j.index.duplicated()]
    # Islands whose point falls in the sea on the older state outlines: nearest state.
    miss = j.adm1.isna()
    if miss.any():
        near = gpd.sjoin_nearest(pts[miss].to_crs(3857), states.to_crs(3857), how="left")
        j.loc[miss, "adm1"] = near[~near.index.duplicated()].adm1
        print("state by nearest outline:", dict(zip(j[miss].shapeName, j[miss].adm1)))

    def state(row):
        if row.shapeName in STATE_FIX:
            return STATE_FIX[row.shapeName]
        if row.adm1.startswith("Dādra"):
            return SPLIT_UT[norm(row.shapeName)]
        return canonical_state(row.adm1)
    return j.apply(state, axis=1)


def main() -> None:
    folder = workdir(sys.argv, "acag")
    nc, tif = fetch(ACAG, folder), fetch(WORLDPOP, folder)
    by_state = pd.read_csv(fetch(SUMMARIES + STATE_SUMMARY, folder))
    by_country = pd.read_csv(fetch(SUMMARIES + COUNTRY_SUMMARY, folder))
    adm2 = gpd.read_file(fetch(GB.format("ADM2"), folder))
    adm1 = gpd.read_file(fetch(GB.format("ADM1"), folder))

    with rasterio.open(tif) as r:
        pop = r.read(1).astype("float64")
        pop[(pop == r.nodata) | ~np.isfinite(pop)] = 0
        transform, shape = r.transform, r.shape
    total = pop.sum()

    # District of every pixel centre; populated pixels outside every polygon -> nearest.
    labels = rasterize(((g, i + 1) for i, g in enumerate(adm2.geometry)), out_shape=shape,
                       transform=transform, fill=0, dtype="int32")
    outside = (labels == 0) & (pop > 0)
    dist, (ri, ci) = distance_transform_edt(labels == 0, return_indices=True)
    labels = labels[ri, ci]
    print(f"pixels outside every district: {outside.sum():,}, holding {pop[outside].sum():,.0f} "
          f"people ({pop[outside].sum() / total:.3%}); farthest {dist[outside].max():.0f} px")

    # ACAG value at every populated pixel centre; empty cells -> nearest non-empty cell.
    rows, cols = np.nonzero(pop)
    xs, ys = rasterio.transform.xy(transform, rows, cols)
    with rasterio.open(nc) as r:
        pm = r.read(1).astype("float64")
        pm[(pm == r.nodata) | ~np.isfinite(pm) | (pm < 0)] = np.nan
        ar, ac = rasterio.transform.rowcol(r.transform, xs, ys)
    ar, ac = np.asarray(ar), np.asarray(ac)
    empty = np.isnan(pm[ar, ac])
    _, (fr, fc) = distance_transform_edt(np.isnan(pm), return_indices=True)
    values = pm[fr[ar, ac], fc[ar, ac]]
    print(f"pixels in empty ACAG cells: {empty.sum():,}, holding {pop[rows, cols][empty].sum():,.0f} people")

    w = pop[rows, cols]
    lab = labels[rows, cols]
    n = len(adm2) + 1
    people = np.bincount(lab, weights=w, minlength=n)[1:]
    pm25 = np.bincount(lab, weights=w * values, minlength=n)[1:] / np.where(people > 0, people, 1)

    out = pd.DataFrame({"state": district_states(adm2, adm1).to_numpy(),
                        "unit": adm2.shapeName.str.strip().replace(NAME_FIX).to_numpy(), "year": YEAR,
                        "pm25": pm25.round(2), "population": people.round().astype(int)})
    empty_districts = out[out.population == 0]
    assert empty_districts.empty, empty_districts
    assert not out.duplicated(["state", "unit"]).any(), out[out.duplicated(["state", "unit"], keep=False)]
    assert abs(out.population.sum() - total) < 0.5 * len(out) + 1

    # Cross-check against ACAG's own population-weighted region means.
    s = by_state[by_state.Year == YEAR].set_index("Region")[PW]
    acag_india = by_country.loc[(by_country.Region == "India") & (by_country.Year == YEAR), PW].item()
    states = out.groupby("state").apply(lambda d: np.average(d.pm25, weights=d.population))
    national = np.average(out.pm25, weights=out.population)
    print(f"India: this table {national:.1f}, ACAG summary {acag_india}")
    for region, v in s.items():
        try:
            name = canonical_state(region)
        except KeyError:
            print(f"  ACAG region not matched: {region} {v}")
            continue
        if name in states:
            print(f"  {name:28s} {states[name]:6.1f}  ACAG {v:6.1f}")
    assert abs(national / acag_india - 1) < 0.10, (national, acag_india)

    out.sort_values(["state", "unit"]).to_csv(OUT, index=False)
    print(f"{len(out)} districts; population {out.population.sum():,} (raster total {total:,.0f})")


if __name__ == "__main__":
    main()
