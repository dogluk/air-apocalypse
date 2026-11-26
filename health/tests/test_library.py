"""The measure library itself: every file loads, and Bengaluru's air measures score.

These run the real files in interventions/library/, not the fixtures, so a broken or
unsourced measure fails here.
"""
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
