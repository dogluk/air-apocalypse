"""Build India's population, deaths and life table by age from the UN World Population
Prospects 2024 (WPP 2024), 2011-2036, into health/data/.

    python scripts/build_unwpp.py [DOWNLOAD_DIR]

DOWNLOAD_DIR (outside the repo) holds the seven gzipped CSV files below, downloaded by the
script from the 'CSV format' section of https://population.un.org/wpp/downloads (Standard
Projections). WPP gives no Indian states: India only (LocID 356, ISO3 IND). Estimates run to
2023; 2024 on is the Medium variant projection. Counts in the files are in thousands, given to
three decimals, so they are whole persons; this script writes persons.

Outputs (both sexes):
  unwpp_population_age.csv   year, age_start, population
      Population on 1 July (the 'PopulationBySingleAgeSex' files; WPP's 1 January series is a
      separate set), single ages 0-99 and 100+ summed into the 19 bands of airhealth.ages.
  unwpp_deaths_age.csv       year, age_start, deaths
      Deaths in the calendar year (1 January - 31 December), single ages summed the same way.
  unwpp_lifetable.csv        year, age_start, mx, lx, Lx
      The abridged life table (bands 0, 1-4, 5-9, ..., 95-99, 100+). Bands 0 to 80-84 are
      copied as printed; 85+ is closed from the printed columns: lx = l(85), Lx = the sum of
      nLx over 85-89 ... 100+ (= T(85)), mx = the sum of ndx over those bands / that Lx, the
      death rate of the open band as one group (not a mean of the rates). lx has radix 100,000.

Checks: the bands sum to WPP's own total population (1 July) and total deaths in the
Demographic Indicators file; single ages are 0..100 once each; the life table's own deaths over
85 equal l(85); life expectancy at birth from the written mx (airhealth.lifetable.e0, which
closes 85+ with L = l/m and uses n/2 and the SRS infant rule for a) is within 0.3 years of WPP's
printed e0 in 2011, 2019 and 2023 (and is printed for every year).

Also printed (not written to a file): India's crude death rate per 1,000, total deaths over
the 1 July population, every year, against WPP's own CDR column and the SRS crude death rate
(data/srs_crude_death_rate.csv) for 2011-2024.
"""
import csv
import gzip
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from _fetch import fetch, workdir
from airhealth.ages import AGE_STARTS
from airhealth.lifetable import e0

DATA = Path(__file__).resolve().parents[1] / "data"
BASE = ("https://population.un.org/wpp/assets/Excel%20Files/"
        "1_Indicator%20(Standard)/CSV_FILES/")
FILES = {
    "pop": ["WPP2024_PopulationBySingleAgeSex_Medium_1950-2023.csv.gz",
            "WPP2024_PopulationBySingleAgeSex_Medium_2024-2100.csv.gz"],
    "deaths": ["WPP2024_DeathsBySingleAgeSex_Medium_1950-2023.csv.gz",
               "WPP2024_DeathsBySingleAgeSex_Medium_2024-2100.csv.gz"],
    "life": ["WPP2024_Life_Table_Abridged_Medium_1950-2023.csv.gz",
             "WPP2024_Life_Table_Abridged_Medium_2024-2100.csv.gz"],
    "ind": ["WPP2024_Demographic_Indicators_Medium.csv.gz"],
}
YEARS = range(2011, 2037)
LAST_ESTIMATE = 2023
OPEN = AGE_STARTS[-1]                   # 85
E0_CHECK_YEARS = (2011, 2019, 2023)
E0_TOLERANCE = 0.3


def india_rows(path: Path) -> pd.DataFrame:
    """India's rows of a WPP CSV (streamed: the files are large), years in YEARS."""
    keep = []
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        iso, time = header.index("ISO3_code"), header.index("Time")
        for row in reader:
            if row[iso] == "IND" and int(row[time]) in YEARS:
                keep.append(row)
    t = pd.DataFrame(keep, columns=header)
    assert (t.LocID == "356").all() and (t.Location == "India").all()
    return t


def read(folder: Path, key: str) -> pd.DataFrame:
    t = pd.concat([india_rows(fetch(BASE + name, folder)) for name in FILES[key]],
                  ignore_index=True)
    assert (t.Variant == "Medium").all()
    t["Time"] = t.Time.astype(int)
    return t


def to_bands(t: pd.DataFrame, value: str, name: str) -> pd.DataFrame:
    """Single ages 0..99 and 100+ (thousands) -> persons in the 19 bands."""
    t = t.assign(age=t.AgeGrpStart.astype(int), v=t[value].astype(float))
    for year, g in t.groupby("Time"):
        assert sorted(g.age) == list(range(101)), (name, year)
        assert g.loc[g.age == 100, "AgeGrp"].item() == "100+", (name, year)
    starts = np.array(AGE_STARTS)
    t["age_start"] = starts[np.searchsorted(starts, t.age, side="right") - 1]
    out = t.groupby(["Time", "age_start"], as_index=False).v.sum()
    out[name] = (out.v * 1000).round().astype("int64")
    return out.rename(columns={"Time": "year"})[["year", "age_start", name]]


def life_table(t: pd.DataFrame) -> pd.DataFrame:
    """Both sexes, printed bands 0 .. 80-84 as they are; 85-89 .. 100+ closed into 85+."""
    t = t[t.Sex == "Total"].copy()
    for c in ("AgeGrpStart", "AgeGrpSpan"):
        t[c] = t[c].astype(int)
    for c in ("mx", "lx", "dx", "Lx", "Tx", "ex"):
        t[c] = t[c].astype(float)
    rows = []
    printed = [0, 1, *range(5, 105, 5)]
    for year, g in t.groupby("Time"):
        g = g.sort_values("AgeGrpStart")
        assert list(g.AgeGrpStart) == printed, (year, list(g.AgeGrp))
        assert g.AgeGrp.iloc[-1] == "100+" and g.AgeGrpSpan.iloc[-1] == -1, year
        # the printed mx is the table's own d/L in every band (to its rounding)
        assert np.allclose(g.mx, g.dx / g.Lx, rtol=2e-3), year
        closed = g[g.AgeGrpStart < OPEN]
        top = g[g.AgeGrpStart >= OPEN]
        l85 = top.lx.iloc[0]
        assert abs(top.dx.sum() - l85) <= 0.01 * len(top), (year, top.dx.sum(), l85)
        assert abs(top.Lx.sum() - top.Tx.iloc[0]) <= 0.01 * len(top), year
        for _, r in closed.iterrows():
            rows.append(dict(year=year, age_start=r.AgeGrpStart, mx=r.mx, lx=r.lx, Lx=r.Lx))
        rows.append(dict(year=year, age_start=OPEN, mx=top.dx.sum() / top.Lx.sum(),
                         lx=l85, Lx=top.Lx.sum()))
    out = pd.DataFrame(rows)
    assert (out.groupby("year").age_start.apply(tuple) == AGE_STARTS).all()
    return out, t[t.AgeGrpStart == 0].set_index("Time").ex


def main() -> None:
    folder = workdir(sys.argv, "unwpp")
    ind = read(folder, "ind").set_index("Time")
    for c in ("TPopulation1July", "TPopulation1Jan", "Deaths", "CDR", "LEx"):
        ind[c] = ind[c].astype(float)
    assert list(ind.index) == list(YEARS)

    pop = to_bands(read(folder, "pop"), "PopTotal", "population")
    deaths = to_bands(read(folder, "deaths"), "DeathTotal", "deaths")
    lt, lt_e0 = life_table(read(folder, "life"))

    pop_total = pop.groupby("year").population.sum()
    death_total = deaths.groupby("year").deaths.sum()
    for year in YEARS:
        # the single-age file is the 1 July population, not 1 January
        july, jan = ind.TPopulation1July[year] * 1000, ind.TPopulation1Jan[year] * 1000
        assert abs(pop_total[year] - july) <= 10, (year, pop_total[year], july)
        assert abs(pop_total[year] - jan) > 1e6, year
        assert abs(death_total[year] - ind.Deaths[year] * 1000) <= 10, \
            (year, death_total[year], ind.Deaths[year])
        assert abs(lt_e0[year] - ind.LEx[year]) <= 0.001, year

    print("\nyear  e0 WPP  e0 from mx  diff")
    for year in YEARS:
        mx = lt[lt.year == year].sort_values("age_start").mx.to_numpy()
        ours = e0(mx)
        diff = ours - lt_e0[year]
        print(f"{year}  {lt_e0[year]:6.2f}  {ours:10.2f}  {diff:+.2f}")
        if year in E0_CHECK_YEARS:
            assert abs(diff) <= E0_TOLERANCE, (year, ours, lt_e0[year])

    srs = pd.read_csv(DATA / "srs_crude_death_rate.csv")
    srs = srs[srs.state == "India"].set_index("year").cdr_per_1000
    print("\nCrude death rate per 1,000, India: WPP deaths / WPP 1 July population")
    print("year  WPP  WPP CDR column  SRS  WPP/SRS")
    for year in YEARS:
        cdr = 1000 * death_total[year] / pop_total[year]
        s = srs.get(year)
        tail = f"{s:4.1f}  {cdr / s:6.3f}" if s is not None else "   -       -"
        kind = "" if year <= LAST_ESTIMATE else " (projection)"
        print(f"{year}  {cdr:5.2f}  {ind.CDR[year]:6.3f}  {tail}{kind}")

    pop.to_csv(DATA / "unwpp_population_age.csv", index=False)
    deaths.to_csv(DATA / "unwpp_deaths_age.csv", index=False)
    lt.to_csv(DATA / "unwpp_lifetable.csv", index=False, float_format="%.10g")
    print(f"\nwrote unwpp_population_age.csv ({len(pop)} rows), unwpp_deaths_age.csv "
          f"({len(deaths)}), unwpp_lifetable.csv ({len(lt)}) to {DATA}")


if __name__ == "__main__":
    main()
