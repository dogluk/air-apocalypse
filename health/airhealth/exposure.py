"""Exposure maps: annual-mean PM2.5 (µg/m³) and population for a place, by map.

Maps (sources and methods in data/sources.toml):
  aqli        AQLI Annual Update 2025, districts (GADM), 1998-2023; satellite PM2.5 with
              dust and sea salt removed; AQLI's population.
  acag_total  ACAG V6.GL.02.04 total PM2.5, 2023, averaged to districts (geoBoundaries)
              with WorldPop 2023 weights.
  gbd2019     GBD 2019 state population-weighted means (Pandey et al. 2021), 2019; one
              value per state, population from the official projections (baseline).
  cpcb        Ground monitors, mean of hourly cross-station medians, for the cities in
              diwali/config.py only; population is the Census 2011 urban agglomeration.

cells() gives one row per district for the country or a state, one row for a district or
city. A city on a satellite map is the population-weighted mean of the district(s) holding
its core (data/cities.csv), carried with the city's own population. The year defaults to
the map's latest; the frame's attrs record map and year.
"""
from functools import cache

import numpy as np
import pandas as pd

from . import baseline, paths
from .places import Place

MAPS: tuple[str, ...] = ("aqli", "acag_total", "gbd2019", "cpcb")
LABELS = {
    "aqli": "AQLI 2025 release, districts, satellite PM2.5 with dust and sea salt removed",
    "acag_total": "ACAG V6.GL.02.04 total PM2.5, districts, WorldPop-weighted",
    "gbd2019": "GBD 2019 state population-weighted means (Pandey et al. 2021)",
    "cpcb": "CPCB ground monitors, city annual means",
}
COLUMNS = ["state", "unit", "pm25", "population"]
DISTRICT_MAPS = {"aqli": "aqli_units", "acag_total": "acag_units"}


@cache
def _table(map_name: str) -> pd.DataFrame:
    return pd.read_csv(paths.DATA / f"exposure_{map_name}.csv")


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


def cells(place: Place, map_name: str, year: int | None = None) -> pd.DataFrame:
    if map_name not in MAPS:
        raise ValueError(f"unknown exposure map {map_name!r}; choose from {', '.join(MAPS)}")
    t = _table(map_name)
    y = _year(t, map_name, year)
    t = t[t.year == y]

    if map_name == "cpcb":
        if place.kind != "city":
            raise ValueError(f"cpcb covers only the cities in diwali/config.py "
                             f"({', '.join(_cities().index)}), not a {place.kind}")
        row = t[t.city == place.name]
        if row.empty:
            raise KeyError(f"cpcb has no {y} value for {place.name!r} (missing or under 75% of hours)")
        out = pd.DataFrame({"state": [place.state], "unit": [place.name],
                            "pm25": [row.pm25.item()], "population": [_city(place).population]})

    elif map_name == "gbd2019":
        if place.kind in ("district", "city"):
            raise ValueError(f"gbd2019 is a state-level map; it has no {place.kind} values")
        t = t[t.state != "India"]
        if place.kind == "state":
            t = t[t.state == place.name]
        out = t.assign(unit=t.state,
                       population=[baseline.load(s, y).population.sum() for s in t.state])

    else:
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

    out = out[COLUMNS].reset_index(drop=True)
    if out.empty:
        raise KeyError(f"{map_name} has no rows for {place.name!r}")
    out.attrs.update(map=map_name, year=y)
    return out


def mean(place: Place, map_name: str, year: int | None = None) -> float:
    """Population-weighted mean PM2.5 of the place on the map."""
    c = cells(place, map_name, year)
    return float(np.average(c.pm25, weights=c.population))
