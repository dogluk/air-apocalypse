"""Sources for each input: the registry, the choice, and what each source does to the baseline."""
import numpy as np
import pandas as pd
import pytest

from airhealth import baseline, lifetable, paths
from airhealth.ages import AGE_STARTS
from airhealth.inputs import REGISTRY, Choice, Sources

UN = Sources(population="unwpp", death_rates="unwpp", deaths="unwpp")


def un(name: str, col: str, year: int) -> np.ndarray:
    t = pd.read_csv(paths.DATA / f"unwpp_{name}.csv")
    return t[t.year == year].sort_values("age_start")[col].to_numpy(float)


def test_registry_and_defaults():
    assert Sources() == Sources.of(None) and Sources.of("model") == Sources(deaths="model")
    assert {i.name for i in REGISTRY.values()} >= {"population", "death_rates", "deaths", "map"}
    with pytest.raises(ValueError, match="unknown source"):
        Sources(deaths="who")
    assert Sources().bodies == ["Indian government"]
    assert Sources(deaths="unwpp").bodies == ["Indian government", "United Nations"]
    assert Sources(deaths="model", population="unwpp", death_rates="unwpp").bodies == ["United Nations"]


def test_choice_parses_flags_into_combinations():
    c = Choice.parse(["deaths=srs,unwpp", "population=unwpp"])
    assert c.combinations() == [Sources(population="unwpp", deaths="srs"),
                                Sources(population="unwpp", deaths="unwpp")]
    assert Choice.parse([], deaths="model").combinations() == [Sources(deaths="model")]
    assert Choice.parse([]).combinations() == [Sources()]
    for bad in (["deaths"], ["curves=gemm"], ["deaths=who"]):
        with pytest.raises(ValueError):
            Choice.parse(bad)


def test_un_population_matches_the_un_for_india_and_keeps_state_shares():
    for year in (2015, 2022, 2030):
        india = baseline.load("India", year, sources=Sources(population="unwpp"))
        assert india.population == pytest.approx(un("population_age", "population", year), rel=1e-9)
        ours = baseline.load("Delhi", year).population / baseline.load("India", year).population
        theirs = (baseline.load("Delhi", year, sources=Sources(population="unwpp")).population
                  / india.population)
        assert theirs == pytest.approx(ours, rel=1e-9)


def test_un_death_rates_match_the_un_for_india_and_keep_state_patterns():
    for year in (2014, 2022):
        india = baseline.load("India", year, sources=Sources(death_rates="unwpp"))
        assert india.mx == pytest.approx(un("lifetable", "mx", year), rel=1e-9)
        assert india.rates is None                       # no SRS early-year adjustment on top
    srs_ratio = baseline.load("Delhi", 2022).mx / baseline.load("India", 2022).mx
    un_ratio = (baseline.load("Delhi", 2022, sources=Sources(death_rates="unwpp")).mx
                / baseline.load("India", 2022, sources=Sources(death_rates="unwpp")).mx)
    assert un_ratio == pytest.approx(srs_ratio, rel=1e-9)
    e0 = lifetable.e0(baseline.load("India", 2023, sources=Sources(death_rates="unwpp")).mx)
    assert e0 == pytest.approx(72.00, abs=0.1)          # WPP 2024's own e0 for India, 2023


def test_srs_scaling_solved_at_run_time_reproduces_the_tables():
    t = pd.read_csv(paths.DATA / "death_reconciliation.csv").set_index("state")
    for state in ("India", "Delhi", "Kerala", "Chandigarh"):
        assert baseline.load(state, 2030).reconciliation.factor == pytest.approx(
            t.factor[state], abs=1e-4), state
    y = pd.read_csv(paths.DATA / "death_reconciliation_by_year.csv")
    for r in y[y.state.isin(["India", "Bihar"])].itertuples():
        assert baseline.load(r.state, r.period).reconciliation.factor == pytest.approx(r.factor, abs=1e-4)


def test_srs_scaling_holds_under_un_population_and_rates():
    """Whatever the population and rates, deaths=srs lands on the SRS crude death rate."""
    for src in (Sources(population="unwpp"), Sources(death_rates="unwpp"),
                Sources(population="unwpp", death_rates="unwpp")):
        b = baseline.load("Delhi", 2016, sources=src)
        assert 1000 * b.deaths.sum() / b.population.sum() == pytest.approx(
            b.reconciliation.srs_cdr, abs=0.005), src
        p = baseline.load("Punjab", 2022, sources=src)   # the period scaling, at its 2022 reference
        assert 1000 * p.deaths.sum() / p.population.sum() == pytest.approx(
            p.reconciliation.srs_cdr, abs=0.005), src


def test_un_deaths_match_the_un_by_age_for_india():
    for year in (2015, 2022):
        for src in (Sources(deaths="unwpp"), UN):
            india = baseline.load("India", year, sources=src)
            assert india.deaths == pytest.approx(un("deaths_age", "deaths", year), rel=1e-6)
            assert india.reconciliation is None and india.un_scaling.year == year
        delhi = baseline.load("Delhi", year, sources=Sources(deaths="unwpp"))
        india = baseline.load("India", year, sources=Sources(deaths="unwpp"))
        assert delhi.death_factor == pytest.approx(india.death_factor)   # one set of factors


def test_all_un_is_close_to_unscaled():
    """UN population × UN rates is already the UN's death count, so its scaling is near 1;
    at 85+ less so, because the open band's rate (l85 / T85) assumes a stationary age mix
    within it and India's 85+ population is younger than that."""
    f = baseline.load("India", 2022, sources=UN).death_factor
    assert np.abs(f[:-1] - 1).max() < 0.02 and 0.85 < f[-1] < 1


def test_deaths_choice_never_touches_life_expectancy():
    base = lifetable.e0(baseline.load("Bihar", 2019).mx)
    for d in ("model", "unwpp"):
        assert lifetable.e0(baseline.load("Bihar", 2019, sources=Sources(deaths=d)).mx) == base
    assert len(AGE_STARTS) == len(baseline.load("Bihar", 2019, sources=UN).death_factor)
