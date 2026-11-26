"""score.py: one measure x one city -> an ordinary Intervention, run, and labelled."""
import dataclasses
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from airhealth import causes, measures, months, places, score
from airhealth.intervention import Dist
from airhealth.months import MONTH_DAYS

FIXTURES = Path(__file__).parent / "fixtures" / "library"
CURVE = ["gemm_ncd_lri"]


def fx(name):
    return measures.load(FIXTURES / f"{name}.toml")


def codes(flags):
    return {f.code for f in flags}


def test_air_change_is_share_times_cut():
    iv, status, *_ = score.compile(fx("air_dust"), "Bengaluru", study="apna_2015")
    assert status == "scored"
    share = causes.shares("Bengaluru", "apna_2015", "annual")["dust"]
    q = np.array([0.5])
    # all-year cut c: annual pct = -share * c (the shape's day-weighted mean is 1)
    assert iv.change_kind == "pct" and iv.places == [places.resolve("Bengaluru", kind="city")]
    assert iv.annual_change(iv.places[0], q)[0] == pytest.approx(
        -share * fx("air_dust").targets[0].cut.median)


def test_winter_cut_uses_the_shape():
    iv, _, _, flags, trail = score.compile(fx("air_winter"), "Bengaluru", study="apna_2015")
    place = places.resolve("Bengaluru", kind="city")
    s = months.shape(place).values
    share = causes.shares("Bengaluru", "apna_2015", "annual")["transport"]
    winter = np.isin(np.arange(1, 13), [11, 12, 1, 2])
    expected = -share * 0.3 * (MONTH_DAYS * s)[winter].sum() / 365
    assert iv.annual_change(place, np.array([0.5]))[0] == pytest.approx(expected)
    assert "annual_share_flat" in codes(flags)
    assert trail["share_basis"][1] == "apna_2015/annual"
    assert trail["cuts"] == [{"cause": "transport", "months": [1, 2, 11, 12], "p5": 0.3,
                              "p95": 0.3, "kind": "fixed"}]


def test_all_origins_study_is_scored_as_upper_bound():
    iv, status, reason, flags, trail = score.compile(fx("air_dust"), "Bengaluru",
                                                     study="cstep_bengaluru2022_cmb")
    assert status == "scored" and reason == "" and iv is not None
    assert "upper_bound_all_origins" in codes(flags)
    # seasonal groups win over the annual one; the partial monsoon group is never used
    assert trail["share_basis"][1] == "cstep_bengaluru2022_cmb/winter"
    assert trail["share_basis"][4] == "cstep_bengaluru2022_cmb/summer"
    assert trail["share_basis"][7] == "cstep_bengaluru2022_cmb/annual"
    assert trail["shares"]["dust"][0] == pytest.approx(24.0)
    assert trail["shares"]["dust"][6] == pytest.approx(25.7)


def test_region_split_study_is_not_scored(monkeypatch):
    t = causes.table()
    rows = t[(t.city == "Bengaluru") & (t.study == "apna_2015")].copy()
    rows = rows.assign(study="geo_fixture", origin="region")
    rows.loc[rows.source_harmonised != "outside", "source_harmonised"] = "local_all"
    monkeypatch.setattr(causes, "table", lambda: pd.concat([t, rows], ignore_index=True))
    iv, status, reason, *_ = score.compile(fx("air_dust"), "Bengaluru", study="geo_fixture")
    assert iv is None and status == "not_scored" and "where" in reason


def test_unreported_cause_is_not_zero(monkeypatch):
    t = causes.table()
    rows = t[(t.city == "Bengaluru") & (t.study == "apna_2015")
             & (t.source_harmonised != "waste_burning")].copy()
    rows = rows.assign(study="tiny_fixture")
    monkeypatch.setattr(causes, "table", lambda: pd.concat([t, rows], ignore_index=True))
    iv, status, reason, *_ = score.compile(fx("air_waste"), "Bengaluru", study="tiny_fixture")
    assert iv is None and status == "not_scored" and "waste_burning" in reason


def test_some_unreported_causes_are_flagged(monkeypatch):
    t = causes.table()
    rows = t[(t.city == "Bengaluru") & (t.study == "apna_2015")
             & (t.source_harmonised != "waste_burning")].copy()
    rows = rows.assign(study="tiny_fixture")
    monkeypatch.setattr(causes, "table", lambda: pd.concat([t, rows], ignore_index=True))
    both = dataclasses.replace(fx("air_waste"),
                               targets=fx("air_waste").targets + fx("air_dust").targets)
    iv, status, _, flags, trail = score.compile(both, "Bengaluru", study="tiny_fixture")
    assert status == "scored"
    missing = [f for f in flags if f.code == "not_reported"]
    assert len(missing) == 1 and "waste_burning" in missing[0].text
    assert trail["shares"]["waste_burning"] is None
    assert [c for c, _ in iv.change.months[0].terms] == [pytest.approx(-23.0)]


def test_outside_share_is_never_cut():
    iv, *_ = score.compile(fx("air_dust"), "Bengaluru", study="apna_2015")
    share = causes.shares("Bengaluru", "apna_2015", "annual")
    for month in iv.change.months:
        assert [c for c, _ in month.terms] == [-share["dust"]]
    assert -share["outside"] not in [c for c, _ in iv.change.months[0].terms]


def test_min_share_below_is_not_applicable():
    m = dataclasses.replace(fx("air_dust"), min_share_pct=50.0)
    iv, status, reason, *_ = score.compile(m, "Bengaluru", study="apna_2015")
    assert iv is None and status == "not_applicable" and "23" in reason


def test_exposure_is_covered_only():
    iv, _, _, flags, trail = score.compile(fx("exposure_purifier"), "Bengaluru")
    assert iv.covered is not None and iv.cost_per_covered and "covered_only" in codes(flags)
    # all-year: annual pct = -100 x hours x cut
    assert iv.annual_change(iv.places[0], np.array([0.5]))[0] == pytest.approx(-100 * 0.5 * 0.5)
    assert trail["exposure"]["months"] == list(range(1, 13))


def test_household_cost_counts_households():
    iv, _, _, _, trail = score.compile(fx("exposure_purifier"), "Bengaluru")
    place = places.resolve("Bengaluru", kind="city")
    from airhealth import exposure
    people = exposure.cells(place, "acag_total").population.sum()
    count = people / measures.persons_per_household("Bengaluru")
    assert iv.cost_annual.median == pytest.approx(2000 * count)
    assert iv.cost_once.median == pytest.approx(8000 * count)
    assert trail["cost"]["units_count"] == pytest.approx(count)


def test_person_cost_counts_people_and_run_agrees():
    s = score.city("Bengaluru", ["air_dust"], folder=FIXTURES, n=50, curves=CURVE)[0]
    assert s.run.intervention.cost_annual.median == pytest.approx(100 * s.run.population)


def test_no_cost_is_shown_unranked():
    s = score.city("Bengaluru", ["no_cost"], folder=FIXTURES, n=100, curves=CURVE)[0]
    assert s.status == "no_cost" and s.per_curve["gemm_ncd_lri"]["life_years"]["median"] > 0
    assert s.per_curve["gemm_ncd_lri"]["life_years_per_crore_if_works"] is None
    assert s.per_curve["gemm_ncd_lri"]["inr_per_life_year_if_works"] is None


def test_pays_for_itself_is_not_ranked():
    s = score.city("Bengaluru", ["pays"], folder=FIXTURES, n=100, curves=CURVE)[0]
    assert s.status == "pays_for_itself" and s.reason
    r = s.per_curve["gemm_ncd_lri"]
    assert r["life_years"]["median"] > 0 and r["cost_inr"]["median"] > 0
    assert r["life_years_per_crore_if_works"] is None
    assert r["expected_life_years_per_crore"] is None


def test_city_not_listed_is_not_applicable():
    s = score.city("Bengaluru", ["air_city"], folder=FIXTURES, n=50, curves=CURVE)[0]
    assert s.status == "not_applicable" and s.run is None and s.per_curve == {}
    assert "Bengaluru" in s.reason


def test_region_measure_is_not_scored_yet():
    s = score.city("Bengaluru", ["air_region"], folder=FIXTURES, n=50, curves=CURVE)[0]
    assert s.status == "not_scored" and "regional" in s.reason and "regional" in codes(s.flags)


def test_placeholders_are_flagged():
    s = score.city("Bengaluru", ["air_dust"], folder=FIXTURES, n=100, curves=CURVE)[0]
    assert any(f.code == "placeholder" for f in s.flags)
    assert sum(f.code == "placeholder" for f in s.flags) == 2
    assert "odds_judgement" in codes(s.flags) and "borrowed_shape" not in codes(s.flags)
    assert s.study == "apna_2015" and s.status == "scored"
    assert s.pm25_change["median"] < 0


def test_evidence_keys_are_flagged():
    m = fx("air_dust")
    ev = measures.Evidence(("targets.dust.cut",), "A report", "https://example.org", "p. 1",
                           "S", "2026-11-27", "")
    m = dataclasses.replace(m, evidence=(ev,), placeholders=("cost.annual",),
                            p_success_basis="from A report, table 2")
    _, _, _, flags, trail = score.compile(m, "Bengaluru")
    assert "evidence_S" in codes(flags) and "odds_judgement" not in codes(flags)
    assert trail["evidence"][0]["source"] == "A report"


def test_city_without_apna_is_not_scored(monkeypatch):
    t = causes.table()
    monkeypatch.setattr(causes, "table", lambda: t[~((t.city == "Bengaluru")
                                                      & t.study.str.startswith("apna"))])
    out = score.city("Bengaluru", ["air_dust", "exposure_purifier"], folder=FIXTURES, n=50,
                     curves=CURVE)
    assert out[0].status == "not_scored" and "APnA" in out[0].reason
    assert out[1].status == "scored"


def test_json_has_the_page_fields():
    out = score.to_json(score.city("Bengaluru", folder=FIXTURES, n=100, curves=CURVE),
                        place="Bengaluru")
    assert out["place"] == "Bengaluru" and out["assumptions"] == list(score.ASSUMPTIONS)
    assert {"study", "map", "discount", "n", "seed"} <= set(out)
    ids = [m["measure"] for m in out["measures"]]
    assert ids == sorted(ids)
    m = out["measures"][0]
    assert {"measure", "name", "kind", "scope", "status", "reason", "who_reaches", "p_success",
            "flags", "pm25_change", "per_curve", "trail"} <= set(m)
    assert "run" not in m
    assert all(s["status"] in score.STATUSES for s in out["measures"])
    json.dumps(out, allow_nan=False)
