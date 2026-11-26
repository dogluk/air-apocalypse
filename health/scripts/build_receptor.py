"""Build data/receptor_<name>.csv: how much each district's PM2.5 falls when a whole source is removed.

    python scripts/build_receptor.py [DOWNLOAD_DIR]

Needs the `build` extra (rasterio, geopandas). A receptor file has one row per district the study's
area covers: district, state, delta_pm25_full (annual-mean µg/m³, negative or 0: the change in that
district when the whole source is removed). airhealth.measures checks the format; score.py reads it.

Which source a receptor comes from (spec part 3, in order of preference):
  1. A published source-receptor result at district level. None could be used yet:
     - Stubble: Lan et al. 2022 (Nat Commun 13:6537, doi 10.1038/s41467-022-34093-z) run the GEOS-Chem
       adjoint with India-wide population-weighted exposure as the one receptor, so they give each
       SOURCE district's share of the national exposure (Supplementary Data 2-4, by state and season),
       not the change in PM2.5 in each RECEPTOR district. Their forward runs with and without burning
       are shown only as maps. See data/MISSING.md.
     - Coal power plants: Cropper et al. 2021 (PNAS, doi 10.1073/pnas.2017936118) give the
       plants' PM2.5 by state only (SI Table S2); scripts/build_receptor_cropper.py turns that into
       receptor_power_cropper2021.csv. Their gridded release (openICPSR 130404) could not be
       opened. See data/MISSING.md.
  2. Otherwise McDuffie et al. 2021 (Nat Commun 12:3594, CC BY 4.0) gridded fractional contributions
     (Zenodo record 4739100, 0.01°, one CSV per source, one value per line, global grid in row order
     from (-89.995, -179.995), longitude fastest) times ACAG total PM2.5. This is what is built here:

       receptor_stubble.csv      GFEDagburn: agricultural waste (crop-residue) burning, GFED fires.
       receptor_energy_coal.csv  ENEcoal: coal burned for energy production. The README defines it as
                                 "electricity and heat production, fuel production and transformation,
                                 oil and gas fugitive/flaring, and fossil fuel fires" (coal combustion
                                 only), so it is power stations plus other coal-fired energy
                                 production, not power stations alone.

     Both are a sector from every origin, not only the named states: the stubble file counts every
     crop fire GEOS-Chem saw (Pakistan's and the rest of India's as well as Punjab's and Haryana's).
     And a McDuffie fraction is a zero-out difference rescaled so that the 24 sources sum to 100%
     (paper, Methods, Eq. 4-5), not the raw change from removing the source; the two differ where
     the chemistry is not additive.

Method: the same pixels, districts and PM2.5 as scripts/build_exposure_acag.py (WorldPop 2023 1 km
populated pixels, geoBoundaries ADM2, ACAG V6.GL.02.04 2023 at 0.1°). Each pixel also takes the
McDuffie fraction of the 0.01° cell holding its centre (a NaN cell -> the nearest non-NaN cell).
District delta_pm25_full = - sum(pop x PM2.5 x fraction) / sum(pop): McDuffie's own way of turning a
fraction into µg/m³ (fraction x PM2.5, Zenodo record description), on this repo's PM2.5 map. Check:
the same sums without the fraction reproduce data/exposure_acag_total.csv's pm25 to 0.01.

The McDuffie CSVs are ~5 GB each; only India's box is kept (streamed; the crop is saved as .npy in
the download folder). The LatLon file is streamed once to check the row order assumed above.
"""
import sys
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_exposure_acag as acag  # noqa: E402
from _fetch import fetch, workdir  # noqa: E402
from airhealth import measures, paths  # noqa: E402

RECORD = "https://zenodo.org/records/4739100"
FILE = "https://zenodo.org/api/records/4739100/files/GBD-MAPS_Gridded_Fractional_Contributions_{}.csv/content"
SOURCES = {"stubble": "GFEDagburn", "energy_coal": "ENEcoal"}
NLON = 36000                      # 0.01° global grid: 18000 rows of 36000
LAT0, LON0, STEP = -89.995, -179.995, 0.01
ROWS = (9600, 12750)              # cell rows kept: lat 6.005 .. 37.495
COLS = (24800, 27750)             # cell columns kept: lon 68.005 .. 97.495
COLUMNS = ["district", "state", "delta_pm25_full"]


def crop(url: str, out: Path, ncols: int = 1) -> np.ndarray:
    """Stream a McDuffie CSV and keep India's box: array (rows, cols) or (rows, cols, ncols)."""
    if out.exists():
        return np.load(out)
    r0, r1 = ROWS
    c0, c1 = COLS
    width = c1 - c0
    first, last = r0 * NLON, r1 * NLON          # data-line indices that can hold kept cells
    kept: list[bytes] = []
    k, rest, header = 0, b"", True
    req = urllib.request.Request(url, headers={"User-Agent": "airhealth-build"})
    with urllib.request.urlopen(req, timeout=600) as resp:
        while k < last:
            chunk = resp.read(1 << 24)
            if not chunk:
                break
            parts = (rest + chunk).split(b"\n")
            rest = parts.pop()
            if header:
                parts, header = parts[1:], False
            n = len(parts)
            if k + n > first:
                for row in range(max(r0, k // NLON), min(r1, (k + n - 1) // NLON + 1)):
                    a = max(row * NLON + c0, k) - k
                    b = min(row * NLON + c1, k + n) - k
                    if b > a:
                        kept.extend(parts[a:b])
            k += n
    rows = r1 - r0
    if len(kept) != rows * width:
        raise RuntimeError(f"{url}: kept {len(kept)} values, expected {rows * width}")
    if ncols == 1:
        arr = np.array(kept, dtype="S24").astype("float32").reshape(rows, width)
    else:
        arr = np.array([p.split(b",") for p in kept], dtype="S24").astype("float64").reshape(rows, width, ncols)
    np.save(out, arr)
    return arr


def check_order(folder: Path) -> None:
    """The LatLon file's coordinates for the kept box equal the row order assumed."""
    ll = crop(FILE.format("LatLon"), folder / "mcduffie_latlon_india.npy", ncols=2)
    lat = LAT0 + STEP * np.arange(*ROWS)
    lon = LON0 + STEP * np.arange(*COLS)
    assert np.allclose(ll[:, :, 0], lat[:, None], atol=1e-6), "LatLon rows differ from the assumed order"
    assert np.allclose(ll[:, :, 1], lon[None, :], atol=1e-6), "LatLon columns differ from the assumed order"
    print("LatLon order checked for India's box")


def fill_nearest(a: np.ndarray) -> np.ndarray:
    from scipy.ndimage import distance_transform_edt
    bad = ~np.isfinite(a)
    if not bad.any():
        return a
    _, (ri, ci) = distance_transform_edt(bad, return_indices=True)
    return a[ri, ci]


def main() -> None:
    import geopandas as gpd
    import rasterio
    from rasterio.features import rasterize
    from scipy.ndimage import distance_transform_edt

    folder = workdir(sys.argv, "receptor")
    check_order(folder)
    fractions = {}
    for name, sector in SOURCES.items():
        f = crop(FILE.format(sector), folder / f"mcduffie_{sector}_india.npy")
        print(f"{sector}: {np.isnan(f).mean():.2%} NaN cells in India's box; max {np.nanmax(f):.4f}")
        fractions[name] = fill_nearest(f.astype("float64"))

    nc, tif = fetch(acag.ACAG, folder), fetch(acag.WORLDPOP, folder)
    adm2 = gpd.read_file(fetch(acag.GB.format("ADM2"), folder))
    adm1 = gpd.read_file(fetch(acag.GB.format("ADM1"), folder))
    with rasterio.open(tif) as r:
        pop = r.read(1).astype("float64")
        pop[(pop == r.nodata) | ~np.isfinite(pop)] = 0
        transform, shape = r.transform, r.shape
    labels = rasterize(((g, i + 1) for i, g in enumerate(adm2.geometry)), out_shape=shape,
                       transform=transform, fill=0, dtype="int32")
    _, (ri, ci) = distance_transform_edt(labels == 0, return_indices=True)
    labels = labels[ri, ci]
    rows, cols = np.nonzero(pop)
    xs, ys = rasterio.transform.xy(transform, rows, cols)
    xs, ys = np.asarray(xs), np.asarray(ys)
    with rasterio.open(nc) as r:
        pm = r.read(1).astype("float64")
        pm[(pm == r.nodata) | ~np.isfinite(pm) | (pm < 0)] = np.nan
        ar, ac = rasterio.transform.rowcol(r.transform, xs, ys)
    ar, ac = np.asarray(ar), np.asarray(ac)
    _, (fr, fc) = distance_transform_edt(np.isnan(pm), return_indices=True)
    values = pm[fr[ar, ac], fc[ar, ac]]
    # McDuffie cell of each pixel centre
    mr = np.floor((ys - (LAT0 - STEP / 2)) / STEP).astype(int) - ROWS[0]
    mc = np.floor((xs - (LON0 - STEP / 2)) / STEP).astype(int) - COLS[0]
    inside = (mr >= 0) & (mr < ROWS[1] - ROWS[0]) & (mc >= 0) & (mc < COLS[1] - COLS[0])
    assert inside.all(), f"{(~inside).sum()} populated pixels fall outside the kept box"

    w = pop[rows, cols]
    lab = labels[rows, cols]
    n = len(adm2) + 1
    people = np.bincount(lab, weights=w, minlength=n)[1:]
    pm25 = np.bincount(lab, weights=w * values, minlength=n)[1:] / people
    names = pd.DataFrame({"state": acag.district_states(adm2, adm1).to_numpy(),
                          "district": adm2.shapeName.str.strip().replace(acag.NAME_FIX).to_numpy()})
    table = pd.read_csv(paths.DATA / "exposure_acag_total.csv")
    check = names.assign(pm25=pm25).merge(table, left_on=["state", "district"],
                                          right_on=["state", "unit"], suffixes=("", "_table"))
    assert len(check) == len(table), (len(check), len(table))
    gap = (check.pm25.round(2) - check.pm25_table).abs().max()
    assert gap <= 0.011, f"district PM2.5 differs from exposure_acag_total.csv by up to {gap}"
    print(f"district PM2.5 reproduces exposure_acag_total.csv (largest gap {gap:.3f})")

    for name, frac in fractions.items():
        f = frac[mr, mc]
        delta = -np.bincount(lab, weights=w * values * f, minlength=n)[1:] / people
        out = names.assign(delta_pm25_full=np.round(delta, 3))[COLUMNS]
        for row in out.itertuples():
            measures.district(row.district, row.state)
        path = paths.DATA / f"receptor_{name}.csv"
        out.sort_values(["state", "district"]).to_csv(path, index=False)
        pw = np.average(delta, weights=people)
        print(f"wrote {path.name}: {len(out)} districts; India population-weighted change {pw:.2f} µg/m³; "
              f"largest {delta.min():.2f} in {out.loc[out.delta_pm25_full.idxmin(), 'district']}")


if __name__ == "__main__":
    main()
