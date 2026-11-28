"""Page polish: plain names, a curve-neutral order, the findings block, and the phone drawing."""
import ast
import html as html_
import re
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from airhealth import causes, curves, measures as library, paths
from citypage import burden, findings, measures, names, svg
from citypage.build import READINGS, build
from citypage.measures import Entry, MeasureFile, ordered, ratios, score_all

LIB = library.LIBRARY
FIXTURE = ("lpg_refill_subsidy", "road_paving", "school_purifiers", "smog_tower",
           "fgd_scrubbers", "stubble_pes_upfront", "construction_dust_controls",
           "waste_collection_burning_ban", "n95_winter")
N = 200


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    lib = tmp_path_factory.mktemp("lib")
    for i in FIXTURE:
        if (LIB / f"{i}.toml").exists():
            shutil.copy(LIB / f"{i}.toml", lib / f"{i}.toml")
    mp = pytest.MonkeyPatch()
    mp.setattr(paths, "LOCAL", tmp_path_factory.mktemp("nolocal"))   # the open tier only
    try:
        out = tmp_path_factory.mktemp("out") / "index.html"
        html = build(out=out, n=N, measures_folder=lib).read_text()
        entries = score_all("Bengaluru", lib, n=N)
    finally:
        mp.undo()
    return SimpleNamespace(html=html, entries=entries, lib=lib)


def _svgs(html):
    return re.findall(r"<svg.*?</svg>", html, flags=re.S)


def _text(markup):
    return html_.unescape(re.sub(r"<[^>]+>", " ", markup))


# ------------------------------------------------------------------ plain names

def test_every_curve_study_and_map_has_a_plain_name():
    for c in curves.catalogue().name:
        assert c in names.CURVES
    for s in causes.studies("Bengaluru"):
        assert s in names.STUDIES
    assert {"cpcb", "aqli", "acag_total", "gbd2019", "gbd2023"} <= set(names.MAPS)


def test_plain_names_match_the_descriptions_they_come_from():
    cat = curves.catalogue()
    labels = dict(zip(cat.name, cat.label))
    for cid, plain in names.CURVES.items():
        if cid in labels:
            for token in re.findall(r"[A-Z][a-z]+ \d{4}|GBD \d{4}|GEMM|AQLI", plain):
                assert token.split()[0] in labels[cid], (cid, token)
            for year in re.findall(r"\d{4}", plain):
                assert year in labels[cid], (cid, year)
    t = causes.table()
    norm = lambda x: re.sub(r"[^a-z0-9]", "", x.lower())
    for sid, plain in names.STUDIES.items():
        year = re.search(r"\d{4}", plain).group(0)
        assert year in sid, sid                      # the year the study's id carries
        first = norm(re.split(r"[ (]", plain)[0])
        assert first in norm(sid) or first in norm(" ".join(t[t.study == sid].institution.unique())), sid


def test_no_code_id_in_any_chart_text(built):
    ids = [i for i in names.every_id() if i != "aqli"] + ["aqli"]
    svgs = _svgs(built.html)
    assert svgs
    for s in svgs:
        for i in ids:
            assert not re.search(rf"\b{i}\b", html_.unescape(s)), i


def test_plain_names_appear_in_the_page(built):
    for plain in ("Jaganathan 2024 (log-linear)", "APnA 2015 (emissions model)",
                  "CSTEP 2022 (receptor study)", "ACAG satellite", "CPCB monitors",
                  "AQLI satellite"):
        assert html_.escape(plain) in built.html or plain in built.html, plain


# ------------------------------------------------------------------ order

def _score(per_curve, gaps=()):
    return SimpleNamespace(per_curve={c: {"expected_life_years_per_crore": v}
                                      for c, v in per_curve.items()}, gaps=set(gaps))


def _entry(name, **kw):
    e = Entry(MeasureFile(Path(f"{name}.toml"), name, None))
    e.scores[None] = _score(**kw)
    return e


def test_worst_curve_orders_and_gap_curves_are_left_out(monkeypatch):
    monkeypatch.setattr(measures.rank, "curve_gap", lambda s, c: c in s.gaps)
    a = _entry("a", per_curve={"x": 5.0, "y": 50.0})           # worst 5
    b = _entry("b", per_curve={"x": 3.0, "y": 900.0})          # worst 3
    c = _entry("c", per_curve={"x": 1.0, "y": 40.0}, gaps=("x",))   # x excluded: worst 40
    d = _entry("d", per_curve={"x": None, "y": None})          # no ratio: last
    got = [e.file.name for e in ordered([d, a, b, c], ["x", "y"])]
    assert got == ["c", "a", "b", "d"]
    assert ratios(c.scores[None], ["x", "y"]) == {"y": 40.0}


def test_no_ratio_entries_keep_library_order(monkeypatch):
    monkeypatch.setattr(measures.rank, "curve_gap", lambda s, c: False)
    a, b = (_entry(n, per_curve={"x": None}) for n in "ab")
    assert [e.file.name for e in ordered([b, a], ["x"])] == ["b", "a"]


def test_page_states_the_order_and_follows_it(built):
    assert measures.ORDER_LINE in html_.unescape(built.html)
    assert "worst (lowest) expected life-years per crore" in html_.unescape(built.html)
    names_ = measures.curve_names_of(built.entries, [])
    full, part, _ = measures.groups(built.entries, names_)
    each = built.html[built.html.index("<h3>Each measure</h3>"):]
    for grp in (full, part):
        at = [each.index(html_.escape(next(iter(e.scores.values())).name)) for e in grp]
        assert at == sorted(at)
        w = [measures.worst(list(e.scores.values()), names_) for e in grp]
        w = [x for x in w if x is not None]
        assert w == sorted(w, reverse=True)


# ------------------------------------------------------------------ findings

def test_findings_block_is_at_the_top_with_a_few_lines(built):
    i = built.html.index('class="card findings"')
    assert i < built.html.index("<h2>") if "<h2>" in built.html else True
    assert i < built.html.index('<nav class="contents"')
    block = built.html[i:built.html.index("</div>", i)]
    assert 4 <= block.count("<li>") <= 6


def test_findings_numbers_are_the_computed_ones(built):
    ls = findings.lines("Bengaluru", built.entries)
    text = " ".join(ls).replace(" *", "")          # the derived-deaths mark is tested apart
    rows = [r["deaths_averted"] for m in burden._maps() for r in burden.burden("Bengaluru", m)["rows"]]
    assert f"{min(rows):,.0f} to {max(rows):,.0f}" in text
    lv = [burden.level("Bengaluru", m)[0] for m in burden._maps()]
    assert f"{min(lv):.1f} to {max(lv):.1f}" in text
    for t in burden.targets():
        if t.url:
            assert f"{t.pm25:g} µg/m³" in text          # India's standard and WHO's guideline
    assert "enforcement-only" in text and "full cost" in text


def test_findings_module_types_no_digits():
    tree = ast.parse(Path(findings.__file__).read_text())
    docs = {id(n.body[0].value) for n in ast.walk(tree)
            if isinstance(n, (ast.Module, ast.FunctionDef))
            and n.body and isinstance(n.body[0], ast.Expr)
            and isinstance(getattr(n.body[0], "value", None), ast.Constant)}
    skip = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.FormattedValue) and n.format_spec is not None:
            skip |= {id(x) for x in ast.walk(n.format_spec)}     # ".1f" and the like
    bad = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Constant) and isinstance(n.value, str) \
                and id(n) not in docs and id(n) not in skip:
            if re.search(r"\d", re.sub(r"<[^>]+>", "", n.value).replace("PM2.5", "")):
                bad.append(n.value)
    assert not bad, bad


def test_readings_line_is_on_the_page(built):
    assert html_.escape(READINGS) in built.html or READINGS in html_.unescape(built.html)
    assert "CPCB monitors" in READINGS and "ACAG satellite map" in READINGS


# ------------------------------------------------------------------ phone

def test_every_chart_has_a_narrow_twin_that_fits_a_phone(built):
    html = built.html
    assert html.count('class="chart wide"') == html.count('class="chart narrow"') > 0
    assert "@media (max-width:600px)" in html and "min-width:" not in html.split("</style>")[1]
    for s in re.findall(r'<div class="chart narrow">(<svg.*?</svg>)', html, flags=re.S):
        w = int(re.search(r'viewBox="0 0 (\d+) ', s).group(1))
        assert w <= 360
        for m in re.finditer(r'<text([^>]*)>(.*?)</text>', s, flags=re.S):
            attrs, inner = m.groups()
            if "rotate" in attrs:
                continue
            for tsp in re.findall(r"<tspan[^>]*>(.*?)</tspan>", inner) or \
                    [re.sub(r"<title>.*?</title>", "", inner)]:
                label = html_.unescape(re.sub(r"<[^>]+>", "", tsp))
                x = float(re.search(r'\bx="([\d.]+)"', attrs + (m.group(0) if "tspan" in inner else "")).group(1))
                half = 6.0 * len(label)
                if 'text-anchor="end"' in attrs:
                    lo, hi = x - half, x
                elif 'text-anchor="middle"' in attrs:
                    lo, hi = x - half / 2, x + half / 2
                else:
                    lo, hi = x, x + half
                assert lo >= -2 and hi <= w + 2, (label, lo, hi)


def test_narrow_chart_stacks_its_legend_and_labels_above_rows():
    s = svg.dot_rows(["Jaganathan 2024 (log-linear)"], [("CPCB monitors", [1.0]), ("ACAG satellite", [2.0])],
                     title="t", x_label="x")
    narrow = s[s.index('class="chart narrow"'):]
    ys = [float(v) for v in re.findall(r'<circle class="f\d" cx="18" cy="([\d.]+)"', narrow)]
    assert len(ys) == 2 and ys[1] > ys[0]                    # one legend row under the other
    assert re.search(r'<text class="lab" x="14" y="[\d.]+">Jaganathan', narrow)   # label above


def _fake_burden(rows):
    return lambda city, m: {"rows": [dict(curve=c, deaths_averted=d, deaths_derived=x)
                                     for c, d, x in rows]}


def test_findings_headline_marks_a_derived_end_and_carries_the_footnote(monkeypatch):
    monkeypatch.setattr(burden, "_maps", lambda: ["acag_total"])
    monkeypatch.setattr(burden, "burden", _fake_burden(
        [("gemm_ncd_lri", 1000.0, True), ("gemm_5cod", 2000.0, False)]))
    text = findings._toll("Bengaluru")
    assert "1,000 * to 2,000 deaths" in text         # the lowest is derived, the highest is not
    assert burden.STAR in text
    monkeypatch.setattr(burden, "burden", _fake_burden(
        [("gemm_ncd_lri", 1000.0, False), ("gemm_5cod", 2000.0, True)]))
    text = findings._toll("Bengaluru")
    assert "1,000 to 2,000 * deaths" in text and burden.STAR in text


def test_findings_headline_has_no_marker_when_no_end_is_derived(monkeypatch):
    monkeypatch.setattr(burden, "_maps", lambda: ["acag_total"])
    monkeypatch.setattr(burden, "burden", _fake_burden(
        [("gemm_ncd_lri", 1000.0, False), ("gemm_5cod", 2000.0, False), ("gemm_5cod", 1500.0, True)]))
    text = findings._toll("Bengaluru")
    assert "*" not in text and burden.STAR not in text     # the derived row is in the middle
