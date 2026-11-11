"""IHME (Global Burden of Disease) files: where they sit in data_local/, and what is read
from them. Nothing here is committed data: every number comes from the files at run time,
and every function raises Unavailable when its files are absent (IHME_DOWNLOADS.md says how
to get them). The files are read as IHME delivers them, under IHME's own names.

What is read:

* GBD 2023 exposure (EXPOSURE_2023): population-weighted annual-mean PM2.5 by location and
  year, 1990-2023, column `mean`. The tool's states map onto GBD's locations (STATE_LOCATION):
  GBD has one location for "Jammu & Kashmir and Ladakh" (4854), so both carry its value, and
  pools Andaman & Nicobar, Chandigarh, Dadra & Nagar Haveli, Daman & Diu, Lakshadweep and
  Puducherry as "Other Union Territories" (44538), so each carries the pooled value. This is
  how exposure_gbd2019.csv treats the same groups in Pandey et al. 2021. India itself is not
  read: it is the population-weighted mean of the states, like every other map.
* GBD 2023 deaths by cause, state and age, and population by state and age (DEATHS_2023,
  POPULATION_2023; GBD Results tool, years 2015, 2019, 2023, both sexes). A cause's death rate
  in one of the tool's age bands is GBD's deaths over GBD's population in the GBD age groups
  the band holds (AGE_BAND). GBD leaves out rows for ages where a cause is not estimated;
  those count as no deaths. For a year between two of GBD's, rates are interpolated linearly
  in the year; outside 2015-2023 the nearest of the three is used (rates_year says which).
* Risk curves: GBD 2023 (RR_2023) and GBD 2019 (RR_2019, TMREL_2019). See ihme_curves.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from pathlib import Path

import numpy as np
import pandas as pd

from . import paths
from .ages import AGE_STARTS


class Unavailable(Exception):
    """IHME files the step needs are not in health/data_local/."""


RAW = "ihme_raw"
EXPOSURE_2023 = (f"{RAW}/IHME_GBD_2023_AIR_POLLUTION_1990_2023_PM/"
                 "IHME_GBD_2023_AIR_POLLUTION_1990_2023_PM_Y20250930.CSV")
DEATHS_2023 = (f"{RAW}/part_b/gbd2023/IHME-GBD_2023_DATA-0b7890d0-1/"
               "IHME-GBD_2023_DATA-0b7890d0-1.csv")
POPULATION_2023 = (f"{RAW}/part_b/gbd2023/IHME-GBD_2023_DATA-bccbe428-1/"
                   "IHME-GBD_2023_DATA-bccbe428-1.csv")
DEATHS_FILES = (DEATHS_2023, POPULATION_2023)

_RR23 = f"{RAW}/IHME_GBD_2023_AIR_POLLUTION_1990_2021_RR_CURVES/IHME_GBD_2023_AIR_POLLUTION_"
# Two scales (see ihme_curves.py): "ratio" files start at 1, "log" files at 0.
RR_2023 = {
    "ihd": (_RR23 + "1990_2022_PM_RR_ISCHEMIC_HEART_DISEASE_MEAN_Y2025M11D18.CSV", "log"),
    "stroke": (_RR23 + "1990_2022_PM_RR_STROKE_MEAN_Y2025M11D18.CSV", "log"),
    "lri": (_RR23 + "1990_2022_PM_RR_LOWER_RESPIRATORY_INFECTIONS_MEAN_Y2025M11D18.CSV", "log"),
    "dementia": (_RR23 + "1990_2022_PM_RR_DEMENTIA_MEAN_Y2025M11D18.CSV", "log"),
    "copd": (_RR23 + "1990_2021_PM_RR_COPD_MEAN_Y2022M01D31.CSV", "ratio"),
    "lung_cancer": (_RR23 + "1990_2021_PM_RR_LUNG_CANCER_MEAN_Y2022M01D31.CSV", "ratio"),
    "t2dm": (_RR23 + "1990_2021_PM_RR_DIABETES_MEAN_Y2022M01D31.CSV", "ratio"),
}
_RR19 = f"{RAW}/IHME_GBD_2019_PM_RISK_SUMM/IHME_GBD_2019_PM_RISK_SUMM_"
CVD_AGES_2019 = tuple(range(25, 100, 5))    # one IHD and one stroke file per five-year age
RR_2019 = {
    "copd": _RR19 + "RESP_COPD_Y2021M01D06.CSV",
    "lri": _RR19 + "LRI_Y2021M01D06.CSV",
    "lung_cancer": _RR19 + "NEO_LUNG_Y2021M01D06.CSV",
    "t2dm": _RR19 + "T2_DM_Y2021M01D06.CSV",
    **{f"ihd_{a}": _RR19 + f"CVD_IHD_{a}_Y2021M01D06.CSV" for a in CVD_AGES_2019},
    **{f"stroke_{a}": _RR19 + f"CVD_STROKE_{a}_Y2021M01D06.CSV" for a in CVD_AGES_2019},
}
TMREL_2019 = f"{RAW}/IHME_GBD_2019_PM_RISK_TMREL_DRAWS_Y2021M01D06.csv"

# GBD 2023 cause ids, as in the Part B query (IHME_DOWNLOADS.md).
CAUSES = {"lri": 322, "lung_cancer": 426, "ihd": 493, "stroke": 494, "copd": 509,
          "dementia": 543, "t2dm": 976}
CAUSE_LABELS = {"ihd": "ischaemic heart disease", "stroke": "stroke", "copd": "COPD",
                "lung_cancer": "lung cancer", "lri": "lower respiratory infection",
                "t2dm": "type 2 diabetes", "dementia": "dementia"}
YEARS = (2015, 2019, 2023)

# GBD age_id -> the tool's band (its first age). "<5 years" (1) and "All ages" (22) are sums
# of these and are not read.
AGE_BAND = {2: 0, 3: 0, 388: 0, 389: 0, 238: 1, 34: 1, 6: 5, 7: 10, 8: 15, 9: 20, 10: 25,
            11: 30, 12: 35, 13: 40, 14: 45, 15: 50, 16: 55, 17: 60, 18: 65, 19: 70, 20: 75,
            30: 80, 31: 85, 32: 85, 235: 85}
# The three GBD groups inside the tool's open band, 85+: age_id -> first age.
OLDEST = {31: 85, 32: 90, 235: 95}

# GBD 2023 location ids (Part B query results; IHME_DOWNLOADS.md) for the tool's states.
OTHER_UTS = 44538
JK_LADAKH = 4854
STATE_LOCATION = {
    "India": 163, "Andhra Pradesh": 4841, "Arunachal Pradesh": 4842, "Assam": 4843,
    "Bihar": 4844, "Chhattisgarh": 4846, "Delhi": 4849, "Goa": 4850, "Gujarat": 4851,
    "Haryana": 4852, "Himachal Pradesh": 4853, "Jammu & Kashmir": JK_LADAKH,
    "Ladakh": JK_LADAKH, "Jharkhand": 4855, "Karnataka": 4856, "Kerala": 4857,
    "Madhya Pradesh": 4859, "Maharashtra": 4860, "Manipur": 4861, "Meghalaya": 4862,
    "Mizoram": 4863, "Nagaland": 4864, "Odisha": 4865, "Punjab": 4867, "Rajasthan": 4868,
    "Sikkim": 4869, "Tamil Nadu": 4870, "Telangana": 4871, "Tripura": 4872,
    "Uttar Pradesh": 4873, "Uttarakhand": 4874, "West Bengal": 4875,
    "Andaman & Nicobar Islands": OTHER_UTS, "Chandigarh": OTHER_UTS,
    "Dadra & Nagar Haveli": OTHER_UTS, "Daman & Diu": OTHER_UTS, "Lakshadweep": OTHER_UTS,
    "Puducherry": OTHER_UTS,
}
POOLED = {JK_LADAKH: "Jammu & Kashmir and Ladakh", OTHER_UTS: "Other Union Territories"}


def path(rel: str) -> Path:
    return paths.LOCAL / rel


def missing(files) -> list[str]:
    return [f for f in files if not path(f).exists()]


def require(files, what: str) -> None:
    gone = missing(files)
    if gone:
        shown = ", ".join(gone[:3]) + (f" and {len(gone) - 3} more" if len(gone) > 3 else "")
        raise Unavailable(f"{what} needs IHME files not found in {paths.LOCAL}: {shown}. "
                          "See health/IHME_DOWNLOADS.md for how to download them.")


# --- exposure -------------------------------------------------------------------------------

@cache
def _exposure(file: str) -> pd.DataFrame:
    t = pd.read_csv(file, usecols=["year_id", "location_id", "mean"])
    rows = []
    for state, loc in STATE_LOCATION.items():
        if state == "India":
            continue
        g = t[t.location_id == loc]
        rows.append(pd.DataFrame({"state": state, "year": g.year_id.to_numpy(int),
                                  "pm25": g["mean"].to_numpy(float), "location_id": loc}))
    out = pd.concat(rows, ignore_index=True).sort_values(["state", "year"])
    return out.reset_index(drop=True)


def exposure_table() -> pd.DataFrame:
    """GBD 2023 PM2.5 by the tool's state and year: columns state, year, pm25, location_id."""
    require([EXPOSURE_2023], "the gbd2023 map")
    return _exposure(str(path(EXPOSURE_2023)))


def india_exposure(year: int) -> float:
    """GBD's own population-weighted mean for India (location 163), for checks."""
    require([EXPOSURE_2023], "the gbd2023 map")
    t = pd.read_csv(path(EXPOSURE_2023), usecols=["year_id", "location_id", "mean"])
    return float(t[(t.location_id == 163) & (t.year_id == year)]["mean"].item())


# --- deaths by cause ------------------------------------------------------------------------

@dataclass(frozen=True)
class _Tables:
    deaths: pd.DataFrame       # location_id, year, cause, band, deaths (Number)
    population: pd.DataFrame   # location_id, year, band, population
    oldest: pd.DataFrame       # location_id, year, cause, age (85/90/95), deaths


@cache
def _tables(deaths_file: str, population_file: str) -> _Tables:
    d = pd.read_csv(deaths_file)
    d = d[(d.metric_name == "Number") & d.age_id.isin(list(AGE_BAND))
          & d.cause_id.isin(list(CAUSES.values())) & (d.sex_name == "Both")]
    key = {v: k for k, v in CAUSES.items()}
    d = d.assign(cause=d.cause_id.map(key), band=d.age_id.map(AGE_BAND))
    oldest = d[d.age_id.isin(list(OLDEST))].assign(age=lambda x: x.age_id.map(OLDEST))
    p = pd.read_csv(population_file)
    p = p[p.age_id.isin(list(AGE_BAND)) & (p.sex_name == "Both")]
    p = p.assign(band=p.age_id.map(AGE_BAND))
    return _Tables(
        deaths=d.groupby(["location_id", "year", "cause", "band"], as_index=False).val.sum()
        .rename(columns={"val": "deaths"}),
        population=p.groupby(["location_id", "year", "band"], as_index=False).val.sum()
        .rename(columns={"val": "population"}),
        oldest=oldest.groupby(["location_id", "year", "cause", "age"], as_index=False).val.sum()
        .rename(columns={"val": "deaths"}))


def tables() -> _Tables:
    require(DEATHS_FILES, "GBD deaths by cause")
    return _tables(str(path(DEATHS_2023)), str(path(POPULATION_2023)))


@cache
def _rates_at(deaths_file: str, population_file: str, loc: int, year: int) -> dict[str, np.ndarray]:
    t = _tables(deaths_file, population_file)
    pop = t.population[(t.population.location_id == loc) & (t.population.year == year)]
    pop = pop.set_index("band").population.reindex(AGE_STARTS)
    if pop.isna().any():
        raise KeyError(f"GBD population for location {loc}, {year} is incomplete")
    d = t.deaths[(t.deaths.location_id == loc) & (t.deaths.year == year)]
    out = {}
    for cause in CAUSES:
        n = d[d.cause == cause].set_index("band").deaths.reindex(AGE_STARTS).fillna(0.0)
        out[cause] = (n / pop).to_numpy(float)
    return out


def rates_year(year: int) -> tuple[int, int, float]:
    """The GBD years a year's rates come from: (lower, upper, weight on upper)."""
    if year <= YEARS[0]:
        return YEARS[0], YEARS[0], 0.0
    if year >= YEARS[-1]:
        return YEARS[-1], YEARS[-1], 0.0
    lo = max(y for y in YEARS if y <= year)
    hi = min(y for y in YEARS if y >= year)
    return lo, hi, (0.0 if hi == lo else (year - lo) / (hi - lo))


def rates_text(year: int) -> str:
    lo, hi, w = rates_year(year)
    if lo == hi == year:
        return str(year)
    if lo == hi:
        return f"{lo} (the nearest year in the files to {year})"
    return f"{year}, interpolated between {lo} and {hi}"


def cause_rates(state: str, year: int) -> dict[str, np.ndarray]:
    """Deaths per person a year by cause, in each of the tool's age bands, for a state (GBD's
    location for it: pooled for Ladakh and the small union territories)."""
    require(DEATHS_FILES, "GBD deaths by cause")
    loc = STATE_LOCATION[state]
    lo, hi, w = rates_year(int(year))
    files = (str(path(DEATHS_2023)), str(path(POPULATION_2023)))
    a = _rates_at(*files, loc, lo)
    if hi == lo:
        return a
    b = _rates_at(*files, loc, hi)
    return {c: (1 - w) * a[c] + w * b[c] for c in CAUSES}


def oldest_shares(cause: str, year: int = 2023) -> dict[int, float]:
    """India's deaths from a cause at 85-89, 90-94 and 95+, as shares of its deaths at 85+."""
    t = tables().oldest
    g = t[(t.location_id == 163) & (t.year == year) & (t.cause == cause)]
    total = g.deaths.sum()
    return {int(a): float(n / total) for a, n in zip(g.age, g.deaths)} if total else {}
