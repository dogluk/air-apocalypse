"""The local (IHME) tier: GBD 2023 exposure map, gbd2023, gbd2019 and gemm_5cod curves.

Tests that read IHME files take the `ihme_files` fixture and skip without them; nothing here
embeds IHME values: every comparison is against the files themselves, read at run time.
"""
import numpy as np
import pandas as pd
import pytest

from airhealth import baseline, cli, curves, exposure, ihme, ihme_curves, paths, places, provenance
from airhealth.ages import AGE_STARTS
from airhealth.impact import Change, steady_state, steady_state_many

INDIA = places.resolve("India")
LOCAL = ("gbd2019", "gbd2023", "gemm_5cod")


# --- without the files ----------------------------------------------------------------------

def test_every_local_curve_and_the_map_explain_what_is_missing(no_ihme):
    for name in LOCAL:
        with pytest.raises(curves.Unavailable, match="IHME_DOWNLOADS.md"):
            curves.get(name)
    run, unavailable = curves.select()
    assert set(unavailable) == set(LOCAL) and {c.name for c in run} == {c.name for c in curves.available()}
    assert not exposure.available("gbd2023")
    with pytest.raises(curves.Unavailable, match="gbd2023 map"):
        exposure.cells(INDIA, "gbd2023")


def test_cli_names_the_missing_map_in_one_line(capsys, no_ihme):
    assert cli.main(["burden", "India", "--map", "gbd2023"]) == 1
    assert "IHME_DOWNLOADS.md" in capsys.readouterr().err
    assert cli.main(["list", "maps"]) == 0
    out = capsys.readouterr().out
    assert "gbd2023  [no:" in out


def test_every_state_has_a_gbd_location():
    assert set(baseline.states()) == set(ihme.STATE_LOCATION)
    pooled = [s for s, loc in ihme.STATE_LOCATION.items() if loc == ihme.OTHER_UTS]
    assert sorted(pooled) == ["Andaman & Nicobar Islands", "Chandigarh", "Dadra & Nagar Haveli",
                              "Daman & Diu", "Lakshadweep", "Puducherry"]
    assert ihme.STATE_LOCATION["Ladakh"] == ihme.STATE_LOCATION["Jammu & Kashmir"] == ihme.JK_LADAKH


def test_age_groups_cover_every_band_once():
    assert sorted(set(ihme.AGE_BAND.values())) == list(AGE_STARTS)
    assert set(ihme.OLDEST) <= set(ihme.AGE_BAND) and all(ihme.AGE_BAND[a] == 85 for a in ihme.OLDEST)


def test_rates_years_interpolate_and_hold_outside():
    assert ihme.rates_year(2023) == (2023, 2023, 0.0)
    assert ihme.rates_year(2030) == (2023, 2023, 0.0) and ihme.rates_year(2011) == (2015, 2015, 0.0)
    assert ihme.rates_year(2021) == (2019, 2023, 0.5)
    assert "interpolated between 2019 and 2023" in ihme.rates_text(2021)
    assert "nearest" in ihme.rates_text(2012)


def test_tmrel_is_the_midpoint_of_gbds_range():
    assert ihme_curves.TMREL_RANGE == (2.4, 5.9) and ihme_curves.TMREL_MID == pytest.approx(4.15)
    listed = {c["name"]: c for c in provenance.constants()}
    assert listed["GBD counterfactual (TMREL midpoint), µg/m³"]["value"] == pytest.approx(4.15)


def test_gemm_5cod_parameters_reproduce_the_authors_calculator():
    # DataGEMM 'GEMM Calculator (PNAS)_ab.xlsx', India at 74.0 µg/m³: hazard ratio implied by
    # each sheet's deaths over its baseline, 1 / (1 - deaths/baseline), cells C91/C87 (25-29)
    # and AJ91/N87 (80+) of Burden_YesCN_<cause> and '<cause> baseline'.
    t = pd.read_csv(paths.DATA / ihme_curves.GEMM5_FILE)
    risks = {c: ihme_curves.GEMMRisk(c, 25, params=g.reset_index(drop=True))
             for c, g in t.groupby("cause")}
    implied = {("ihd", 25): 4.528424, ("ihd", 80): 1.580246, ("stroke", 25): 2.826739,
               ("stroke", 80): 1.370237, ("copd", 25): 1.749748, ("lung_cancer", 25): 1.939312,
               ("lri", 25): 3.054898}
    for (cause, age), hr in implied.items():
        r = risks[cause]
        assert np.exp(r.log_h(74.0, r.key(age), 0)) == pytest.approx(hr, rel=1e-6)
    assert r.key(85) == 80                                   # 80+ covers the 85+ band
    assert set(risks) == {"ihd", "stroke", "copd", "lung_cancer", "lri"}


# --- with the files ---------------------------------------------------------------------------

def test_the_two_scales_of_the_gbd2023_files(ihme_files):
    """Ratio-scale files start at 1, log-scale files at 0, and both load as ln RR from 0."""
    for cause, (rel, scale) in ihme.RR_2023.items():
        raw = pd.read_csv(ihme.path(rel))
        first = raw["mean"].iloc[0]
        assert first == pytest.approx(1.0 if scale == "ratio" else 0.0), cause
        assert list(raw.columns[:2]) == (["cause", "exposure"] if scale == "ratio" else ["risk", "mean"])
    c = curves.get("gbd2023")
    for r in c.risks:
        mean, _ = r.curves[0]
        assert mean[0] == pytest.approx(0.0) and (np.diff(mean) >= -1e-6).all(), r.cause   # flat tails


def test_log_scale_mean_file_is_the_mean_of_its_log_draws(ihme_files):
    """IHD: the 2025 mean file equals the mean of the draws file at the same exposures."""
    mean_rel, _ = ihme.RR_2023["ihd"]
    draws_rel = mean_rel.replace("MEAN_Y2025M11D18", "DRAWS_Y2024M02D07")
    if ihme.missing([draws_rel]):
        pytest.skip("IHD draws file not downloaded")
    m = pd.read_csv(ihme.path(mean_rel))
    d = pd.read_csv(ihme.path(draws_rel))
    draws = d.filter(like="draw_").to_numpy(float)
    for x in (5.0, 50.0, 100.0):
        i = int(np.argmin(abs(d.exposure.to_numpy() - x)))
        e = d.exposure.iloc[i]
        assert np.interp(e, m.risk, m["mean"]) == pytest.approx(draws[i].mean(), abs=2e-4)
        assert np.interp(e, m.risk, m.upper) == pytest.approx(np.percentile(draws[i], 97.5), abs=2e-4)


def test_gbd2023_ratio_is_the_files_ratio_above_the_tmrel(ihme_files):
    c = curves.get("gbd2023")
    copd = next(r for r in c.risks if r.cause == "copd")
    ihd = next(r for r in c.risks if r.cause == "ihd")
    raw = pd.read_csv(ihme.path(ihme.RR_2023["copd"][0]))
    f = lambda x: np.interp(x, raw.exposure, raw["mean"])      # noqa: E731
    assert c.cause_ratio(copd, 4.15, 100.0, 60) == pytest.approx(f(100) / f(4.15))
    log = pd.read_csv(ihme.path(ihme.RR_2023["ihd"][0]))
    g = lambda x: np.interp(x, log.risk, log["mean"])          # noqa: E731
    assert c.cause_ratio(ihd, 4.15, 100.0, 60) == pytest.approx(np.exp(g(100) - g(4.15)))
    assert c.cause_ratio(ihd, 3.0, 2.0, 60) == 1.0               # below the TMREL: no change
    assert c.cause_ratio(ihd, 100.0, 50.0, 20) == 1.0            # IHD from 25 only
    lri = next(r for r in c.risks if r.cause == "lri")
    assert c.cause_ratio(lri, 100.0, 50.0, 0) < 1.0              # LRI at every age


def test_gbd2019_oldest_band_mixes_the_85_90_95_curves(ihme_files):
    c = curves.get("gbd2019")
    ihd = next(r for r in c.risks if r.cause == "ihd")
    assert sum(ihd.oldest.values()) == pytest.approx(1.0) and set(ihd.oldest) == {85, 90, 95}
    one = {a: float(np.exp(ihd.log_h(100.0, a, 0) - ihd.log_h(50.0, a, 0)))
           for a in (85, 90, 95)}
    mixed = float(c.cause_ratio(ihd, 100.0, 50.0, 85))
    assert mixed == pytest.approx(sum(ihd.oldest[a] / one[a] for a in one))
    assert c.cause_ratio(ihd, 100.0, 50.0, 25) < c.cause_ratio(ihd, 100.0, 50.0, 60) < mixed
    draws = ihme_curves.tmrel_draws()
    assert len(draws) == 1000 and draws.min() >= 2.4 and draws.max() <= 5.9
    assert draws.mean() == pytest.approx(ihme_curves.TMREL_MID, abs=0.05)


def test_cause_rates_reproduce_gbds_own_counts(ihme_files):
    """Rates × GBD's population give back GBD's own all-ages count, for every cause."""
    raw = pd.read_csv(ihme.path(ihme.DEATHS_2023))
    pop = ihme.tables().population
    for state, year in (("India", 2023), ("Kerala", 2019), ("Puducherry", 2015)):
        loc = ihme.STATE_LOCATION[state]
        p = pop[(pop.location_id == loc) & (pop.year == year)].set_index("band").population
        rates = ihme.cause_rates(state, year)
        for cause, cid in ihme.CAUSES.items():
            total = raw[(raw.location_id == loc) & (raw.year == year) & (raw.cause_id == cid)
                        & (raw.age_id == 22) & (raw.metric_name == "Number")].val.item()
            assert (rates[cause] * p.reindex(AGE_STARTS).to_numpy()).sum() == pytest.approx(total, rel=1e-6)
        # GBD's own Rate (per 100,000) for a five-year group equals ours
        r = raw[(raw.location_id == loc) & (raw.year == year) & (raw.cause_id == 493)
                & (raw.age_id == 17) & (raw.metric_name == "Rate")].val.item()
        assert rates["ihd"][AGE_STARTS.index(60)] * 1e5 == pytest.approx(r, rel=1e-6)
    mid = ihme.cause_rates("Bihar", 2021)
    lo, hi = ihme.cause_rates("Bihar", 2019), ihme.cause_rates("Bihar", 2023)
    assert mid["copd"] == pytest.approx((lo["copd"] + hi["copd"]) / 2)


def test_gbd2023_map_is_ihmes_state_values(ihme_files):
    raw = pd.read_csv(ihme.path(ihme.EXPOSURE_2023))
    val = lambda loc, y: raw[(raw.location_id == loc) & (raw.year_id == y)]["mean"].item()  # noqa: E731
    assert exposure.mean(places.resolve("Delhi"), "gbd2023", 2023) == pytest.approx(val(4849, 2023))
    assert exposure.mean(places.resolve("Ladakh"), "gbd2023", 2023) == pytest.approx(val(4854, 2023))
    assert exposure.mean(places.resolve("Puducherry"), "gbd2023", 2019) == pytest.approx(val(44538, 2019))
    assert exposure.mean(INDIA, "gbd2023", 2023) == pytest.approx(ihme.india_exposure(2023), rel=0.02)
    c = exposure.cells(INDIA, "gbd2023", 2023)
    assert set(c.state) == set(baseline.states()) - {"India"}
    with pytest.raises(ValueError, match="state-level"):
        exposure.cells(places.resolve("Pune"), "gbd2023")


@pytest.mark.parametrize("name", LOCAL)
def test_local_curves_run_and_agree_with_their_many_draw_form(ihme_files, name):
    c = curves.get(name)
    one = steady_state(places.resolve("Delhi"), c, "aqli", Change(to=80), pm25_override=100)
    many = steady_state_many(places.resolve("Delhi"), c, "aqli", "to", np.array([80.0, 80.0]),
                             pm25_override=100)
    assert one.deaths_averted > 0 and one.yll_averted > 0 and one.e0_after > one.e0_before
    assert many.deaths_averted == pytest.approx([one.deaths_averted] * 2)
    assert many.e0_after - many.e0_before == pytest.approx([one.e0_after - one.e0_before] * 2)
    assert many.yll_averted == pytest.approx([one.yll_averted] * 2)
    assert "GBD 2023 round" in one.curve_note


@pytest.mark.parametrize("name", LOCAL)
def test_local_curve_deaths_are_ihmes_not_the_srs_scaled_count(ihme_files, name):
    c = curves.get(name)
    srs = steady_state(INDIA, c, "aqli", Change(to=20))
    model = steady_state(INDIA, c, "aqli", Change(to=20), deaths="model")
    assert srs.deaths_baseline < model.deaths_baseline          # the all-cause count moves
    assert srs.deaths_averted == pytest.approx(model.deaths_averted)   # IHME's deaths do not


def test_local_deaths_equal_rates_times_people(ihme_files):
    """One state at one level: averted = Σ causes, bands of people × rate × (1 − ratio)."""
    c = curves.get("gbd2023")
    kerala = places.resolve("Kerala")
    i = steady_state(kerala, c, "gbd2023", Change(to=10), year=2023)
    b = baseline.load("Kerala", 2023)
    rates = ihme.cause_rates("Kerala", 2023)
    pm = exposure.mean(kerala, "gbd2023", 2023)
    expect = sum(b.population[k] * rates[r.cause][k] * (1 - float(c.cause_ratio(r, pm, 10, a)))
                 for r in c.risks for k, a in enumerate(AGE_STARTS))
    assert i.deaths_averted == pytest.approx(expect)


def test_sampling_moves_all_causes_together(ihme_files):
    c = curves.get("gbd2023")
    rng = np.random.default_rng(3)
    batch = c.sample_many(rng, 4000)
    lri = next(r for r in c.risks if r.cause == "lri")
    draws = np.asarray(batch.cause_ratio(lri, np.full((4000, 1), 100.0), np.full((4000, 1), 50.0), 0))
    assert draws.std() > 0
    assert np.median(draws) == pytest.approx(float(c.cause_ratio(lri, 100.0, 50.0, 0)), abs=0.01)
    assert c.z == 0.0                                            # sampling leaves the original


def test_footer_says_where_local_deaths_come_from(capsys, ihme_files):
    assert cli.main(["burden", "India", "--curves", "gbd2019,gemm_ncd_lri"]) == 0
    foot = capsys.readouterr().out.strip().splitlines()[-1]
    assert "Deaths for gbd2019: the GBD 2023 round's death rates" in foot
    assert "GBD 2019-round deaths are no longer published" in foot
    assert "Other Union Territories" in foot


def test_dashboard_shapes_include_local_curves(ihme_files):
    from airhealth import dashboard
    m = dashboard.meta()
    assert {"gbd2019", "gbd2023", "gemm_5cod"} <= set(m["shapes"]["rr"])
    india = next(r for r in m["exposure"] if r["place"] == "India")
    assert india["aqli"] < india["gbd2023"] < india["gbd2019"]
    assert "gbd2023" in {x["name"] for x in m["maps"]}
