"""Ranking benchmarks (benchmarks/rank_run.py): published cost rankings against library measures.

A tested case that needs a regional measure scored over its whole reach (about two minutes a
measure) runs only with AIRHEALTH_SLOW_BENCHMARKS=1; `python benchmarks/rank_run.py` always runs
it. Everything else here is quick."""
import importlib.util
import os
from pathlib import Path

import numpy as np
import pytest

from airhealth import paths, prices, score

_spec = importlib.util.spec_from_file_location("rank_run", paths.HEALTH / "benchmarks" / "rank_run.py")
rb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rb)

FIXTURES = Path(__file__).parent / "fixtures" / "library"
REQUIRED = ("study", "source_url", "locator", "published", "published_text", "published_currency",
            "published_year", "kind", "measure", "place", "curve", "map", "discount", "expected_ratio",
            "tolerance", "band_why", "in_short", "tested")
SLOW = os.environ.get("AIRHEALTH_SLOW_BENCHMARKS") == "1"

CASE = dict(id="fixture", study="fixture", source_url="", locator="", published=1.0,
            published_text="", published_currency="INR", published_year=2025, kind="per_life",
            measure="air_dust", other_measure="", place="Bengaluru", causes_study="apna_2015",
            curve="gemm_ncd_lri", map="acag_total", discount=0.0, cost_basis="total",
            expected_ratio=1.0, tolerance=0.1, band_why="", in_short="", tested=True,
            folder=str(FIXTURES), n=50)


def test_rank_cases_are_complete():
    cases = rb.load_cases()
    assert cases
    for c in cases:
        assert not [k for k in REQUIRED if k not in c], c["id"]
        assert c["kind"] in rb.METRICS and 0 < c["tolerance"] <= 0.10, c["id"]
        if c["expected_ratio"] != 1:
            assert c.get("expected_why"), c["id"]
        if not c["tested"]:
            assert c.get("why_untested"), c["id"]
        if c["kind"] == "ratio_of_measures":
            assert c["other_measure"], c["id"]
        if c["kind"] == "order":
            assert len(c.get("published_values", {})) >= 2, c["id"]


def test_per_life_metric_on_a_fixture():
    s = score.city("Bengaluru", ["air_dust"], study="apna_2015", folder=FIXTURES, n=50,
                   curves=["gemm_ncd_lri"], discount=0.0)[0]
    r = s.run.per_curve["gemm_ncd_lri"]
    assert rb.METRICS["per_life"](CASE) == pytest.approx(r.cost_inr.mean() / r.deaths_postponed.mean())


def test_per_ugm3_metric_on_a_fixture():
    s = score.city("Bengaluru", ["air_dust"], study="apna_2015", folder=FIXTURES, n=50,
                   curves=["gemm_ncd_lri"], discount=0.0)[0]
    r = s.run.per_curve["gemm_ncd_lri"]
    change = abs(np.median(r.pm25_after - s.run.pm25_before))
    assert rb.METRICS["per_ugm3"](dict(CASE, kind="per_ugm3")) == pytest.approx(
        np.median(r.cost_inr) / change)
    # annual basis: once spread over the years, plus the yearly cost
    iv = s.run.intervention
    annual = prices.to_base_inr(iv.cost_annual.median + iv.cost_once.median / iv.duration_years,
                                iv.cost_currency, iv.cost_year)
    assert rb.METRICS["per_ugm3"](dict(CASE, kind="per_ugm3", cost_basis="annual")) == pytest.approx(
        annual / change)


def test_ratio_of_measures_is_the_ratio_of_per_life():
    a = rb.METRICS["per_life"](CASE)
    assert rb.METRICS["ratio_of_measures"](dict(CASE, kind="ratio_of_measures",
                                                other_measure="air_dust")) == pytest.approx(a / a)


def test_order_counts_agreeing_pairs(monkeypatch):
    values = {"a": 1.0, "b": 2.0, "c": 3.0}
    ours = {"a": 10.0, "b": 30.0, "c": 20.0}     # (a,b) and (a,c) agree, (b,c) does not
    monkeypatch.setattr(rb, "_per_ugm3_or_reason", lambda case, m: ours[m])
    got = rb.METRICS["order"](dict(CASE, kind="order", published_values=values))
    assert got == pytest.approx(2 / 3)


def test_published_is_put_in_2025_rupees():
    case = dict(CASE, published=100.0, published_currency="INR", published_year=2019)
    assert rb.published_base(case) == pytest.approx(prices.to_base_inr(100.0, "INR", 2019))
    assert rb.published_base(dict(case, kind="per_ugm3")) == pytest.approx(
        prices.to_base_inr(100.0e9, "INR", 2019))
    assert rb.published_base(dict(case, kind="ratio_of_measures")) == 100.0


def test_band_is_around_the_expectation():
    r = rb.judge(dict(CASE, expected_ratio=0.5, tolerance=0.1), ours=0.52, published=1.0)
    assert r["within"] and r["ratio"] == pytest.approx(0.52)
    assert not rb.judge(dict(CASE, expected_ratio=1.0, tolerance=0.1), ours=0.52, published=1.0)["within"]


def test_missing_measure_skips_with_a_reason():
    r = rb.evaluate_or_skip({**CASE, "measure": "no_such_measure"})
    assert r["skipped"] and "library" in r["reason"]


def test_unscored_place_skips_with_a_reason():
    r = rb.evaluate_or_skip({**CASE, "place": "Kanpur", "causes_study": "no_such_study"})
    assert r["skipped"] and "Kanpur" in r["reason"]


def test_ihme_curve_skips_without_the_files(no_ihme):
    r = rb.evaluate_or_skip({**CASE, "curve": "gbd2023"})
    assert r["skipped"] and "IHME" in r["reason"]


def test_regional_part_in_a_city_skips_for_want_of_a_cost():
    case = next(c for c in rb.load_cases() if c["id"] == "teri2021_delhi_fgd_scrubbers")
    r = rb.evaluate_or_skip(case)
    assert r["skipped"] and "whole reach" in r["reason"]


def test_ranking_page_lists_every_case_and_the_ones_not_compared():
    cases = [dict(c, skipped=True, reason="not run in this test") for c in rb.load_cases()]
    page = rb.ranking_md(cases)
    for c in cases:
        assert c["id"] in page
    for name in ("World Bank", "creahia", "UNDP"):
        assert name in page


@pytest.mark.parametrize("case", [c for c in rb.load_cases() if c["tested"]], ids=lambda c: c["id"])
def test_rank_benchmark_within_band(case):
    if rb.needs_region(case) and not SLOW:
        pytest.skip("scores a regional measure over its whole reach (minutes); "
                    "set AIRHEALTH_SLOW_BENCHMARKS=1 or run benchmarks/rank_run.py")
    r = rb.evaluate_or_skip(case)
    if r.get("skipped"):
        pytest.skip(r["reason"])
    assert r["within"], (f"{case['id']}: ratio {r['ratio']:.3f}, expected {case['expected_ratio']} "
                         f"±{case['tolerance']:.0%}")
