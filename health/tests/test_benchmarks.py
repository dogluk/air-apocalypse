"""Reproduction benchmarks (open tier, and local tier when the IHME files are here): each case's ratio (ours / published) within its band
around the ratio the case expects."""
import importlib.util

import pytest

from airhealth import paths

_spec = importlib.util.spec_from_file_location("bench_run", paths.HEALTH / "benchmarks" / "run.py")
bench = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bench)

CASES = bench.load_cases()
REQUIRED = ("study", "measures", "published", "published_text", "source_url", "locator", "place",
            "curve", "map", "year", "counterfactual", "expected_ratio", "tolerance", "band_why",
            "in_short", "why_different")
MAX_BAND = 0.10


def test_cases_are_complete():
    assert CASES
    for case in CASES:
        missing = [k for k in REQUIRED if k not in case]
        assert not missing, (case["id"], missing)
        assert case["measures"] in bench.MEASURES
        assert 0 < case["tolerance"] <= MAX_BAND, case["id"]
        if case["expected_ratio"] != 1:
            assert case.get("expected_why"), case["id"]


def test_band_is_around_the_expectation_not_around_one():
    case = dict(next(c for c in CASES if c["expected_ratio"] < 0.9), )
    r = bench.evaluate(case)
    assert r["within"]
    # the same result would fail if the case expected a match
    assert not bench.evaluate(dict(case, expected_ratio=1.0))["within"]
    # and a result that matched the paper would fail this case
    assert abs(1.0 / case["expected_ratio"] - 1) > case["tolerance"]


def test_local_cases_skip_cleanly_without_ihme_files(no_ihme):
    local = [c for c in CASES if c.get("tier") == "local"]
    assert local
    for case in local:
        assert bench.evaluate_or_skip(case)["skipped"]


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_benchmarks_within_tolerance(case, request):
    if case.get("tier") == "local":
        request.getfixturevalue("ihme_files")        # skips without the IHME files
    r = bench.evaluate(case)
    assert r["within"], (
        f"{case['id']}: ours {r['ours']:.4g} vs published {case['published']:.4g}, "
        f"ratio {r['ratio']:.3f}, expected {bench.band(r)}")
