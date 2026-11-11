"""Build data/districts.geojson: simplified district and state outlines for the dashboard map.

    python scripts/build_district_shapes.py [DOWNLOAD_DIR]

Needs the `build` extra (geopandas, rasterio). Downloads geoBoundaries gbOpen IND ADM2 and
ADM1 (pinned to release commit 9469f09, the same files build_exposure_acag.py uses) to a
folder outside the repo.

Each district keeps the state and unit name exposure_acag_total.csv gives it (same state
assignment, same name fixes), so ACAG values join one to one. AQLI uses older GADM district
boundaries with other spellings; each district gets `aqli_unit`, the AQLI unit of the same
state whose normalised name matches exactly, else the closest by difflib (ratio >= CUTOFF),
else the state's only AQLI unit if it has one (Delhi), else none; ALIASES overrides all of these (drawn grey, "no matching
AQLI district"). A new district carved out of an old one keeps none unless its name matches.

Outlines are simplified together (shapely.coverage_simplify, so neighbours still meet) with
TOLERANCE degrees, coordinates rounded to 3 decimals (about 100 m). State outlines are the
union of their simplified districts. Output: one FeatureCollection, `layer` = "district" or
"state". The map is for looking, not measuring: no number is computed from these outlines.
"""
import difflib
import json
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import shapely
from shapely.geometry import mapping

from _fetch import fetch, workdir
from airhealth.places import norm
from build_exposure_acag import GB, NAME_FIX, district_states

DATA = Path(__file__).resolve().parents[1] / "data"
OUT = DATA / "districts.geojson"
TOLERANCE = 0.02
CUTOFF = 0.7
# Checked by hand against the AQLI unit list, 2026-11-11: spelling matches that picked the
# wrong unit (Agar -> Sagar, ...), and districts with no AQLI unit of their own, which would
# otherwise take a wrong neighbour's name.
ALIASES = {
    ("Uttar Pradesh", "Kanshiram Nagar"): "Kasganj",
    ("Madhya Pradesh", "Agar"): "Agar Malwa",
    ("Uttarakhand", "Garhwal"): "Pauri Garhwal",
    ("Telangana", "Warangal (R)"): "Warangal (Rural)",
    ("Arunachal Pradesh", "Lower Siang"): None,
    ("Mizoram", "Khawzawl"): None,
    ("Tamil Nadu", "Tirupathur"): None,
}


def aqli_units(gb: pd.DataFrame) -> list[str | None]:
    aq = pd.read_csv(DATA / "exposure_aqli.csv")
    aq = aq[aq.year == aq.year.max()]
    by_state = {s: list(g.unit) for s, g in aq.groupby("state")}
    out = []
    for state, unit in zip(gb.state, gb.unit):
        names = by_state.get(state, [])
        if (state, unit) in ALIASES:
            alias = ALIASES[state, unit]
            assert alias is None or alias in names, (state, unit, alias)
            out.append(alias)
            continue
        normed = {norm(n): n for n in names}
        if norm(unit) in normed:
            out.append(normed[norm(unit)])
            continue
        close = difflib.get_close_matches(norm(unit), list(normed), n=1, cutoff=CUTOFF)
        if close:
            out.append(normed[close[0]])
        elif len(names) == 1:
            out.append(names[0])
        else:
            out.append(None)
    return out


def rounded(geom) -> dict:
    return json.loads(json.dumps(mapping(shapely.set_precision(geom, 0.001))))


def main() -> None:
    folder = workdir(sys.argv, "shapes")
    adm2 = gpd.read_file(fetch(GB.format("ADM2"), folder))
    adm1 = gpd.read_file(fetch(GB.format("ADM1"), folder))
    gb = pd.DataFrame({"state": district_states(adm2, adm1).to_numpy(),
                       "unit": adm2.shapeName.str.strip().replace(NAME_FIX).to_numpy()})
    acag = pd.read_csv(DATA / "exposure_acag_total.csv")
    assert set(zip(gb.state, gb.unit)) == set(zip(acag.state, acag.unit)), "ACAG units differ"
    gb["aqli_unit"] = aqli_units(gb)

    geoms = shapely.coverage_simplify(adm2.geometry.make_valid().to_numpy(), TOLERANCE)
    feats = [dict(type="Feature", properties=dict(layer="district", state=s, unit=u,
                                                  aqli_unit=a if isinstance(a, str) else None),
                  geometry=rounded(g))
             for s, u, a, g in zip(gb.state, gb.unit, gb.aqli_unit, geoms)]
    for state, idx in gb.groupby("state").groups.items():
        feats.append(dict(type="Feature", properties=dict(layer="state", state=state),
                          geometry=rounded(shapely.union_all(geoms[list(idx)]))))
    OUT.write_text(json.dumps(dict(type="FeatureCollection", features=feats),
                              separators=(",", ":"), allow_nan=False))

    aq = pd.read_csv(DATA / "exposure_aqli.csv")
    aq = aq[aq.year == aq.year.max()]
    hit = aq.set_index(["state", "unit"]).index.isin(list(zip(gb.state, gb.aqli_unit)))
    print(f"{len(gb)} districts, {gb.state.nunique()} states; {OUT.stat().st_size / 1e3:,.0f} kB")
    print(f"districts with an AQLI unit: {gb.aqli_unit.notna().sum()} of {len(gb)}")
    print(f"AQLI units drawn: {hit.sum()} of {len(aq)}, "
          f"{aq.population[hit].sum() / aq.population.sum():.1%} of AQLI's population")
    fuzzy = gb[gb.aqli_unit.notna() & (gb.unit.map(norm) != gb.aqli_unit.fillna("").map(norm))]
    print("matched by spelling, not exactly:")
    print(fuzzy.to_string(index=False))


if __name__ == "__main__":
    main()
