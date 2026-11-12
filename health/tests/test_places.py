import pandas as pd
import pytest

from airhealth import baseline, paths, places
from airhealth.places import Place, resolve


def test_aliases_resolve():
    assert resolve("Orissa") == resolve("Odisha")
    assert resolve("NCT of Delhi").name == "Delhi"
    assert resolve("delhi") == Place("state", "Delhi", "Delhi")


def test_unknown_place_suggests():
    with pytest.raises(KeyError, match="Delhi"):
        resolve("Dilli")


def test_country_and_city():
    assert resolve("India") == Place("country", "India", None)
    assert resolve("Bangalore") == Place("city", "Bengaluru", "Karnataka")


def test_district_needs_state_when_ambiguous():
    with pytest.raises(KeyError, match="Himachal"):
        resolve("Bilaspur")                       # a district in Chhattisgarh and in Himachal Pradesh
    p = resolve("Aurangabad, Bihar")              # Aurangabad itself is a city now (Maharashtra)
    assert (p.kind, p.name, p.state) == ("district", "Aurangabad", "Bihar")


def test_canonical_state_covers_every_baseline_spelling():
    for s in baseline.states():
        assert places.canonical_state(s) == s
    assert places.canonical_state("JAMMU & KASHMIR (UT)") == "Jammu & Kashmir"
    assert places.canonical_state("Telengana") == "Telangana"
    assert places.canonical_state("Bihār") == "Bihar"
    with pytest.raises(KeyError):
        places.canonical_state("Atlantis")


def test_fifty_cities_cover_every_apna_airshed():
    c = pd.read_csv(paths.DATA / "cities.csv")
    a = pd.read_csv(paths.DATA / "apna_source_apportionment.csv")
    assert len(c) == 50 and c.city.is_unique
    assert sorted(c.apna_airshed.dropna()) == sorted(a.City)
    assert c.set_index("city").apna_airshed.isna()["Delhi"]


def test_existing_city_rows_unchanged():
    c = pd.read_csv(paths.DATA / "cities.csv").set_index("city")
    assert c.loc["Delhi", "population"] == 16349831
    assert c.loc["Jaipur", "population"] == 3046163
    assert c.loc["Mumbai", "aqli_units"] == "Mumbai City;Mumbai Suburban"


def test_new_city_names_resolve():
    assert resolve("Kanpur") == Place("city", "Kanpur", "Uttar Pradesh")
    assert resolve("Aurangabad").kind == "city"
    assert resolve("Aurangabad").state == "Maharashtra"
    assert resolve("Aurangabad, Bihar").kind == "district"
    assert resolve("Prayagraj") == resolve("Allahabad") == Place("city", "Allahabad", "Uttar Pradesh")
    assert resolve("Patna").kind == "city" and resolve("Patna", kind="district").state == "Bihar"
    for name in ("Bengaluru", "Mumbai", "Pune", "Hyderabad"):
        assert resolve(name).kind == "city"
    assert resolve("Maharashtra").kind == "state"


def test_multi_town_airsheds_sum_their_census_entries():
    c = pd.read_csv(paths.DATA / "cities.csv").set_index("city")
    assert c.loc["Raipur-Durg-Bhilai", "census_name"] == "Raipur U.A.;Durg-Bhilainagar U.A."
    assert c.loc["Raipur-Durg-Bhilai", "population"] == 1123558 + 1064222
    assert pd.isna(c.loc["Aurangabad", "cpcb_cities"])        # CPCB's Aurangabad is the Bihar one
