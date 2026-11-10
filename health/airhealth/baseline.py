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
SRS crude death rate. The same factor is used in every year. Baseline.death_factor is that
factor by band, and Baseline.deaths = population × mx × death_factor. The life table (mx,
and so life expectancy) is never scaled. deaths="model" switches the reconciliation off
(death_factor all ones).
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


@dataclass(frozen=True)
class Reconciliation:
    """How a state's death counts are scaled to its SRS crude death rate."""
    state: str
    factor: float          # on deaths at ages from_age and over
    from_age: int          # 45 for a state with its own SRS tables, 0 (every age) otherwise
    srs_cdr: float         # mean SRS crude death rate over the life-table period, per 1,000
    srs_unit: str          # the SRS row the rate is from, as printed (the state, or its merged UT)

    @property
    def text(self) -> str:
        ages = f" at ages {self.from_age} and over" if self.from_age else ""
        return (f"deaths{ages} scaled by ×{self.factor:.2f} to the SRS crude death rate for "
                f"{self.srs_unit}, {PERIOD_TEXT} ({self.srs_cdr:.1f} per 1,000)")


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


def reconciliation(state: str) -> Reconciliation:
    return _reconciliations()[state]


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

    rec = reconciliation(state) if deaths == "srs" else None
    factor = np.ones(len(AGE_STARTS))
    if rec:
        factor[np.array(AGE_STARTS) >= rec.from_age] = rec.factor
    return Baseline(state=state, year=year, population=population, mx=_rates(table),
                    share_ncd_lri=_share_ncd_lri().copy(), fallback=fallback,
                    death_factor=factor, reconciliation=rec)
