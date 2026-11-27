"""The dashboard answers with the same numbers as the command line."""
import json

import pandas as pd
import pytest

from airhealth import cli, dashboard, paths, places


def _cli(capsys, *argv):
    assert cli.main(["--json", *argv]) == 0
    return json.loads(capsys.readouterr().out)


def test_result_matches_cli_compare_and_burden(capsys):
    r = dashboard.result({"place": "Delhi", "kind": "state", "map": "aqli", "from": "100", "to": "80"})
    c = _cli(capsys, "compare", "Delhi", "--from", "100", "--to", "80")
    b = _cli(capsys, "burden", "Delhi")
    for ours, theirs in ((r["compare"], c), (r["burden"], b)):
        assert [x["curve"] for x in ours["rows"]] == [x["curve"] for x in theirs["rows"]]
        for x, y in zip(ours["rows"], theirs["rows"]):
            assert x["deaths_averted"] == pytest.approx(y["deaths_averted"])
            assert x["life_expectancy_gain"] == pytest.approx(y["life_expectancy_gain"])
        assert ours["deaths_baseline"] == pytest.approx(theirs["deaths_baseline"])


def test_result_without_from_starts_at_the_map_level(capsys):
    r = dashboard.result({"place": "Kerala", "to": "10"})
    c = _cli(capsys, "compare", "Kerala", "--to", "10")
    assert r["origin"] == pytest.approx(r["map_level"])
    assert r["compare"]["rows"][0]["deaths_averted"] == pytest.approx(c["rows"][0]["deaths_averted"])


def test_deaths_switch_changes_counts_not_life_expectancy():
    q = {"place": "India", "to": "20"}
    srs, model = dashboard.result({**q, "deaths": "srs"}), dashboard.result({**q, "deaths": "model"})
    assert model["compare"]["deaths_baseline"] > srs["compare"]["deaths_baseline"]
    assert (model["compare"]["rows"][0]["life_expectancy_gain"]
            == pytest.approx(srs["compare"]["rows"][0]["life_expectancy_gain"]))


def test_bad_input_raises_value_error():
    with pytest.raises(ValueError):
        dashboard.result({"place": "Delhi", "to": "-5"})
    with pytest.raises(ValueError):
        dashboard.result({"place": "Kerala", "map": "cpcb", "to": "10"})


def test_meta_lists_what_the_page_needs(no_ihme):
    m = dashboard.meta()
    assert {p["kind"] for p in m["places"]} == {"country", "state", "city"}
    assert "aqli" not in m["shapes"]["rr"]          # AQLI is years of life, not a risk ratio
    assert all(len(v) == len(m["shapes"]["conc"]) for v in m["shapes"]["rr"].values())
    india = next(r for r in m["exposure"] if r["place"] == "India")
    assert india["aqli"] < india["acag_total"] < india["gbd2019"]
    assert {u["name"] for u in m["unavailable"]} >= {"gbd2019", "gbd2023"}


def test_year_is_passed_through_like_the_cli(capsys):
    r = dashboard.result({"place": "Delhi", "kind": "state", "map": "aqli", "year": "2015",
                          "from": "100", "to": "80"})
    c = _cli(capsys, "compare", "Delhi", "--from", "100", "--to", "80", "--year", "2015")
    assert r["year"] == 2015 and r["compare"]["rows"][0]["year"] == 2015
    assert r["compare"]["deaths_baseline"] == pytest.approx(c["deaths_baseline"])
    assert r["map_level"] != dashboard.result({"place": "Delhi", "to": "80"})["map_level"]


def test_meta_lists_the_years_each_map_can_run():
    years = {m["name"]: m["years"] for m in dashboard.meta()["maps"]}
    assert years["aqli"][0] == 2011 and years["aqli"][-1] == 2023     # projections start 2011
    assert years["gbd2019"] == [2019] and years["acag_total"] == [2023]
    assert years["cpcb"][0] == 2016


# --- the district map ---------------------------------------------------------------------

def _strict(token):
    raise ValueError(f"{token} is not valid JSON in a browser")


def test_shapes_hold_every_acag_district_and_the_states():
    feats = json.loads(dashboard.SHAPES.read_text(), parse_constant=_strict)["features"]
    districts = [f["properties"] for f in feats if f["properties"]["layer"] == "district"]
    assert len(districts) == 735
    assert len([f for f in feats if f["properties"]["layer"] == "state"]) == 37


def test_map_values_follow_each_map():
    acag = dashboard.district_values("acag_total", 2023)
    assert len(acag) == 735
    t = pd.read_csv(paths.DATA / "exposure_acag_total.csv").set_index(["state", "unit"])
    assert acag["Delhi|New Delhi"] == t.loc[("Delhi", "New Delhi"), "pm25"]
    aqli = dashboard.district_values("aqli", 2015)
    a = pd.read_csv(paths.DATA / "exposure_aqli.csv").set_index(["state", "unit", "year"])
    assert aqli["Delhi|Central"] == aqli["Delhi|Shahdara"] == a.loc[("Delhi", "NCT of Delhi", 2015), "pm25"]
    assert "Mizoram|Khawzawl" not in aqli                  # no AQLI district of its own
    gbd = dashboard.district_values("gbd2019", 2019)
    assert gbd["Delhi|Central"] == gbd["Delhi|North"]
    cpcb = dashboard.district_values("cpcb", 2025)
    assert cpcb["Maharashtra|Mumbai"] == cpcb["Maharashtra|Mumbai Suburban"]
    assert "Kerala|Ernakulam" not in cpcb                   # cpcb has ten cities only


def test_selected_districts_for_each_kind_of_place():
    sel = lambda name, kind: dashboard.selected_districts(places.resolve(name, kind=kind))  # noqa: E731
    assert len(sel("Delhi", "state")) == 11
    assert sorted(sel("Mumbai", "city")) == ["Maharashtra|Mumbai", "Maharashtra|Mumbai Suburban"]
    assert sel("India", "country") == []                   # everything; nothing singled out


def test_result_carries_the_map():
    r = dashboard.result({"place": "Delhi", "kind": "state", "map": "aqli", "year": "2015", "to": "80"})
    assert r["districts"]["Delhi|Central"] == pytest.approx(r["map_level"], rel=0.02)
    assert len(r["selected"]) == 11


def test_sources_pass_through_like_the_cli(capsys):
    q = {"place": "Delhi", "kind": "state", "from": "100", "to": "80"}
    r = dashboard.result({**q, "population": "unwpp", "death_rates": "unwpp", "deaths": "unwpp"})
    c = _cli(capsys, "compare", "Delhi", "--from", "100", "--to", "80", "--use",
             "population=unwpp", "--use", "death_rates=unwpp", "--use", "deaths=unwpp")
    assert r["compare"]["sources"] == c["sources"] == {"population": "unwpp",
                                                       "death_rates": "unwpp", "deaths": "unwpp"}
    assert r["compare"]["deaths_baseline"] == pytest.approx(c["deaths_baseline"])
    with pytest.raises(ValueError):
        dashboard.result({**q, "deaths": "who"})


def test_meta_inputs_come_from_the_registry():
    m = dashboard.meta()
    names = [i["name"] for i in m["inputs"]]
    assert names[:3] == ["population", "death_rates", "deaths"]
    deaths = m["inputs"][2]
    assert [s["name"] for s in deaths["sources"]] == ["srs", "model", "unwpp"] and deaths["default"] == "srs"


# --- the ranking tab ----------------------------------------------------------------------

def _without_region_reasons(tables):
    """The page leaves regional measures unscored with its own reason; the CLI scores them."""
    return {c: [{**r, "reason": "" if r["scope"] == "region" else r["reason"]} for r in t["rows"]]
            for c, t in tables.items()}


def _no_reach(*a, **k):
    raise ValueError("stub: whole-reach scoring is not run in tests")


def test_rank_result_matches_cli_on_the_city_measures(capsys, monkeypatch, tmp_path):
    monkeypatch.setattr(dashboard.score, "region", _no_reach)
    r = dashboard.rank_result({"place": "Bengaluru", "n": "100", "curves": "gemm_ncd_lri"}, out=tmp_path)
    c = _cli(capsys, "rank", "Bengaluru", "--n", "100", "--curves", "gemm_ncd_lri")
    assert _without_region_reasons(r["tables"]) == _without_region_reasons(c["tables"])
    assert r["spread"] == c["spread"]
    assert r["source"] == "computed now, 100 draws"
    region = [x for x in r["tables"]["gemm_ncd_lri"]["rows"]
              if x["scope"] == "region" and x["status"] == "not_scored"]
    assert region and all("airhealth rank --write" in x["reason"] for x in region)


def test_rank_result_never_scores_a_whole_reach(monkeypatch, tmp_path):
    def boom(*a, **k):
        raise AssertionError("a page load started whole-reach scoring")
    monkeypatch.setattr(dashboard.score, "region", boom)
    dashboard.rank_result({"place": "Bengaluru", "n": "50", "curves": "gemm_ncd_lri"}, out=tmp_path)


def test_india_without_a_written_file_says_how(tmp_path):
    with pytest.raises(ValueError, match="airhealth rank --write"):
        dashboard.rank_result({"place": "India"}, out=tmp_path)


def test_india_reads_the_written_file(tmp_path):
    (tmp_path / "rank_india.json").write_text(json.dumps({"place": "India", "tables": {}}))
    r = dashboard.rank_result({"place": "India"}, out=tmp_path)
    assert r["source"].startswith("file rank_india.json, written ")
    assert r["sensitivity_file"] is False and r["legend"]["flags"]


def test_a_city_file_is_read_when_no_draws_or_curves_are_asked_for(tmp_path):
    (tmp_path / "rank_bengaluru.json").write_text(json.dumps({"place": "Bengaluru", "tables": {}}))
    r = dashboard.rank_result({"place": "bengaluru"}, out=tmp_path)
    assert r["source"].startswith("file rank_bengaluru.json")


def test_unknown_place_is_a_value_error(tmp_path):
    for bad in ("Atlantis", "../etc", ""):
        with pytest.raises(ValueError):
            dashboard.rank_result({"place": bad}, out=tmp_path)


def test_sensitivity_result_reads_its_file_or_names_the_command(tmp_path):
    with pytest.raises(ValueError, match="airhealth rank Bengaluru --sensitivity --write"):
        dashboard.sensitivity_result({"place": "Bengaluru"}, out=tmp_path)
    (tmp_path / "sensitivity_india.json").write_text(json.dumps({"place": "India", "research": []}))
    assert dashboard.sensitivity_result({"place": "India"}, out=tmp_path)["source"].startswith(
        "file sensitivity_india.json")


def test_api_rank_route(monkeypatch):
    import threading
    import urllib.error
    import urllib.request
    from http.server import ThreadingHTTPServer
    monkeypatch.setattr(dashboard.score, "region", _no_reach)
    server = ThreadingHTTPServer(("127.0.0.1", 0), dashboard.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with urllib.request.urlopen(f"{base}/api/rank?place=Bengaluru&n=50&curves=gemm_ncd_lri") as f:
            body = json.load(f)
            assert f.status == 200 and list(body["tables"]) == ["gemm_ncd_lri"]
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(f"{base}/api/sensitivity?place=Atlantis")
        assert e.value.code == 400
    finally:
        server.shutdown()
        server.server_close()


def test_page_has_the_ranking_tab():
    html = dashboard.PAGE.read_text()
    assert 'id="tab-ranking"' in html and 'id="view-ranking"' in html


def test_meta_lists_the_ranking_cities():
    m = dashboard.meta()
    assert len(m["rank_cities"]) == 50 and m["rank_dash_n"] == dashboard.DASH_N


def test_rank_result_carries_the_stubble_note_and_uses_the_engine_discount(monkeypatch, tmp_path):
    from airhealth import simulate
    row = {"measure": "pes", "flags": ["receptor_fallback", "regional"],
           "trail": {"region": {"receptor": "receptor_stubble.csv"}}}
    (tmp_path / "rank_india.json").write_text(json.dumps(
        {"place": "India", "tables": {"c": {"rows": [row]}}}))
    r = dashboard.rank_result({"place": "India"}, out=tmp_path)
    assert r["notes"] == [dashboard.report.STUBBLE_NOTE]
    (tmp_path / "rank_india.json").write_text(json.dumps({"place": "India", "tables": {}}))
    assert dashboard.rank_result({"place": "India"}, out=tmp_path)["notes"] == []
    assert "RK.notes" in dashboard.PAGE.read_text()             # printed at the top of the tab
    seen = {}

    def fake_city(name, **kw):
        seen.update(kw)
        return []
    monkeypatch.setattr(dashboard.score, "city", fake_city)
    monkeypatch.setattr(simulate, "DISCOUNT", 0.05)
    try:
        dashboard._city_now("Bengaluru", None, 10)
    except Exception:
        pass
    assert seen.get("discount") == 0.05
