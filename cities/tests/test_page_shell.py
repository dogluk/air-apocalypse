from citypage import page
from citypage.page import Section


def test_page_is_self_contained():
    html = page.page("T", "<p>i</p>", [Section("ground", "One", "<p>a</p>")], "<p>f</p>")
    assert html.startswith("<!doctype html>")
    assert "@font-face" in html and "base64," in html and "Young Serif" in html
    assert "<script src" not in html and "url(http" not in html and 'rel="stylesheet"' not in html
    assert "prefers-color-scheme: dark" in html
    assert '<section id="ch-ground">' in html and 'href="#ch-ground"' in html


def test_fmt_missing_and_kinds():
    assert page.fmt(None) == "no data" and page.fmt(float("nan"), missing="—") == "—"
    assert page.fmt(11154.7) == "11,155" and page.fmt(0.17215, "pct") == "17.2%"
    assert page.fmt(18.2e6, "usd") == "$18.2 M"
    assert page.fmt(61.7, "usd") == "$61.7" and page.fmt(1250, "usd") == "$1,250"
    assert page.fmt(26.5, "pct_points") == "26.5%" and page.fmt(2.67, "years") == "+2.67"
    assert page.fmt(3.14159, "1dp") == "3.1"


def test_table_escapes():
    assert "&lt;b&gt;" in page.table(["a"], [["<b>"]])
    assert "class=num" in page.table(["a", "b"], [["1", "2"]], numeric=(1,))
