"""Write data/places.csv: India, its states and UTs, cities and districts, with aliases.

    python scripts/build_places.py

States: canonical names are those of baseline.states() (the SRS and population
projection tables); the aliases below are every other spelling found in the sources
this package reads (SRS, projections, AQLI gadm1, geoBoundaries ADM1, Pandey et al.
2021, CPCB). Spellings that differ only in case, accents or '&'/'and' need no alias.

Cities come from data/cities.csv, districts from the units of the exposure tables
(data/exposure_aqli.csv, data/exposure_acag_total.csv), each under its parent state.
Run it once before the exposure builds (they need the state aliases) and again after.
"""
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parents[1] / "data"

STATES = {  # canonical name: aliases
    "India": ["INDIA"],
    "Andaman & Nicobar Islands": ["Andaman and Nicobar", "A & N Islands"],
    "Andhra Pradesh": [],
    "Arunachal Pradesh": [],
    "Assam": [],
    "Bihar": [],
    "Chandigarh": [],
    "Chhattisgarh": [],
    "Dadra & Nagar Haveli": [],
    "Daman & Diu": [],
    "Delhi": ["NCT of Delhi", "National Capital Territory of Delhi"],
    "Goa": [],
    "Gujarat": [],
    "Haryana": [],
    "Himachal Pradesh": [],
    "Jammu & Kashmir": ["JAMMU & KASHMIR (UT)"],
    "Jharkhand": [],
    "Karnataka": [],
    "Kerala": [],
    "Ladakh": [],
    "Lakshadweep": [],
    "Madhya Pradesh": [],
    "Maharashtra": [],
    "Manipur": [],
    "Meghalaya": [],
    "Mizoram": [],
    "Nagaland": [],
    "Odisha": ["Orissa"],
    "Puducherry": ["Pondicherry"],
    "Punjab": ["Punjab(India)"],
    "Rajasthan": [],
    "Sikkim": [],
    "Tamil Nadu": ["TamilNadu"],
    "Telangana": ["Telengana"],
    "Tripura": [],
    "Uttar Pradesh": [],
    "Uttarakhand": ["Uttaranchal"],
    "West Bengal": [],
}

CITY_ALIASES = {
    "Mumbai": ["Bombay", "Greater Mumbai"],
    "Kolkata": ["Calcutta"],
    "Bengaluru": ["Bangalore", "Bruhat Bangalore"],
    "Chennai": ["Madras"],
    "Ahmedabad": ["Ahmadabad"],
    "Pune": ["Poona"],
}


def main() -> None:
    rows = [{"name": "India", "kind": "country", "state": "",
             "aliases": ";".join(STATES["India"])}]
    rows += [{"name": s, "kind": "state", "state": s, "aliases": ";".join(a)}
             for s, a in STATES.items() if s != "India"]

    cities = DATA / "cities.csv"
    if cities.exists():
        for c in pd.read_csv(cities).itertuples():
            rows.append({"name": c.city, "kind": "city", "state": c.state,
                         "aliases": ";".join(CITY_ALIASES.get(c.city, []))})

    units = []
    for f in ("exposure_aqli.csv", "exposure_acag_total.csv"):
        if (DATA / f).exists():
            units.append(pd.read_csv(DATA / f, usecols=["state", "unit"]))
    if units:
        d = pd.concat(units).drop_duplicates().sort_values(["state", "unit"])
        rows += [{"name": r.unit, "kind": "district", "state": r.state, "aliases": ""}
                 for r in d.itertuples()]

    out = pd.DataFrame(rows, columns=["name", "kind", "state", "aliases"])
    assert not out.duplicated(["name", "kind", "state"]).any()
    out.to_csv(DATA / "places.csv", index=False)
    print(out.kind.value_counts().to_string())


if __name__ == "__main__":
    main()
