"""score.py: one measure x one city -> an ordinary Intervention, run, and labelled."""
import dataclasses
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from airhealth import causes, exposure, measures, months, places, score, simulate
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


REGION = FIXTURES.parent / "library" / "air_region.toml"


def region_library(tmp_path, rows: str):
    """A library holding only the region fixture, beside a receptor table with these rows."""
    (tmp_path / "air_region.toml").write_text(REGION.read_text())
    (tmp_path / "receptor_fixture.csv").write_text("district,state,delta_pm25_full\n" + rows)
    return tmp_path


def test_regional_city_part_uses_the_receptor(tmp_path):
    # Mumbai's map units are the districts Mumbai and Mumbai Suburban (data/cities.csv)
    folder = region_library(tmp_path, "Mumbai,Maharashtra,-2.0\nMumbai Suburban,Maharashtra,-1.0\n"
                                      "Thane,Maharashtra,-0.4\n")
    m = measures.load(folder / "air_region.toml")
    iv, status, reason, flags, trail = score.compile(m, "Mumbai", folder=folder)
    state = exposure.cells(places.resolve("Maharashtra"), "acag_total")
    pop = state.set_index("unit").population
    want = (-2.0 * pop["Mumbai"] - 1.0 * pop["Mumbai Suburban"]) / (pop["Mumbai"] + pop["Mumbai Suburban"])
    city = places.resolve("Mumbai", kind="city")
    assert status == "scored" and iv.places == [city] and iv.change_kind == "delta"
    assert iv.scale == {city.label: pytest.approx(want)}
    assert trail["region"]["city_delta_pm25_full"] == pytest.approx(want)
    q = np.array([0.5])
    assert iv.annual_change(city, q)[0] == pytest.approx(m.region.cut.median * want)
    assert "airhealth score --region air_region" in reason and "regional" in codes(flags)

    s = score.city("Mumbai", ["air_region"], folder=folder, n=50, curves=CURVE)[0]
    assert s.status == "scored" and s.pm25_change["median"] < 0
    summary = s.per_curve[CURVE[0]]
    assert summary["life_years"]["median"] > 0
    assert all(summary[k] is None for k in (*score.RATIO_KEYS, *score.COST_KEYS))
    json.dumps(score.to_json([s]), allow_nan=False)


def test_city_outside_the_receptor_domain_is_not_scored(tmp_path):
    folder = region_library(tmp_path, "Mumbai,Maharashtra,-2.0\nNorth Goa,Goa,0\nSouth Goa,Goa,0\n")
    out = {s.place: s for c in ("Delhi", "Panaji", "Mumbai")
           for s in score.city(c, ["air_region"], folder=folder, n=50, curves=CURVE)}
    assert out["Delhi"].status == "not_scored" and out["Delhi"].run is None
    assert "outside the source-receptor study's area" in out["Delhi"].reason
    assert out["Panaji"].status == "not_applicable"           # every unit's change is 0
    assert out["Mumbai"].status == "not_scored"                # Mumbai Suburban has no row
    assert "Mumbai Suburban" in out["Mumbai"].reason


def test_region_reach_sums_its_districts(tmp_path):
    rows = "Mumbai,Maharashtra,-2.0\nThane,Maharashtra,-0.5\nNorth Goa,Goa,0\n"
    folder = region_library(tmp_path, rows)
    s = score.region("air_region", folder=folder, n=40, curves=CURVE)
    assert s.status == "pays_for_itself" or s.status == "scored"
    assert [p.name for p in s.run.intervention.places] == ["Mumbai", "Thane"]  # 0 rows left out
    assert "regional" in codes(s.flags) and s.trail["region"]["districts"] == 2
    m = measures.load(folder / "air_region.toml")
    total = 0.0
    for name, full in (("Mumbai", -2.0), ("Thane", -0.5)):
        p = places.resolve(f"{name}, Maharashtra", kind="district")
        one = dataclasses.replace(s.run.intervention, places=[p], scale={p.label: full})
        total = total + simulate.run(one, map_name="acag_total", curves=CURVE, n=40,
                                     seed=0).per_curve[CURVE[0]].life_years
    np.testing.assert_allclose(s.run.per_curve[CURVE[0]].life_years, total, rtol=1e-9)
    # the whole cost: units x annual over the duration, in 2025 rupees
    assert s.per_curve[CURVE[0]]["cost_inr"]["median"] > 0
    assert m.cost.driver == "unit"


def test_region_measure_with_household_cost_is_refused(tmp_path):
    t = REGION.read_text().replace('driver = "unit"', 'driver = "household"')
    t = t.replace('units = { dist = "normal", p5 = 1e6, p95 = 2e6 }\nunit = "acre"\n', "")
    t = t.replace('"cost.units", ', "")
    (tmp_path / "m.toml").write_text(t)
    with pytest.raises(measures.Invalid, match="^cost.driver"):
        measures.load(tmp_path / "m.toml")


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
