"""Build data/death_reconciliation.csv: the factor that brings each state's modelled death
count to its SRS crude death rate; and data/death_reconciliation_by_year.csv, the same for
each early year (baseline.EARLY_YEARS) and every state the SRS printed a rate for that year.

    python scripts/build_death_reconciliation.py

Inputs, all in data/: srs_crude_death_rate.csv (SRS Statistical Reports 2020-2024,
Statement 40), lifetables_srs.csv and population_age_state.csv (through airhealth.baseline).

For each state and union territory, and India:
  srs_cdr_per_1000      mean of the five annual SRS crude death rates, 2020-2024, the years
                        the life tables cover. Dadra & Nagar Haveli and Daman & Diu take the
                        rate of their merged union territory, the only one the SRS prints.
  modelled_cdr_per_1000 deaths per 1,000 from the projected population of 1 July 2022 (the
                        middle of the period) × the life-table death rates, unscaled.
  from_age, factor      a state with its own SRS life table: from_age 45, and factor solves
                            deaths under 45 + factor × deaths at 45 and over = SRS rate × population;
                        a state that borrows all-India rates: from_age 0, and
                            factor = SRS rate ÷ modelled rate.
Why 45: for India and all 22 states with their own tables, the life-table rates equal the
SRS's age-specific death rates, and the whole excess of modelled over SRS deaths is the
projection having more people aged 45 and over than the SRS's own population distribution
(srs_population_age_pct.csv); under 45 the two agree within 0.1 per 1,000.

By year: the same, for each early year, with that year's own SRS crude death rate, that
year's projected population, and that year's death rates by age (baseline.load adjusts the
period's rates band by band to the SRS's rates by age around the year). Before 2020 the SRS
prints a crude rate for India and the bigger states only (20 in 2011-13, 22 from 2014).
"""
from pathlib import Path

import numpy as np
import pandas as pd

from airhealth import baseline
from airhealth.ages import AGE_STARTS
from airhealth.places import canonical_state

DATA = Path(__file__).resolve().parents[1] / "data"
COMBINED_UT = "Dadra and Nagar Haveli and Daman and Diu"
COMBINED_PARTS = ("Dadra & Nagar Haveli", "Daman & Diu")
YEARS = list(range(baseline.LIFE_TABLE_PERIOD[0], baseline.LIFE_TABLE_PERIOD[1] + 1))


def srs_rates() -> dict[str, tuple[float, str]]:
    """Canonical state -> (mean SRS crude death rate over YEARS, the SRS row's printed name)."""
    t = pd.read_csv(DATA / "srs_crude_death_rate.csv")
    t = t[t.year.isin(YEARS)]      # the file also holds 2011-19
    assert sorted(t.year.unique()) == YEARS
    out = {}
    for printed, g in t.groupby("state"):
        assert len(g) == len(YEARS), printed
        mean = round(float(g.cdr_per_1000.mean()), 2)
        if printed == COMBINED_UT:
            out.update({part: (mean, printed) for part in COMBINED_PARTS})
        else:
            out[canonical_state(printed)] = (mean, printed)
    return out


def main() -> None:
    rates = srs_rates()
    starts = np.array(AGE_STARTS)
    old = starts >= baseline.RECONCILE_FROM_AGE
    rows = []
    for state in baseline.states():
        b = baseline.load(state, baseline.MID_YEAR, deaths="model")
        cdr, unit = rates[state]
        modelled = b.population * b.mx
        target = cdr / 1000 * b.population.sum()
        if b.fallback:
            from_age, factor = 0, target / modelled.sum()
        else:
            from_age = baseline.RECONCILE_FROM_AGE
            factor = (target - modelled[~old].sum()) / modelled[old].sum()
        assert 0.3 < factor < 1.5, (state, factor)
        rows.append(dict(state=state, period=baseline.PERIOD_TEXT, srs_unit=unit,
                         srs_cdr_per_1000=cdr, reference_year=baseline.MID_YEAR,
                         modelled_cdr_per_1000=round(1000 * modelled.sum() / b.population.sum(), 3),
                         from_age=from_age, factor=round(factor, 4)))
    out = pd.DataFrame(rows)
    out.to_csv(DATA / "death_reconciliation.csv", index=False)
    print(out.to_string(index=False))
    by_year = pd.DataFrame(early_rows())
    by_year.to_csv(DATA / "death_reconciliation_by_year.csv", index=False)
    print(by_year.to_string(index=False))


def factor_for(b: baseline.Baseline, cdr: float) -> tuple[int, float]:
    """from_age and factor that bring b's modelled deaths to `cdr` per 1,000."""
    modelled = b.population * b.mx
    target = cdr / 1000 * b.population.sum()
    if b.fallback:
        return 0, target / modelled.sum()
    old = np.array(AGE_STARTS) >= baseline.RECONCILE_FROM_AGE
    return baseline.RECONCILE_FROM_AGE, (target - modelled[~old].sum()) / modelled[old].sum()


def early_rows() -> list[dict]:
    t = pd.read_csv(DATA / "srs_crude_death_rate.csv")
    lo, hi = baseline.EARLY_YEARS
    t = t[t.year.between(lo, hi)]
    rows = []
    for r in t.itertuples():
        state = canonical_state(r.state)
        b = baseline.load(state, r.year, deaths="model")
        from_age, factor = factor_for(b, r.cdr_per_1000)
        assert 0.5 < factor < 1.5, (state, r.year, factor)
        rows.append(dict(state=state, period=r.year, srs_unit=r.state,
                         srs_cdr_per_1000=r.cdr_per_1000, reference_year=r.year,
                         modelled_cdr_per_1000=round(1000 * (b.population * b.mx).sum()
                                                     / b.population.sum(), 3),
                         from_age=from_age, factor=round(factor, 4)))
    return rows


if __name__ == "__main__":
    main()
