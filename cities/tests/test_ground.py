import pytest

from citypage import page
from citypage.ground import (annual, fingerprints, hour_of_day, maps_compared, month_by_year,
                             render, station_coverage)


def test_annual_reads_exposure_cpcb():
    a = annual("Bengaluru").set_index("year")
    assert a.loc[2025, "pm25"] == 27.9 and a.loc[2025, "stations"] == 12   # read from exposure_cpcb.csv


def test_hour_of_day_has_24_values():
    h = hour_of_day("Bengaluru")
    assert list(h.index) == list(range(24)) and h.notna().all()


def test_missing_cells_are_none_not_zero():
    cov = station_coverage("Bengaluru")
    assert cov.isna().any().any()                       # stations added after 2016: NaN, not 0
    m = month_by_year("Bengaluru")
    assert not (m == 0).any().any()                     # a dropped month is NaN
    s = render("Bengaluru").html
    assert "no data" in s


def test_fingerprints_are_relative_to_own_mean():
    f = fingerprints("Bengaluru")
    for p in ("pm25", "no2", "so2", "co", "o3"):
        col = f["hour"][p].dropna()
        assert col.mean() == pytest.approx(1, abs=0.05)


def test_maps_compared_keeps_every_map_apart():
    m = maps_compared("Bengaluru")
    assert {"cpcb", "aqli", "acag_total"} <= set(m['map'])
    assert len(m[m['map'] == "acag_total"]) == 1
    assert m.groupby(["map", "year"]).size().max() == 1    # never pooled


def test_render_has_charts_and_every_station():
    s = render("Bengaluru")
    assert s.id == "ground" and s.html.count("<svg") >= 5
    for name in station_coverage("Bengaluru").index:
        assert page.esc(name) in s.html
