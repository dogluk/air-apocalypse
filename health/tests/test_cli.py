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


# --- death counts and the SRS crude death rate ------------------------------------------------

def test_footer_says_how_deaths_were_scaled(capsys):
    _, out, _ = run(capsys, "compare", "Delhi", "--from", "100", "--to", "80")
    footer = out.strip().splitlines()[-1]
    assert "scaled by ×0.72 to the SRS crude death rate for Delhi, 2020-24" in footer
    assert "ages 45 and over" in footer and "unscaled life table" in footer
    assert "per 1,000)" in out.splitlines()[1]             # the implied crude death rate
    _, out, _ = run(capsys, "burden", "India", "--curves", "gemm_ncd_lri")
    footer = out.strip().splitlines()[-1]
    assert "each state's SRS crude death rate, 2020-24" in footer and "overall" in footer
    _, out, _ = run(capsys, "burden", "Chandigarh", "--curves", "gemm_ncd_lri")
    footer = out.strip().splitlines()[-1]
    assert "Deaths scaled by ×0.57" in footer and "Chandigarh" in footer


def test_deaths_model_switches_the_scaling_off(capsys):
    args = ("--json", "compare", "Delhi", "--from", "100", "--to", "80")
    srs = json.loads(run(capsys, *args)[1])
    model = json.loads(run(capsys, *args, "--deaths", "model")[1])
    assert (srs["deaths_basis"], model["deaths_basis"]) == ("srs", "model")
    assert srs["deaths_unscaled"] == pytest.approx(model["deaths_baseline"])
    assert srs["deaths_baseline"] < model["deaths_baseline"]
    assert srs["death_scaling"][0]["state"] == "Delhi" and model["death_scaling"] == []
    assert "not reconciled to the SRS crude death rate" in model["footer"]
    for a, b in zip(srs["rows"], model["rows"]):
        assert a["life_expectancy_gain"] == b["life_expectancy_gain"]
        assert a["deaths_averted"] < b["deaths_averted"]


def test_run_footer_says_how_deaths_were_scaled(capsys):
    args = ("run", "interventions/delhi_100_to_80.toml", "--n", "50", "--curves", "gemm_ncd_lri")
    _, out, _ = run(capsys, *args)
    assert "SRS crude death rate for Delhi, 2020-24" in out.strip().splitlines()[-1]
    result = json.loads(run(capsys, "--json", *args, "--deaths", "model")[1])
    assert result["deaths_basis"] == "model" and "not reconciled" in result["footer"]


# --- city population, floors, bad levels, debug (final review I4, M2, M3, M4, M12) -----------

def test_city_result_names_its_population_year(capsys):
    _, out, _ = run(capsys, "compare", "Bengaluru", "--to", "20", "--curves", "gemm_ncd_lri")
    footer = out.strip().splitlines()[-1]
    assert "Population of Bengaluru: Census 2011" in footer and "not updated to 2025" in footer
    result = json.loads(run(capsys, "--json", "compare", "Bengaluru", "--to", "20")[1])
    assert result["population_year"] == 2011 and "Census 2011" in result["footer"]
    _, out, _ = run(capsys, "compare", "Karnataka", "--to", "20", "--curves", "gemm_ncd_lri")
    assert "Census" not in out


def test_negative_level_is_refused(capsys):
    for flags, named in ((["--from", "100", "--to", "-5"], "--to"),
                         (["--from", "-1", "--to", "5"], "--from")):
        code, out, err = run(capsys, "compare", "Delhi", *flags)
        assert code == 1 and out == ""
        assert "cannot be below 0" in err and err.startswith(f"airhealth: {named}:")


def test_move_below_the_floor_is_marked(capsys):
    _, out, _ = run(capsys, "compare", "Delhi", "--from", "10", "--to", "1",
                    "--curves", "loglinear_jaganathan,loglinear_brown")
    assert "loglinear_jaganathan †" in out and "loglinear_brown †" in out
    assert "below the curve's floor" in out and "loglinear_jaganathan 5" in out
    rows = json.loads(run(capsys, "--json", "compare", "Delhi", "--from", "10", "--to", "1")[1])["rows"]
    assert all(r["below_floor"] for r in rows)
    _, out, _ = run(capsys, "compare", "Delhi", "--from", "100", "--to", "80")
    assert "†" not in out


def test_list_maps_says_which_years_give_results(capsys):
    _, out, _ = run(capsys, "list", "maps")
    aqli = out.split("aqli  [")[1].split("]")[0]
    assert aqli.startswith("1998-2023") and "results 2011-2023" in aqli


def test_debug_shows_the_traceback(capsys):
    with pytest.raises(KeyError):
        cli.main(["--debug", "compare", "Dehli", "--to", "80"])
    capsys.readouterr()
    assert cli.main(["compare", "Dehli", "--to", "80"]) == 1


def test_curve_chart_labels_say_what_each_line_is_the_risk_of():
    by_name = {c.name: c for c in curves.available()}
    assert charts.line_label(by_name["gemm_ncd_lri"]) == "GEMM NCD+LRI: NCD+LRI deaths only"
    assert charts.line_label(by_name["loglinear_jaganathan"]) == "Jaganathan 2024: all deaths"
    assert charts.age_band(60) == "ages 60-64" and charts.age_band(62) == "ages 60-64"
    assert charts.age_band(85) == "ages 85 and over" and charts.age_band(0) == "ages 0-0"
