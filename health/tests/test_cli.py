import json

import pytest

from airhealth import charts, cli, curves, paths


def run(capsys, *argv):
    code = cli.main(list(argv))
    out, err = capsys.readouterr()
    return code, out, err


@pytest.fixture
def no_ihme(monkeypatch, tmp_path):
    """An empty data_local/, so the IHME curves are unavailable whatever is on this machine."""
    monkeypatch.setattr(paths, "LOCAL", tmp_path)


def test_compare_delhi_lists_every_available_curve(capsys):
    code, out, _ = run(capsys, "compare", "Delhi", "--from", "100", "--to", "80")
    assert code == 0
    for c in curves.available():
        assert c.name in out
        assert c.label in out
    assert "aqli" in out.splitlines()[-1]          # the default map for a state, named last


def test_compare_from_sets_the_starting_level(capsys):
    code, out, _ = run(capsys, "--json", "compare", "Delhi", "--from", "100", "--to", "80")
    assert code == 0
    rows = json.loads(out)["rows"]
    assert {r["pm25_before"] for r in rows} == {100.0}
    assert {r["pm25_after"] for r in rows} == {80.0}
    assert all(r["deaths_averted"] > 0 for r in rows)


def test_json_flag_emits_valid_json_with_curve_and_map_on_every_row(capsys):
    for argv in (["--json", "compare", "Delhi", "--from", "100", "--to", "80"],
                 ["compare", "Delhi", "--to", "80", "--json"],
                 ["--json", "burden", "Delhi"]):
        code, out, _ = run(capsys, *argv)
        assert code == 0
        result = json.loads(out)
        assert len(result["rows"]) == len(curves.available())
        for row in result["rows"]:
            assert row["curve"] and row["map"] == "aqli"


def test_city_defaults_to_cpcb_map(capsys):
    code, out, _ = run(capsys, "--json", "burden", "Pune", "--curves", "loglinear_jaganathan")
    assert code == 0
    assert json.loads(out)["rows"][0]["map"] == "cpcb"


def test_unknown_place_exits_nonzero_with_suggestion(capsys):
    code, out, err = run(capsys, "compare", "Dehli", "--to", "80")
    assert code != 0
    assert "did you mean" in err and "Delhi" in err
    assert "Traceback" not in err and out == ""


def test_unknown_curve_exits_nonzero(capsys):
    code, _, err = run(capsys, "burden", "India", "--curves", "nonesuch")
    assert code != 0 and "nonesuch" in err and "Traceback" not in err


def test_unavailable_curve_is_named_in_footer(capsys, no_ihme):
    code, out, _ = run(capsys, "compare", "Delhi", "--from", "100", "--to", "80",
                       "--curves", "loglinear_jaganathan,gbd2019")
    assert code == 0
    footer = out.strip().splitlines()[-1]
    assert "gbd2019" in footer and "IHME" in footer
    _, out, _ = run(capsys, "--json", "compare", "Delhi", "--from", "100", "--to", "80",
                    "--curves", "loglinear_jaganathan,gbd2019")
    result = json.loads(out)
    assert [r["curve"] for r in result["rows"]] == ["loglinear_jaganathan"]
    assert "IHME" in result["unavailable"]["gbd2019"]


def test_unavailable_curves_are_named_by_default(capsys, no_ihme):
    code, out, _ = run(capsys, "burden", "India")
    footer = out.strip().splitlines()[-1]
    for name in curves.IHME:
        assert name in footer


@pytest.mark.parametrize("what", ["curves", "maps", "places"])
def test_list_gives_sources(capsys, what):
    code, out, _ = run(capsys, "list", what)
    assert code == 0 and "http" in out


def test_curve_chart_is_written(tmp_path):
    path = charts.curves_chart(curves.available(), {"Delhi": 88.4, "India": 41.0},
                               tmp_path / "curves.png")
    assert path.exists() and path.stat().st_size > 30_000
