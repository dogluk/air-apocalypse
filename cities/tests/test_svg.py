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
