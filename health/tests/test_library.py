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
    assert m.cities == (None if mid in WIDENED else ("Bengaluru",))
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
    assert m.cities == (None if mid in WIDENED else ("Bengaluru",))
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


# ---- Regional measures (stubble smoke, coal power plants) ----

REGIONAL = ["stubble_pes_upfront", "happy_seeder_subsidy", "punjab_out_of_rice", "fgd_scrubbers"]
STUBBLE = ["stubble_pes_upfront", "happy_seeder_subsidy", "punjab_out_of_rice"]


@pytest.mark.parametrize("mid", REGIONAL)
def test_regional_measure_reach_scores(mid):
    if mid in WRITTEN_UP_AS_MISSING:
        pytest.skip("see data/MISSING.md")
    s = score.region(mid, n=200, curves=["gemm_ncd_lri"])
    assert s.scope == "region" and s.status in ("scored", "no_cost", "pays_for_itself")
    assert s.pm25_change["median"] < 0


@pytest.mark.parametrize("mid", REGIONAL)
def test_regional_measure_is_sourced(mid):
    """Every number read at source (key O), none a placeholder; the odds a flagged judgement."""
    m = measures.library()[mid]
    assert m.scope == "region" and m.placeholders == ()
    assert {e.key for e in m.evidence} == {"O"}
    assert all(e.locator and e.url for e in m.evidence)
    assert m.p_success_basis.startswith("judgement:")


@pytest.mark.parametrize("mid", STUBBLE)
def test_stubble_measures_carry_the_fallback_flag(mid):
    """The stubble table is a stand-in for a published source-receptor result (Task 10), about
    14 times smaller than Lan et al. 2022's national figure: every result says so."""
    m = measures.library()[mid]
    assert m.region.receptor == "receptor_stubble.csv"
    s = score.city("Delhi", [mid], n=100, curves=["gemm_ncd_lri"])[0]
    fallback = [f for f in s.flags if f.code == "receptor_fallback"]
    assert len(fallback) == 1
    assert "fallback" in fallback[0].text and "14 times smaller" in fallback[0].text
    assert "understated" in fallback[0].text


def test_scrubbers_use_the_power_plant_table_not_the_coal_energy_one():
    """Two coal tables are kept side by side, never averaged: scrubbers act on power plants,
    so they use Cropper et al. 2021's (no fallback flag); the McDuffie one stays a fallback."""
    m = measures.library()["fgd_scrubbers"]
    assert m.region.receptor == "receptor_power_cropper2021.csv"
    s = score.city("Delhi", ["fgd_scrubbers"], n=100, curves=["gemm_ncd_lri"])[0]
    codes = {f.code for f in s.flags}
    assert "receptor_basis" in codes and "receptor_fallback" not in codes
    assert score.receptor_basis("receptor_energy_coal.csv", key="fallback")


def test_cropper_receptor_is_its_state_figure():
    """Each district takes its state's Table S2 value; states the table omits get no row."""
    import pandas as pd

    from airhealth import paths
    t = measures.receptor("receptor_power_cropper2021.csv")
    s2 = pd.read_csv(paths.DATA / "cropper2021_state_power_pm25.csv").set_index("state")
    assert set(t.state) == set(s2.index)
    for state, g in t.groupby("state"):
        assert (g.delta_pm25_full == -s2.loc[state, "pm25_power_2018"]).all()
    assert "Ladakh" not in set(t.state) and "Chandigarh" not in set(t.state)


def test_stubble_reaches_delhi():
    assert score.city("Delhi", ["stubble_pes_upfront"], n=100,
                      curves=["gemm_ncd_lri"])[0].status == "scored"


@pytest.mark.xfail(strict=True, reason=(
    "receptor_stubble.csv (the McDuffie fallback) counts crop fires from every origin, so "
    "Bengaluru gets a small change from southern burning that a Punjab measure would not touch; "
    "it passes once a Punjab-origin source-receptor table replaces it (data/MISSING.md)"))
def test_stubble_does_not_reach_bengaluru():
    assert score.city("Bengaluru", ["stubble_pes_upfront"], n=100,
                      curves=["gemm_ncd_lri"])[0].status in ("not_applicable", "not_scored")


# ---- The rest of the first library: industry, brick kilns, the cloud-seeding long shot ----

OTHERS = ["emissions_market", "zigzag_kilns", "industrial_fuel_switch", "winter_cloud_seeding"]
SCORED = ("scored", "no_cost", "pays_for_itself")


@pytest.mark.parametrize("mid", OTHERS)
def test_other_measure_loads_and_scores_where_it_applies(mid):
    m = measures.library()[mid]
    assert m.scope == "city" and len(m.cities) == 1
    s = score.city(m.cities[0], [mid], n=100, curves=["gemm_ncd_lri"])[0]
    assert s.status in SCORED
    assert s.pm25_change["median"] < 0


@pytest.mark.parametrize("mid", OTHERS)
def test_other_measure_is_sourced(mid):
    """Every number backed by evidence with a link and a locator, none a placeholder; the odds a
    flagged judgement. Only the cloud-seeding long shot rests on press accounts (key S)."""
    m = measures.library()[mid]
    assert m.placeholders == ()
    assert all(e.locator and e.url for e in m.evidence)
    assert {e.key for e in m.evidence} == ({"S"} if mid == "winter_cloud_seeding" else {"O"})
    assert m.p_success_basis.startswith("judgement:")


def test_emissions_market_is_surat_industry_at_the_trial_effect():
    """Greenstone et al. 2025: the market cut plants' emissions 20-30% against the old rules."""
    m = measures.library()["emissions_market"]
    (t,) = m.targets
    assert t.cause == "industry" and (t.cut.p5, t.cut.p95) == (0.20, 0.30)
    assert m.cost.units.median == 906 and m.cost.currency == "USD"


def test_zigzag_kilns_pay_for_themselves():
    """The owner earns the conversion back in a season or two (CSE 2017): society's net cost is
    below zero, so the measure is listed apart, not ranked by a ratio."""
    s = score.city("Patna", ["zigzag_kilns"], n=100, curves=["gemm_ncd_lri"])[0]
    assert s.status == "pays_for_itself"
    assert s.per_curve["gemm_ncd_lri"]["expected_life_years_per_crore"] is None


def test_cloud_seeding_is_a_long_shot_with_near_zero_odds():
    m = measures.library()["winter_cloud_seeding"]
    assert m.long_shot and m.p_success <= 0.05
    s = score.city("Delhi", ["winter_cloud_seeding"], n=100, curves=["gemm_ncd_lri"])[0]
    codes = {f.code for f in s.flags}
    assert {"long_shot", "evidence_S", "odds_judgement"} <= codes


def test_library_has_about_twenty_measures():
    assert len(measures.library()) + len(WRITTEN_UP_AS_MISSING) >= 20


def test_every_measure_runs_in_every_city():
    """No exception anywhere; every result has a known status (n kept tiny: statuses only)."""
    from airhealth import causes
    for city in causes.known_cities():
        for s in score.city(city, n=50, curves=["gemm_ncd_lri"]):
            assert s.status in score.STATUSES


def test_school_purifiers_reach_children_only():
    m = measures.library()["school_purifiers"]
    assert m.exposure.ages == (5, 19)
    s = score.city("Bengaluru", ["school_purifiers"], n=200, curves=["gemm_ncd_lri"])[0]
    assert s.per_curve["gemm_ncd_lri"]["life_years"]["median"] == 0     # adult-only curve
    assert "age_group" in {f.code for f in s.flags}


# ---- Measures for every city where their numbers transfer (plan D Task 5) ----
# Rule: a measure is widened only when (a) its cut (or exposure hours and cut) is read from a
# source not about its one city alone, (b) its cost is per person, household or unit at a price
# not tied to that city's contract or budget, with no count of that city's units, and (c) its
# covered share is not a ratio for that city or its state. One city-specific number blocks it.

WIDENED: set[str] = {"home_purifiers", "old_vehicle_retirement"}

# General variants: a single-city measure whose city-specific numbers are replaced by all-India
# ones read at source; each runs in every city except the one whose own file keeps its own values.
GENERAL = {"school_purifiers_india": "school_purifiers"}


@pytest.mark.parametrize("mid", sorted(WIDENED))
def test_widened_measure_is_for_every_city(mid):
    m = measures.library()[mid]
    assert m.cities is None                                # cities = "all"
    assert m.min_share_pct is None                         # no source gives a threshold
    assert "Bengaluru" not in m.name and "Bengaluru" not in m.who_reaches
    assert "Widened to every city" in m.notes


@pytest.mark.parametrize("mid", sorted(WIDENED) + sorted(GENERAL))
def test_widened_measure_scores_outside_bengaluru(mid):
    # Delhi has no APnA study (the default), so an air measure is scored on one of its own
    # studies; in the all-India table it is simply not scored there (not reported is not zero).
    study = "arai_teri_delhi2018_receptor" if measures.library()[mid].kind == "air" else None
    s = score.city("Delhi", [mid], study=study, n=100, curves=["gemm_ncd_lri"])[0]
    assert s.status in ("scored", "no_cost", "pays_for_itself", "not_applicable")
    assert "Bengaluru" not in s.reason
    assert s.pm25_change["median"] < 0


def test_every_single_city_measure_says_why():
    """A measure kept to one city names, in a 'city-specific:' line in its notes, the number
    that blocks widening (the plan asks this of Bengaluru-only ones; it holds for every city)."""
    for mid, m in measures.library().items():
        if m.cities is not None and len(m.cities) == 1:
            assert "city-specific:" in m.notes, mid


@pytest.mark.parametrize("variant,original", sorted(GENERAL.items()))
def test_general_variant_leaves_out_the_original_city(variant, original):
    from airhealth import causes
    lib = measures.library()
    (home,) = lib[original].cities
    assert set(lib[variant].cities) == set(causes.known_cities()) - {home}
    assert "city-specific:" in lib[original].notes


def test_school_purifiers_india_uses_all_india_ratios():
    """Only the Karnataka numbers change: the enrolled share and the pupil-teacher ratio are
    India's (UDISE+ 2023-24); cut and hours rest on the same sources as Bengaluru's file."""
    lib = measures.library()
    g, b = lib["school_purifiers_india"], lib["school_purifiers"]
    assert g.exposure.cut == b.exposure.cut and g.exposure.hours == b.exposure.hours
    assert g.exposure.ages == b.exposure.ages
    assert g.exposure.covered.median != b.exposure.covered.median
    assert {e.key for e in g.evidence} == {"O"} and g.placeholders == ()
    covered = [e for e in g.evidence if "exposure.covered" in e.fields]
    assert "Karnataka" not in covered[0].derivation
