"""Steady-state health impact of a change in annual-mean PM2.5 at a place.

For each exposure unit (a district, a state on the gbd2019 map, or a city) and age band:
the unit's population is split by age in its state's proportions; deaths = population ×
the state's all-cause rate mx × the state's death_factor (the reconciliation to the SRS
crude death rate, baseline.py; all ones with deaths="model"); deaths in scope = deaths × share_ncd_lri for an NCD+LRI
curve, all deaths otherwise; averted = in-scope deaths × (1 − ratio), ratio = the curve's
rr(after) / rr(before) for that band (1 below the curve's min_age). Units add up to the place.

Life expectancy: the state's life table is rebuilt with each band's rate multiplied by the
population-weighted mean over the state's units of 1 − scope × (1 − ratio); the life table
is never scaled by death_factor. Life-years averted are deaths averted in a band × remaining
life expectancy at the mean age of death in that band (lifetable.ex_at_death), from the
state's baseline table. A place spanning several states (the country) is computed
state by state: deaths and life-years add, life expectancy is population-weighted.

AQLI gives life expectancy, not relative risk: each unit's e0 moves by the curve's
delta_e0; the deaths are derived by solving for the one multiplier on the state's death
rates, from the curve's min_age (0, as AQLI's estimate is all-age), that gives that change,
and the result is marked derived.

A cause-specific curve (death_scope "causes": gbd2019, gbd2023, gemm_5cod; ihme_curves.py)
brings its own deaths: for each cause, the unit's people in the band × IHME's death rate for
the cause, state and age (not scaled by death_factor), times 1 − that cause's ratio. The life
table's rate in the band loses the averted rate, Σ_c rate_c × (1 − ratio_c), population-
weighted over the state's units.

Results are steady state: the change in deaths per year and in period life expectancy once
the new air has been breathed long enough for the full effect, with today's age structure.

steady_state() is the reference implementation, one change and one curve at a time.
steady_state_many() gives the same numbers for n draws at once (n changes, and a curve from
Curve.sample_many() or a fixed one), for the Monte Carlo in simulate.py. Once the factors on
death rates are known the arithmetic is linear in deaths by unit and age, so it runs as array
operations over draws. For AQLI, the multiplier on death rates that gives each life-expectancy
gain is solved exactly when there are at most AQLI_EXACT distinct gains, and otherwise on a
grid of AQLI_GRID gains spanning the draws, interpolating the log of the multiplier, which is
nearly linear in the gain (tests hold the two within 0.1% of steady_state()).
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import baseline, exposure, lifetable
from .ages import AGE_STARTS
from .curves import Curve
from .inputs import Sources
from .places import Place

STARTS = np.array(AGE_STARTS)
AQLI_EXACT = 64
AQLI_GRID = 33


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
    year: int                 # the exposure map's year (also the population year, but see below)
    pm25_before: float        # population-weighted, µg/m³
    pm25_after: float
    population: float
    deaths_baseline: float    # all-cause deaths per year, on the deaths basis asked for
    deaths_averted: float     # per year at steady state; negative if the air gets worse
    e0_before: float
    e0_after: float
    yll_averted: float        # deaths averted by age × remaining life expectancy at death
    derived: bool             # True when the deaths are derived from a life-expectancy curve
    fallback_states: list[str]
    deaths_model: float = 0.0   # all-cause deaths per year before reconciliation (population × mx)
    reconciliations: tuple[baseline.Reconciliation, ...] = ()
    rate_adjustments: tuple[baseline.RateAdjustment, ...] = ()   # one per state, early years only
    sources: Sources = Sources()
    un_scaling: baseline.UNScaling | None = None   # deaths="unwpp": India's figure, the same in every state   # one per state; empty for deaths="model"
    population_year: int = 0    # the year the population is for (2011 for a city: Census)
    curve_note: str = ""        # what a cause-specific curve's deaths are (ihme_curves)


def _curve_note(curve: Curve, year: int) -> str:
    return curve.deaths_note(year) if curve.death_scope == "causes" else ""


def _cause_lost(curve: Curve, b: baseline.Baseline, before, after) -> np.ndarray:
    """Death rate averted per person, unit × band (or draw × unit × band when after is
    (n, units)): Σ over the curve's causes of IHME's rate × (1 − ratio)."""
    rates = curve.cause_rates(b.state, b.year)
    shape = np.broadcast_shapes(np.shape(before), np.shape(after))
    lost = np.zeros((*shape, len(STARTS)))
    for risk in curve.risks:
        rate = rates[risk.cause]
        cache: dict = {}
        for k, age in enumerate(STARTS):
            if rate[k] == 0 or age < risk.min_age:
                continue
            key = risk.key(int(age))
            if key not in cache:
                cache[key] = 1 - np.broadcast_to(curve.cause_ratio(risk, before, after, int(age)), shape)
            lost[..., k] += rate[k] * cache[key]
    return lost


@dataclass(frozen=True)
class _StateResult:
    population: float
    deaths_model: float
    deaths_baseline: float
    deaths_averted: float
    yll_averted: float
    e0_before: float
    e0_after: float


def _state(b: baseline.Baseline, curve: Curve, before: np.ndarray, after: np.ndarray,
           pop: np.ndarray) -> _StateResult:
    """One state's units (before, after, pop are per unit) against its baseline."""
    model = np.outer(pop, b.population / b.population.sum()) * b.mx     # unit × band
    deaths = model * b.death_factor
    table = lifetable.life_table(b.mx)
    if curve.kind == "life_expectancy":
        gains = np.array([curve.delta_e0(c0, c1) for c0, c1 in zip(before, after)])
        solved = {g: lifetable.solve_adult_factor(b.mx, g, from_age=curve.min_age)
                  for g in np.unique(gains)}
        per_unit = np.array([solved[g] for g in gains])[:, None]
        factor = np.where(STARTS >= curve.min_age, per_unit, 1.0)      # on all-cause rates
        e0_after = table.ex[0] + np.average(gains, weights=pop)
    elif curve.death_scope == "causes":
        lost = _cause_lost(curve, b, before, after)                     # unit × band
        people = model / b.mx
        averted = (people * lost).sum(axis=0)
        e0_after = lifetable.e0(b.mx - np.average(lost, axis=0, weights=pop))
        return _StateResult(
            population=pop.sum(), deaths_model=model.sum(), deaths_baseline=deaths.sum(),
            deaths_averted=averted.sum(), yll_averted=(averted * lifetable.ex_at_death(b.mx)).sum(),
            e0_before=table.ex[0], e0_after=e0_after)
    else:
        scope = b.share_ncd_lri if curve.death_scope == "ncd_lri" else np.ones(len(STARTS))
        ratio = np.column_stack([np.broadcast_to(curve.ratio(before, after, int(age)),
                                                 before.shape) for age in STARTS])
        factor = 1 - scope * (1 - ratio)                                # on all-cause rates
        e0_after = lifetable.e0(b.mx * np.average(factor, axis=0, weights=pop))
    averted = (deaths * (1 - factor)).sum(axis=0)                       # by band
    return _StateResult(
        population=pop.sum(), deaths_model=model.sum(), deaths_baseline=deaths.sum(),
        deaths_averted=averted.sum(), yll_averted=(averted * lifetable.ex_at_death(b.mx)).sum(),
        e0_before=table.ex[0], e0_after=e0_after)


def steady_state(place: Place, curve: Curve, map_name: str, change: Change,
                 year: int | None = None, pm25_override: float | None = None,
                 deaths: "str | Sources" = "srs") -> Impact:
    """Deaths averted per year and change in life expectancy when `change` is applied to
    every exposure unit of `place` on `map_name`. pm25_override, if given, sets every unit's
    starting concentration (population weights unchanged), e.g. Delhi from 100 to 80.
    deaths: an inputs.Sources, or a deaths basis ("srs", "model", "unwpp") for the defaults
    with that death count."""
    src = Sources.of(deaths)
    cells: pd.DataFrame = exposure.cells(place, map_name, year, src.population)
    year = int(cells.attrs["year"])
    before = cells.pm25.to_numpy(float)
    if pm25_override is not None:
        before = np.full_like(before, float(pm25_override))
    after = change.apply(before)
    pop = cells.population.to_numpy(float)

    results, fallback, recs, adjs, un = [], [], [], [], None
    for state, rows in cells.groupby("state", sort=True).indices.items():
        b = baseline.load(state, year, sources=src)
        if b.fallback:
            fallback.append(state)
        if b.reconciliation:
            recs.append(b.reconciliation)
        if b.rates:
            adjs.append(b.rates)
        un = b.un_scaling or un
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
        fallback_states=fallback,
        deaths_model=float(sum(r.deaths_model for r in results)),
        reconciliations=tuple(recs), rate_adjustments=tuple(adjs), sources=src,
        un_scaling=un,
        population_year=int(cells.attrs["population_year"]),
        curve_note=_curve_note(curve, year))


def burden(place: Place, curve: Curve, map_name: str, counterfactual: float | None = None,
           year: int | None = None, deaths: "str | Sources" = "srs") -> Impact:
    """The impact of bringing every unit down to the counterfactual (default: the curve's
    floor), i.e. the deaths attributable to the air above it."""
    to = curve.floor if counterfactual is None else counterfactual
    return steady_state(place, curve, map_name, Change(to=to), year=year, deaths=deaths)


# --- many draws at once ---------------------------------------------------------------------

def apply_many(kind: str, values: np.ndarray, before: np.ndarray) -> np.ndarray:
    """Change.apply for n values of one kind at once: shape (n, units), never below 0. A drawn
    target below 0 counts as 0."""
    v = np.asarray(values, dtype=float)[:, None]
    pm = np.asarray(before, dtype=float)[None, :]
    if kind == "delta":
        out = pm + v
    elif kind == "pct":
        out = pm * (1 + v / 100)
    elif kind == "to":
        out = np.minimum(pm, np.maximum(v, 0.0))
    else:
        raise ValueError(f"unknown change kind {kind!r}; use delta, pct or to")
    return np.maximum(out, 0.0)


@dataclass(frozen=True)
class ImpactDraws:
    """Impact for n draws: the fields that vary are arrays of length n."""
    place: Place
    curve: Curve
    map_name: str
    year: int
    pm25_before: float
    pm25_after: np.ndarray
    population: float
    deaths_baseline: float
    deaths_averted: np.ndarray
    e0_before: float
    e0_after: np.ndarray
    yll_averted: np.ndarray
    derived: bool
    fallback_states: list[str]
    deaths_model: float = 0.0
    reconciliations: tuple[baseline.Reconciliation, ...] = ()
    rate_adjustments: tuple[baseline.RateAdjustment, ...] = ()   # one per state, early years only
    sources: Sources = Sources()
    un_scaling: baseline.UNScaling | None = None   # deaths="unwpp": India's figure, the same in every state
    population_year: int = 0
    curve_note: str = ""


def _aqli_factors(mx: np.ndarray, gains: np.ndarray, from_age: int) -> np.ndarray:
    """The multiplier on death rates that gives each gain in e0 (same shape as gains)."""
    unique = np.unique(gains)
    if len(unique) <= AQLI_EXACT:
        solved = np.array([lifetable.solve_adult_factor(mx, g, from_age=from_age) for g in unique])
        return solved[np.searchsorted(unique, gains)]
    grid = np.linspace(unique[0], unique[-1], AQLI_GRID)
    solved = np.array([lifetable.solve_adult_factor(mx, g, from_age=from_age) for g in grid])
    return np.exp(np.interp(gains, grid, np.log(solved)))   # log f is nearly linear in g


def _state_many(b: baseline.Baseline, curve: Curve, before: np.ndarray, after: np.ndarray,
                pop: np.ndarray) -> dict:
    """_state for n draws: before (units,), after (n, units)."""
    model = np.outer(pop, b.population / b.population.sum()) * b.mx     # unit × band
    deaths = model * b.death_factor
    table = lifetable.life_table(b.mx)
    if curve.kind == "life_expectancy":
        gains = np.broadcast_to(curve.delta_e0(before[None, :], after), after.shape)
        f = _aqli_factors(b.mx, gains, curve.min_age)                    # draw × unit
        factor = np.where(STARTS >= curve.min_age, f[..., None], 1.0)    # draw × unit × band
        e0_after = table.ex[0] + np.average(gains, axis=1, weights=pop)
        averted = np.einsum("ub,nub->nb", deaths, 1 - factor)            # draw × band
    elif curve.death_scope == "causes":
        lost = _cause_lost(curve, b, before[None, :], after)             # draw × unit × band
        people = model / b.mx                                             # unit × band
        averted = np.einsum("ub,nub->nb", people, lost)
        e0_after = lifetable.e0_many(b.mx - np.einsum("u,nub->nb", pop / pop.sum(), lost))
    else:
        # Bands whose risk is the same function of concentration share one ratio; with
        # g = 1 − ratio (draw × unit), deaths averted in band b are scope_b × g @ deaths[:, b]
        # and the population-weighted factor on band b's rate is 1 − scope_b × g @ pop / Σpop.
        scope = b.share_ncd_lri if curve.death_scope == "ncd_lri" else np.ones(len(STARTS))
        groups: dict = {}
        for k, age in enumerate(STARTS):
            groups.setdefault(curve.age_group(int(age)), []).append(k)
        averted = np.zeros((after.shape[0], len(STARTS)))
        mean_g = np.zeros_like(averted)
        for key, bands in groups.items():
            if key is None:
                continue                                                  # rr = 1: nothing moves
            age = int(STARTS[bands[0]])
            g = 1 - np.broadcast_to(curve.ratio(before[None, :], after, age), after.shape)
            averted[:, bands] = (g @ deaths[:, bands]) * scope[bands]
            mean_g[:, bands] = (g @ pop / pop.sum())[:, None]
        e0_after = lifetable.e0_many(b.mx * (1 - scope * mean_g))
    return dict(population=pop.sum(), deaths_model=model.sum(), deaths_baseline=deaths.sum(),
                deaths_averted=averted.sum(axis=1),
                yll_averted=averted @ lifetable.ex_at_death(b.mx),
                e0_before=table.ex[0], e0_after=e0_after)


def steady_state_many(place: Place, curve: Curve, map_name: str, kind: str,
                      values: np.ndarray, year: int | None = None,
                      pm25_override: float | None = None,
                      deaths: "str | Sources" = "srs") -> ImpactDraws:
    """steady_state() for n draws: values[i] is the change (of `kind`: delta, pct or to) in
    draw i, and draw i uses row i of the curve's parameters if the curve came from
    sample_many(), else the curve as it is."""
    src = Sources.of(deaths)
    cells: pd.DataFrame = exposure.cells(place, map_name, year, src.population)
    year = int(cells.attrs["year"])
    before = cells.pm25.to_numpy(float)
    if pm25_override is not None:
        before = np.full_like(before, float(pm25_override))
    after = apply_many(kind, values, before)
    pop = cells.population.to_numpy(float)

    results, fallback, recs, adjs, un = [], [], [], [], None
    for state, rows in cells.groupby("state", sort=True).indices.items():
        b = baseline.load(state, year, sources=src)
        if b.fallback:
            fallback.append(state)
        if b.reconciliation:
            recs.append(b.reconciliation)
        if b.rates:
            adjs.append(b.rates)
        un = b.un_scaling or un
        results.append(_state_many(b, curve, before[rows], after[:, rows], pop[rows]))

    weights = [r["population"] for r in results]
    return ImpactDraws(
        place=place, curve=curve, map_name=map_name, year=year,
        pm25_before=float(np.average(before, weights=pop)),
        pm25_after=np.average(after, axis=1, weights=pop),
        population=float(pop.sum()),
        deaths_baseline=float(sum(r["deaths_baseline"] for r in results)),
        deaths_averted=sum(r["deaths_averted"] for r in results),
        e0_before=float(np.average([r["e0_before"] for r in results], weights=weights)),
        e0_after=np.average([r["e0_after"] for r in results], axis=0, weights=weights),
        yll_averted=sum(r["yll_averted"] for r in results),
        derived=curve.kind == "life_expectancy",
        fallback_states=fallback,
        deaths_model=float(sum(r["deaths_model"] for r in results)),
        reconciliations=tuple(recs), rate_adjustments=tuple(adjs), sources=src,
        un_scaling=un,
        population_year=int(cells.attrs["population_year"]),
        curve_note=_curve_note(curve, year))
