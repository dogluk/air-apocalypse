import re

import numpy as np

from airhealth import causes
from citypage.origins import PLAIN, blind_spots, columns, emission_columns, partials, render


def test_plain_covers_harmonised():
    assert set(PLAIN) == set(causes.HARMONISED)


def test_bengaluru_has_four_complete_columns():
    cols = columns("Bengaluru")
    assert [(c.study, c.season) for c in cols][0] == ("apna_2015", "annual")
    assert len(cols) == 4
    apna = cols[0]
    assert apna.shares["transport"] == 26.5 and apna.shares["outside"] == 15.6


def test_not_reported_stays_nan():
    cstep = next(c for c in columns("Bengaluru") if c.study.startswith("cstep") and c.season == "annual")
    assert np.isnan(cstep.shares["residential"])


def test_blind_spots_are_specific():
    cols = columns("Bengaluru")
    apna = cols[0]
    cstep = next(c for c in cols if c.study.startswith("cstep") and c.season == "annual")
    assert any("outside" in s and "15.6" in s for s in blind_spots(apna))
    assert any("cannot say how much came from outside" in s for s in blind_spots(cstep))
    assert any(PLAIN["residential"] in s for s in blind_spots(cstep))


def test_not_reported_renders_as_dash():
    html = render("Bengaluru").html
    assert "—" in html and "does not report" in html
    assert not re.search(r"\bnan\b", html, flags=re.I)


def test_partials_listed():
    assert len(partials("Bengaluru")) > 0 and "Jun-Sep" in render("Bengaluru").html


def test_emission_columns_empty_ok():
    assert emission_columns("Bengaluru") == []
    assert render("Bengaluru").id == "sources"


def test_does_not_report_names_only_sources_a_reader_knows():
    html = render("Bengaluru").html
    sentences = re.findall(r"It does not report: ([^<]*)\.", html)
    assert sentences
    for s in sentences:
        for bad in ("local_all", "all sources inside the city, not split", "from outside the city",
                    "other sources", "source not assigned", "not split further"):
            assert bad not in s
