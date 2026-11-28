"""The eleven city pages and their index: each builds from the open data alone, has every chapter,
says how many library measures apply and why, names studies in plain words, draws no empty chart,
and the index's numbers are the pages' numbers."""
import ast
import html as html_
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from airhealth import causes, measures as library, paths
from citypage import build, findings, ground, index, measures, names, origins
from citypage.build import CITIES

N = 60
CHAPTERS = ("ground", "sources", "health", "measures")


def _text(markup: str) -> str:
    markup = re.sub(r"<style.*?</style>|<svg.*?</svg>", " ", markup, flags=re.S)
    return html_.unescape(re.sub(r"<[^>]+>", " ", markup))


def _svgs(markup: str) -> list[str]:
    return re.findall(r"<svg.*?</svg>", markup, flags=re.S)


@pytest.fixture(scope="module")
def pages(tmp_path_factory):
    """Every city page and the index, built with no IHME files (the open tier only)."""
    out = tmp_path_factory.mktemp("cities")
    mp = pytest.MonkeyPatch()
    mp.setattr(paths, "LOCAL", tmp_path_factory.mktemp("nolocal"))
    try:
        built = {c: build.build(c, out / c.lower() / "index.html", n=N).read_text() for c in CITIES}
        idx = build.build_index(out / "index.html").read_text()
        rows = index.rows()
    finally:
        mp.undo()
    return SimpleNamespace(html=built, index=idx, rows=rows, out=out)


# ------------------------------------------------------------------ the list

def test_the_eleven_cities_are_the_diwali_track_cities():
    src = (paths.REPO / "diwali" / "config.py").read_text()
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "CITIES":
            assert tuple(k.value for k in node.value.keys) == CITIES
            return
    raise AssertionError("diwali/config.py has no CITIES")


def test_slug_is_the_lowercase_name():
    assert [build.default_out(c).parent.name for c in CITIES] == [c.lower() for c in CITIES]


def test_every_study_of_every_city_has_a_plain_name():
    for c in CITIES:
        for s in causes.studies(c):
            assert s in names.STUDIES, (c, s)


def test_plain_study_names_carry_the_year_and_author_of_their_id():
    norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
    for sid, plain in names.STUDIES.items():
        assert re.search(r"\d{4}", plain).group(0) in sid, sid
        first = re.split(r"[ (]", plain)[0]
        inst = " ".join(causes.table().query("study == @sid").institution.unique())
        assert norm(first) in norm(sid) or norm(first) in norm(inst), (sid, plain)


# ------------------------------------------------------------------ pages

def test_every_city_page_builds_without_ihme_and_has_every_chapter(pages):
    assert set(pages.html) == set(CITIES)
    for c, h in pages.html.items():
        for cid in CHAPTERS:
            assert f'id="ch-{cid}"' in h, (c, cid)
        assert "IHME files: absent" in h, c
        assert f"python -m citypage.build --city {c}" in h, c


def test_no_nan_none_or_inf_in_any_page(pages):
    for c, h in pages.html.items():
        assert not re.search(r"\b(nan|None|NaN|inf)\b", _text(h)), c


def test_no_code_id_in_charts_or_headings(pages):
    ids = [i for i in names.every_id() if i != "aqli"]
    for c, h in pages.html.items():
        heads = " ".join(re.findall(r"<(?:h\d|caption|summary)[^>]*>.*?</(?:h\d|caption|summary)>", h,
                                    flags=re.S))
        for blob in [*_svgs(h), heads]:
            blob = html_.unescape(blob)
            for i in ids:
                assert not re.search(rf"\b{i}\b", blob), (c, i)
        for blob in _svgs(h):
            assert not re.search(r"\baqli\b", html_.unescape(blob)), c


def test_no_study_id_is_shown_to_a_reader_outside_the_source_notes(pages):
    for c, h in pages.html.items():
        text = _text(h)
        # "where in the source" locators and the data-file notes may quote ids; nothing else does
        body = re.sub(r"<details>.*?</details>", " ", h, flags=re.S)
        body = _text(body.split("<footer>")[0])
        for s in causes.studies(c):
            assert s not in body, (c, s)
        assert text


def test_a_city_names_only_its_own_studies(pages):
    body = {c: h.split("<footer>")[0] for c, h in pages.html.items()}    # the footer lists data files
    assert "APnA" not in body["Delhi"]
    assert "ARAI-TERI" in body["Delhi"]
    assert "CSTEP" in body["Bengaluru"] and "CSTEP" not in body["Chennai"]


def test_every_page_says_how_many_library_measures_apply_and_why(pages):
    total = len([p for p in library.LIBRARY.glob("*.toml") if not p.name.startswith("_")])
    for c, h in pages.html.items():
        k = len(measures.find(c))
        text = " ".join(_text(h).split())
        assert f"{k} of the {total} library measures apply to {c}" in text, c
        assert "written for" in text and "single-city" in text, c


def test_the_findings_block_gives_the_count_too(pages):
    for c, h in pages.html.items():
        block = h.split('class="card findings"')[1].split("</div>")[0]
        assert "library measures apply" in block, c


def test_a_city_with_no_regional_or_local_measure_is_told_so_plainly(pages):
    # Delhi and Surat have measures written for them; the others have the widened ones only
    assert "winter_cloud_seeding.toml" in pages.html["Delhi"]
    assert "emissions_market.toml" in pages.html["Surat"]
    assert "emissions_market.toml" not in pages.html["Delhi"]


def test_no_chart_is_empty(pages):
    for c, h in pages.html.items():
        for s in _svgs(h):
            drawn = ("color-mix" in s or "<polyline" in s
                     or re.search(r"<(circle|rect)[^>]*>\s*<title>", s))
            assert drawn, (c, re.search(r'class="ttl">([^<]*)', s).group(1))


def test_surat_pollutants_with_no_data_are_said_not_drawn(pages):
    text = " ".join(_text(pages.html["Surat"]).split())
    cov = ground.fingerprints("Surat")["coverage"]
    for p in cov.index[cov.years == 0]:
        assert f"{ground.POLLUTANTS[p][0]}: no monitor" in text


def test_pages_are_offline_and_self_contained(pages):
    for c, h in pages.html.items():
        assert "<script" not in h and "url(http" not in h and "@import" not in h, c


def test_no_source_study_is_said_plainly(monkeypatch):
    monkeypatch.setattr(origins, "columns", lambda c: [])
    monkeypatch.setattr(origins, "emission_columns", lambda c: [])
    monkeypatch.setattr(origins, "partials", lambda c: causes.table().iloc[0:0])
    s = origins.render("Chennai")
    assert "no source study" in _text(s.html)


def test_a_group_with_no_chart_gets_one_sentence_not_an_empty_chart():
    assert "no measure" in measures.no_chart_sentence(["Chennai: exposure measures"]).lower()


# ------------------------------------------------------------------ the index

def test_index_has_one_row_per_city_in_order(pages):
    assert [r["city"] for r in pages.rows] == list(CITIES)
    body = pages.index.split("<tbody>")[1].split("</tbody>")[0]
    assert body.count("<tr>") == len(CITIES)
    for c in CITIES:
        assert f'href="{c.lower()}/index.html"' in body


def test_index_columns_are_the_four_asked_for(pages):
    head = _text(pages.index.split("<thead>")[1].split("</thead>")[0])
    for word in ("PM2.5", "deaths", "studies", "measures"):
        assert word in head


def test_index_numbers_match_the_pages(pages):
    total = len([p for p in library.LIBRARY.glob("*.toml") if not p.name.startswith("_")])
    for r in pages.rows:
        c = r["city"]
        page_text = " ".join(_text(pages.html[c]).split())
        ann = ground.annual(c)
        last = ann.loc[ann.year.idxmax()]
        assert r["pm25_year"] == int(last.year) and r["pm25"] == pytest.approx(float(last.pm25))
        assert f"{last.pm25:,.1f}" in page_text
        assert r["studies"] == len(causes.studies(c))
        assert r["measures"] == len(measures.find(c)) and r["measures_total"] == total
        assert f"{r['measures']} of the {total} library measures apply to {c}" in page_text
        lo, hi = f"{r['deaths_low']:,.0f}", f"{r['deaths_high']:,.0f}"
        assert f"{lo}" in page_text and f"{hi}" in page_text, c
        assert r["deaths_low"] < r["deaths_high"]


def test_index_shows_the_numbers_as_text(pages):
    text = " ".join(_text(pages.index).split())
    for r in pages.rows:
        assert f"{r['pm25']:.1f}" in text
        assert f"{r['deaths_low']:,.0f}" in text and f"{r['deaths_high']:,.0f}" in text


def test_index_says_it_is_not_a_ranking(pages):
    assert "not a ranking" in " ".join(_text(pages.index).split())


def test_index_is_self_contained_and_clean(pages):
    h = pages.index
    assert "<script" not in h and "url(http" not in h
    assert "font-face" in h and "--bg" in h and "prefers-color-scheme: dark" in h
    assert not re.search(r"\b(nan|None|NaN|inf)\b", _text(h))


def test_index_row_uses_the_same_toll_as_the_findings_block(pages, no_ihme):
    for r in pages.rows:
        line = findings._toll(r["city"])
        assert f"{r['deaths_low']:,.0f}" in line and f"{r['deaths_high']:,.0f}" in line
