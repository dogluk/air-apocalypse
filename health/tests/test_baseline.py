import numpy as np
import pandas as pd
import pytest

from airhealth import baseline, paths, places
from airhealth.lifetable import e0

# India, persons, as on 1st July 2022 ('000): Technical Group on Population
# Projections (2019), Table 11, first row block, column 2.
INDIA_2022_THOUSANDS = 1_377_901


def published_e0() -> dict[str, float]:
    t = pd.read_csv(paths.DATA / "lifetables_srs.csv")
    at_birth = t[t.age_start == 0]
    return {places.canonical_state(s): e for s, e in zip(at_birth.state, at_birth.ex)}


def test_computed_e0_matches_srs_published():
    published = published_e0()
    assert len(published) == 23  # India and 22 states/UTs
    for state, e in published.items():
        b = baseline.load(state)
        assert not b.fallback
        assert abs(e0(b.mx) - e) < 0.5, state


def test_state_without_table_falls_back():
    b = baseline.load("Puducherry")
    india = baseline.load("India")
    assert b.fallback is True
    assert np.array_equal(b.mx, india.mx)
    assert b.population.sum() > 0
    assert b.population.sum() < india.population.sum() / 100


def test_unknown_name_raises_naming_it():
    with pytest.raises(KeyError, match="Atlantis"):
        baseline.load("Atlantis")


def test_india_population_total():
    total = sum(baseline.load(s).population.sum() for s in baseline.states() if s != "India")
    assert total == pytest.approx(INDIA_2022_THOUSANDS * 1000, rel=0.01)
    assert baseline.load("India").population.sum() == pytest.approx(
        INDIA_2022_THOUSANDS * 1000, rel=0.001)


def test_default_year_is_life_table_mid_year():
    assert baseline.load("Kerala").year == 2022


def test_shapes_and_ranges():
    b = baseline.load("Delhi", 2030)
    assert b.year == 2030
    for arr in (b.population, b.mx, b.share_ncd_lri):
        assert arr.shape == (19,)
    assert (b.mx > 0).all()
    assert ((b.share_ncd_lri > 0) & (b.share_ncd_lri <= 1)).all()


def test_year_outside_projections_raises():
    with pytest.raises(KeyError, match="2040"):
        baseline.load("India", 2040)


# --- death counts against the SRS's own crude death rate (final review, I1) ------------------

def period(t: pd.DataFrame) -> pd.DataFrame:
    """The rows for the life-table period; the SRS files also hold 2011-19."""
    lo, hi = baseline.LIFE_TABLE_PERIOD
    return t[t.year.between(lo, hi)]


def srs_mean_cdr() -> dict[str, float]:
    """Mean SRS crude death rate 2020-24 by canonical state, straight from the transcription."""
    t = period(pd.read_csv(paths.DATA / "srs_crude_death_rate.csv"))
    assert sorted(t.year.unique()) == [2020, 2021, 2022, 2023, 2024]
    out = {}
    for printed, g in t.groupby("state"):
        if printed == "Dadra and Nagar Haveli and Daman and Diu":
            out["Dadra & Nagar Haveli"] = out["Daman & Diu"] = g.cdr_per_1000.mean()
        else:
            out[places.canonical_state(printed)] = g.cdr_per_1000.mean()
    return out


def test_every_state_has_its_own_srs_crude_death_rate():
    assert set(srs_mean_cdr()) == set(baseline.states())


def test_implied_crude_death_rate_equals_the_srs_rate_in_every_state():
    for state, cdr in srs_mean_cdr().items():
        b = baseline.load(state, 2022)
        implied = 1000 * b.deaths.sum() / b.population.sum()
        assert implied == pytest.approx(cdr, rel=0.005), state
        assert b.reconciliation.srs_cdr == pytest.approx(cdr, abs=0.005), state


def test_unreconciled_deaths_exceed_the_srs_rate_because_of_age_structure():
    """The diagnosis: same death rates, older population. Modelled deaths are above the SRS's
    by 5% to 32% in every state with its own table, and all of the excess is at 45 and over."""
    cdr = srs_mean_cdr()
    asdr = period(pd.read_csv(paths.DATA / "srs_age_specific_death_rates.csv"))
    age = period(pd.read_csv(paths.DATA / "srs_population_age_pct.csv"))
    for frame in (asdr, age):
        frame["state"] = frame.state.map(places.canonical_state)
    starts = np.array(baseline.AGE_STARTS)
    assert asdr.state.nunique() == 23
    for state in asdr.state.unique():
        b = baseline.load(state, 2022, deaths="model")
        assert not b.fallback and b.reconciliation is None and (b.death_factor == 1).all()
        pop_share = b.population / b.population.sum()
        ours = 1000 * (pop_share * b.mx).sum()
        assert 1.04 < ours / cdr[state] < 1.33, state
        # the SRS's own rates on the SRS's own age distribution give back its crude rate ...
        rates = asdr[asdr.state == state].groupby("age_start").rate_per_1000.mean().reindex(starts)
        srs_share = age[age.state == state].groupby("age_start").pct.mean() / 100
        infants = pop_share[0] / pop_share[:2].sum()
        srs_share = np.concatenate([[srs_share[0] * infants, srs_share[0] * (1 - infants)],
                                    srs_share.to_numpy()[1:]])
        assert (srs_share * rates.to_numpy()).sum() == pytest.approx(cdr[state], rel=0.03), state
        # ... and so do the life-table rates below 85: the rates are not where the excess is.
        # (At 85+ the life table is closed by model and its rate differs from the SRS's in
        # either direction, by up to 0.4 per 1,000 of population: Jammu & Kashmir.)
        lt = np.where(starts < 85, 1000 * b.mx, rates.to_numpy())
        assert (srs_share * lt).sum() == pytest.approx(cdr[state], rel=0.03), state
        assert abs(srs_share[-1] * (1000 * b.mx[-1] - rates.to_numpy()[-1])) < 0.45, state
        # the excess is the projection's older population, at 45 and over
        excess = 1000 * pop_share * b.mx - srs_share * rates.to_numpy()
        assert excess[starts >= 45].sum() > 0.9 * (ours - cdr[state]), state
        assert abs(excess[starts < 45].sum()) < 0.1, state


def test_reconciliation_table_matches_its_inputs():
    t = pd.read_csv(paths.DATA / "death_reconciliation.csv").set_index("state")
    assert set(t.index) == set(baseline.states())
    cdr = srs_mean_cdr()
    starts = np.array(baseline.AGE_STARTS)
    for state, row in t.iterrows():
        b = baseline.load(state, 2022, deaths="model")
        assert row.srs_cdr_per_1000 == pytest.approx(cdr[state], abs=0.005)
        assert row.from_age == (0 if b.fallback else 45), state
        modelled = b.population * b.mx
        old = starts >= row.from_age
        target = row.srs_cdr_per_1000 / 1000 * b.population.sum()
        assert row.factor == pytest.approx((target - modelled[~old].sum()) / modelled[old].sum(),
                                           abs=1e-4), state
        assert 0.5 < row.factor < 1.0, state


def test_states_reconciled_one_by_one_add_up_to_indias_own_rate():
    states = [baseline.load(s, 2022) for s in baseline.states() if s != "India"]
    deaths = sum(b.deaths.sum() for b in states)
    population = sum(b.population.sum() for b in states)
    assert 1000 * deaths / population == pytest.approx(srs_mean_cdr()["India"], rel=0.015)


def test_life_table_is_not_scaled():
    for state in ("India", "Delhi", "Chandigarh"):
        srs, model = baseline.load(state), baseline.load(state, deaths="model")
        assert np.array_equal(srs.mx, model.mx) and np.array_equal(srs.population, model.population)
        assert srs.deaths.sum() < model.deaths.sum()
    with pytest.raises(ValueError, match="deaths"):
        baseline.load("Delhi", deaths="registered")


# --- years before the life-table period: the SRS's own rates for that year ------------------

def srs_asdr(unit: str, years) -> np.ndarray:
    t = pd.read_csv(paths.DATA / "srs_age_specific_death_rates.csv")
    t = t[t.state.map(places.canonical_state) == unit]
    return t[t.year.isin(list(years))].groupby("age_start").rate_per_1000.mean().to_numpy()


def test_early_year_rates_follow_the_srs_band_by_band():
    """2011-19: each band's rate is the period's times the SRS's own rate for the year and
    its neighbours over the SRS's 2020-24 rate, so the age pattern is that year's."""
    period = baseline.load("Delhi", 2022)
    for year, window in ((2015, range(2014, 2017)), (2011, range(2011, 2013)),
                         (2019, range(2018, 2021))):
        b = baseline.load("Delhi", year)
        ratio = srs_asdr("Delhi", window) / srs_asdr("Delhi", range(2020, 2025))
        assert b.mx == pytest.approx(period.mx * ratio, rel=1e-9), year
        assert b.rates.unit == "Delhi" and b.rates.years == (window[0], window[-1])
    india = baseline.load("India", 2011)
    assert india.mx[0] > 1.5 * baseline.load("India", 2022).mx[0]       # infant deaths
    assert e0(india.mx) < e0(baseline.load("India", 2022).mx) - 1


def test_states_without_their_own_early_rates_borrow_indias():
    india = baseline.load("India", 2012).mx / baseline.load("India", 2022).mx
    for state in ("Telangana", "Uttarakhand", "Chandigarh"):        # Telangana: from 2014
        b = baseline.load(state, 2012)
        assert b.rates.unit == "India", state
        assert b.mx / baseline.load(state, 2022).mx == pytest.approx(india, rel=1e-9), state


def test_rates_in_and_after_the_period_are_the_life_tables():
    for year in (2020, 2022, 2024, 2030):
        b = baseline.load("Delhi", year)
        assert b.rates is None and b.mx == pytest.approx(baseline.load("Delhi", 2022).mx)


def test_early_year_counts_equal_that_years_srs_crude_death_rate():
    t = pd.read_csv(paths.DATA / "srs_crude_death_rate.csv")
    t = t[t.year < baseline.LIFE_TABLE_PERIOD[0]]
    assert sorted(t.year.unique()) == list(range(2011, 2020))
    for r in t.itertuples():
        state = places.canonical_state(r.state)
        b = baseline.load(state, r.year)
        assert 1000 * b.deaths.sum() / b.population.sum() == pytest.approx(r.cdr_per_1000,
                                                                           abs=0.006), r
        assert b.reconciliation.period == str(r.year) and 0.5 < b.reconciliation.factor < 1.5


def test_early_year_without_an_srs_rate_keeps_the_period_scaling():
    for state, year in (("Chandigarh", 2015), ("Telangana", 2012)):
        rec = baseline.load(state, year).reconciliation
        assert rec.period == baseline.PERIOD_TEXT and rec == baseline.reconciliation(state)
