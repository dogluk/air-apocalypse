import html as _h
import json
import shutil

from airhealth import cli, exposure, paths, places
from citypage import names
from citypage.burden import MAPS, ROUND_TARGET, burden, change_to, curves_status, render, targets


def test_burden_matches_the_cli(capsys):
    assert cli.main(["--json", "burden", "Bengaluru", "--map", "cpcb"]) == 0
    expected = json.loads(capsys.readouterr().out)
    assert burden("Bengaluru", "cpcb")["rows"] == expected["rows"]


def test_curves_status_without_ihme(no_ihme):
    run, missing = curves_status()
    assert {"gbd2019", "gbd2023", "gemm_5cod"} <= set(missing)
    assert "loglinear_jaganathan" in run
    assert "gbd2023" in render("Bengaluru").html            # named as not run, with why


def test_target_already_met_is_none():
    level = exposure.mean(places.resolve("Bengaluru", kind="city"), "cpcb")
    assert change_to("Bengaluru", "cpcb", level + 1) is None
    assert change_to("Bengaluru", "cpcb", 5.0)["rows"][0]["pm25_after"] == 5.0


def test_every_map_and_curve_has_its_own_row():
    html = render("Bengaluru").html
    for m in MAPS:
        assert names.exposure_map(m) in html
    run, _ = curves_status()
    for c in run:                                           # one row per curve on every map
        assert html.count(names.curve(c)) >= len(MAPS)


def test_targets_round_first_then_file_order():
    t = targets()
    assert t[0].pm25 == ROUND_TARGET and t[0].url is None
    assert [x.key for x in t[1:]] == ["india_naaqs_annual", "who_aqg_2021_annual"]
    assert [x.pm25 for x in t[1:]] == [40, 5]


def test_page_labels_round_target_and_links_standards():
    html = render("Bengaluru").html
    assert "a round number, not a standard" in html
    assert "naaqs-2009.pdf" in html


def test_standard_missing_from_file_is_left_out(monkeypatch, tmp_path):
    f = tmp_path / "targets.csv"
    lines = (paths.DATA / "targets.csv").read_text().splitlines()
    f.write_text("\n".join(lines[:2]) + "\n")
    import citypage.burden as b
    monkeypatch.setattr(b, "_TARGETS", f)
    assert [x.key for x in b.targets()] == ["round", "india_naaqs_annual"]
    assert b.render("Bengaluru").html


def test_report_footer_shown_once_per_chapter():
    from citypage.burden import burden, _maps
    html = render("Bengaluru").html
    for m in _maps():
        assert html.count(_h.escape(burden("Bengaluru", m)["footer"])) == 1
