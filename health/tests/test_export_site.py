"""scripts/export_site_data.py: compact JSON for the website, written beside a note saying
when, from which commit and from what it was made. Nothing here runs the model: the tests give it
rank outputs to read."""
import json
import sys

import pytest

from airhealth import paths

sys.path.insert(0, str(paths.HEALTH / "scripts"))
import export_site_data as ex  # noqa: E402


def rank_file(folder, slug, place):
    row = {"measure": "m", "life_years": {"median": 1.0}, "trail": {"shares": [1] * 500}}
    (folder / f"rank_{slug}.json").write_text(json.dumps(
        {"place": place, "context": {"map": "acag_total", "study": "apna_2015", "n": 500,
                                     "seed": 0},
         "assumptions": ["a"], "spread": [], "tables": {"gemm_ncd_lri": {"label": "L", "rows": [row]}},
         "parts": {}}))


def test_wrap_carries_generated_commit_and_sources():
    w = ex.wrap({"x": 1}, sources="from a test")
    assert set(w) == {"generated", "commit", "sources", "data"}
    assert w["sources"] == "from a test" and w["data"] == {"x": 1}
    assert w["generated"].endswith("Z") and w["commit"]


def test_ranking_from_an_existing_output_drops_the_bulky_trail(tmp_path):
    rank_file(tmp_path, "bengaluru", "Bengaluru")
    out = ex.ranking_for("Bengaluru", tmp_path, with_regions=False, n=100)
    row = out["data"]["tables"]["gemm_ncd_lri"]["rows"][0]
    assert "trail" not in row and row["measure"] == "m"
    assert "rank_bengaluru.json" in out["sources"]


def test_cities_found_are_those_with_rank_output_not_india_or_sensitivity(tmp_path):
    rank_file(tmp_path, "bengaluru", "Bengaluru")
    rank_file(tmp_path, "agra", "Agra")
    rank_file(tmp_path, "india", "India")
    (tmp_path / "sensitivity_bengaluru.json").write_text("{}")
    assert ex.cities_with_output(tmp_path) == ["Agra", "Bengaluru"]


def test_sensitivity_keeps_the_research_lists_and_notes_only(tmp_path):
    (tmp_path / "sensitivity_bengaluru.json").write_text(json.dumps(
        {"place": "Bengaluru", "top": 5, "notes": ["n"], "research": [{"unit": "a"}],
         "research_comparable": [{"unit": "b"}], "ranks": [1] * 1000, "settings": [{"id": "s"}]}))
    out = ex.sensitivity_for("bengaluru", tmp_path)
    assert set(out["data"]) == {"place", "top", "notes", "research", "research_comparable"}
    assert out["data"]["research"] == [{"unit": "a"}]
    assert ex.sensitivity_for("agra", tmp_path) is None


def test_main_writes_compact_json_and_an_index(tmp_path):
    rank_file(tmp_path, "bengaluru", "Bengaluru")
    (tmp_path / "sensitivity_bengaluru.json").write_text(json.dumps(
        {"place": "Bengaluru", "top": 5, "notes": [], "research": [], "research_comparable": []}))
    site = tmp_path / "site"
    ex.main(["--rank-dir", str(tmp_path), "--out", str(site), "--skip-score"])
    text = (site / "ranking" / "bengaluru.json").read_text()
    assert "\n" not in text and '", "' not in text and '": "' not in text
    index = json.loads((site / "index.json").read_text())
    assert [c["city"] for c in index["data"]["cities"]] == ["Bengaluru"]
    assert (site / "sensitivity" / "bengaluru.json").exists()
    assert not (site / "score").exists()


def test_default_output_folder_is_git_ignored():
    assert ex.DEFAULT_OUT == paths.HEALTH / "out" / "site"
    ignore = (paths.REPO / ".gitignore").read_text()
    assert "health/out/" in ignore


def test_a_city_without_output_is_ranked_without_whole_region_runs(monkeypatch, tmp_path):
    """No rank output for the city and no --with-regions: city measures only, regional ones
    carry a plain reason."""
    called = {}

    def fake_scores(city, **kw):
        called["city"] = city
        return []

    monkeypatch.setattr(ex.score, "city", fake_scores)
    monkeypatch.setattr(ex.rank, "_reaches", lambda *a, **k: pytest.fail("whole-region scoring"))
    out = ex.ranking_for("Agra", tmp_path, with_regions=False, n=50)
    assert called["city"] == "Agra" and out["data"]["place"] == "Agra"
    assert "whole-region" in out["sources"]


def test_unknown_city_is_refused_in_plain_words(tmp_path):
    with pytest.raises(SystemExit):
        ex.main(["--rank-dir", str(tmp_path), "--out", str(tmp_path / "s"), "--skip-score",
                 "--city", "Atlantis"])
