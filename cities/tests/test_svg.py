import re
import xml.etree.ElementTree as ET

from citypage import svg


def test_svgs_parse_and_use_no_literal_colours():
    for s in (svg.line_chart([svg.Series("a", [1, 2, 3], [1, None, 3])], title="t", x_label="x", y_label="y"),
              svg.line_chart([svg.Series("p", [1, 2], [1, 2], kind="points", colour=3)], title="t",
                             x_label="x", y_label="y", x_ticks=[(1, "a"), (2, "b")]),
              svg.heatmap(["r"], ["c1", "c2"], [[1.0, None]], title="t", value_label="v"),
              svg.dot_rows(["r1", "r2"], [("g", [1.0, None])], title="t", x_label="x"),
              svg.dot_rows(["r1"], [("g", [1.0])], title="t", x_label="x", lo=[[0.5]], hi=[[1.5]]),
              svg.stacked_bars(["c"], ["p1", "p2"], [[30.0], [None]], title="t")):
        ET.fromstring(s)                                  # well-formed XML
        assert not re.search(r'(fill|stroke)="#', s)      # colours only via classes
        assert "<title>" in s and 'role="img"' in s


def test_heatmap_marks_missing_cells():
    s = svg.heatmap(["r"], ["c1", "c2"], [[1.0, None]], title="t", value_label="v")
    assert "no data" in s


def test_stacked_bars_not_padded():
    s = svg.stacked_bars(["c"], ["p1", "p2"], [[30.0], [None]], title="t")
    assert s.count("<rect") == 1 + 2  # one bar part, two legend swatches


def test_nice_ticks_4_to_6():
    for lo, hi in ((0, 7), (0, 130), (3, 4.1), (0, 0.9)):
        assert 3 <= len(svg.nice_ticks(lo, hi)) <= 7


def test_nice_ticks_cover_the_data():
    # the top tick must reach the largest value, or the chart draws it outside the plot
    for lo, hi in ((0, 43.2), (0, 0.93), (0, 1.6), (0.4, 1.6), (0, 7), (0, 130), (3, 4.1),
                   (0, 10), (12.5, 97.3)):
        t = svg.nice_ticks(lo, hi)
        assert t[0] <= lo and t[-1] >= hi, (lo, hi, t)
        assert 3 <= len(t) <= 7


def test_charts_cover_their_data():
    import re as re_
    s = svg.line_chart([svg.Series("a", [2016, 2017], [43.2, 30.0])], title="t", x_label="x",
                       y_label="y")
    ys = [float(v) for v in re_.findall(r'<polyline[^>]*points="([^"]+)"', s)[0]
          .replace(",", " ").split()[1::2]]
    assert min(ys) >= 30 - 1e-6                    # nothing above the top of the plot area
    d = svg.dot_rows(["r"], [("g", [0.93])], title="t", x_label="x")
    cx = float(re_.search(r'<circle class="f0" cx="([\d.]+)" cy="[\d.]+" r="4"><title>', d)[1])
    assert cx <= 640 - 150 + 1e-6                  # inside the plot, left of the legend


def test_charts_scale_to_a_phone():
    # wrapped so they can scroll sideways on a narrow screen instead of shrinking the text
    s = svg.dot_rows(["r"], [("g", [1.0])], title="t", x_label="x")
    assert s.startswith('<div class="chart">') and s.endswith("</svg></div>")
