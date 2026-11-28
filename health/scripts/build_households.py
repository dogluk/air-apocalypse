"""Build data/city_households.csv: Census 2011 households for each city of data/cities.csv.

    python scripts/build_households.py [DOWNLOAD_DIR]

Needs the `build` extra (openpyxl). Columns: city, households, population, census_name.
census_name and population are copied from cities.csv (population is the Census 2011 persons
figure there). households is the Census 2011 count of households ("No_HH") for the same
entries: the sum over the ';'-separated census_name entries.

Two Census tables are read, both from censusindia.gov.in:
- PCA-UA, Primary Census Abstract - Urban Agglomeration, India, 2011: one row per urban
  agglomeration ("Level" 0), with No_HH and TOT_P. Used for every entry printed 'U.A.' in cities.csv.
- PCA TV, Primary Census Abstract at town, village and ward level, one file per district: used
  for the entries cities.csv takes as a single town, because the census lists no urban
  agglomeration for them (TOWN_ENTRIES below). A town split across sub-districts is printed in
  several 'TOWN' rows with the same town code; they are added up.

Check in the script: for every city, the persons found in the Census file equal the population in
cities.csv (to the person), so the households are counted over the same area as the population.
"""
import re
import sys
from pathlib import Path

import pandas as pd

from _fetch import fetch, workdir

HEALTH = Path(__file__).resolve().parents[1]
DATA = HEALTH / "data"
BASE = "https://censusindia.gov.in/nada/index.php/catalog"
UA_FILE = (f"{BASE}/45261/download/48987/PCA11-UA-0000.xlsx", "PCA11-UA-0000.xlsx")

# census_name as in cities.csv -> (district file, town code). The file is the PCA TV workbook of the
# district that holds the town (catalog id / download id / file name).
TOWN_ENTRIES = {
    "Jaipur *": ("6301/download/9378/DDW_PCA0812", 800522),               # Jaipur (M Corp.), in three parts
    "Agartala #": ("6480/download/9557/DDW_PCA1601", 801523),             # Agartala (M Cl)
    "Hubli-Dharwad": ("6753/download/9830/DDW_PCA2908", 803083),          # Hubli-Dharwad (M Corp.)
    "Kota*": ("6318/download/9395/DDW_PCA0829", 800609),                  # Kota (M Corp.)
    "Cuddalore": ("6808/download/9885/DDW_PCA3316", 803650),              # Cuddalore (M)
    "Tenali": ("6739/download/9816/DDW_PCA2817", 802982),                 # Tenali (M)
    "Visakhapatnam @": ("6735/download/9812/DDW_PCA2813", 802947),        # GVMC (Greater Visakhapatnam), in seven parts
    "Ludhiana": ("6232/download/9309/DDW_PCA0307", 800196),               # Ludhiana (M Corp.)
    "Ambala": ("6261/download/9338/DDW_PCA0602", 800365),                 # Ambala (M Cl); Ambala Sadar is in the UA
}


def clean(name: str) -> str:
    """'Delhi  U.A.' -> 'delhi'; 'Panaji U.A' -> 'panaji'; census footnote marks dropped."""
    name = re.sub(r"[$@!#*]", "", name)
    name = re.sub(r"\bU\.?A\.?\s*$", "", name.strip(), flags=re.I)
    return re.sub(r"\s+", " ", name).strip().lower()


def ua_table(xlsx: Path) -> dict[str, tuple[int, int]]:
    d = pd.read_excel(xlsx, sheet_name="Data", dtype={"Town Code": str})
    d = d[d["Level"] == 0]
    out = {}
    for _, r in d.iterrows():
        key = clean(r["UA Name"])
        assert key not in out, f"urban agglomeration {key!r} appears twice"
        out[key] = (int(r["No_HH"]), int(r["TOT_P"]))
    return out


def town_totals(xlsx: Path, code: int) -> tuple[int, int]:
    d = pd.read_excel(xlsx, sheet_name=0)
    t = d[(d["Level"] == "TOWN") & (d["Town/Village"] == code)]
    assert len(t), f"town {code} not in {xlsx.name}"
    return int(t["No_HH"].sum()), int(t["TOT_P"].sum())


def main() -> None:
    folder = workdir(sys.argv, "households")
    uas = ua_table(fetch(UA_FILE[0], folder, UA_FILE[1]))
    cities = pd.read_csv(DATA / "cities.csv")
    towns = {}
    for entry, (path, code) in TOWN_ENTRIES.items():
        name = path.rsplit("/", 1)[-1] + ".xlsx"
        towns[entry] = town_totals(fetch(f"{BASE}/{path}_2011_MDDS%20with%20UI.xlsx", folder, name), code)

    rows = []
    for _, c in cities.iterrows():
        hh = pop = 0
        for entry in c["census_name"].split(";"):
            if entry in towns:
                h, p = towns[entry]
            else:
                h, p = uas[clean(entry)]
            hh += h
            pop += p
        assert pop == c["population"], f"{c['city']}: census file says {pop} persons, cities.csv {c['population']}"
        rows.append({"city": c["city"], "households": hh, "population": pop, "census_name": c["census_name"]})
    pd.DataFrame(rows).to_csv(DATA / "city_households.csv", index=False)
    print(f"wrote {len(rows)} cities")


if __name__ == "__main__":
    main()
