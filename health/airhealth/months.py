"""A twelve-month PM2.5 shape for every place: how dirty each month is, relative to the year.

A Shape is twelve numbers, January first, scaled so the day-weighted mean is exactly 1. A
percent cut in one month then weighs that month by how dirty it is in that place
(intervention.py, monthly_pct).

Source: data/monthly_cpcb.csv (monthly CPCB means per city; a city-month exists only with
>= 75% hourly coverage). Rules, in order:
  1. A city with a complete own profile: each month's mean over the years in the window that
     have it, normalised. Complete = all twelve months in at least one year. If the window
     (default 2023-2025) lacks a month, all CPCB years 2016-2025 are used; that is still the
     city's own data (borrowed=False) and the basis names the years.
  2. A city without one: the largest (population) city in its state with a complete profile,
     borrowed=True. None in the state: India's shape.
  3. A state or district: the population-weighted mean of the normalised shapes of the
     state's cities with complete profiles (not borrowed ones), borrowed=True. None: India's.
  4. India: the population-weighted mean over all cities with complete profiles.
cities.csv has no coordinates, so "nearest city" is "largest city in the same state".
"""
from dataclasses import dataclass
from functools import cache

import numpy as np
import pandas as pd

from . import paths
from .places import Place

MONTH_DAYS = np.array([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
ALL_YEARS = (2016, 2025)


@dataclass(frozen=True)
class Shape:
    values: np.ndarray        # twelve, Jan first, day-weighted mean exactly 1
    basis: str                # "Delhi, CPCB 2023-25" / "borrowed from Patna" / "Bihar: 3 monitored cities"
    borrowed: bool            # True whenever it is not the place's own monitors


@cache
def _table() -> pd.DataFrame:
    return pd.read_csv(paths.DATA / "monthly_cpcb.csv")


@cache
def _cities() -> pd.DataFrame:
    return pd.read_csv(paths.DATA / "cities.csv")


def _normalise(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, dtype=float)
    return v / (np.dot(MONTH_DAYS, v) / MONTH_DAYS.sum())


def _span(years: tuple[int, int]) -> str:
    return f"{years[0]}-{years[1] % 100:02d}"


def _own(city: str, years: tuple[int, int]) -> tuple[np.ndarray, str] | None:
    """A city's own normalised profile and the years it came from, or None if incomplete."""
    t = _table()
    t = t[t.city == city]
    for window in dict.fromkeys([years, ALL_YEARS]):        # the window, then everything
        w = t[t.year.between(*window)]
        means = w.groupby("month").pm25.mean()
        if set(means.index) >= set(range(1, 13)):
            return _normalise(means.reindex(range(1, 13)).to_numpy()), f"{city}, CPCB {_span(window)}"
    return None


def _profiles(years: tuple[int, int]) -> pd.DataFrame:
    """Cities.csv rows with a complete own profile, with `shape` and `basis` columns."""
    rows = []
    for r in _cities().itertuples():
        own = _own(r.city, years)
        if own:
            rows.append({"city": r.city, "state": r.state, "population": r.population,
                         "shape": own[0], "basis": own[1]})
    return pd.DataFrame(rows, columns=["city", "state", "population", "shape", "basis"])


def _weighted(rows: pd.DataFrame) -> np.ndarray:
    w = rows.population.to_numpy(dtype=float)
    return _normalise(np.average(np.stack(rows["shape"].to_list()), axis=0, weights=w))


def _india(prof: pd.DataFrame) -> Shape:
    return Shape(_weighted(prof), "borrowed from India", True)


def shape(place: Place, years: tuple[int, int] = (2023, 2025)) -> Shape:
    """The twelve-month shape for a country, state, district or city (see the module doc)."""
    prof = _profiles(years)
    if place.kind == "country":
        return Shape(_weighted(prof), f"India: {len(prof)} monitored cities", True)
    state = place.state
    in_state = prof[prof.state == state]
    if place.kind == "city":
        own = prof[prof.city == place.name]
        if len(own):
            r = own.iloc[0]
            return Shape(r["shape"], r.basis, False)
        if len(in_state):
            r = in_state.sort_values("population", ascending=False).iloc[0]
            return Shape(r["shape"], f"borrowed from {r.city}", True)
        return _india(prof)
    if len(in_state):
        n = len(in_state)
        return Shape(_weighted(in_state), f"{state}: {n} monitored {'city' if n == 1 else 'cities'}", True)
    return _india(prof)
