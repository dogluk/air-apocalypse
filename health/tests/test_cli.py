import json

import pytest

from airhealth import charts, cli, curves, paths


def run(capsys, *argv):
    code = cli.main(list(argv))
    out, err = capsys.readouterr()
    return code, out, err


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


def test_json_flag_emits_valid_json_with_curve_and_map_on_every_row(capsys, no_ihme):
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
    assert "each state's SRS crude death rate for 2020-24" in footer and "overall" in footer
    _, out, _ = run(capsys, "burden", "Chandigarh", "--curves", "gemm_ncd_lri")
    footer = out.strip().splitlines()[-1]
    assert "Deaths scaled by ×0.57" in footer and "Chandigarh" in footer


def test_deaths_model_switches_the_scaling_off(capsys, no_ihme):
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


def test_year_outside_the_srs_years_is_flagged(capsys):
    """2011-19 are scaled to their own year's SRS rate; after 2024 there is none to check."""
    args = ("compare", "Delhi", "--from", "100", "--to", "80", "--curves", "gemm_ncd_lri")
    footer = run(capsys, *args, "--year", "2015")[1].strip().splitlines()[-1]
    assert "SRS crude death rate for Delhi, 2015" in footer and "not checked" not in footer
    assert "Delhi's own SRS rates by age for 2014-16" in footer
    footer = run(capsys, *args, "--year", "2022")[1].strip().splitlines()[-1]
    assert "not checked" not in footer and "rates by age for" not in footer
    footer = run(capsys, "burden", "Delhi", "--map", "gbd2019",
                 "--curves", "gemm_ncd_lri")[1].strip().splitlines()[-1]
    assert "SRS crude death rate for Delhi, 2019" in footer
    footer = run(capsys, "compare", "Bengaluru", "--to", "20",       # cpcb's latest is 2025
                 "--curves", "gemm_ncd_lri")[1].strip().splitlines()[-1]
    assert "Death counts for 2025 are not checked" in footer and "projected" in footer
    result = json.loads(run(capsys, "--json", *args, "--year", "2015", "--deaths", "model")[1])
    assert "Delhi's own SRS rates by age for 2014-16" in result["footer"]
    assert result["death_scaling"] == []
    srs = json.loads(run(capsys, "--json", *args, "--year", "2015")[1])
    assert srs["death_scaling"][0]["period"] == "2015"


def test_early_year_names_states_on_the_period_scaling(capsys):
    footer = run(capsys, "burden", "India", "--year", "2015",
                 "--curves", "gemm_ncd_lri")[1].strip().splitlines()[-1]
    assert "each state's SRS crude death rate for 2015" in footer
    assert "2020-24 for the 15 without an SRS life table" in footer   # no SRS rate before 2020
    assert "death_reconciliation_by_year.csv" in footer
    assert footer.count("Chandigarh") == 1        # named once, in the life-table line
    footer = run(capsys, "burden", "India", "--year", "2012",
                 "--curves", "gemm_ncd_lri")[1].strip().splitlines()[-1]
    assert "2020-24 for Telangana, Uttarakhand, the 15" in footer   # in the SRS from 2014
    assert "India's used for Telangana, Uttarakhand" in footer


def test_run_in_an_early_year_is_scaled_to_it(capsys):
    args = ("run", "interventions/delhi_100_to_80.toml", "--n", "50", "--curves", "gemm_ncd_lri")
    footer = run(capsys, *args, "--map", "gbd2019")[1].strip().splitlines()[-1]
    assert "SRS crude death rate for Delhi, 2019" in footer and "not checked" not in footer
    assert "not checked" not in run(capsys, *args)[1]                  # aqli 2023


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


# --- a source for every input (docs/specs/2026-11-11-source-switches.md) ---------------------

def test_footer_names_every_source(capsys):
    args = ("compare", "Delhi", "--from", "100", "--to", "80", "--curves", "gemm_ncd_lri")
    footer = run(capsys, *args)[1].strip().splitlines()[-1]
    assert ("Sources: population by age, projection (default); death rates by age, srs "
            "(default); death count, srs (default)") in footer
    assert "mixes" not in footer
    footer = run(capsys, *args, "--use", "deaths=unwpp")[1].strip().splitlines()[-1]
    assert "death count, unwpp" in footer and "UN's deaths by age for India, 2023" in footer
    assert "mixes the Indian government's and the United Nations' figures" in footer
    result = json.loads(run(capsys, "--json", *args, "--use", "population=unwpp",
                            "--use", "death_rates=unwpp", "--use", "deaths=unwpp")[1])
    assert result["sources"] == {"population": "unwpp", "death_rates": "unwpp", "deaths": "unwpp"}
    assert result["deaths_basis"] == "unwpp" and "mixes" not in result["footer"]


def test_deaths_flag_is_shorthand_for_use(capsys):
    a = json.loads(run(capsys, "--json", "burden", "India", "--deaths", "model")[1])
    b = json.loads(run(capsys, "--json", "burden", "India", "--use", "deaths=model")[1])
    assert a["rows"] == b["rows"]


def test_several_sources_print_a_result_each_and_the_range(capsys):
    _, out, _ = run(capsys, "compare", "India", "--to", "20", "--curves", "gemm_ncd_lri",
                    "--use", "deaths=srs,unwpp,model")
    assert out.count("Sources: ") == 3
    spread = next(ln for ln in out.splitlines() if ln.startswith("Across sources"))
    assert "deaths/yr" in spread and "gemm_ncd_lri" in spread
    result = json.loads(run(capsys, "--json", "compare", "India", "--to", "20", "--curves",
                            "gemm_ncd_lri", "--use", "deaths=srs,unwpp")[1])
    assert [r["sources"]["deaths"] for r in result["results"]] == ["srs", "unwpp"]
    lo, hi = result["across_sources"]["gemm_ncd_lri"]["deaths_averted"]
    assert lo < hi


def test_list_inputs_prints_the_registry(capsys):
    _, out, _ = run(capsys, "list", "inputs")
    for name in ("population", "death_rates", "deaths", "unwpp", "map", "curves"):
        assert name in out


def test_run_takes_sources_from_the_file_or_the_flag(capsys, tmp_path):
    f = tmp_path / "un.toml"
    f.write_text((paths.HEALTH / "interventions" / "delhi_100_to_80.toml").read_text()
                 + '\n[sources]\ndeaths = "unwpp"\n')
    args = ("--json", "run", str(f), "--n", "50", "--curves", "gemm_ncd_lri")
    assert json.loads(run(capsys, *args)[1])["sources"]["deaths"] == "unwpp"
    assert json.loads(run(capsys, *args, "--deaths", "srs")[1])["sources"]["deaths"] == "srs"
