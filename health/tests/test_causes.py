import tomllib

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
             size_fraction="PM2.5", method="CMB", metric="concentration_share", boundary="site",
             origin="all_origins", covers="all",
             source_raw="x", source_harmonised="transport", share_pct=100.0, n_sites=None, n_days=None,
             url="u", locator="l", evidence_key="O")
    r.update(kw)
    return r


def test_validate_names_the_bad_group():
    ok = pd.DataFrame([_row(share_pct=60.0), _row(source_raw="y", source_harmonised="other", share_pct=40.0)])
    causes.validate(ok)
    bad = pd.DataFrame([_row(share_pct=60.0), _row(source_raw="y", source_harmonised="other", share_pct=30.0)])
    with pytest.raises(ValueError, match="Chennai.*sum"):
        causes.validate(bad)
    with pytest.raises(ValueError, match="Atlantis"):
        causes.validate(pd.DataFrame([_row(city="Atlantis")]))
    with pytest.raises(ValueError, match="smoke"):
        causes.validate(pd.DataFrame([_row(source_harmonised="smoke")]))
    with pytest.raises(ValueError, match="metric"):
        causes.validate(pd.DataFrame([_row(share_pct=50.0), _row(source_raw="y", source_harmonised="other", share_pct=50.0,
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


@pytest.mark.parametrize("city, study, season, cause, share", [
    # one pinned value per transcribed study, each read in the report PDF (locator in the row says where)
    ("Delhi", "arai_teri_delhi2018_receptor", "winter", "secondary_unassigned", 26),      # Fig E.5, p. E7
    ("Delhi", "arai_teri_delhi2018_dispersion", "summer", "dust", 38),                    # Table E.2, p. E13
    ("Delhi", "arai_teri_delhi2018_region", "winter", "local_all", 36),                      # Fig E.9, p. E18: Delhi's own
    ("Delhi", "govardhan2024_dss", "post-monsoon", "outside", 59),                        # Fig 7b: 25 + 8 + 26
    ("Kolkata", "teri_kolkata2025_cmb", "winter+summer campaigns", "residential", 29),                    # Fig E4: cooking
    ("Kolkata", "teri_kolkata2025_cmaq", "winter", "residential", 18),                    # Table 42
    ("Kolkata", "teri_kolkata2025_cmaq_region", "winter", "outside", 68),                 # Fig 73: 15 + 10 + 43
    ("Lucknow", "teri_lucknow2022_cmaq", "winter", "residential", 27),                    # Table 26
    ("Lucknow", "teri_lucknow2022_region", "summer", "outside", 81),                      # Fig 60: 5 + 5 + 52 + 19
    ("Kanpur", "iitk_kanpur2022_pmf", "winter", "transport", 29.9),                       # Table 4.8
    ("Kanpur", "iitk_kanpur2022_pmf", "summer", "dust", 33.8),                            # Table 4.12: 21.9 + 11.9
    ("Patna", "teri_patna2021_cmb", "winter", "secondary_unassigned", 38),                # Fig 4.3
    ("Patna", "teri_patna2021_cmb", "summer", "industry", 27),                            # Fig 4.3
    ("Agra", "iitk_agra2021_pmf", "winter", "transport", 22.8),                           # Table 4.8
    ("Agra", "iitk_agra2021_pmf", "summer", "dust", 37.4),                                # Table 4.12: 34.5 + 2.9
    ("Mumbai", "neeri_iitb_mumbai2023_pmf", "summer", "natural", 26),                     # Table 4.1: marine aerosols
    ("Pune", "neeri_iitb_pune2024_pmf", "winter", "dust", 21),                            # Table 4.1: road dust 9 + construction 12
    ("Bengaluru", "cstep_bengaluru2022_cmb", "annual", "transport", 39.9),                # Fig 15
    ("Bengaluru", "cstep_bengaluru2022_cmb", "winter", "secondary_unassigned", 20),       # Table 30: 4 + 16
    ("Hyderabad", "iitk_hyderabad2023_pmf", "winter", "transport", 29.5),                 # Table 4.8
    ("Hyderabad", "iitk_hyderabad2023_pmf", "summer", "dust", 43.3),                      # Table 4.12: 31.5 + 11.8
    ("Surat", "teri_surat2021_cmb", "winter", "secondary_unassigned", 33),                # Fig 4.3
    ("Surat", "teri_surat2021_cmaq", "summer", "outside", 57),                            # Table 6.1: international
    ("Surat", "teri_surat2021_cmaq_region", "winter", "outside", 83),                     # Fig 6.4: 7 + 76
    ("Delhi", "biswal2025_2023", "post-monsoon", "agri_burning", 16),                     # Sec. 3.4 / Fig 7
    ("Delhi", "kulkarni2020", "post-monsoon", "agri_burning", 20),                        # abstract
])
def test_transcribed_values(city, study, season, cause, share):
    t = causes.for_city(city, study)
    assert len(t), f"no rows for {city} / {study}"
    got = t[(t.season == season) & (t.source_harmonised == cause)].share_pct.sum()
    assert got == pytest.approx(share, abs=0.05)


def test_stubble_rows_are_partial():
    s = causes.table().query("source_harmonised == 'agri_burning' and covers == 'partial'")
    assert "Delhi" in set(s.city)
    assert set(s.months.unique()) <= {"10,11", "10,11,12", "11", "10"}   # whatever the studies state; no annual
    assert set(s.metric) == {"concentration_share"}
    assert set(s.origin) == {"all_origins"}


def test_no_press_or_memory_rows():
    assert set(causes.table().evidence_key) == {"O"}
    assert not causes.table().study.str.startswith(("dss_loksabha", "nagar_sharma")).any()


def test_origin_vocabulary_and_assignment():
    t = causes.table()
    assert set(t.origin) == set(causes.ORIGINS)
    apna = t[t.study.str.startswith("apna")]
    assert (apna[apna.source_harmonised == "outside"].origin == "region").all()
    assert (apna[apna.source_harmonised != "outside"].origin == "inside").all()
    for kind in ("mcduffie2021", "_cmb", "_pmf", "_receptor", "_dispersion", "teri_kolkata2025_cmaq",
                 "teri_lucknow2022_cmaq", "teri_surat2021_cmaq"):
        sel = t[t.study.str.contains(kind) & ~t.study.str.contains("_region")]
        assert len(sel) and set(sel.origin) == {"all_origins"}, kind
    geo = t[t.study.str.endswith("_region") | (t.study == "govardhan2024_dss")]
    assert set(geo.origin) == {"region"}
    assert (t[t.covers == "partial"].study.str.endswith("_region")
            | (t[t.covers == "partial"].origin == "all_origins")).all()
    assert (t[t.study == "mcduffie2021"].boundary == "grid_cell").all()


def test_geographic_splits_use_local_all_and_outside_only():
    t = causes.table()
    geo = t[t.study.str.endswith("_region")]
    assert set(geo.source_harmonised) == {"local_all", "outside"}
    assert set(t[t.source_harmonised == "local_all"].origin) == {"region"}
    gov = t[(t.study == "govardhan2024_dss") & (t.season == "winter")].set_index("source_harmonised")
    assert gov.loc["other", "share_pct"] == 20       # Delhi's sectors except transport: not all of Delhi's own
    assert "local_all" not in gov.index


def test_validate_rejects_local_all_beside_a_sector_row():
    rows = [_row(origin="region", source_harmonised="local_all", share_pct=40.0),
            _row(origin="region", source_raw="y", source_harmonised="outside", share_pct=60.0)]
    causes.validate(pd.DataFrame(rows))
    rows[1] = _row(origin="region", source_raw="y", source_harmonised="transport", share_pct=60.0)
    with pytest.raises(ValueError, match="local_all.*transport"):
        causes.validate(pd.DataFrame(rows))


def test_sources_toml_states_the_real_counts():
    src = tomllib.loads((paths.DATA / "sources.toml").read_text())
    t = pd.read_csv(paths.DATA / "causes_transcribed.csv")
    assert (f"{len(t)} rows, {t.study.nunique()} study ids, {t.city.nunique()} cities"
            in src["causes_transcribed.csv"]["source"])
    c = causes.table()
    assert f"{len(c)} rows, {c.study.nunique()} study ids, {c.city.nunique()} cities" in src["causes.csv"]["source"]


def test_locator_sentences_are_separated():
    assert not causes.table().locator.str.contains(r"[a-z] (?:Mapped to|Transport includes)").any()


def test_kolkata_summer_region_is_complete_with_derived_row():
    g = causes.for_city("Kolkata", "teri_kolkata2025_cmaq_region").query("season == 'summer'")
    assert set(g.covers) == {"all"} and g.share_pct.sum() == pytest.approx(100)
    d = g[g.source_raw.str.contains("derived")].iloc[0]
    assert d.share_pct == 2 and "DERIVED" in d.locator


def test_shares_is_nan_for_unreported_causes():
    s = causes.shares("Delhi", "govardhan2024_dss", "winter")
    assert list(s.index) == list(causes.HARMONISED)
    assert s["transport"] == 14 and s["other"] == 20 and pd.isna(s["local_all"])
    assert pd.isna(s["industry"]) and pd.isna(s["dust"])          # not reported, not 0
    k = causes.shares("Kanpur", "iitk_kanpur2022_pmf", "winter")
    assert k["other"] >= 3.5 and pd.isna(k["residential"])
    with pytest.raises(KeyError):
        causes.shares("Delhi", "govardhan2024_dss", "monsoon")
    with pytest.raises(KeyError):
        causes.shares("Atlantis", "x", "annual")


def test_coal_and_fly_ash_is_other():
    t = causes.table()
    f = t[t.source_raw.str.contains("fly ?ash", case=False) & t.study.str.contains("iitk")]
    assert len(f) == 6 and set(f.source_harmonised) == {"other"}


def test_kolkata_cmb_is_not_labelled_annual():
    k = causes.for_city("Kolkata", "teri_kolkata2025_cmb")
    assert set(k.season) == {"winter+summer campaigns"} and set(k.months) == {"12,1,4,5"}


@pytest.mark.parametrize("change, match", [
    (dict(evidence_key="S"), "evidence_key"),
    (dict(evidence_key="R"), "evidence_key"),
    (dict(origin="everywhere"), "origin"),
    (dict(size_fraction="PM10"), "size_fraction"),
    (dict(method="guess"), "method"),
    (dict(boundary="county"), "boundary"),
    (dict(months="13"), "months"),
    (dict(months="winter"), "months"),
    (dict(source_harmonised="local_all"), "local_all"),
])
def test_validate_rejects_bad_vocabulary(change, match):
    with pytest.raises(ValueError, match=match):
        causes.validate(pd.DataFrame([_row(**change)]))


def test_validate_rejects_duplicates():
    with pytest.raises(ValueError, match="duplicate"):
        causes.validate(pd.DataFrame([_row(share_pct=50.0), _row(share_pct=50.0)]))
