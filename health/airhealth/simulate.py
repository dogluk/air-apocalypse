"""Run an intervention file: Monte Carlo over its PM2.5 change, the curve parameters and cost.

For each curve, n draws. A draw takes one quantile of the PM2.5 change (the same n quantiles for
every curve; each place turns it into its own change, which differs by place only for
monthly_pct, whose months are weighted by the place's shape), one set of curve parameters (Curve.sample_many) and one value of each cost.
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
lag profile itself.

The horizon is common to every measure: duration_years plus the length of its lag (20 for
epa20, nothing for immediate). When the intervention ends the air goes back, which is one
more step, of minus the full level, in year duration_years, and that step starts its own lag
too: the benefit that is still arriving when the measure stops keeps arriving (the tail), and
the rest of the effect fades out as the lag runs the other way. A one-year measure under epa20
therefore delivers all of one year's effect, spread over 21 years; today's accounting
(tail=False) stops at duration_years and drops the rest. Deaths postponed are the
steady-state figures times the sum of the yearly shares, undiscounted. Life-years are
the same sum with each year's share times (1 + DISCOUNT) ** -t, t = 0 for the first year
(DISCOUNT_SOURCE); discount=0 is the switch for no discounting. Costs are discounted the
same way: the one-off cost falls at t = 0, the annual cost in each year of duration_years.

Cost if it works = (once + annual × duration_years, discounted), in 2025 rupees (prices.to_base_inr: the
GDP deflator, and for dollar costs the rate of the cost year); dollars shown are those rupees at
the 2025 rate.
Expected cost = that × (1 − s + s × p_success), s = cost_share_only_on_success. The two
cost-effectiveness figures are ratios of means over draws: mean cost / mean life-years if
it works, and expected cost / expected life-years. Also given in rupees: rupees per life-year,
and life-years per crore (1 crore = 1e7 rupees).

covered (Intervention.covered): the share of each place's people the change reaches, drawn from
its own stream. Life-years, deaths postponed (and cost, when cost_per_covered) are the full-
population result times the covered draw, draw by draw: covered people are spread like everyone
else across units and ages, so this is exact, and it applies the cut to the covered people only
(not coverage x cut to everyone, which is wrong on curves that flatten at high levels).
e0_change_years and pm25_after describe the covered people.

covered_ages (Intervention.covered_ages): the covered people are one age group, e.g. (5, 19)
for schoolchildren, and covered is the share of that group reached. Deaths and life-years then
come from that group's own age bands only (impact.steady_state_many's ages), times the covered
draw; a curve that starts at 25 gives children nothing. e0_change_years then means the change
if everyone in the place breathed the change (no single life expectancy describes one age
group's gain). In the variance split the covered
draws belong to the pm25_change group; the curve_parameters group uses the covered median.

spread: the share of variance in life-years from the PM2.5 change and from the curve
parameters, each measured by sampling that group alone with the other at its median (the
published curve; the median change), and divided by the sum of the two.

monthly_curves (a sensitivity, off by default; percent changes only): the curves are applied
to each month's level instead of the annual mean. Month m starts from the place's level times
its shape for that month (months.shape), takes its own percent change (the file's monthly
entry m at the draw's quantile, or the flat percent), and the steady-state deaths and
life-years are the day-weighted mean (days / 365) of the twelve results. On a curve that
flattens at high levels a winter cut in Delhi is then worth less than the same annual mean
change spread evenly. Everything after the steady state (shares, discounting, cost, covered)
is as before. Twelve steady-state calculations replace one, so a run takes about twelve times
as long (see score.city for a timing).
"""
from __future__ import annotations

import dataclasses
import zlib
from dataclasses import dataclass, field
from itertools import combinations

import numpy as np

from . import curves as curves_
from . import exposure, impact, intervention, months, prices
from . import lag as lags
from .curves import Curve
from .inputs import Sources
from .intervention import Intervention, Invalid
from .places import Place

GROUPS = ("pm25_change", "curve_parameters")

DISCOUNT = 0.03   # a year, for costs and life-years alike
DISCOUNT_SOURCE = (
    "Tan-Torres Edejer T, Baltussen R, Adam T, Hutubessy R, Acharya A, Evans DB, Murray CJL "
    "(eds). Making choices in health: WHO guide to cost-effectiveness analysis. Geneva: World "
    "Health Organization, 2003. Section 3.3.1 'Choice of discount rate' (printed p. 45): "
    "'WHO-CHOICE uses a discount rate of 3% for the base case, as suggested in a number of "
    "guidelines. A discount rate of 6% is also explored using sensitivity analysis.' Section "
    "4.1.5 'Discounting' (p. 54): future healthy years gained 'are discounted at a 3% rate to "
    "their present values for the base case analysis in WHO-CHOICE'. Summary of "
    "recommendations (p. 71): '1. Costs and effects should be discounted at 3% in the base-case "
    "analysis. 2. In the sensitivity analysis ... we recommend testing the sensitivity of the "
    "results to a 0% discount rate for health effects and a 6% discount rate for costs.' "
    "https://iris.who.int/handle/10665/42699 "
    "(sha256 71c495bc26791acd5b262cd1248199de96513df5ce1a74666f3a20de498eb04b), read 2026-11-27."
)


@dataclass(frozen=True)
class CurveRun:
    """One curve's draws, all conditional on the intervention working (arrays of length n)."""
    curve: Curve
    life_years: np.ndarray        # over the run
    deaths_postponed: np.ndarray  # over the run
    e0_change_years: np.ndarray   # population-weighted, at full effect
    cost_inr: np.ndarray          # the whole cost, if it works, in 2025 rupees
    cost_usd: np.ndarray          # the same, in dollars at the 2025 rate
    pm25_after: np.ndarray        # population-weighted annual mean at full effect, µg/m³
    p_success: float
    cost_share_only_on_success: float
    spread: dict[str, float]      # share of variance in life_years, by GROUPS
    widths: dict[str, float] = field(default_factory=dict)   # p95 − p5 of life_years, by GROUPS

    def summary(self) -> dict:
        out = {}
        for k in ("life_years", "deaths_postponed", "e0_change_years", "cost_usd", "cost_inr"):
            a = getattr(self, k)
            out[k] = dict(median=float(np.median(a)), p5=float(np.percentile(a, 5)),
                          p95=float(np.percentile(a, 95)), mean=float(np.mean(a)))
        p, s = self.p_success, self.cost_share_only_on_success
        mean_ly, mean_cost = float(np.mean(self.life_years)), float(np.mean(self.cost_usd))
        mean_inr = float(np.mean(self.cost_inr))
        expected_ly = p * mean_ly
        expected_cost = mean_cost * (1 - s + s * p)
        expected_inr = mean_inr * (1 - s + s * p)
        crore = 1e7
        out.update(
            p_success=p, expected_life_years=expected_ly, expected_cost_usd=expected_cost,
            cost_per_life_year_if_works=mean_cost / mean_ly if mean_ly > 0 else None,
            expected_cost_per_expected_life_year=(expected_cost / expected_ly
                                                  if expected_ly > 0 else None),
            expected_cost_inr=expected_inr,
            inr_per_life_year_if_works=mean_inr / mean_ly if mean_ly > 0 else None,
            expected_inr_per_expected_life_year=(expected_inr / expected_ly
                                                 if expected_ly > 0 else None),
            life_years_per_crore_if_works=mean_ly * crore / mean_inr if mean_inr > 0 else None,
            expected_life_years_per_crore=(expected_ly * crore / expected_inr
                                           if expected_inr > 0 else None))
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
    discount: float                 # a year, for life-years and costs
    horizon_years: int              # years counted: the duration, plus the lag's tail
    usd_per_unit: float             # dollars per 2025 rupee
    fallback_states: list[str]
    unavailable: dict[str, str]     # curves asked for that could not run, with why
    deaths_model: float = 0.0       # all-cause deaths a year before reconciliation to the SRS
    reconciliations: tuple = ()     # baseline.Reconciliation per state; empty for deaths="model"
    rate_adjustments: tuple = ()    # baseline.RateAdjustment per state, early years only
    sources: Sources = Sources()
    un_scaling: object = None       # baseline.UNScaling for deaths="unwpp"
    population_year: int = 0        # the year the population is for (2011 if any place is a city)
    census_places: tuple = ()       # the places whose population is the Census's, not the map year's
    shapes: dict = field(default_factory=dict)   # months.Shape by Place.label; monthly_pct runs only
    monthly_curves: bool = False    # the curves were applied to each month's level


def yearly_shares(iv: Intervention, tail: bool = True) -> np.ndarray:
    """Share of the steady-state effect realised in each year t = 0..H-1 of the horizon.

    H = duration_years + the lag's length (20 for epa20, 0 for immediate) when tail, else
    duration_years. The ramp's steps switch the air on; at the end of the duration the whole
    level switches off (a step of minus one), and every step starts its own lag."""
    d = iv.duration_years
    horizon = d + (len(lags._EPA20) if tail and iv.lag == "epa20" else 0)
    k = np.arange(1, d + 1)
    ramp = np.minimum(k / iv.ramp_years, 1.0) if iv.ramp_years else np.ones(d)
    on = np.zeros(horizon + 1)
    on[:d] = np.diff(ramp, prepend=0.0)
    on[d] = -ramp[-1]
    increments = np.diff(lags.profile(iv.lag, horizon), prepend=0.0)
    return np.cumsum(np.convolve(on, increments)[:horizon])


def discount_factors(years: int, rate: float) -> np.ndarray:
    """(1 + rate) ** -t for t = 0..years-1."""
    return (1.0 + rate) ** -np.arange(years)


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
    rate_adjustments: tuple
    sources: Sources
    un_scaling: object
    population_year: int
    census_places: tuple


def _month_values(iv: Intervention, place: Place, m: int, q: np.ndarray) -> np.ndarray:
    """Month m's (0-11) own percent change at quantiles q (flat pct when the file has no months)."""
    out = (iv.monthly[m] if iv.monthly is not None else iv.change).ppf(q)
    if iv.scale is not None:
        if place.label not in iv.scale:
            raise KeyError(f"scale: no multiplier for {place.label!r}")
        out = out * iv.scale[place.label]
    return out


def _steady_monthly(iv: Intervention, place: Place, curve: Curve, q: np.ndarray,
                    map_name: str, deaths) -> impact.ImpactDraws:
    """impact.steady_state_many for one place, month by month: the day-weighted mean of twelve."""
    shape = months.shape(place).values
    w = months.MONTH_DAYS / months.MONTH_DAYS.sum()
    rs = [impact.steady_state_many(place, curve, map_name, "pct", _month_values(iv, place, m, q),
                                   deaths=deaths, ages=iv.covered_ages,
                                   level_factor=float(shape[m]))
          for m in range(12)]

    def mean(f):
        return sum(wi * f(r) for wi, r in zip(w, rs))
    return dataclasses.replace(
        rs[0], pm25_before=float(mean(lambda r: r.pm25_before)),
        pm25_after=mean(lambda r: r.pm25_after), deaths_averted=mean(lambda r: r.deaths_averted),
        yll_averted=mean(lambda r: r.yll_averted),
        e0_after=mean(lambda r: r.e0_after), e0_before=float(mean(lambda r: r.e0_before)))


def _steady(iv: Intervention, curve: Curve, q: np.ndarray, map_name: str,
            deaths: "str | Sources" = "srs", monthly_curves: bool = False) -> _Steady:
    """Steady-state results for every draw, added over the intervention's places."""
    if monthly_curves:
        parts = [_steady_monthly(iv, p, curve, q, map_name, deaths) for p in iv.places]
    else:
        parts = [impact.steady_state_many(p, curve, map_name, iv.change_kind,
                                          iv.annual_change(p, q), pm25_override=iv.from_level,
                                          deaths=deaths, ages=iv.covered_ages)
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
        rate_adjustments=tuple(dict.fromkeys(x for r in parts for x in r.rate_adjustments)),
        sources=parts[0].sources, un_scaling=parts[0].un_scaling,
        population_year=min(r.population_year for r in parts),
        census_places=tuple(r.place.name for r in parts if r.population_year != r.year))


def _var(x: np.ndarray) -> float:
    return 0.0 if np.ptp(x) == 0 else float(np.var(x))


def _width(x: np.ndarray) -> float:
    return float(np.percentile(x, 95) - np.percentile(x, 5))


def run(iv: Intervention, map_name: str = "aqli", curves: list[str] | None = None,
        n: int = 5000, seed: int = 0, deaths: "str | Sources | None" = None,
        discount: float = DISCOUNT, tail: bool = True,
        monthly_curves: bool = False) -> Run:
    """Run the intervention on every curve asked for (default: every curve that can run).
    discount: a year, for life-years and costs (0 for none); tail: count the years after the
    intervention ends in which its effect is still arriving (see the module docstring).
    deaths: an inputs.Sources or a deaths basis ("srs", "model", "unwpp"); None takes the
    intervention file's [sources] table, else the defaults. monthly_curves: see the module
    docstring."""
    if monthly_curves:
        if iv.change_kind != "pct":
            raise ValueError("monthly_curves: percent changes only")
        if iv.from_level is not None:
            raise ValueError("monthly_curves: not with from_level (a what-if level has no months)")
    deaths = Sources.of(iv.sources if deaths is None else deaths)
    if n < 2:
        raise ValueError(f"n: need at least 2 draws, got {n}")
    if map_name not in exposure.MAPS:
        raise ValueError(f"unknown exposure map {map_name!r}; choose from {', '.join(exposure.MAPS)}")
    _check_places(iv.places, map_name)
    chosen, unavailable = curves_.select(curves)
    if not chosen:
        raise ValueError("no curve can run: " + "; ".join(f"{k}: {v}" for k, v in unavailable.items()))

    q = _rng(seed, 0).random(n)
    median_q = np.full(n, 0.5)
    usd = prices.usd_per_base_inr()
    cost_rng = _rng(seed, 1)
    once = iv.cost_once.sample(cost_rng, n)
    annual = iv.cost_annual.sample(cost_rng, n)
    paid = discount_factors(iv.duration_years, discount).sum()    # annual cost, in present value
    cost_inr = prices.to_base_inr(once + annual * paid, iv.cost_currency, iv.cost_year)
    covered, covered_median = np.ones(n), 1.0
    if iv.covered is not None:
        covered = iv.covered.sample(_rng(seed, 3), n)
        covered_median = iv.covered.median
        if iv.cost_per_covered:
            cost_inr = cost_inr * covered
    cost_usd = cost_inr * usd
    shares = yearly_shares(iv, tail)
    deaths_years = shares.sum()
    years = float(shares @ discount_factors(len(shares), discount))

    per_curve, first = {}, None
    for curve in chosen:
        batch = curve.sample_many(_rng(seed, 2, zlib.crc32(curve.name.encode())), n)
        joint = _steady(iv, batch, q, map_name, deaths, monthly_curves)
        change_only = joint if batch is curve else _steady(iv, curve, q, map_name, deaths, monthly_curves)
        curve_only = _steady(iv, batch, median_q, map_name, deaths, monthly_curves)
        if first is None:
            first = joint
        alone = {"pm25_change": change_only.yll * years * covered,
                 "curve_parameters": curve_only.yll * years * covered_median}
        var = {k: _var(v) for k, v in alone.items()}
        total = sum(var.values())
        per_curve[curve.name] = CurveRun(
            curve=curve, life_years=joint.yll * years * covered,
            deaths_postponed=joint.deaths * deaths_years * covered,
            e0_change_years=joint.e0_change, cost_inr=cost_inr, cost_usd=cost_usd, pm25_after=joint.pm25_after,
            p_success=iv.p_success, cost_share_only_on_success=iv.cost_share_only_on_success,
            spread={k: v / total if total > 0 else 0.0 for k, v in var.items()},
            widths={k: _width(v) for k, v in alone.items()})

    return Run(intervention=iv, map_name=map_name, per_curve=per_curve, seed=seed, n=n,
               year=first.year, population=first.population,
               deaths_baseline=first.deaths_baseline, pm25_before=first.pm25_before,
               shares=shares, discount=discount, horizon_years=len(shares), usd_per_unit=usd, fallback_states=first.fallback,
               unavailable=unavailable, deaths_model=first.deaths_model,
               reconciliations=first.reconciliations, rate_adjustments=first.rate_adjustments,
               sources=first.sources, un_scaling=first.un_scaling,
               population_year=first.population_year,
               census_places=first.census_places, monthly_curves=monthly_curves,
               shapes={p.label: months.shape(p) for p in iv.places}
               if iv.monthly is not None and iv.change_kind == "pct" else {})


def across_curve_spread(run: Run) -> float:
    """Largest median life-years across curves ÷ the smallest (by size; inf if one is 0)."""
    medians = [abs(float(np.median(r.life_years))) for r in run.per_curve.values()]
    return max(medians) / min(medians) if min(medians) > 0 else float("inf")
