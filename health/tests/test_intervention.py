import numpy as np
import pytest

from airhealth import intervention, paths
from airhealth.impact import Change
from airhealth.intervention import Dist, Invalid, annual_from_monthly, load
from airhealth.places import resolve

BASE = """
name = "test"
places = ["Delhi"]
start_year = 2027
duration_years = 10
p_success = 0.5

[change]
{change}

[cost]
annual = 1e8
currency = "INR"
year = 2025
"""


def write(tmp_path, text):
    path = tmp_path / "x.toml"
    path.write_text(text)
    return path


def from_change(tmp_path, change, **top):
    text = BASE.format(change=change)
    for key, value in top.items():
        text = text.replace(f"\n{key} = ", f"\n#{key} = ")
        text = f"{key} = {value}\n" + text
    return load(write(tmp_path, text))


def test_november_only_is_small_on_the_annual_mean():
    assert annual_from_monthly([0] * 10 + [-40, 0]) == pytest.approx(-40 * 30 / 365, rel=1e-6)


def test_two_change_fields_rejected(tmp_path):
    with pytest.raises(Invalid, match="change"):
        from_change(tmp_path, "delta = -10\npct = -10")
    with pytest.raises(Invalid, match="change"):
        from_change(tmp_path, "")


def test_monthly_must_have_twelve(tmp_path):
    with pytest.raises(Invalid, match="monthly"):
        from_change(tmp_path, f"monthly_delta = {[0] * 11}")


def test_probability_bounds(tmp_path):
    with pytest.raises(Invalid, match="p_success"):
        from_change(tmp_path, "delta = -10", p_success="1.2")


def test_percentiles_ordered(tmp_path):
    with pytest.raises(Invalid, match=r"change\.delta"):
        from_change(tmp_path, 'delta = { dist = "normal", p5 = -10, p95 = -20 }')


def test_unknown_place_rejected_with_suggestion(tmp_path):
    with pytest.raises(Invalid, match="places") as e:
        from_change(tmp_path, "delta = -10", places='["Dilli"]')
    assert "Delhi" in str(e.value)
    assert "\n" not in str(e.value)


def test_template_and_examples_load():
    files = sorted((paths.HEALTH / "interventions").glob("*.toml"))
    assert {f.stem for f in files} >= {"_template", "delhi_100_to_80", "november_only_delhi",
                                       "punjab_haryana_10pct"}
    for f in files:
        i = load(f)
        assert i.name and i.places and i.lag in ("immediate", "epa20")

    delhi = load(paths.HEALTH / "interventions" / "delhi_100_to_80.toml")
    assert delhi.places == [resolve("Delhi")] and delhi.places[0].kind == "state"
    assert delhi.from_level == 100 and delhi.as_change(delhi.change.median) == Change(to=80)

    nov = load(paths.HEALTH / "interventions" / "november_only_delhi.toml")
    assert nov.change_kind == "delta" and len(nov.monthly) == 12
    assert nov.change.median == pytest.approx(-40 * 30 / 365)

    ph = load(paths.HEALTH / "interventions" / "punjab_haryana_10pct.toml")
    assert {p.name for p in ph.places} == {"Punjab", "Haryana"}
    assert ph.as_change(ph.change.median) == Change(pct=-10)
    assert "placeholder" in ph.notes


def test_lognormal_recovers_its_percentiles():
    d = Dist.parse({"dist": "lognormal", "p5": 5e7, "p95": 5e8}, "cost.annual")
    x = d.sample(np.random.default_rng(1), 200_000)
    assert np.percentile(x, 5) == pytest.approx(5e7, rel=0.02)
    assert np.percentile(x, 95) == pytest.approx(5e8, rel=0.02)
    assert d.median == pytest.approx(np.sqrt(5e7 * 5e8))


@pytest.mark.parametrize("spec", [
    {"dist": "normal", "p5": -30, "p95": -10},
    {"dist": "uniform", "p5": 2, "p95": 11},
    {"dist": "triangular", "p5": 10, "p95": 40, "mode": 15},
    {"dist": "lognormal", "p5": -60, "p95": -20},     # a cut, sampled as a negative lognormal
])
def test_every_kind_recovers_its_percentiles(spec):
    d = Dist.parse(spec, "change.delta")
    x = d.sample(np.random.default_rng(2), 200_000)
    assert np.percentile(x, 5) == pytest.approx(spec["p5"], rel=0.02)
    assert np.percentile(x, 95) == pytest.approx(spec["p95"], rel=0.02)
    assert np.median(x) == pytest.approx(d.median, rel=0.02)


def test_fixed_number_is_a_dist():
    d = Dist.parse(-20, "change.delta")
    assert d.median == -20
    assert (d.sample(np.random.default_rng(0), 5) == -20).all()


def test_bad_dists_name_their_field(tmp_path):
    cases = {
        'delta = { dist = "gamma", p5 = 1, p95 = 2 }': "gamma",
        'delta = { dist = "lognormal", p5 = -5, p95 = 5 }': "lognormal",
        'delta = { dist = "triangular", p5 = 1, p95 = 5 }': "mode",
        'delta = { dist = "triangular", p5 = 1, p95 = 5, mode = 9 }': "mode",
        'delta = { dist = "normal", p5 = 1 }': "p95",
        'delta = "ten"': "number",
    }
    for change, word in cases.items():
        with pytest.raises(Invalid, match=word) as e:
            from_change(tmp_path, change)
        assert str(e.value).startswith("change.delta")


def test_monthly_distributions_move_together(tmp_path):
    months = ['{ dist = "normal", p5 = -50, p95 = -30 }' if m in (10, 11) else "0"
              for m in range(12)]
    i = from_change(tmp_path, f"monthly_delta = [{', '.join(months)}]")
    assert i.change.median == pytest.approx(annual_from_monthly([0] * 10 + [-40, -40]))
    x = i.change.sample(np.random.default_rng(3), 200_000)
    # Months share one draw, so the annual spread is the months' spread, day-weighted.
    assert np.percentile(x, 5) == pytest.approx(annual_from_monthly([0] * 10 + [-50, -50]), rel=0.02)


def test_other_fields_checked(tmp_path):
    with pytest.raises(Invalid, match="ramp_years"):
        from_change(tmp_path, "delta = -10", ramp_years="12")
    with pytest.raises(Invalid, match="lag"):
        from_change(tmp_path, "delta = -10", lag='"slow"')
    with pytest.raises(Invalid, match="colour"):
        from_change(tmp_path, "delta = -10", colour='"blue"')
    with pytest.raises(Invalid, match="change.pct"):
        from_change(tmp_path, "pct = -120")
    with pytest.raises(Invalid, match="from_level"):
        from_change(tmp_path, "to = 80", from_level="-1")
    with pytest.raises(Invalid, match="cost.currency"):
        load(write(tmp_path, BASE.format(change="delta = -1").replace('"INR"', '"EUR"')))
    with pytest.raises(Invalid, match="TOML"):
        load(write(tmp_path, "name = "))


def test_defaults(tmp_path):
    i = from_change(tmp_path, "delta = -10")
    assert i.lag == "epa20" and i.ramp_years == 0 and i.cost_share_only_on_success == 0.0
    assert i.cost_once.median == 0 and i.from_level is None and i.monthly is None
    assert isinstance(intervention.load(write(tmp_path, BASE.format(change="pct = -5"))).change,
                      Dist)


# --- monthly_pct weights months by the place's shape ------------------------------------------

from dataclasses import replace  # noqa: E402

from airhealth import months, simulate  # noqa: E402

INTERVENTIONS = paths.HEALTH / "interventions"


def test_monthly_pct_weights_by_shape():
    iv = load(INTERVENTIONS / "november_pct_delhi.toml")
    s = months.shape(iv.places[0]).values
    q = np.array([0.5])
    assert iv.annual_change(iv.places[0], q) == pytest.approx(-20 * s[10] * 30 / 365)


def test_draws_unchanged_for_other_kinds():
    for f in ("delhi_100_to_80.toml", "november_only_delhi.toml", "punjab_haryana_10pct.toml"):
        iv = load(INTERVENTIONS / f)
        old = iv.change.sample(simulate._rng(0, 0), 500)
        new = iv.annual_change(iv.places[0], simulate._rng(0, 0).random(500))
        assert np.array_equal(old, new)


def test_monthly_pct_two_places(tmp_path):
    text = BASE.replace('places = ["Delhi"]', 'places = ["Punjab", "Haryana"]').format(
        change="monthly_pct = [0, 0, 0, 0, 0, 0, 0, 0, 0, -10, -10, 0]")
    iv = load(write(tmp_path, text))
    q = np.array([0.5])
    shapes = {}
    for p in iv.places:
        s = months.shape(p).values
        shapes[p.name] = s
        assert iv.annual_change(p, q) == pytest.approx(-10 * (s[9] * 31 + s[10] * 30) / 365)
    assert not np.allclose(*shapes.values())
    run = simulate.run(iv, curves=["gemm_ncd_lri"], n=200)
    assert set(run.shapes) == {"Punjab (state)", "Haryana (state)"}
    # the run adds the two places, each cut by its own shape: the same as two one-place runs
    # (same seed, so the same quantiles), averaged by population
    one = [simulate.run(replace(iv, places=[p]), curves=["gemm_ncd_lri"], n=200) for p in iv.places]
    pops = [r.population for r in one]
    assert run.population == pytest.approx(sum(pops))
    both = run.per_curve["gemm_ncd_lri"]
    alone = [r.per_curve["gemm_ncd_lri"] for r in one]
    assert np.allclose(both.pm25_after, np.average([a.pm25_after for a in alone], axis=0, weights=pops))
    assert np.allclose(both.deaths_postponed, sum(a.deaths_postponed for a in alone))
    # and a flat (shape-blind) cut would give different answers
    assert not np.allclose(*(a.pm25_after for a in alone))


def test_monthly_pct_with_from_level():
    iv = load(INTERVENTIONS / "november_pct_delhi.toml")
    p = iv.places[0]
    pct = float(iv.annual_change(p, np.array([0.5]))[0])
    run = simulate.run(replace(iv, from_level=100), curves=["gemm_ncd_lri"], n=2001)
    after = run.per_curve["gemm_ncd_lri"].pm25_after
    assert np.median(after) == pytest.approx(100 * (1 + pct / 100), rel=0.005)
    # the draws are exactly level x (1 + annual pct at each quantile)
    q = simulate._rng(0, 0).random(2001)
    assert np.allclose(after, 100 * (1 + iv.annual_change(p, q) / 100))


def test_report_names_the_shape():
    from airhealth import report
    iv = load(INTERVENTIONS / "november_pct_delhi.toml")
    run = simulate.run(iv, curves=["gemm_ncd_lri"], n=50)
    footer_text = report.run_footer(run)
    assert "shape" in footer_text and "CPCB 2023-25" in footer_text and "borrowed" in footer_text
    assert "as polluted as the annual mean" not in footer_text


# --- composites, per-place scale ---------------------------------------------------------------

from airhealth.intervention import Linear, Product  # noqa: E402


def test_scaled_dist():
    d = Dist.parse({"dist": "lognormal", "p5": 2, "p95": 8}, "x").scaled(3)
    assert (d.p5, d.p95) == (6, 24)
    t = Dist.parse({"dist": "triangular", "p5": 1, "p95": 5, "mode": 2}, "x").scaled(2)
    assert (t.p5, t.p95, t.mode) == (2, 10, 4)
    assert Dist.parse({"dist": "normal", "p5": 1, "p95": 2}, "x").scaled(0) == Dist.fixed(0)


def test_linear_and_product_draw_together():
    a, b = Dist.parse({"dist": "uniform", "p5": 1, "p95": 2}, "a"), Dist.fixed(4)
    q = np.array([0.05, 0.5, 0.95])
    lin, prod = Linear(((-2.0, a), (1.0, b))), Product((a, b))
    assert np.allclose(lin.ppf(q), -2 * a.ppf(q) + 4)
    assert np.allclose(prod.ppf(q), 4 * a.ppf(q))
    assert lin.median == pytest.approx(-2 * a.median + 4)
    assert prod.median == pytest.approx(4 * a.median)
    assert np.allclose(prod.sample(np.random.default_rng(1), 5),
                       prod.ppf(np.random.default_rng(1).random(5)))


def test_monthly_mean_accepts_composites():
    a = Dist.parse({"dist": "uniform", "p5": 1, "p95": 2}, "a")
    m = intervention.MonthlyMean(tuple(Product((a, Dist.fixed(2))) for _ in range(12)))
    assert m.median == pytest.approx(2 * a.median)


def test_scale_multiplies_per_place():
    iv = replace(load(INTERVENTIONS / "punjab_haryana_10pct.toml"), change_kind="delta",
                 change=Dist.fixed(1.0), monthly=None,
                 scale={"Punjab (state)": -5.0, "Haryana (state)": -2.0})
    q = np.array([0.5])
    assert iv.annual_change(iv.places[0], q)[0] == -5.0
    assert iv.annual_change(iv.places[1], q)[0] == -2.0


def test_scale_missing_place_is_a_key_error_naming_it():
    iv = replace(load(INTERVENTIONS / "punjab_haryana_10pct.toml"), scale={"Punjab (state)": 1.0})
    with pytest.raises(KeyError, match="Haryana"):
        iv.annual_change(iv.places[1], np.array([0.5]))
