import html as html_
import re
import shutil

import pytest

from airhealth import causes, curves, measures as library, score
from citypage import measures
from citypage.measures import MeasureFile, find, render, score_all

LIB = library.LIBRARY
FIXTURE = ("lpg_refill_subsidy", "road_paving", "school_purifiers", "smog_tower")
N = 200


def _copy(folder, *ids):
    for i in ids:
        shutil.copy(LIB / f"{i}.toml", folder / f"{i}.toml")
    return folder


@pytest.fixture(scope="module")
def lib(tmp_path_factory):
    return _copy(tmp_path_factory.mktemp("lib"), *FIXTURE)


@pytest.fixture(scope="module")
def page(lib):
    return render("Bengaluru", folder=lib, n=N).html


def test_empty_library_says_so(tmp_path):
    s = render("Bengaluru", folder=tmp_path, n=N)
    assert s.id == "measures" and "not yet in the library" in s.html


def test_finds_bengaluru_files_and_skips_the_template(tmp_path):
    _copy(tmp_path, "road_paving")
    shutil.copy(LIB / "_template.toml", tmp_path / "_template.toml")
    found = find("Bengaluru", tmp_path)
    assert [m.path.name for m in found] == ["road_paving.toml"]
    assert found[0] == MeasureFile(tmp_path / "road_paving.toml",
                                   "Paving the edges of Bengaluru's main roads", None)


def test_other_cities_are_ignored(tmp_path):
    text = (LIB / "road_paving.toml").read_text()
    (tmp_path / "d.toml").write_text(text.replace('cities = ["Bengaluru"]', 'cities = ["Delhi"]'))
    assert find("Bengaluru", tmp_path) == []


def test_broken_measure_is_listed_not_dropped(tmp_path):
    _copy(tmp_path, "road_paving")
    text = (LIB / "road_paving.toml").read_text()
    (tmp_path / "x.toml").write_text(text.replace("p_success = 0.6", "p_success = 2"))
    found = {m.path.name: m for m in find("Bengaluru", tmp_path)}
    assert found["x.toml"].error and "p_success" in found["x.toml"].error
    assert found["road_paving.toml"].error is None
    h = render("Bengaluru", folder=tmp_path, n=N).html
    assert "could not run" in h and "x.toml" in h
    assert "Paving the edges of Bengaluru" in h            # the good one still runs


def test_a_measure_that_fails_to_run_is_listed(tmp_path, monkeypatch):
    _copy(tmp_path, "road_paving", "school_purifiers")
    real = score.city

    def flaky(city, ids=None, **kw):
        if ids == ["road_paving"]:
            raise RuntimeError("boom in the engine")
        return real(city, ids, **kw)
    monkeypatch.setattr(score, "city", flaky)
    h = render("Bengaluru", folder=tmp_path, n=N).html
    assert "could not run" in h and "boom in the engine" in h
    assert "HEPA purifiers in Bengaluru" in h


def test_air_measures_scored_on_every_study_separately(lib):
    got = {e.file.path.stem: e for e in score_all("Bengaluru", folder=lib, n=N)}
    studies = causes.studies("Bengaluru")
    assert len(studies) >= 2
    assert list(got["road_paving"].scores) == studies
    assert [s.study for s in got["road_paving"].scores.values()] == studies
    assert list(got["school_purifiers"].scores) == [None]   # exposure: no study needed


def test_every_study_and_every_curve_appear(page):
    for st in causes.studies("Bengaluru"):
        assert st in page
    run, missing = curves.select()
    for c in run:
        assert page.count(c.name) >= 3                     # charts and tables, every measure
    for name in missing:
        assert name in page                                # named as not run, with why
    assert "acag_total" in page and "chapter 1" in page.lower()


def test_not_scored_and_its_reason_are_shown(page):
    # LPG targets household burning, which the CSTEP study does not report
    assert "not scored" in page
    assert "does not report residential" in page


def test_flags_in_plain_words_beside_the_ratio(page):
    for code_text in (score.UPPER_BOUND_TEXT,
                      "This is a long shot",
                      "are a judgement, not a figure from a cited source",
                      "not read at the source",
                      "Only the people it reaches breathe less"):
        assert html_.escape(code_text) in page
    partial = library.load(LIB / "school_purifiers.toml").cost.partial
    assert html_.escape(partial) in page
    assert 'class="caveats"' in page


def test_exposure_change_is_labelled_for_the_covered(page):
    assert "what the covered people breathe" in page
    assert "city average" in page


def test_assumptions_and_engine_limit_are_printed(page):
    for a in score.ASSUMPTIONS:
        assert html_.escape(a) in page
    assert "overstated" in page


def test_no_ranking_no_average(page):
    assert "library order" in page
    full = [library.load(LIB / f"{i}.toml").name for i in ("lpg_refill_subsidy", "road_paving")]
    part = [library.load(LIB / f"{i}.toml").name for i in ("school_purifiers", "smog_tower")]
    each = page[page.index("<h3>Each measure</h3>"):]
    at = [each.index(html_.escape(n)) for n in full + part]
    assert at == sorted(at)                    # library order inside each group, not by a value
    for phrase in ("central estimate", "average of the curves", "best curve", "best measure"):
        assert phrase not in page.lower()


def test_no_nan_or_none_in_the_page(page):
    text = re.sub(r"<[^>]+>", " ", page)
    assert not re.search(r"\bnan\b", text, re.I)
    assert "None" not in text
    assert "inf" not in re.findall(r"\b\w+\b", text.lower())


def test_curves_not_run_named_without_ihme(no_ihme, tmp_path):
    _copy(tmp_path, "school_purifiers")
    h = render("Bengaluru", folder=tmp_path, n=N).html
    assert "gbd2023" in h and "IHME" in h
    assert measures.__doc__ and "seam" in measures.__doc__


def test_partial_cost_measures_come_last_in_their_own_group(page):
    head = "Costs that leave things out"
    assert head in page
    each = page[page.index("<h3>Each measure</h3>"):]
    cut = each.index("<h3>" + head)
    for i in ("lpg_refill_subsidy", "road_paving"):
        assert each.index(html_.escape(library.load(LIB / f"{i}.toml").name)) < cut
    for i in ("school_purifiers", "smog_tower"):
        assert each.index(html_.escape(library.load(LIB / f"{i}.toml").name)) > cut
    # the glance charts do the same: the group's heading comes after the fully costed charts
    glance = page[page.index("All measures at a glance"):page.index("<h3>Each measure</h3>")]
    assert glance.index("<h3>" + head) > glance.index("air measures on study")
    assert "not comparable" in page
