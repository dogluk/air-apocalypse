"""Exposure maps: annual-mean PM2.5 (µg/m³) and population for a place, by map.

Maps (sources and methods in data/sources.toml):
  aqli        AQLI Annual Update 2025, districts (GADM), 1998-2023; satellite PM2.5 with
              dust and sea salt removed; district shares from AQLI's (LandScan) population.
  acag_total  ACAG V6.GL.02.04 total PM2.5, 2023, averaged to districts (geoBoundaries)
              with WorldPop 2023 weights; district shares from WorldPop 2023.
  gbd2019     GBD 2019 state population-weighted means (Pandey et al. 2021), 2019; one
              value per state, population from the official projections (baseline).
  gbd2023     GBD 2023 state population-weighted means, 1990-2023 (IHME, local tier: read
              from data_local/ at run time, never committed; ihme.py). Ladakh carries GBD's
              Jammu & Kashmir and Ladakh, and the six small union territories GBD pools carry
              the pooled value. Population as for gbd2019.
  cpcb        Ground monitors, mean of hourly cross-station medians, for the cities in
              data/cities.csv that have a monitor; population is the Census 2011 figure of the
              city's agglomeration(s), the same in every year.

Population on the district maps: each map carries one population (AQLI's and WorldPop's are
both 2023 figures). cells() scales each state's districts so the state's total is the
official projection (baseline.load) for the year asked for, keeping the map's split between
districts; a state then has the same population here as in baseline.load, and a 2014 run
uses 2014's people. With no year given, the year is the map's latest (2023 for both), scaled
the same way. A year the projections do not cover (AQLI 1998-2010) keeps the map's own
population. attrs["population_year"] names the year the population is for.

cells() gives one row per district for the country or a state, one row for a district or
city. A city on a satellite map is the population-weighted mean of the district(s) holding
its core (data/cities.csv), carried with the city's own population (Census 2011, as on cpcb).
The year defaults to the map's latest; the frame's attrs record map, year and
population_year.
"""
from functools import cache

import numpy as np
import pandas as pd

from . import baseline, ihme, paths
from .inputs import Sources
from .places import Place

MAPS: tuple[str, ...] = ("aqli", "acag_total", "gbd2019", "gbd2023", "cpcb")
LABELS = {
    "aqli": "AQLI 2025 release, districts, satellite PM2.5 with dust and sea salt removed",
    "acag_total": "ACAG V6.GL.02.04 total PM2.5, districts, WorldPop-weighted",
    "gbd2019": "GBD 2019 state population-weighted means (Pandey et al. 2021)",
    "gbd2023": "GBD 2023 state population-weighted means (IHME, local)",
    "cpcb": "CPCB ground monitors, city annual means",
}
COLUMNS = ["state", "unit", "pm25", "population"]
DISTRICT_MAPS = {"aqli": "aqli_units", "acag_total": "acag_units"}
STATE_MAPS = ("gbd2019", "gbd2023")      # one value per state
LOCAL_MAPS = {"gbd2023": "IHME, GBD 2023 Air Pollution Exposure Estimates 1990-2023, population-"
                         "weighted means by location (read from data_local/), "
                         "https://ghdx.healthdata.org/node/594794"}
MAP_POPULATION_YEAR = {"aqli": 2023, "acag_total": 2023}  # see data/sources.toml


def _table(map_name: str) -> pd.DataFrame:
    if map_name == "gbd2023":
        return ihme.exposure_table()          # raises ihme.Unavailable without the file
    return _committed(map_name)


@cache
def _committed(map_name: str) -> pd.DataFrame:
    return pd.read_csv(paths.DATA / f"exposure_{map_name}.csv")


def available(map_name: str) -> bool:
    """Whether the map's data is here (the local-tier maps need IHME files)."""
    try:
        _table(map_name)
        return True
    except ihme.Unavailable:
        return False


@cache
def _districts(map_name: str, year: int, population: str = "projection") -> tuple[pd.DataFrame, int]:
    """A district map's rows for one year, each state scaled to its projected population."""
    t = _table(map_name)
    t = t[t.year == year]
    if year not in baseline.projection_years():
        return t, MAP_POPULATION_YEAR[map_name]
    src = Sources(population=population)
    projected = {s: baseline.load(s, year, sources=src).population.sum() for s in t.state.unique()}
    return t.assign(population=t.population * t.state.map(projected)
                    / t.groupby("state").population.transform("sum")), year


@cache
def _cities() -> pd.DataFrame:
    return pd.read_csv(paths.DATA / "cities.csv").set_index("city")


def _year(t: pd.DataFrame, map_name: str, year: int | None) -> int:
    years = sorted(t.year.unique())
    if year is None:
        return int(years[-1])
    if year not in years:
        raise KeyError(f"{map_name} has no {year}; it covers {years[0]}-{years[-1]}"
                       if len(years) > 1 else f"{map_name} has no {year}; only {years[0]}")
    return int(year)


def _city(place: Place) -> pd.Series:
    try:
        return _cities().loc[place.name]
    except KeyError:
        raise KeyError(f"no exposure data for city {place.name!r}") from None


def cells(place: Place, map_name: str, year: int | None = None,
          population: str = "projection") -> pd.DataFrame:
    """The exposure units of the place on the map, with their PM2.5 and population (scaled to
    the population source asked for: inputs.REGISTRY["population"])."""
    if map_name not in MAPS:
        raise ValueError(f"unknown exposure map {map_name!r}; choose from {', '.join(MAPS)}")
    t = _table(map_name)
    y = _year(t, map_name, year)
    t = t[t.year == y]
    population_year = y

    if map_name == "cpcb":
        population_year = 2011
        if place.kind != "city":
            raise ValueError(f"cpcb covers only the cities in data/cities.csv "
                             f"({', '.join(_cities().index)}), not a {place.kind}")
        row = t[t.city == place.name]
        if row.empty:
            raise KeyError(f"cpcb has no {y} value for {place.name!r} (missing or under 75% of hours)")
        out = pd.DataFrame({"state": [place.state], "unit": [place.name],
                            "pm25": [row.pm25.item()], "population": [_city(place).population]})

    elif map_name in STATE_MAPS:
        if place.kind in ("district", "city"):
            raise ValueError(f"{map_name} is a state-level map; it has no {place.kind} values")
        t = t[t.state != "India"]
        if place.kind == "state":
            t = t[t.state == place.name]
        out = t.assign(unit=t.state,
                       population=[baseline.load(s, y, sources=Sources(population=population))
                                   .population.sum() for s in t.state])

    else:
        t, population_year = _districts(map_name, y, population)
        if place.kind == "country":
            out = t
        elif place.kind == "state":
            out = t[t.state == place.name]
        elif place.kind == "district":
            out = t[(t.state == place.state) & (t.unit == place.name)]
            if out.empty:
                raise KeyError(f"{map_name} has no district {place.name!r} in {place.state}; "
                               "the maps use different district boundaries")
        else:
            c = _city(place)
            d = t[(t.state == place.state) & t.unit.isin(c[DISTRICT_MAPS[map_name]].split(";"))]
            out = pd.DataFrame({"state": [place.state], "unit": [place.name],
                                "pm25": [np.average(d.pm25, weights=d.population)],
                                "population": [c.population]})
            population_year = 2011

    out = out[COLUMNS].reset_index(drop=True)
    if out.empty:
        raise KeyError(f"{map_name} has no rows for {place.name!r}")
    out.attrs.update(map=map_name, year=y, population_year=population_year)
    return out


def mean(place: Place, map_name: str, year: int | None = None) -> float:
    """Population-weighted mean PM2.5 of the place on the map."""
    c = cells(place, map_name, year)
    return float(np.average(c.pm25, weights=c.population))
