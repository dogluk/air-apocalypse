import pandas as pd
import pytest

from airhealth import causes, paths


def test_apna_rows_match_the_published_file():
    t = causes.table()
    a = t[t.study.str.startswith("apna")]
    assert a.city.nunique() == 49
    chennai = a[a.city == "Chennai"].set_index("source_harmonised").share_pct
    assert chennai["outside"] == 13.3 and chennai["transport"] == 24.5
    assert "natural" not in a[a.city == "Delhi"].source_harmonised.values      # Delhi has no APnA row at all
    assert a[a.city == "Mumbai"].set_index("source_harmonised").share_pct["natural"] == 12.1


def test_apna_base_years_are_the_model_years_not_the_batch():
    t = causes.table()
    a = t[t.study.str.startswith("apna")].drop_duplicates("city").set_index("city")
    assert (a.loc["Chennai", "study"], a.loc["Chennai", "year_sampled"]) == ("apna_2015", 2015)
    assert (a.loc["Mumbai", "study"], a.loc["Mumbai", "year_sampled"]) == ("apna_2018", 2018)
    assert set(a.study) == {"apna_2015", "apna_2018"}


def test_complete_groups_sum_to_100():
    t = causes.table()
    g = t[t.covers == "all"].groupby(["city", "study", "season", "size_fraction", "metric"]).share_pct.sum()
    assert ((g - 100).abs() <= 2).all(), g[(g - 100).abs() > 2]


def test_metrics_never_mix():
    t = causes.table()
    assert (t.groupby(["city", "study", "season"]).metric.nunique() == 1).all()


def test_every_city_is_known():
    known = set(pd.read_csv(paths.DATA / "cities.csv").city)
    assert set(causes.table().city) <= known
    assert set(causes.table().source_harmonised) <= set(causes.HARMONISED)


def test_for_city_and_studies():
    assert causes.studies("Chennai")[0].startswith("apna")
    assert set(causes.for_city("Chennai").columns) == set(causes.COLUMNS)
    with pytest.raises(KeyError):
        causes.for_city("Atlantis")


def _row(**kw):
    r = dict(city="Chennai", study="s", institution="i", year_sampled=2020, season="annual", months="1-12",
             size_fraction="PM2.5", method="CMB", metric="concentration_share", boundary="site", covers="all",
             source_raw="x", source_harmonised="transport", share_pct=100.0, n_sites=None, n_days=None,
             url="u", locator="l", evidence_key="O")
    r.update(kw)
    return r


def test_validate_names_the_bad_group():
    ok = pd.DataFrame([_row(share_pct=60.0), _row(source_harmonised="other", share_pct=40.0)])
    causes.validate(ok)
    bad = pd.DataFrame([_row(share_pct=60.0), _row(source_harmonised="other", share_pct=30.0)])
    with pytest.raises(ValueError, match="Chennai.*sum"):
        causes.validate(bad)
    with pytest.raises(ValueError, match="Atlantis"):
        causes.validate(pd.DataFrame([_row(city="Atlantis")]))
    with pytest.raises(ValueError, match="smoke"):
        causes.validate(pd.DataFrame([_row(source_harmonised="smoke")]))
    with pytest.raises(ValueError, match="metric"):
        causes.validate(pd.DataFrame([_row(share_pct=50.0), _row(source_harmonised="other", share_pct=50.0,
                                                                   metric="emission_share")]))
    with pytest.raises(ValueError, match="columns"):
        causes.validate(ok.drop(columns=["url"]))


# Kanpur, McDuffie 2021 Supplementary Data 1: Residential Coal 1.6 + Biofuel 24.5 + Other 2.2, read in the xlsx
RESIDENTIAL_KANPUR = 28.3


def test_mcduffie_rows():
    m = causes.table().query("study == 'mcduffie2021'")
    assert {"Kanpur", "Mumbai", "Kolkata"} <= set(m.city)
    kanpur = m[m.city == "Kanpur"].groupby("source_harmonised").share_pct.sum()
    assert kanpur["residential"] == pytest.approx(RESIDENTIAL_KANPUR, abs=0.05)
    assert (m.method == "GEOS-Chem").all() and (m.year_sampled == 2017).all()
