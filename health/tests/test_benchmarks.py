"""Open-tier reproduction benchmarks: each case's ratio (ours / published) within its tolerance."""
import importlib.util

import pytest

from airhealth import paths

_spec = importlib.util.spec_from_file_location("bench_run", paths.HEALTH / "benchmarks" / "run.py")
bench = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bench)

CASES = bench.load_cases()
REQUIRED = ("study", "measures", "published", "published_text", "source_url", "locator", "place",
            "curve", "map", "year", "counterfactual", "tolerance", "in_short", "why_different")


def test_cases_are_complete():
    assert CASES
    for case in CASES:
        missing = [k for k in REQUIRED if k not in case]
        assert not missing, (case["id"], missing)
        assert case["measures"] in bench.MEASURES
        if case["tolerance"] > bench.DEFAULT_TOLERANCE:
            assert case.get("tolerance_why"), case["id"]


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_benchmarks_within_tolerance(case):
    r = bench.evaluate(case)
    assert abs(r["ratio"] - 1) <= case["tolerance"], (
        f"{case['id']}: ours {r['ours']:.4g} vs published {case['published']:.4g}, "
        f"ratio {r['ratio']:.3f}, tolerance ±{case['tolerance']:.0%}")
