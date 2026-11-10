import pytest

from airhealth import baseline, exposure, provenance
from airhealth.places import resolve

INDIA = resolve("India")

# AQLI Annual Update 2025 release, gadm1 file, 'NCT of Delhi', column pm2023 (88.35).
AQLI_DELHI_2023 = 88.35


@pytest.mark.parametrize("map_name", ["aqli", "acag_total"])
def test_no_population_lost_in_join(map_name):
    source_total = provenance.load_sources()[f"exposure_{map_name}.csv"]["population_total"]
    c = exposure.cells(INDIA, map_name)
    assert c.population.sum() == pytest.approx(source_total, rel=0.005)
    missing = set(baseline.states()) - {"India"} - set(c.state)
    assert not missing


def test_delhi_aqli_matches_published():
    assert exposure.mean(resolve("Delhi"), "aqli", 2023) == pytest.approx(AQLI_DELHI_2023, abs=0.5)


def test_cpcb_refuses_states():
    with pytest.raises(ValueError, match="cit"):
        exposure.cells(resolve("Delhi"), "cpcb")
    with pytest.raises(ValueError, match="cit"):
        exposure.cells(INDIA, "cpcb")


def test_acag_exceeds_aqli_where_dusty():
    rajasthan = resolve("Rajasthan")
    assert exposure.mean(rajasthan, "acag_total", 2023) > exposure.mean(rajasthan, "aqli", 2023)


def test_cells_shape():
    for map_name in exposure.MAPS:
        place = resolve("Mumbai") if map_name == "cpcb" else INDIA
        c = exposure.cells(place, map_name)
        assert list(c.columns) == ["state", "unit", "pm25", "population"]
        assert (c.pm25 > 0).all() and (c.population > 0).all()
    assert len(exposure.cells(resolve("Kerala"), "gbd2019")) == 1
    assert len(exposure.cells(resolve("Delhi"), "aqli")) == 1
    assert len(exposure.cells(resolve("Pune"), "aqli")) == 1


def test_gbd2019_published_values():
    # Pandey et al. 2021, appendix table 3: Delhi 217.6, Kerala 15.8.
    assert exposure.mean(resolve("Delhi"), "gbd2019") == 217.6
    assert exposure.mean(resolve("Kerala"), "gbd2019") == 15.8
    with pytest.raises(ValueError, match="state"):
        exposure.cells(resolve("Pune"), "gbd2019")


def test_unknown_map_and_year():
    with pytest.raises(ValueError, match="aqli"):
        exposure.cells(INDIA, "nasa")
    with pytest.raises(KeyError, match="1990"):
        exposure.cells(INDIA, "aqli", 1990)
