import subprocess

import pytest

from airhealth import paths, provenance


def test_every_data_file_has_a_source():
    sources = provenance.load_sources()
    for f in paths.DATA.glob("**/*.csv"):
        assert f.relative_to(paths.DATA).as_posix() in sources
    assert provenance.check() == []


def test_entry_missing_field_is_reported(tmp_path):
    (tmp_path / "x.csv").write_text("a\n1\n")
    (tmp_path / "sources.toml").write_text(
        '["x.csv"]\nsource = "s"\nurl = "u"\nlocator = "l"\n'
        'retrieved = "2026-11-10"\nmethod = "downloaded"\n'
    )
    problems = provenance.check(tmp_path)
    assert any("x.csv" in p and "licence" in p for p in problems)


def test_local_folder_is_ignored():
    r = subprocess.run(
        ["git", "check-ignore", "health/data_local/x.csv"],
        cwd=paths.REPO, capture_output=True,
    )
    assert r.returncode == 0


def test_constants_in_code_carry_sources():
    listed = provenance.constants()
    assert provenance.check_constants() == []
    values = {c["name"]: c["value"] for c in listed}
    assert values["AQLI: years of life expectancy per 10 µg/m³"] == 0.98
    assert values["GEMM: counterfactual, µg/m³"] == 2.4
    assert values["Highest long-term exposure in a cohort behind GEMM, µg/m³"] == 84.0
    assert values["EPA 20-year cessation lag: shares in year 1, years 2-5, years 6-20"] == \
        pytest.approx((0.30, 0.50, 0.20))
    assert values["Infant a0 = intercept + slope × q0"] == (0.0425, 2.875)


def test_a_constant_without_a_link_is_reported(monkeypatch):
    from airhealth import curves
    monkeypatch.setattr(curves, "AQLI_SOURCE", "somebody said so")
    assert len(provenance.check_constants()) == 2 and provenance.check() != []
