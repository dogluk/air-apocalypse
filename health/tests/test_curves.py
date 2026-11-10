import numpy as np
import pytest

from airhealth import curves, paths
from airhealth.curves import Unavailable, get

IHME_TIER = ("gbd2019", "gbd2023", "gemm_5cod")


def test_delhi_100_to_80_on_indian_slope():
    c = get("loglinear_jaganathan")
    assert 0.14 < 1 - c.ratio(100, 80, 40) < 0.16


def test_no_benefit_below_floor():
    c = get("loglinear_jaganathan").with_floor(40)
    assert c.ratio(35, 20, 40) == 1.0
    assert c.ratio(50, 20, 40) == c.ratio(50, 40, 40)


def test_children_unaffected():
    assert get("gemm_ncd_lri").ratio(100, 50, 5) == 1.0
    assert get("loglinear_vodonos").ratio(100, 50, 20) == 1.0
    assert get("loglinear_brown").ratio(100, 50, 10) == 1.0


def test_each_curve_starts_at_its_own_age():
    # Jaganathan is estimated on all-age deaths, Brown at ages 15-69; GEMM's parameters
    # start at 25; AQLI's estimate is all-age life expectancy.
    ages = {c.name: c.min_age for c in curves.available()}
    assert ages == {"loglinear_jaganathan": 0, "loglinear_brown": 15, "loglinear_vodonos": 25,
                    "gemm_ncd_lri": 25, "aqli": 0}
    assert get("loglinear_jaganathan").ratio(100, 50, 5) < 1.0
    assert get("loglinear_jaganathan").ratio(100, 50, 0) < 1.0
    assert get("loglinear_brown").ratio(100, 50, 15) < 1.0
    assert get("loglinear_vodonos").ratio(100, 50, 25) < 1.0


def test_worse_air_raises_risk():
    assert get("gemm_ncd_lri").ratio(60, 90, 50) > 1.0


def test_gemm_flattens_relative_to_loglinear():
    g, l = get("gemm_ncd_lri"), get("loglinear_jaganathan")
    assert (1 - g.ratio(100, 80, 50)) < (1 - l.ratio(100, 80, 50))


def test_rr_vectorised_and_one_at_floor():
    g = get("gemm_ncd_lri")
    out = g.rr(np.array([0.0, g.floor, 50.0]), 60)
    assert out.shape == (3,)
    assert out[0] == out[1] == 1.0 and out[2] > 1.0


def test_aqli_delhi():
    # AQLI India fact sheet 2025: NCT of Delhi, PM2.5 88.4 in 2023, 8.2 years to gain at
    # the WHO guideline, 4.74 years at India's national standard of 40.
    a = get("aqli")
    assert a.delta_e0(88.4, 5) == pytest.approx(8.2, abs=0.1)
    assert a.delta_e0(88.4, 40) == pytest.approx(4.74, abs=0.01)
    assert a.delta_e0(88.4, 0) == a.delta_e0(88.4, 5)      # nothing below the guideline
    assert a.delta_e0(40, 88.4) == -a.delta_e0(88.4, 40)   # dirtier air costs years


def test_aqli_is_not_a_relative_risk():
    with pytest.raises(TypeError, match="life expectancy"):
        get("aqli").ratio(100, 80, 40)


def test_gemm_matches_published_point():
    # GEMM authors' calculator (DataGEMM, 'GEMM Calculator (PNAS)_ab.xlsx'), sheet
    # 'Burden_YesCN_NCD+LRI', India at 74.0 µg/m³ (the exposure of PNAS Table 1). Hazard
    # ratio implied by its printed deaths and its NCD+LRI baseline: 1 / (1 - deaths/baseline).
    # Age 25-29: 34252.54 / 87373.08; age 80+: 428408.96 / 1422883.50.
    g = get("gemm_ncd_lri")
    assert g.rr(74.0, 25) == pytest.approx(1.644808, rel=0.01)
    assert g.rr(74.0, 80) == pytest.approx(1.430789, rel=0.01)
    assert g.rr(74.0, 85) == g.rr(74.0, 80)                  # 80+ covers the 85+ band


def test_max_cohort_concentration_recorded():
    assert curves.MAX_COHORT_PM25 == 84.0
    assert "84" in curves.MAX_COHORT_PM25_SOURCE


def test_ihme_curve_without_files_explains(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "LOCAL", tmp_path)
    for name in IHME_TIER:
        with pytest.raises(Unavailable, match="IHME_DOWNLOADS.md") as e:
            get(name)
        assert ".csv" in str(e.value)
    with pytest.raises(Unavailable, match="gbd2019_pm_rr_summary.csv"):
        get("gbd2019")


def test_unknown_curve():
    with pytest.raises(KeyError, match="loglinear_jaganathan"):
        get("no_such_curve")


def test_catalogue_lists_every_curve(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "LOCAL", tmp_path)
    cat = curves.catalogue()
    assert list(cat.columns) == ["name", "label", "available", "needs", "source"]
    assert set(IHME_TIER) <= set(cat.name)
    assert not cat.set_index("name").loc[list(IHME_TIER), "available"].any()
    open_names = {c.name for c in curves.available()}
    assert {"loglinear_jaganathan", "loglinear_brown", "loglinear_vodonos",
            "gemm_ncd_lri", "aqli"} <= open_names
    assert set(cat[cat.available].name) == open_names
    assert cat.source.str.contains("http").all()


@pytest.mark.parametrize("name", ["loglinear_jaganathan", "loglinear_brown",
                                  "loglinear_vodonos", "gemm_ncd_lri"])
def test_sampling_is_reproducible_and_varies(name):
    c = get(name)
    a = [c.sample(np.random.default_rng(7)).ratio(100, 80, 60) for _ in range(2)]
    assert a[0] == a[1]
    rng = np.random.default_rng(7)
    draws = np.array([c.sample(rng).ratio(100, 80, 60) for _ in range(2000)])
    assert draws.std() > 0
    assert np.median(draws) == pytest.approx(c.ratio(100, 80, 60), abs=0.01)
    assert c.ratio(100, 80, 60) == get(name).ratio(100, 80, 60)   # sampling leaves the original
    assert c.sample(rng).min_age == c.min_age


def test_loglinear_slopes_as_published():
    # Jaganathan 2024: 8.6% (6.4-10.8) per 10; Brown 2022: RR 1.01 (1.00-1.03) per 10.
    j, b = get("loglinear_jaganathan"), get("loglinear_brown")
    assert j.pct_per_10 == pytest.approx(8.6)
    assert j.se_pct_per_10 == pytest.approx((10.8 - 6.4) / (2 * 1.959964))
    assert b.pct_per_10 == pytest.approx(1.0)
    assert b.ratio(10, 20, 40) == pytest.approx(1.01)
