"""Steady-state health impact of a change in annual-mean PM2.5 at a place.

For each exposure unit (a district, a state on the gbd2019 map, or a city) and age band:
the unit's population is split by age in its state's proportions; deaths = population ×
the state's all-cause rate mx; deaths in scope = deaths × share_ncd_lri for an NCD+LRI
curve, all deaths otherwise; averted = in-scope deaths × (1 − ratio), ratio = the curve's
rr(after) / rr(before) for that band (1 below the curve's min_age). Units add up to the place.

Life expectancy: the state's life table is rebuilt with each band's rate multiplied by the
population-weighted mean over the state's units of 1 − scope × (1 − ratio). Life-years
averted are deaths averted in a band × remaining life expectancy at the start of that band,
from the state's baseline table. A place spanning several states (the country) is computed
state by state: deaths and life-years add, life expectancy is population-weighted.

AQLI gives life expectancy, not relative risk: each unit's e0 moves by the curve's
delta_e0; the deaths are derived by solving for the one multiplier on the state's death
rates, from the curve's min_age (0, as AQLI's estimate is all-age), that gives that change,
and the result is marked derived.

Results are steady state: the change in deaths per year and in period life expectancy once
the new air has been breathed long enough for the full effect, with today's age structure.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import baseline, exposure, lifetable
from .ages import AGE_STARTS
from .curves import Curve
from .places import Place

STARTS = np.array(AGE_STARTS)


@dataclass(frozen=True)
class Change:
    """A change in annual-mean PM2.5 (µg/m³), given exactly one way:
    delta (signed, negative = cleaner), pct (signed percent of each unit's level), or to
    (a target; units already at or below it are left alone). Never goes below 0."""
    delta: float | None = None
    pct: float | None = None
    to: float | None = None

    def __post_init__(self):
        given = [k for k in ("delta", "pct", "to") if getattr(self, k) is not None]
        if len(given) != 1:
            raise ValueError(f"give exactly one of delta, pct, to (got {given or 'none'})")
        if self.to is not None and self.to < 0:
            raise ValueError(f"target concentration must be at least 0, got {self.to}")

    def apply(self, pm25: np.ndarray) -> np.ndarray:
        pm = np.asarray(pm25, dtype=float)
        if self.delta is not None:
            out = pm + self.delta
        elif self.pct is not None:
            out = pm * (1 + self.pct / 100)
        else:
            out = np.minimum(pm, self.to)
        return np.maximum(out, 0.0)


@dataclass(frozen=True)
class Impact:
    place: Place
    curve: Curve
    map_name: str
    year: int                 # the exposure map's year (also the population year)
    pm25_before: float        # population-weighted, µg/m³
    pm25_after: float
    population: float
    deaths_baseline: float    # all-cause deaths per year
    deaths_averted: float     # per year at steady state; negative if the air gets worse
    e0_before: float
    e0_after: float
    yll_averted: float        # deaths averted by age × remaining life expectancy at that age
    derived: bool             # True when the deaths are derived from a life-expectancy curve
    fallback_states: list[str]


@dataclass(frozen=True)
class _StateResult:
    population: float
    deaths_baseline: float
    deaths_averted: float
    yll_averted: float
    e0_before: float
    e0_after: float


def _state(b: baseline.Baseline, curve: Curve, before: np.ndarray, after: np.ndarray,
           pop: np.ndarray) -> _StateResult:
    """One state's units (before, after, pop are per unit) against its baseline."""
    deaths = np.outer(pop, b.population / b.population.sum()) * b.mx    # unit × band
    table = lifetable.life_table(b.mx)
    if curve.kind == "life_expectancy":
        gains = np.array([curve.delta_e0(c0, c1) for c0, c1 in zip(before, after)])
        solved = {g: lifetable.solve_adult_factor(b.mx, g, from_age=curve.min_age)
                  for g in np.unique(gains)}
        per_unit = np.array([solved[g] for g in gains])[:, None]
        factor = np.where(STARTS >= curve.min_age, per_unit, 1.0)      # on all-cause rates
        e0_after = table.ex[0] + np.average(gains, weights=pop)
    else:
        scope = b.share_ncd_lri if curve.death_scope == "ncd_lri" else np.ones(len(STARTS))
        ratio = np.column_stack([np.broadcast_to(curve.ratio(before, after, int(age)),
                                                 before.shape) for age in STARTS])
        factor = 1 - scope * (1 - ratio)                                # on all-cause rates
        e0_after = lifetable.e0(b.mx * np.average(factor, axis=0, weights=pop))
    averted = (deaths * (1 - factor)).sum(axis=0)                       # by band
    return _StateResult(
        population=pop.sum(), deaths_baseline=deaths.sum(), deaths_averted=averted.sum(),
        yll_averted=(averted * table.ex).sum(), e0_before=table.ex[0], e0_after=e0_after)


def steady_state(place: Place, curve: Curve, map_name: str, change: Change,
                 year: int | None = None, pm25_override: float | None = None) -> Impact:
    """Deaths averted per year and change in life expectancy when `change` is applied to
    every exposure unit of `place` on `map_name`. pm25_override, if given, sets every unit's
    starting concentration (population weights unchanged), e.g. Delhi from 100 to 80."""
    cells: pd.DataFrame = exposure.cells(place, map_name, year)
    year = int(cells.attrs["year"])
    before = cells.pm25.to_numpy(float)
    if pm25_override is not None:
        before = np.full_like(before, float(pm25_override))
    after = change.apply(before)
    pop = cells.population.to_numpy(float)

    results, fallback = [], []
    for state, rows in cells.groupby("state", sort=True).indices.items():
        b = baseline.load(state, year)
        if b.fallback:
            fallback.append(state)
        results.append(_state(b, curve, before[rows], after[rows], pop[rows]))

    weights = [r.population for r in results]
    return Impact(
        place=place, curve=curve, map_name=map_name, year=year,
        pm25_before=float(np.average(before, weights=pop)),
        pm25_after=float(np.average(after, weights=pop)),
        population=float(pop.sum()),
        deaths_baseline=float(sum(r.deaths_baseline for r in results)),
        deaths_averted=float(sum(r.deaths_averted for r in results)),
        e0_before=float(np.average([r.e0_before for r in results], weights=weights)),
        e0_after=float(np.average([r.e0_after for r in results], weights=weights)),
        yll_averted=float(sum(r.yll_averted for r in results)),
        derived=curve.kind == "life_expectancy",
        fallback_states=fallback)


def burden(place: Place, curve: Curve, map_name: str, counterfactual: float | None = None,
           year: int | None = None) -> Impact:
    """The impact of bringing every unit down to the counterfactual (default: the curve's
    floor), i.e. the deaths attributable to the air above it."""
    to = curve.floor if counterfactual is None else counterfactual
    return steady_state(place, curve, map_name, Change(to=to), year=year)
