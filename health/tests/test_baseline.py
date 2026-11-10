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
