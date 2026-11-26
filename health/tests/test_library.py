"""The measure library itself: every file loads, and Bengaluru's air measures score.

These run the real files in interventions/library/, not the fixtures, so a broken or
unsourced measure fails here.
"""
import re

import pytest

from airhealth import measures, score

BENGALURU_AIR = ["road_vacuum_sweeping", "construction_dust_controls", "road_paving",
                 "waste_collection_burning_ban", "electric_buses", "old_vehicle_retirement",
                 "electric_two_three_wheelers", "dg_set_replacement", "lpg_refill_subsidy"]

# A measure goes here only with an entry in data/MISSING.md saying why it has no citable cut.
WRITTEN_UP_AS_MISSING: set[str] = set()


@pytest.mark.parametrize("mid", BENGALURU_AIR)
def test_bengaluru_air_measure_scores(mid):
    if mid in WRITTEN_UP_AS_MISSING:
        pytest.skip("no citable cut; see data/MISSING.md")
    s = score.city("Bengaluru", [mid], n=200, curves=["gemm_ncd_lri"])[0]
    assert s.kind == "air" and s.scope == "city"
    assert s.status in ("scored", "no_cost", "pays_for_itself")
    assert s.pm25_change["median"] < 0


@pytest.mark.parametrize("mid", BENGALURU_AIR)
def test_bengaluru_air_measure_is_sourced(mid):
    """Every number is backed by evidence read at source (key O); none is a placeholder, and
    the odds are flagged as a judgement."""
    if mid in WRITTEN_UP_AS_MISSING:
        pytest.skip("no citable cut; see data/MISSING.md")
    m = measures.library()[mid]
    assert m.placeholders == ()
    assert {e.key for e in m.evidence} == {"O"}
    assert m.cities == ("Bengaluru",)
    assert m.p_success_basis.startswith("judgement:")


def test_bengaluru_measures_on_an_all_origins_study_are_upper_bounds():
    out = score.city("Bengaluru", ["road_paving", "waste_collection_burning_ban"],
                     study="cstep_bengaluru2022_cmb", n=100, curves=["gemm_ncd_lri"])
    paving, waste = out
    assert paving.status == "scored"
    assert "upper_bound_all_origins" in {f.code for f in paving.flags}
    # CSTEP's receptor model does not report waste burning: not reported is not zero
    assert waste.status == "not_scored" and "waste_burning" in waste.reason


def test_library_is_clean():
    assert measures.check_library() == []


# ---- Bengaluru exposure measures (and the one long shot) ----

BENGALURU_EXPOSURE = ["home_purifiers", "school_purifiers", "n95_winter", "smog_tower"]


@pytest.mark.parametrize("mid", BENGALURU_EXPOSURE)
def test_bengaluru_exposure_measure_scores(mid):
    s = score.city("Bengaluru", [mid], n=200, curves=["gemm_ncd_lri"])[0]
    assert s.kind == "exposure" and "covered_only" in {f.code for f in s.flags}
    assert s.status in ("scored", "no_cost", "pays_for_itself")
    assert s.pm25_change["median"] < 0     # what the covered people breathe


@pytest.mark.parametrize("mid", BENGALURU_EXPOSURE)
def test_bengaluru_exposure_measure_is_sourced(mid):
    """No placeholders; every number has a locator; the odds are a flagged judgement."""
    m = measures.library()[mid]
    assert m.placeholders == ()
    assert all(e.locator and e.url for e in m.evidence)
    assert m.cities == ("Bengaluru",)
    assert m.p_success_basis.startswith("judgement:")


@pytest.mark.parametrize("mid", BENGALURU_EXPOSURE)
def test_exposure_odds_say_how_they_compare_and_why(mid):
    """Lower odds for exposure measures are a guideline, not a rule (controller ruling): each
    basis must say how it compares with the air measures and speak to adoption or use."""
    basis = measures.library()[mid].p_success_basis.lower()
    assert basis
    assert "air measures" in basis
    assert re.search(r"\b(adoption|use)\b", basis)


def test_smog_tower_is_a_long_shot():
    assert measures.library()["smog_tower"].long_shot
    s = score.city("Bengaluru", ["smog_tower"], n=100, curves=["gemm_ncd_lri"])[0]
    assert "long_shot" in {f.code for f in s.flags}


def test_policy_only_cost_is_flagged_partial():
    s = score.city("Bengaluru", ["waste_collection_burning_ban"], n=100,
                   curves=["gemm_ncd_lri"])[0]
    partial = [f for f in s.flags if f.code == "partial_cost"]
    assert len(partial) == 1 and "leaves out" in partial[0].text
    assert partial[0].text == measures.library()["waste_collection_burning_ban"].cost.partial
