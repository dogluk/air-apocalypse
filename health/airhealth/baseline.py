"""Baseline demography for a state: population, all-cause death rates, cause shares.

Death rates are the SRS Abridged Life Tables 2020-24 (persons, total), as the
central rate m = d / L recovered from the printed lx and nLx columns, with the open
band m(85+) = l85 / L85+. A state the SRS does not cover gets all-India rates and is
flagged `fallback`.

Population is the official projection (Technical Group on Population Projections,
2019) as on 1st July of the year. Its last band is 80+; it is split into 80-84 and
85+ in proportion to the stationary population (L80 : L85+) of the same life table
that supplies the rates.

share_ncd_lri is the share of all-India deaths (SRS Causes of Death 2021-23,
Table 1.3A, persons) that are non-communicable disease or respiratory infection,
with ill-defined deaths shared out in proportion to the defined causes. The report's
seven broad age groups are mapped onto the 19 bands by containment (0-4 covers bands
0 and 1; 70+ covers 70 to 85+).

Death counts are reconciled to the SRS's own crude death rate (deaths="srs", the default).
Population × life-table rates gives more deaths than the SRS publishes (India 7.5 per 1,000
against 6.6 for 2020-24) although the rates are the SRS's own age-specific rates: the
projection has more people aged 45 and over than the population the SRS measured its rates
on (see the README, "How many deaths a year"). data/death_reconciliation.csv holds one
factor per state, built by scripts/build_death_reconciliation.py: for a state with its own
SRS tables, the factor on deaths at ages 45 and over that makes total deaths equal the
state's mean SRS crude death rate for 2020-24 × its population, at the 2022 population; for
a state that borrows all-India rates, one factor on deaths at every age, to the state's own
SRS crude death rate. Baseline.death_factor is that factor by band, and Baseline.deaths =
population × mx × death_factor. The reconciliation never changes mx, and so never life
expectancy. deaths="model" switches it off (death_factor all ones).

Years. In the life-table period, and after it (a projection, checked against nothing), the
rates are the period's and so is the factor. In an early year (EARLY_YEARS, 2011-19) the
SRS's own reports for that year are used instead: each band's rate is the period's times
the ratio of the SRS's rate by age for the year and a year either side
(data/srs_age_specific_death_rates.csv) to its 2020-24 mean, for the state, or for India
where the state has no rates by age for all those years (the smaller states, and Telangana
and Uttarakhand before 2014; Andhra Pradesh before 2014 is the undivided state). Mortality
then fell mostly at young ages, so this moves the age pattern, and life expectancy, as well
as the total. The deaths are then reconciled to that year's own SRS crude death rate, ages 45
and over, as above (data/death_reconciliation_by_year.csv); where the SRS printed no rate for
the state that year (smaller states and UTs before 2020), the period factor is kept.
"""
from dataclasses import dataclass
from functools import cache

import numpy as np
import pandas as pd

from . import paths
from .ages import AGE_STARTS
from .places import canonical_state

LIFE_TABLE_PERIOD = (2020, 2024)
MID_YEAR = sum(LIFE_TABLE_PERIOD) // 2
PERIOD_TEXT = f"{LIFE_TABLE_PERIOD[0]}-{LIFE_TABLE_PERIOD[1] % 100}"
DEATHS_BASES = ("srs", "model")   # reconciled to the SRS crude death rate, or not
RECONCILE_FROM_AGE = 45           # where the diagnosis puts the excess (see module docstring)
EARLY_YEARS = (2011, 2019)        # years before the period with the SRS's own rates transcribed
RATE_WINDOW = 1                   # an early year's rates by age: it and a year either side
RECONCILE_SOURCE = (
    "This project's comparison of modelled deaths by age with the SRS's own age-specific death "
    "rates and population age distribution, 2020-2024 (data/srs_age_specific_death_rates.csv, "
    "data/srs_population_age_pct.csv; tests/test_baseline.py): in India and all 22 states with "
    "a life table the excess over the SRS crude death rate is at ages 45 and over. SRS "
    "Statistical Reports, https://censusindia.gov.in/nada/index.php/catalog/46172"
)


@dataclass(frozen=True)
class Reconciliation:
    """How a state's death counts are scaled to its SRS crude death rate."""
    state: str
    factor: float          # on deaths at ages from_age and over
    from_age: int          # 45 for a state with its own SRS tables, 0 (every age) otherwise
    srs_cdr: float         # mean SRS crude death rate over the life-table period, per 1,000
    srs_unit: str          # the SRS row the rate is from, as printed (the state, or its merged UT)
    period: str = PERIOD_TEXT   # the years of that rate: the life-table period, or one early year

    @property
    def text(self) -> str:
        ages = f" at ages {self.from_age} and over" if self.from_age else ""
        return (f"deaths{ages} scaled by ×{self.factor:.2f} to the SRS crude death rate for "
                f"{self.srs_unit}, {self.period} ({self.srs_cdr:.1f} per 1,000)")


@dataclass(frozen=True)
class RateAdjustment:
    """An early year's death rates: the period's, times the SRS's rates by age over `years`
    divided by its rates for the life-table period, band by band, for `unit`."""
    state: str             # the state whose death rates were adjusted
    unit: str              # the state whose SRS rates by age were used, or India
    years: tuple[int, int] # first and last year averaged

    @property
    def text(self) -> str:
        return f"{self.unit}'s own SRS rates by age for {self.years[0]}-{self.years[1] % 100}"


@dataclass(frozen=True)
class Baseline:
    state: str
    year: int
    population: np.ndarray     # persons by band, 1st July of year
    mx: np.ndarray             # all-cause central death rate by band
    share_ncd_lri: np.ndarray  # share of deaths that are NCD or respiratory infection
    fallback: bool             # True when mx is all-India, not the state's own
    death_factor: np.ndarray   # factor on death counts by band (all ones for deaths="model")
    reconciliation: Reconciliation | None   # None for deaths="model"
    rates: RateAdjustment | None = None     # set in an early year (EARLY_YEARS), else None

    @property
    def deaths(self) -> np.ndarray:
        """All-cause deaths a year by band: population × mx × death_factor."""
        return self.population * self.mx * self.death_factor


@cache
def _life_tables() -> dict[str, pd.DataFrame]:
    t = pd.read_csv(paths.DATA / "lifetables_srs.csv")
    out = {}
    for printed, g in t.groupby("state", sort=False):
        g = g.sort_values("age_start")
        assert tuple(g.age_start) == AGE_STARTS, printed
        out[canonical_state(printed)] = g
    return out


@cache
def _population() -> pd.DataFrame:
    p = pd.read_csv(paths.DATA / "population_age_state.csv")
    p["state"] = p["state"].map(canonical_state)
    return p


@cache
def _share_ncd_lri() -> np.ndarray:
    c = pd.read_csv(paths.DATA / "cause_share_ncd_lri.csv")
    defined = 100 - c.ill_defined_pct
    share = ((c.ncd_pct + c.resp_infections_pct) / defined).to_numpy()
    starts = np.array(AGE_STARTS)
    out = np.empty(len(starts))
    for (lo, hi), s in zip(zip(c.age_from, c.age_to), share):
        hi = np.inf if pd.isna(hi) else hi
        out[(starts >= lo) & (starts <= hi)] = s
    return out


@cache
def _reconciliations() -> dict[str, Reconciliation]:
    t = pd.read_csv(paths.DATA / "death_reconciliation.csv")
    return {r.state: Reconciliation(r.state, float(r.factor), int(r.from_age),
                                    float(r.srs_cdr_per_1000), r.srs_unit)
            for r in t.itertuples()}


@cache
def _year_reconciliations() -> dict[tuple[str, int], Reconciliation]:
    t = pd.read_csv(paths.DATA / "death_reconciliation_by_year.csv")
    return {(r.state, int(r.period)): Reconciliation(r.state, float(r.factor), int(r.from_age),
                                                     float(r.srs_cdr_per_1000), r.srs_unit,
                                                     str(r.period))
            for r in t.itertuples()}


def reconciliation(state: str, year: int | None = None) -> Reconciliation:
    """The scaling to the SRS crude death rate: that year's, for an early year the SRS printed
    a rate for the state; otherwise the life-table period's."""
    return _year_reconciliations().get((state, year)) or _reconciliations()[state]


@cache
def _srs_asdr() -> pd.DataFrame:
    """SRS rates by age, one row per (canonical state, year), one column per band."""
    t = pd.read_csv(paths.DATA / "srs_age_specific_death_rates.csv")
    t["state"] = t.state.map(canonical_state)
    wide = t.pivot_table(index=["state", "year"], columns="age_start", values="rate_per_1000")
    assert tuple(wide.columns) == AGE_STARTS
    return wide


def rate_adjustment(state: str, year: int) -> tuple[np.ndarray, RateAdjustment]:
    """Factor by band on the period's death rates for an early year, from the state's own SRS
    rates by age (India's when the state has none for every year needed)."""
    t = _srs_asdr()
    lo, hi = LIFE_TABLE_PERIOD
    window = [y for y in range(year - RATE_WINDOW, year + RATE_WINDOW + 1)
              if EARLY_YEARS[0] <= y <= hi]
    needed = [*window, *range(lo, hi + 1)]
    unit = state if all((state, y) in t.index for y in needed) else "India"
    rows = lambda years: t.loc[[(unit, y) for y in years]].mean().to_numpy()  # noqa: E731
    return rows(window) / rows(range(lo, hi + 1)), RateAdjustment(state, unit, (window[0], window[-1]))


def _rates(table: pd.DataFrame) -> np.ndarray:
    lx, Lx = table.lx.to_numpy(float), table.Lx.to_numpy(float)
    return np.append((lx[:-1] - lx[1:]) / Lx[:-1], lx[-1] / Lx[-1])


def states() -> list[str]:
    """Every place with a population: India, states and union territories."""
    return list(dict.fromkeys(_population().state))


def projection_years() -> range:
    """The years the population projections cover (2011-2036)."""
    y = _population().year
    return range(int(y.min()), int(y.max()) + 1)


def load(state: str, year: int | None = None, deaths: str = "srs") -> Baseline:
    if deaths not in DEATHS_BASES:
        raise ValueError(f"deaths must be one of {', '.join(DEATHS_BASES)}, got {deaths!r}")
    pop = _population()
    rows = pop[pop.state == state]
    if rows.empty:
        raise KeyError(f"unknown state {state!r}; see baseline.states()")
    year = MID_YEAR if year is None else int(year)
    rows = rows[rows.year == year].sort_values("age_start")
    if rows.empty:
        raise KeyError(f"no population for {state!r} in {year}; "
                       f"projections cover {pop.year.min()}-{pop.year.max()}")

    tables = _life_tables()
    fallback = state not in tables
    table = tables["India" if fallback else state]

    persons = rows.population.to_numpy(float)       # bands 0, 1, 5, ..., 75, 80+
    L80, L85 = table.Lx.to_numpy(float)[-2:]
    population = np.append(persons[:-1], persons[-1] * np.array([L80, L85]) / (L80 + L85))

    mx, adjustment = _rates(table), None
    if EARLY_YEARS[0] <= year <= EARLY_YEARS[1]:
        ratio, adjustment = rate_adjustment(state, year)
        mx = mx * ratio
    rec = reconciliation(state, year) if deaths == "srs" else None
    factor = np.ones(len(AGE_STARTS))
    if rec:
        factor[np.array(AGE_STARTS) >= rec.from_age] = rec.factor
    return Baseline(state=state, year=year, population=population, mx=mx,
                    share_ncd_lri=_share_ncd_lri().copy(), fallback=fallback,
                    death_factor=factor, reconciliation=rec, rates=adjustment)
