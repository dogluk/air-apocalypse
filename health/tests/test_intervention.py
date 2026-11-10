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
year = 2026
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
