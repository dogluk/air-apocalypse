"""Run an intervention file: Monte Carlo over its PM2.5 change, the curve parameters and cost.

For each curve, n draws. A draw takes one value of the PM2.5 change (the same n values for
every curve), one set of curve parameters (Curve.sample_many) and one value of each cost.
Which curve and which map are not sampled: each curve is its own result, and a run uses one
map. The probability of success is not sampled either. Every array in a CurveRun is
conditional on the intervention working; summary() multiplies by p_success for the expected
figures.

Accounting (a cohort run to 2050 replaces it in a later version). The steady-state change
in deaths per year and in life-years per year (deaths by age × remaining life expectancy at
the age of death, impact.steady_state_many) is computed once per draw, with the map year's
population and age structure. Each year of the intervention realises a share of it: the
ramp brings the change in over ramp_years in equal steps, and each step starts its own
cessation lag (lag.profile), so the share in year k is the sum over steps of the step's
size times the lag's cumulative share k - j years after step j. With no ramp this is the
lag profile itself. Deaths postponed and life-years over the run are the steady-state
figures times the sum of those shares. Years after duration_years count for nothing, in
either direction; nothing is discounted.

Cost if it works = (once + annual × duration_years), in dollars at the cost year's rate.
Expected cost = that × (1 − s + s × p_success), s = cost_share_only_on_success. The two
cost-effectiveness figures are ratios of means over draws: mean cost / mean life-years if
it works, and expected cost / expected life-years.

spread: the share of variance in life-years from the PM2.5 change and from the curve
parameters, each measured by sampling that group alone with the other at its median (the
published curve; the median change), and divided by the sum of the two.
"""
from __future__ import annotations

import zlib
from dataclasses import dataclass, field
from itertools import combinations

import numpy as np

from . import curves as curves_
from . import exposure, impact, intervention
from . import lag as lags
from .curves import Curve
from .intervention import Intervention, Invalid
from .places import Place

GROUPS = ("pm25_change", "curve_parameters")


@dataclass(frozen=True)
class CurveRun:
    """One curve's draws, all conditional on the intervention working (arrays of length n)."""
    curve: Curve
    life_years: np.ndarray        # over the run
    deaths_postponed: np.ndarray  # over the run
    e0_change_years: np.ndarray   # population-weighted, at full effect
    cost_usd: np.ndarray          # the whole cost, if it works
    pm25_after: np.ndarray        # population-weighted annual mean at full effect, µg/m³
    p_success: float
    cost_share_only_on_success: float
    spread: dict[str, float]      # share of variance in life_years, by GROUPS
    widths: dict[str, float] = field(default_factory=dict)   # p95 − p5 of life_years, by GROUPS

    def summary(self) -> dict:
        out = {}
        for k in ("life_years", "deaths_postponed", "e0_change_years", "cost_usd"):
            a = getattr(self, k)
            out[k] = dict(median=float(np.median(a)), p5=float(np.percentile(a, 5)),
                          p95=float(np.percentile(a, 95)), mean=float(np.mean(a)))
        p, s = self.p_success, self.cost_share_only_on_success
        mean_ly, mean_cost = float(np.mean(self.life_years)), float(np.mean(self.cost_usd))
        expected_ly = p * mean_ly
        expected_cost = mean_cost * (1 - s + s * p)
        out.update(
            p_success=p, expected_life_years=expected_ly, expected_cost_usd=expected_cost,
            cost_per_life_year_if_works=mean_cost / mean_ly if mean_ly > 0 else None,
            expected_cost_per_expected_life_year=(expected_cost / expected_ly
                                                  if expected_ly > 0 else None))
        return out


@dataclass(frozen=True)
class Run:
    intervention: Intervention
    map_name: str
    per_curve: dict[str, CurveRun]
    seed: int
    n: int
    year: int                       # the map's year, which also sets the population
    population: float
    deaths_baseline: float          # all-cause deaths a year in the places
    pm25_before: float              # population-weighted, µg/m³
    shares: np.ndarray              # share of the full effect realised in each year
    usd_per_unit: float             # dollars per unit of the cost currency
    fallback_states: list[str]
    unavailable: dict[str, str]     # curves asked for that could not run, with why
    deaths_model: float = 0.0       # all-cause deaths a year before reconciliation to the SRS
    reconciliations: tuple = ()     # baseline.Reconciliation per state; empty for deaths="model"
    population_year: int = 0        # the year the population is for (2011 if any place is a city)
    census_places: tuple = ()       # the places whose population is the Census's, not the map year's


def realised_shares(iv: Intervention) -> np.ndarray:
    """Share of the steady-state effect realised in each year of the intervention."""
    years = iv.duration_years
    k = np.arange(1, years + 1)
    ramp = np.minimum(k / iv.ramp_years, 1.0) if iv.ramp_years else np.ones(years)
    steps = np.diff(ramp, prepend=0.0)
    return np.convolve(steps, lags.profile(iv.lag, years))[:years]


def _overlap(a: Place, b: Place, map_name: str) -> bool:
    for x, y in ((a, b), (b, a)):
        if x.kind == "country" or (x.kind == "state" and y.state == x.name):
            return True
        if x.kind == "city" and y.kind == "district" and x.state == y.state:
            column = exposure.DISTRICT_MAPS.get(map_name)
            if column and y.name in exposure._cities().loc[x.name, column].split(";"):
                return True
    return False


def _check_places(places: list[Place], map_name: str) -> None:
    for a, b in combinations(places, 2):
        if _overlap(a, b, map_name):
            raise Invalid(f"places: {a.name} ({a.kind}) and {b.name} ({b.kind}) overlap, so "
                          "the people in both would be counted twice; list one of them")


def _rng(seed: int, *stream: int) -> np.random.Generator:
    return np.random.default_rng([seed, *stream])


@dataclass(frozen=True)
class _Steady:
    deaths: np.ndarray       # per year at full effect, by draw
    yll: np.ndarray
    e0_change: np.ndarray
    pm25_after: np.ndarray
    pm25_before: float
    population: float
    deaths_baseline: float
    year: int
    fallback: list[str]
    deaths_model: float
    reconciliations: tuple
    population_year: int
    census_places: tuple


def _steady(iv: Intervention, curve: Curve, values: np.ndarray, map_name: str,
            deaths: str = "srs") -> _Steady:
    """Steady-state results for every draw, added over the intervention's places."""
    parts = [impact.steady_state_many(p, curve, map_name, iv.change_kind, values,
                                      pm25_override=iv.from_level, deaths=deaths)
             for p in iv.places]
    pop = np.array([r.population for r in parts])
    return _Steady(
        deaths=sum(r.deaths_averted for r in parts), yll=sum(r.yll_averted for r in parts),
        e0_change=np.average([r.e0_after - r.e0_before for r in parts], axis=0, weights=pop),
        pm25_after=np.average([r.pm25_after for r in parts], axis=0, weights=pop),
        pm25_before=float(np.average([r.pm25_before for r in parts], weights=pop)),
        population=float(pop.sum()), deaths_baseline=float(sum(r.deaths_baseline for r in parts)),
        year=parts[0].year, fallback=sorted({s for r in parts for s in r.fallback_states}),
        deaths_model=float(sum(r.deaths_model for r in parts)),
        reconciliations=tuple(dict.fromkeys(x for r in parts for x in r.reconciliations)),
        population_year=min(r.population_year for r in parts),
        census_places=tuple(r.place.name for r in parts if r.population_year != r.year))


def _var(x: np.ndarray) -> float:
    return 0.0 if np.ptp(x) == 0 else float(np.var(x))


def _width(x: np.ndarray) -> float:
    return float(np.percentile(x, 95) - np.percentile(x, 5))


def run(iv: Intervention, map_name: str = "aqli", curves: list[str] | None = None,
        n: int = 5000, seed: int = 0, deaths: str = "srs") -> Run:
    """Run the intervention on every curve asked for (default: every curve that can run).
    deaths: "srs" (death counts reconciled to the SRS crude death rate) or "model"."""
    if n < 2:
        raise ValueError(f"n: need at least 2 draws, got {n}")
    if map_name not in exposure.MAPS:
        raise ValueError(f"unknown exposure map {map_name!r}; choose from {', '.join(exposure.MAPS)}")
    _check_places(iv.places, map_name)
    chosen, unavailable = curves_.select(curves)
    if not chosen:
        raise ValueError("no curve can run: " + "; ".join(f"{k}: {v}" for k, v in unavailable.items()))

    values = iv.change.sample(_rng(seed, 0), n)
    median_values = np.full(n, iv.change.median)
    usd = intervention.usd_per(iv.cost_currency, iv.cost_year)
    cost_rng = _rng(seed, 1)
    cost_usd = (iv.cost_once.sample(cost_rng, n)
                + iv.cost_annual.sample(cost_rng, n) * iv.duration_years) * usd
    shares = realised_shares(iv)
    years = shares.sum()

    per_curve, first = {}, None
    for curve in chosen:
        batch = curve.sample_many(_rng(seed, 2, zlib.crc32(curve.name.encode())), n)
        joint = _steady(iv, batch, values, map_name, deaths)
        change_only = joint if batch is curve else _steady(iv, curve, values, map_name, deaths)
        curve_only = _steady(iv, batch, median_values, map_name, deaths)
        if first is None:
            first = joint
        alone = {"pm25_change": change_only.yll * years, "curve_parameters": curve_only.yll * years}
        var = {k: _var(v) for k, v in alone.items()}
        total = sum(var.values())
        per_curve[curve.name] = CurveRun(
            curve=curve, life_years=joint.yll * years, deaths_postponed=joint.deaths * years,
            e0_change_years=joint.e0_change, cost_usd=cost_usd, pm25_after=joint.pm25_after,
            p_success=iv.p_success, cost_share_only_on_success=iv.cost_share_only_on_success,
            spread={k: v / total if total > 0 else 0.0 for k, v in var.items()},
            widths={k: _width(v) for k, v in alone.items()})

    return Run(intervention=iv, map_name=map_name, per_curve=per_curve, seed=seed, n=n,
               year=first.year, population=first.population,
               deaths_baseline=first.deaths_baseline, pm25_before=first.pm25_before,
               shares=shares, usd_per_unit=usd, fallback_states=first.fallback,
               unavailable=unavailable, deaths_model=first.deaths_model,
               reconciliations=first.reconciliations, population_year=first.population_year,
               census_places=first.census_places)


def across_curve_spread(run: Run) -> float:
    """Largest median life-years across curves ÷ the smallest (by size; inf if one is 0)."""
    medians = [abs(float(np.median(r.life_years))) for r in run.per_curve.values()]
    return max(medians) / min(medians) if min(medians) > 0 else float("inf")
