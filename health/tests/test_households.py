import pandas as pd
import pytest

from airhealth import measures, paths


def test_every_city_has_households():
    h = pd.read_csv(paths.DATA / "city_households.csv")
    c = pd.read_csv(paths.DATA / "cities.csv")
    assert sorted(h.city) == sorted(c.city)
    assert (h.set_index("city").population == c.set_index("city").population).all()
    assert (h.set_index("city").census_name == c.set_index("city").census_name).all()
    assert h.households.gt(0).all()


def test_household_size_is_plausible():          # a sanity band, not a source value
    assert 3 < measures.persons_per_household("Bengaluru") < 6


def test_every_city_household_size_is_plausible():
    for city in pd.read_csv(paths.DATA / "cities.csv").city:
        assert 3 < measures.persons_per_household(city) < 7


def test_unknown_city_is_a_key_error():
    with pytest.raises(KeyError):
        measures.persons_per_household("Atlantis")
