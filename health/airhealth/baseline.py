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
"""
from dataclasses import dataclass
from functools import cache

import numpy as np
import pandas as pd

from . import paths
from .ages import AGE_STARTS

LIFE_TABLE_PERIOD = (2020, 2024)
MID_YEAR = sum(LIFE_TABLE_PERIOD) // 2

# Printed names that differ from the SRS life-table spelling. Next task replaces
# state_name with places.canonical_state.
_RENAMES = {
    "Telengana": "Telangana",                  # SRS table heading; Statement 3 has Telangana
    "INDIA": "India",
    "NCT OF DELHI": "Delhi",
    "JAMMU & KASHMIR (UT)": "Jammu & Kashmir",
}


def state_name(printed: str) -> str:
    """Display name for a state as printed by any of the three sources."""
    if printed in _RENAMES:
        return _RENAMES[printed]
    if printed.isupper():
        return " ".join(w if w == "&" else w.capitalize() for w in printed.split())
    return printed


@dataclass(frozen=True)
class Baseline:
    state: str
    year: int
    population: np.ndarray     # persons by band, 1st July of year
    mx: np.ndarray             # all-cause central death rate by band
    share_ncd_lri: np.ndarray  # share of deaths that are NCD or respiratory infection
    fallback: bool             # True when mx is all-India, not the state's own


@cache
def _life_tables() -> dict[str, pd.DataFrame]:
    t = pd.read_csv(paths.DATA / "lifetables_srs.csv")
    out = {}
    for printed, g in t.groupby("state", sort=False):
        g = g.sort_values("age_start")
        assert tuple(g.age_start) == AGE_STARTS, printed
        out[state_name(printed)] = g
    return out


@cache
def _population() -> pd.DataFrame:
    p = pd.read_csv(paths.DATA / "population_age_state.csv")
    p["state"] = p["state"].map(state_name)
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


def _rates(table: pd.DataFrame) -> np.ndarray:
    lx, Lx = table.lx.to_numpy(float), table.Lx.to_numpy(float)
    return np.append((lx[:-1] - lx[1:]) / Lx[:-1], lx[-1] / Lx[-1])


def states() -> list[str]:
    """Every place with a population: India, states and union territories."""
    return list(dict.fromkeys(_population().state))


def load(state: str, year: int | None = None) -> Baseline:
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

    return Baseline(state=state, year=year, population=population, mx=_rates(table),
                    share_ncd_lri=_share_ncd_lri().copy(), fallback=fallback)
