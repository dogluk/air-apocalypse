"""The dashboard answers with the same numbers as the command line."""
import json

import pytest

from airhealth import cli, dashboard


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


def test_meta_lists_what_the_page_needs():
    m = dashboard.meta()
    assert {p["kind"] for p in m["places"]} == {"country", "state", "city"}
    assert "aqli" not in m["shapes"]["rr"]          # AQLI is years of life, not a risk ratio
    assert all(len(v) == len(m["shapes"]["conc"]) for v in m["shapes"]["rr"].values())
    india = next(r for r in m["exposure"] if r["place"] == "India")
    assert india["aqli"] < india["acag_total"] < india["gbd2019"]
    assert {u["name"] for u in m["unavailable"]} >= {"gbd2019", "gbd2023"}
