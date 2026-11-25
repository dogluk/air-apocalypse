import numpy as np
import pandas as pd
import pytest

from airhealth import baseline, curves, exposure, lifetable
from airhealth.ages import AGE_STARTS
from airhealth.curves import LogLinear, get
from airhealth.impact import Change, burden, steady_state
from airhealth.places import Place, resolve

STARTS = np.array(AGE_STARTS, dtype=float)
COUNTRY = Place("country", "Testia", None)
STATE_A = Place("state", "A", "A")


def synthetic_baseline(state: str, fallback: bool = False) -> baseline.Baseline:
    mx = 0.0004 * np.exp(0.085 * STARTS)
    mx[:2] = (0.03, 0.002)
    return baseline.Baseline(state=state, year=2022, population=1000 * np.exp(-0.03 * STARTS),
                             mx=mx, share_ncd_lri=np.where(STARTS < 5, 0.3, 0.8),
                             fallback=fallback, death_factor=np.ones(len(STARTS)),
                             reconciliation=None)


@pytest.fixture
def world(monkeypatch):
    """Install a synthetic exposure table (state, unit, pm25, population) and baselines."""
    def install(rows, fallback=()):
        table = pd.DataFrame(rows, columns=exposure.COLUMNS)

        def cells(place, map_name, year=None, population="projection"):
            if place.kind == "country":
                out = table
            elif place.kind == "state":
                out = table[table.state == place.name]
            else:
                out = table[(table.state == place.state) & (table.unit == place.name)]
            out = out.reset_index(drop=True)
            out.attrs.update(map=map_name, year=2022, population_year=2022)
            return out

        monkeypatch.setattr(exposure, "cells", cells)
        monkeypatch.setattr(baseline, "load",
                            lambda state, year=None, deaths="srs", sources=None: synthetic_baseline(
                                state, state in fallback))
    return install


SLOPE = LogLinear("test_slope", pct_per_10=8.0, se_pct_per_10=0.0, floor=5, min_age=25)


def district(name, state="A"):
    return Place("district", name, state)


# --- Change ---------------------------------------------------------------------------------

def test_change_needs_exactly_one_kind():
    with pytest.raises(ValueError):
        Change()
    with pytest.raises(ValueError):
        Change(delta=-5, to=40)


def test_change_never_below_zero():
    pm = np.array([10.0, 50.0])
    assert Change(delta=-30).apply(pm).tolist() == [0.0, 20.0]
    assert Change(pct=-150).apply(pm).tolist() == [0.0, 0.0]
    assert Change(pct=-20).apply(pm).tolist() == [8.0, 40.0]


def test_target_leaves_clean_units_alone(world):
    assert Change(to=40).apply(np.array([30.0, 60.0])).tolist() == [30.0, 40.0]
    world([("A", "a1", 30.0, 1000), ("A", "a2", 60.0, 1000)])
    whole = steady_state(STATE_A, SLOPE, "test", Change(to=40))
    clean = steady_state(district("a1"), SLOPE, "test", Change(to=40))
    dirty = steady_state(district("a2"), SLOPE, "test", Change(to=40))
    assert clean.deaths_averted == 0
    assert whole.deaths_averted == pytest.approx(dirty.deaths_averted)


# --- steady state, synthetic ----------------------------------------------------------------

def test_no_change_no_effect(world):
    world([("A", "a1", 80.0, 1000), ("A", "a2", 40.0, 3000)])
    for curve in (SLOPE, get("gemm_ncd_lri"), get("aqli")):
        r = steady_state(STATE_A, curve, "test", Change(delta=0))
        assert r.deaths_averted == 0
        assert r.yll_averted == 0
        assert r.e0_after == r.e0_before


def test_cleaner_air_averts_deaths_and_adds_years(world):
    world([("A", "a1", 80.0, 1000), ("A", "a2", 40.0, 3000)])
    r = steady_state(STATE_A, SLOPE, "test", Change(delta=-10))
    assert r.deaths_averted > 0
    assert r.yll_averted > r.deaths_averted
    assert r.e0_after > r.e0_before
    assert r.pm25_before == pytest.approx(50.0)
    assert r.pm25_after == pytest.approx(40.0)
    assert r.population == 4000
    assert r.derived is False
    assert (r.curve, r.map_name, r.place) == (SLOPE, "test", STATE_A)


def test_worse_air_gives_negative_numbers(world):
    world([("A", "a1", 80.0, 1000)])
    r = steady_state(STATE_A, SLOPE, "test", Change(delta=+10))
    assert r.deaths_averted < 0
    assert r.yll_averted < 0
    assert r.e0_after < r.e0_before


def test_cut_is_clamped_at_floor(world):
    world([("A", "a1", 20.0, 1000)])
    curve = SLOPE.with_floor(15)
    deep = steady_state(STATE_A, curve, "test", Change(delta=-30))
    exact = steady_state(STATE_A, curve, "test", Change(delta=-5))
    assert deep.deaths_averted == pytest.approx(exact.deaths_averted)
    assert deep.e0_after == pytest.approx(exact.e0_after)


def test_state_is_sum_of_its_districts(world):
    world([("A", "a1", 30.0, 1000), ("A", "a2", 90.0, 2000), ("A", "a3", 150.0, 500)])
    curve = get("gemm_ncd_lri")
    whole = steady_state(STATE_A, curve, "test", Change(pct=-30))
    parts = [steady_state(district(d), curve, "test", Change(pct=-30)) for d in ("a1", "a2", "a3")]
    assert whole.deaths_averted == pytest.approx(sum(p.deaths_averted for p in parts))
    assert whole.deaths_baseline == pytest.approx(sum(p.deaths_baseline for p in parts))
    assert whole.yll_averted == pytest.approx(sum(p.yll_averted for p in parts))
    assert whole.population == sum(p.population for p in parts)


def test_nonlinearity_matters(world):
    world([("A", "a1", 30.0, 1000), ("A", "a2", 150.0, 1000)])
    curve = get("gemm_ncd_lri")
    spread = steady_state(STATE_A, curve, "test", Change(delta=-20))
    at_mean = steady_state(STATE_A, curve, "test", Change(delta=-20),
                           pm25_override=spread.pm25_before)
    assert at_mean.pm25_before == spread.pm25_before
    assert spread.deaths_averted != pytest.approx(at_mean.deaths_averted, rel=0.01)


def test_ncd_scope_averts_fewer_than_all_scope(world):
    world([("A", "a1", 80.0, 1000)])
    ncd = LogLinear("ncd", 8.0, 0.0, floor=5, min_age=25, death_scope="ncd_lri")
    every = steady_state(STATE_A, SLOPE, "test", Change(delta=-20))
    some = steady_state(STATE_A, ncd, "test", Change(delta=-20))
    assert 0 < some.deaths_averted < every.deaths_averted
    assert some.e0_before == every.e0_before < some.e0_after < every.e0_after


def test_younger_start_averts_more(world):
    world([("A", "a1", 80.0, 1000)])
    from_birth = LogLinear("all_ages", 8.0, 0.0, floor=5, min_age=0)
    adults = steady_state(STATE_A, SLOPE, "test", Change(delta=-20))
    everyone = steady_state(STATE_A, from_birth, "test", Change(delta=-20))
    assert everyone.deaths_averted > adults.deaths_averted


def test_yll_uses_remaining_life_expectancy(world):
    world([("A", "a1", 80.0, 1000)])
    oldest_only = LogLinear("oldest", 8.0, 0.0, floor=5, min_age=85)
    r = steady_state(STATE_A, oldest_only, "test", Change(delta=-20))
    ex85 = lifetable.life_table(synthetic_baseline("A").mx).ex[-1]
    assert r.yll_averted == pytest.approx(r.deaths_averted * ex85)


def test_yll_is_below_the_band_start_figure(world):
    # Deaths happen inside the band, where less life remains than at its start.
    world([("A", "a1", 80.0, 1000)])
    r = steady_state(STATE_A, SLOPE, "test", Change(delta=-20))
    b = synthetic_baseline("A")
    averted = b.population / b.population.sum() * 1000 * b.mx * (1 - 1.08 ** -2) * (STARTS >= 25)
    at_start = (averted * lifetable.life_table(b.mx).ex).sum()
    assert r.yll_averted == pytest.approx((averted * lifetable.ex_at_death(b.mx)).sum())
    assert 0.85 * at_start < r.yll_averted < 0.97 * at_start


def test_aqli_impact_is_marked_derived_and_consistent(world):
    world([("A", "a1", 50.0, 1000)])
    aqli = get("aqli")
    r = steady_state(STATE_A, aqli, "test", Change(delta=-10))
    assert r.derived is True
    assert r.e0_after - r.e0_before == pytest.approx(aqli.delta_e0(50, 40))
    # The deaths come from the one multiplier on every age's rate that gives that e0 change.
    factor = 1 - r.deaths_averted / r.deaths_baseline
    mx = synthetic_baseline("A").mx
    assert lifetable.e0(mx * factor) - lifetable.e0(mx) == pytest.approx(aqli.delta_e0(50, 40))


def test_aqli_state_is_population_weighted(world):
    world([("A", "a1", 50.0, 1000), ("A", "a2", 100.0, 3000)])
    aqli = get("aqli")
    r = steady_state(STATE_A, aqli, "test", Change(to=40))
    expected = (aqli.delta_e0(50, 40) * 1000 + aqli.delta_e0(100, 40) * 3000) / 4000
    assert r.e0_after - r.e0_before == pytest.approx(expected)
    assert r.deaths_averted > 0


def test_fallback_states_listed(world):
    world([("A", "a1", 80.0, 1000), ("B", "b1", 60.0, 1000), ("C", "c1", 60.0, 1000)],
          fallback=("C", "B"))
    r = steady_state(COUNTRY, SLOPE, "test", Change(delta=-10))
    assert r.fallback_states == ["B", "C"]
    assert steady_state(STATE_A, SLOPE, "test", Change(delta=-10)).fallback_states == []


def test_country_adds_states(world):
    world([("A", "a1", 80.0, 1000), ("B", "b1", 40.0, 3000)])
    states = [steady_state(Place("state", s, s), SLOPE, "test", Change(delta=-10)) for s in "AB"]
    whole = steady_state(COUNTRY, SLOPE, "test", Change(delta=-10))
    assert whole.deaths_averted == pytest.approx(sum(s.deaths_averted for s in states))
    assert whole.e0_after == pytest.approx((states[0].e0_after * 1000
                                            + states[1].e0_after * 3000) / 4000)


def test_override_sets_every_unit(world):
    world([("A", "a1", 30.0, 1000), ("A", "a2", 150.0, 3000)])
    r = steady_state(STATE_A, SLOPE, "test", Change(to=80), pm25_override=100)
    assert (r.pm25_before, r.pm25_after) == (100, 80)
    assert r.population == 4000


def test_burden_runs_to_the_floor(world):
    world([("A", "a1", 80.0, 1000)])
    b = burden(STATE_A, SLOPE, "test")
    assert b.pm25_after == SLOPE.floor
    assert b.deaths_averted == pytest.approx(
        steady_state(STATE_A, SLOPE, "test", Change(to=SLOPE.floor)).deaths_averted)
    assert burden(STATE_A, SLOPE, "test", counterfactual=40).pm25_after == 40
    assert burden(STATE_A, SLOPE, "test", counterfactual=0).pm25_after == 0


# --- real data ------------------------------------------------------------------------------

DELHI = resolve("Delhi", kind="city")


def test_delhi_100_to_80_orders_curves():
    # The brief expected Jaganathan, then GEMM. On the real curves Vodonos (one slope of
    # 8.5% per 10 µg/m³, from 25) and AQLI's derived deaths also land between the two.
    share = {}
    for c in curves.available():
        r = steady_state(DELHI, c, "aqli", Change(to=80), pm25_override=100)
        assert (r.pm25_before, r.pm25_after) == (100, 80)
        assert r.fallback_states == []
        share[c.name] = r.deaths_averted / r.deaths_baseline
    others = {k: v for k, v in share.items() if k != "loglinear_jaganathan"}
    assert share["loglinear_jaganathan"] > max(others.values())
    assert min(share["loglinear_vodonos"], share["aqli"]) > share["gemm_ncd_lri"]
    assert share["gemm_ncd_lri"] > share["loglinear_brown"] > 0


def test_city_uses_its_own_population_and_state_rates():
    r = steady_state(DELHI, get("loglinear_jaganathan"), "cpcb", Change(delta=-10))
    assert r.population == exposure.cells(DELHI, "cpcb").population.item()
    b = baseline.load("Delhi", r.year)
    assert r.e0_before == pytest.approx(lifetable.e0(b.mx))


def test_map_errors_pass_through():
    with pytest.raises(ValueError, match="state-level"):
        steady_state(DELHI, get("loglinear_jaganathan"), "gbd2019", Change(delta=-10))
    with pytest.raises(ValueError, match="cit"):
        steady_state(resolve("India"), get("loglinear_jaganathan"), "cpcb", Change(delta=-10))


def test_india_lists_its_fallback_states():
    r = burden(resolve("India"), get("loglinear_jaganathan"), "gbd2019")
    expected = sorted(s for s in baseline.states() if s != "India" and baseline.load(s, 2019).fallback)
    assert r.fallback_states == expected
    assert r.deaths_averted > 0 and r.e0_after > r.e0_before


# --- life-years and death counts against an independent computation ---------------------------

def _independent_delhi(year: int = 2023):
    """Delhi's deaths by band and remaining life expectancy at the mean age of death, from the
    CSVs alone: no airhealth.lifetable, no airhealth.baseline. Life expectancy is integrated
    numerically over a survivorship curve that is a straight line between the printed l(x)
    within each band and falls at the constant rate l85 / L85+ above 85."""
    from airhealth import paths
    t = pd.read_csv(paths.DATA / "lifetables_srs.csv")
    t = t[t.state == "Delhi"].sort_values("age_start")
    lx, Lx = t.lx.to_numpy(float), t.Lx.to_numpy(float)
    mx = np.append((lx[:-1] - lx[1:]) / Lx[:-1], lx[-1] / Lx[-1])
    ages = np.linspace(0, 400, 400_001)                     # steps of 0.001 years
    surv = np.interp(ages, STARTS, lx)
    old = ages >= 85
    surv[old] = lx[-1] * np.exp(-mx[-1] * (ages[old] - 85))
    lived = np.concatenate([[0.0], np.cumsum((surv[1:] + surv[:-1]) / 2 * np.diff(ages))])
    remaining = (lived[-1] - lived) / surv                  # e(t) at every grid age
    width = np.diff(STARTS)
    mean_age_in_band = width / 2
    mean_age_in_band[0] = (Lx[0] - lx[1]) / (lx[0] - lx[1])  # infants: the table's own a0
    e_at_death = np.append(np.interp(STARTS[:-1] + mean_age_in_band, ages, remaining), 1 / mx[-1])

    p = pd.read_csv(paths.DATA / "population_age_state.csv")
    p = p[(p.state == "NCT OF DELHI") & (p.year == year)].sort_values("age_start")
    persons = p.population.to_numpy(float)
    assert len(persons) == 18
    population = np.append(persons[:-1], persons[-1] * Lx[-2:] / Lx[-2:].sum())
    rec = pd.read_csv(paths.DATA / "death_reconciliation.csv").set_index("state").loc["Delhi"]
    deaths = population * mx * np.where(STARTS >= rec.from_age, rec.factor, 1.0)
    return population, deaths, e_at_death


def test_delhi_life_years_match_an_independent_computation():
    population, deaths, e_at_death = _independent_delhi()
    state = resolve("Delhi")
    r = steady_state(state, get("loglinear_jaganathan"), "aqli", Change(to=80), pm25_override=100)
    assert r.year == 2023
    assert r.population == pytest.approx(population.sum())
    # 1e-4: the CSV's factor is rounded to four places; the tool solves it unrounded
    assert r.deaths_baseline == pytest.approx(deaths.sum(), rel=1e-4)
    averted = deaths * (1 - 1.086 ** -2)                    # every age: Jaganathan is all-age
    assert r.deaths_averted == pytest.approx(averted.sum(), rel=1e-4)
    # 0.05%: the independent curve runs through the printed (rounded) l(x); the tool rebuilds
    # l(x) from the rates
    assert r.yll_averted == pytest.approx((averted * e_at_death).sum(), rel=5e-4)
    # the band-start figure this replaces was about 7% higher
    b = baseline.load("Delhi", 2023)
    at_start = (averted * lifetable.life_table(b.mx).ex).sum()
    assert at_start / r.yll_averted == pytest.approx(1.07, abs=0.02)


def test_deaths_basis_scales_counts_not_life_expectancy():
    state = resolve("Delhi")
    curve = get("gemm_ncd_lri")
    srs = steady_state(state, curve, "aqli", Change(to=80), pm25_override=100)
    model = steady_state(state, curve, "aqli", Change(to=80), pm25_override=100, deaths="model")
    assert (srs.e0_before, srs.e0_after) == (model.e0_before, model.e0_after)
    assert srs.deaths_model == pytest.approx(model.deaths_baseline)
    assert model.deaths_model == model.deaths_baseline and model.reconciliations == ()
    rec, = srs.reconciliations
    assert (rec.state, rec.from_age) == ("Delhi", 45)
    assert rec.factor < srs.deaths_baseline / model.deaths_baseline < 1
    assert rec.factor < srs.deaths_averted / model.deaths_averted < 1
    with pytest.raises(ValueError, match="deaths"):
        steady_state(state, curve, "aqli", Change(to=80), deaths="registered")


def test_city_population_year_is_recorded():
    city = steady_state(DELHI, get("loglinear_jaganathan"), "aqli", Change(delta=-10))
    state = steady_state(resolve("Delhi"), get("loglinear_jaganathan"), "aqli", Change(delta=-10))
    assert (city.population_year, city.year) == (2011, 2023)
    assert (state.population_year, state.year) == (2023, 2023)
