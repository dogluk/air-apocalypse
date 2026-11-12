"""A twelve-month PM2.5 shape for every place: how dirty each month is, relative to the year.

A Shape is twelve numbers, January first, scaled so the day-weighted mean is exactly 1. A
percent cut in one month then weighs that month by how dirty it is in that place
(intervention.py, monthly_pct).

Sources: data/monthly_cpcb.csv (monthly CPCB means per city; a city-month exists only with
>= 75% hourly coverage) and data/monthly_cpcb_state.csv (the same per state, from all CPCB
monitors in it). A profile is complete when it has all twelve months in the data. Each
profile uses the window (default 2023-2025); if the window lacks a month, all CPCB years
2016-2025 are used; that is still the place's own data and the basis names the years. Rules,
in order:
  1. A city with a complete own profile: each month's mean over the years in the window that
     have it, normalised (borrowed=False).
  2. A city without one: the largest (population) city in its state with a complete profile,
     borrowed=True. None in the state: the state-wide profile of the state's monitors (all
     CPCB monitors in it, whatever the city), borrowed=True. Still none: India's shape.
  3. A state or district: the population-weighted mean of the normalised shapes of the
     state's cities with complete profiles (not borrowed ones), borrowed=True. None: the
     state-wide profile, borrowed=True; still none: India's.
  4. India: the population-weighted mean over all cities with complete profiles.
cities.csv has no coordinates, so "nearest city" is "largest city in the same state".
Every basis names its source and the CPCB years it used, so a report can print it as is.
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
    basis: str                # "Delhi, CPCB 2023-25" / "borrowed from Patna, CPCB 2023-25" / ...
    borrowed: bool            # True whenever it is not the place's own monitors


@cache
def _table() -> pd.DataFrame:
    return pd.read_csv(paths.DATA / "monthly_cpcb.csv")


@cache
def _state_table() -> pd.DataFrame:
    return pd.read_csv(paths.DATA / "monthly_cpcb_state.csv")


@cache
def _cities() -> pd.DataFrame:
    return pd.read_csv(paths.DATA / "cities.csv")


def clear_cache() -> None:
    """Forget the computed profiles (tests that replace the tables call it)."""
    _profiles.cache_clear()
    _state_profiles.cache_clear()


def _normalise(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, dtype=float)
    return v / (np.dot(MONTH_DAYS, v) / MONTH_DAYS.sum())


def _span(years: tuple[int, int]) -> str:
    return f"{years[0]}-{years[1] % 100:02d}"


def _profile(t: pd.DataFrame, years: tuple[int, int]) -> tuple[np.ndarray, tuple[int, int]] | None:
    """The normalised profile of one place's monthly rows and the window it came from, or None."""
    for window in dict.fromkeys([years, ALL_YEARS]):        # the window, then everything
        w = t[t.year.between(*window)]
        means = w.groupby("month").pm25.mean()
        if set(means.index) >= set(range(1, 13)):
            return _normalise(means.reindex(range(1, 13)).to_numpy()), window
    return None


@cache
def _profiles(years: tuple[int, int]) -> pd.DataFrame:
    """Cities.csv rows with a complete own profile, with `shape` and `span` (the years) columns."""
    t = _table()
    rows = []
    for r in _cities().itertuples():
        own = _profile(t[t.city == r.city], years)
        if own:
            rows.append({"city": r.city, "state": r.state, "population": r.population,
                         "shape": own[0], "span": _span(own[1])})
    return pd.DataFrame(rows, columns=["city", "state", "population", "shape", "span"])


@cache
def _state_profiles(years: tuple[int, int]) -> dict[str, Shape]:
    """State-wide profiles (all CPCB monitors in the state) for the states that have a complete one."""
    t = _state_table()
    out = {}
    for state, rows in t.groupby("state"):
        own = _profile(rows, years)
        if own:
            n = int(rows[rows.year.between(*own[1])].stations.max())
            monitors = f"all {n} CPCB monitors" if n > 1 else "its one CPCB monitor"
            out[state] = Shape(own[0], f"{state}: {monitors}, {_span(own[1])}", True)
    return out


def _weighted(rows: pd.DataFrame) -> np.ndarray:
    w = rows.population.to_numpy(dtype=float)
    return _normalise(np.average(np.stack(rows["shape"].to_list()), axis=0, weights=w))


def _spans(rows: pd.DataFrame) -> str:
    return " and ".join(dict.fromkeys(rows.span))


def _india(prof: pd.DataFrame) -> Shape:
    return Shape(_weighted(prof), f"borrowed from India: {len(prof)} monitored cities, CPCB {_spans(prof)}", True)


def shape(place: Place, years: tuple[int, int] = (2023, 2025)) -> Shape:
    """The twelve-month shape for a country, state, district or city (see the module doc)."""
    prof = _profiles(years)
    if place.kind == "country":
        return Shape(_weighted(prof), f"India: {len(prof)} monitored cities, CPCB {_spans(prof)}", True)
    state = place.state
    in_state = prof[prof.state == state]
    if place.kind == "city":
        own = prof[prof.city == place.name]
        if len(own):
            r = own.iloc[0]
            return Shape(r["shape"], f"{r.city}, CPCB {r.span}", False)
        if len(in_state):
            r = in_state.sort_values("population", ascending=False).iloc[0]
            return Shape(r["shape"], f"borrowed from {r.city}, CPCB {r.span}", True)
    elif len(in_state):
        n = len(in_state)
        return Shape(_weighted(in_state),
                     f"{state}: {n} monitored {'city' if n == 1 else 'cities'}, CPCB {_spans(in_state)}", True)
    return _state_profiles(years).get(state) or _india(prof)
