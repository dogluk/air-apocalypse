import re

from airhealth import paths
from airhealth.provenance import load_sources
from citypage.build import DATA_FILES, build, main


def test_page_builds_without_ihme(no_ihme, tmp_path):
    out = build(out=tmp_path / "index.html", n=200, measures_folder=tmp_path)
    html = out.read_text()
    for cid in ("ground", "sources", "health", "measures"):
        assert f'id="ch-{cid}"' in html
    assert "IHME files: absent" in html and "gemm_5cod" in html


def test_page_has_no_nan_or_none(no_ihme, tmp_path):
    html = build(out=tmp_path / "i.html", n=200, measures_folder=tmp_path).read_text()
    text = re.sub(r"<[^>]+>", " ", re.sub(r"<style.*?</style>|<svg.*?</svg>", "", html, flags=re.S))
    assert not re.search(r"\b(nan|None|NaN|inf)\b", text)


def test_build_is_deterministic(no_ihme, tmp_path):
    a = build(out=tmp_path / "a.html", n=200, measures_folder=tmp_path).read_text()
    b = build(out=tmp_path / "b.html", n=200, measures_folder=tmp_path).read_text()
    assert a == b


def test_page_is_offline(no_ihme, tmp_path):
    html = build(out=tmp_path / "i.html", n=200, measures_folder=tmp_path).read_text()
    assert "<script src" not in html and "url(http" not in html


def test_build_line_and_footer(no_ihme, tmp_path):
    html = build(out=tmp_path / "i.html", n=200, measures_folder=tmp_path).read_text()
    assert "python -m citypage.build --city Bengaluru" in html
    assert "n = 200" in html and "seed = 0" in html
    assert "Vonter/india-cpcb-aqi" in html and "ODbL" in html
    assert "SIL Open Font License" in html


def test_every_listed_data_file_exists_and_has_a_source():
    sources = load_sources()
    for f in DATA_FILES:
        assert (paths.DATA / f).exists(), f
        assert f in sources, f


def test_main_prints_the_path(no_ihme, tmp_path, capsys):
    out = tmp_path / "x.html"
    assert main(["--out", str(out), "--n", "100"]) == 0
    assert str(out) in capsys.readouterr().out and out.exists()
