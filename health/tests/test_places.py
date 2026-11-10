import pytest

from airhealth import baseline, places
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
    with pytest.raises(KeyError, match="Bihar"):
        resolve("Aurangabad")
    p = resolve("Aurangabad, Bihar")
    assert (p.kind, p.name, p.state) == ("district", "Aurangabad", "Bihar")


def test_canonical_state_covers_every_baseline_spelling():
    for s in baseline.states():
        assert places.canonical_state(s) == s
    assert places.canonical_state("JAMMU & KASHMIR (UT)") == "Jammu & Kashmir"
    assert places.canonical_state("Telengana") == "Telangana"
    assert places.canonical_state("Bihār") == "Bihar"
    with pytest.raises(KeyError):
        places.canonical_state("Atlantis")
