import dataclasses

import numpy as np
import pytest

from airhealth import charts, cli, curves, impact, intervention, lifetable, paths, report, simulate
from airhealth.intervention import Dist, Invalid
from airhealth.places import resolve

IV = paths.HEALTH / "interventions"
N = 400


def load(name: str) -> intervention.Intervention:
    return intervention.load(IV / f"{name}.toml")


def nov(**changes) -> intervention.Intervention:
    return dataclasses.replace(load("november_only_delhi"), **changes)


def fixed(delta: float, **changes) -> intervention.Intervention:
    """Delhi, a fixed year-round change of `delta` µg/m³."""
    return nov(change_kind="delta", change=Dist.fixed(delta), monthly=None, **changes)


# --- the brief's tests ----------------------------------------------------------------------

def test_same_seed_same_answer():
    a = simulate.run(load("november_only_delhi"), n=N, seed=3)
    b = simulate.run(load("november_only_delhi"), n=N, seed=3)
    for name, r in a.per_curve.items():
        assert np.array_equal(r.life_years, b.per_curve[name].life_years)
        assert np.array_equal(r.cost_usd, b.per_curve[name].cost_usd)


def test_different_seed_differs():
    a = simulate.run(load("november_only_delhi"), n=N, seed=3)
    b = simulate.run(load("november_only_delhi"), n=N, seed=4)
    j = "loglinear_jaganathan"
    assert not np.array_equal(a.per_curve[j].life_years, b.per_curve[j].life_years)
    assert not np.array_equal(a.per_curve[j].cost_usd, b.per_curve[j].cost_usd)


def test_fixed_inputs_have_no_pm25_spread():
    run = simulate.run(fixed(-10), n=N)
    for r in run.per_curve.values():
        assert r.spread["pm25_change"] == 0
    assert run.per_curve["loglinear_jaganathan"].spread["curve_parameters"] > 0
    assert run.per_curve["gemm_ncd_lri"].spread["curve_parameters"] > 0
    # AQLI publishes no interval, so nothing varies at all.
    assert run.per_curve["aqli"].spread["curve_parameters"] == 0


def test_expected_is_probability_times_conditional():
    run = simulate.run(fixed(-10, p_success=0.25), n=N)
    for r in run.per_curve.values():
        s = r.summary()
        assert s["expected_life_years"] == pytest.approx(0.25 * np.mean(r.life_years))


def test_cost_per_life_year_two_ways():
    run = simulate.run(nov(p_success=0.4, cost_share_only_on_success=0.0), n=N)
    for r in run.per_curve.values():
        s = r.summary()
        assert s["expected_cost_per_expected_life_year"] == pytest.approx(
            s["cost_per_life_year_if_works"] / 0.4)
    run = simulate.run(nov(p_success=0.4, cost_share_only_on_success=1.0), n=N)
    for r in run.per_curve.values():
        s = r.summary()
        assert s["expected_cost_per_expected_life_year"] == pytest.approx(
            s["cost_per_life_year_if_works"])


def test_november_only_buys_about_a_twelfth():
    curve = ["loglinear_jaganathan"]
    november = simulate.run(load("november_only_delhi"), curves=curve, n=N)
    year_round = simulate.run(fixed(-40), curves=curve, n=N)
    ratio = (november.per_curve[curve[0]].life_years.mean()
             / year_round.per_curve[curve[0]].life_years.mean())
    assert ratio == pytest.approx(1 / 12, rel=0.25)
    text = report.run_table(november)
    assert "annual-mean change -3.29 µg/m³" in text


def test_harmful_intervention_reports_negative_life_years(capsys):
    run = simulate.run(fixed(+10), n=N)
    for r in run.per_curve.values():
        # Medians, not every draw: Brown 2022's interval (RR 1.00-1.03) reaches below 1.
        assert np.median(r.life_years) < 0 and np.median(r.deaths_postponed) < 0
        assert np.median(r.e0_change_years) < 0
        assert r.summary()["cost_per_life_year_if_works"] is None   # no life-years bought
    assert (run.per_curve["loglinear_jaganathan"].life_years < 0).all()
    text = report.run_table(run)
    assert "no life-years gained" in text
    row = next(l for l in text.splitlines() if l.startswith("loglinear_jaganathan"))
    assert "-" in row.split()[1]


def test_ramp_and_lag_reduce_early_years():
    curve = ["loglinear_jaganathan"]
    immediate = simulate.run(fixed(-20, lag="immediate"), curves=curve, n=N)
    epa = simulate.run(fixed(-20, lag="epa20"), curves=curve, n=N)
    ramped = simulate.run(fixed(-20, lag="epa20", ramp_years=3), curves=curve, n=N)
    a, b, c = (r.per_curve[curve[0]].life_years.mean() for r in (immediate, epa, ramped))
    assert a > b > c > 0
    # With an immediate lag and no ramp, ten years are ten full-effect years.
    assert immediate.shares.sum() == pytest.approx(10)


def test_run_command_prints_every_curve_and_both_cost_figures(capsys):
    code = cli.main(["run", str(IV / "november_only_delhi.toml"), "--n", "300"])
    out, err = capsys.readouterr()
    assert code == 0, err
    for c in curves.available():
        assert c.name in out
    assert "cost per life-year if it works" in out
    assert "expected cost per expected life-year" in out
    assert "aqli" in out.strip().splitlines()[-1]          # the map, named last
    assert "no published interval" in out


def test_across_curve_spread_exceeds_within_curve_for_delhi():
    run = simulate.run(load("delhi_100_to_80"), n=N)
    across = simulate.across_curve_spread(run)
    assert across > 1.5
    within = max(np.percentile(r.life_years, 95) / np.percentile(r.life_years, 5)
                 for r in run.per_curve.values())
    assert across > within


# --- accounting -----------------------------------------------------------------------------

def test_life_years_are_steady_state_times_realised_years():
    iv = fixed(-20, lag="epa20", ramp_years=2)
    run = simulate.run(iv, curves=["loglinear_jaganathan"], n=50)
    ref = impact.steady_state(resolve("Delhi"), curves.get("loglinear_jaganathan"), "aqli",
                              impact.Change(delta=-20))
    r = run.per_curve["loglinear_jaganathan"]
    # The draws scatter around the published slope; the median is close to the reference.
    assert np.median(r.life_years) == pytest.approx(ref.yll_averted * run.shares.sum(), rel=0.05)
    # Ramp of two years: year 1 has half the change, and each half starts its own lag.
    assert run.shares[0] == pytest.approx(0.5 * 0.30)
    assert run.shares[1] == pytest.approx(0.5 * 0.425 + 0.5 * 0.30)


def test_cost_converted_at_the_years_rate():
    iv = fixed(-10, cost_once=Dist.fixed(0), cost_annual=Dist.fixed(1e8), cost_year=2024,
               duration_years=10)
    run = simulate.run(iv, curves=["loglinear_jaganathan"], n=10)
    cost = run.per_curve["loglinear_jaganathan"].cost_usd
    assert cost == pytest.approx(np.full(10, 1e9 / 83.669281580941))


def test_cost_year_outside_the_table_is_invalid(tmp_path):
    text = (IV / "november_only_delhi.toml").read_text().replace("year = 2025", "year = 1990")
    (tmp_path / "x.toml").write_text(text)
    with pytest.raises(Invalid, match=r"^cost\.year"):
        intervention.load(tmp_path / "x.toml")


def test_dollar_costs_need_no_rate(tmp_path):
    text = (IV / "november_only_delhi.toml").read_text().replace(
        'currency = "INR"\nyear = 2025', 'currency = "USD"\nyear = 1990')
    (tmp_path / "x.toml").write_text(text)
    assert intervention.load(tmp_path / "x.toml").cost_year == 1990


def test_sampled_target_and_result_never_below_zero():
    iv = nov(change_kind="to", change=Dist.parse({"dist": "normal", "p5": 1, "p95": 30}, "change.to"),
             monthly=None)
    run = simulate.run(iv, curves=["loglinear_jaganathan"], n=2000)
    r = run.per_curve["loglinear_jaganathan"]
    assert (r.pm25_after >= 0).all() and np.isfinite(r.life_years).all()
    big = nov(change_kind="delta", monthly=None,
              change=Dist.parse({"dist": "normal", "p5": -300, "p95": -200}, "change.delta"))
    r = simulate.run(big, curves=["loglinear_jaganathan"], n=500).per_curve["loglinear_jaganathan"]
    assert (r.pm25_after == 0).all()
    # A drawn target below zero counts as zero, as does a cut larger than the level.
    out = impact.apply_many("to", np.array([-5.0, 20.0]), np.array([10.0, 50.0]))
    assert out.tolist() == [[0.0, 0.0], [10.0, 20.0]]
    out = impact.apply_many("pct", np.array([-120.0]), np.array([10.0, 50.0]))
    assert out.tolist() == [[0.0, 0.0]]


def test_overlapping_places_are_invalid():
    iv = nov(places=[resolve("Delhi"), resolve("Delhi", kind="city")])
    with pytest.raises(Invalid, match="^places"):
        simulate.run(iv, n=10)
    iv = nov(places=[resolve("India"), resolve("Kerala")])
    with pytest.raises(Invalid, match="^places"):
        simulate.run(iv, n=10)


def test_two_places_add_up():
    ph = load("punjab_haryana_10pct")
    both = simulate.run(ph, curves=["gemm_ncd_lri"], n=50, seed=1)
    parts = [simulate.run(dataclasses.replace(ph, places=[p]), curves=["gemm_ncd_lri"], n=50, seed=1)
             for p in ph.places]
    total = sum(r.per_curve["gemm_ncd_lri"].life_years for r in parts)
    assert both.per_curve["gemm_ncd_lri"].life_years == pytest.approx(total)


# --- the vectorised impact agrees with the reference ------------------------------------------

@pytest.mark.parametrize("name", ["loglinear_jaganathan", "loglinear_brown", "gemm_ncd_lri", "aqli"])
@pytest.mark.parametrize("place,kind,values,override", [
    ("Delhi", "delta", [-40, -3.3, 0, 15], None),
    ("Punjab", "pct", [-10, -50], None),
    ("Delhi", "to", [80, 30], 100),
])
def test_many_agrees_with_steady_state(name, place, kind, values, override):
    curve, p = curves.get(name), resolve(place)
    many = impact.steady_state_many(p, curve, "aqli", kind, np.array(values, float),
                                    pm25_override=override)
    for i, v in enumerate(values):
        ref = impact.steady_state(p, curve, "aqli", impact.Change(**{kind: v}),
                                  pm25_override=override)
        assert many.deaths_averted[i] == pytest.approx(ref.deaths_averted, rel=1e-9, abs=1e-6)
        assert many.yll_averted[i] == pytest.approx(ref.yll_averted, rel=1e-9, abs=1e-6)
        assert many.e0_after[i] == pytest.approx(ref.e0_after, rel=1e-12)
        assert many.pm25_after[i] == pytest.approx(ref.pm25_after)


@pytest.mark.parametrize("name", ["loglinear_jaganathan", "gemm_ncd_lri"])
def test_many_with_sampled_curve_agrees_draw_by_draw(name):
    curve, p = curves.get(name), resolve("Uttar Pradesh")
    batch = curve.sample_many(np.random.default_rng(5), 6)
    many = impact.steady_state_many(p, batch, "aqli", "delta", np.full(6, -20.0))
    field = "pct_per_10" if name.startswith("loglinear") else "z"
    for i in range(6):
        one = curves._evolve(curve, **{field: float(getattr(batch, field)[i, 0])})
        ref = impact.steady_state(p, one, "aqli", impact.Change(delta=-20))
        assert many.deaths_averted[i] == pytest.approx(ref.deaths_averted, rel=1e-9)
        assert many.e0_after[i] == pytest.approx(ref.e0_after, rel=1e-12)
    assert np.std(many.deaths_averted) > 0


def test_aqli_interpolation_is_close_to_exact():
    p, aqli = resolve("Bihar"), curves.get("aqli")
    values = np.random.default_rng(0).uniform(-60, 10, 300)     # > AQLI_EXACT distinct gains
    many = impact.steady_state_many(p, aqli, "aqli", "delta", values)
    for i in (0, 77, 299):
        ref = impact.steady_state(p, aqli, "aqli", impact.Change(delta=values[i]))
        assert many.deaths_averted[i] == pytest.approx(ref.deaths_averted, rel=1e-3, abs=1)


def test_sample_many_matches_sample():
    for name in ("loglinear_jaganathan", "gemm_ncd_lri"):
        c = curves.get(name)
        batch = np.asarray(c.sample_many(np.random.default_rng(1), 20_000).ratio(100, 80, 60))
        one = np.array([c.sample(np.random.default_rng(i)).ratio(100, 80, 60) for i in range(2000)])
        assert batch.shape == (20_000, 1)
        assert batch.std() == pytest.approx(one.std(), rel=0.1)
        assert np.median(batch) == pytest.approx(c.ratio(100, 80, 60), abs=0.005)
    aqli = curves.get("aqli")
    assert aqli.sample_many(np.random.default_rng(1), 5) is aqli


def test_e0_many_matches_e0():
    rng = np.random.default_rng(2)
    starts = np.array(lifetable.STARTS)
    mx = 0.0004 * np.exp(0.085 * starts) * rng.uniform(0.7, 1.3, (5, len(starts)))
    mx[:, 0] = rng.uniform(0.005, 0.05, 5)
    assert lifetable.e0_many(mx) == pytest.approx([lifetable.e0(m) for m in mx], rel=1e-12)


# --- CLI and charts ---------------------------------------------------------------------------

def test_invalid_file_is_one_line_exit_1(capsys, tmp_path):
    text = (IV / "november_only_delhi.toml").read_text().replace("p_success = 0.5", "p_success = 2")
    (tmp_path / "bad.toml").write_text(text)
    code = cli.main(["run", str(tmp_path / "bad.toml")])
    out, err = capsys.readouterr()
    assert code == 1 and out == ""
    assert err.startswith("airhealth: p_success") and err.count("\n") == 1
    assert "Traceback" not in err


def test_run_json_and_charts(capsys, tmp_path):
    import json
    code = cli.main(["--json", "run", str(IV / "punjab_haryana_10pct.toml"), "--n", "200",
                     "--charts", str(tmp_path)])
    out, err = capsys.readouterr()
    assert code == 0, err
    result = json.loads(out)
    assert result["map"] == "aqli" and result["n"] == 200
    assert {r["curve"] for r in result["rows"]} == {c.name for c in curves.available()}
    for row in result["rows"]:
        assert row["life_years"]["p5"] <= row["life_years"]["median"] <= row["life_years"]["p95"]
    assert len(result["charts"]) == 2
    for path in result["charts"]:
        assert (tmp_path / path.rsplit("/", 1)[-1]).stat().st_size > 30_000


def test_charts_are_written(tmp_path):
    run = simulate.run(load("delhi_100_to_80"), n=200)
    assert charts.results_chart(run, tmp_path / "r.png").stat().st_size > 30_000
    assert charts.spread_chart(run, tmp_path / "s.png").stat().st_size > 30_000
