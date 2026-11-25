import numpy as np
import pytest

from airhealth.lifetable import STARTS, e0, ex_at_death, life_table, scale_adult, solve_adult_factor


def test_constant_hazard_gives_reciprocal_life_expectancy():
    mx = np.full(19, 0.02)
    assert e0(mx) == pytest.approx(50.0, rel=0.02)


def test_scaling_adults_leaves_children_alone():
    mx = np.full(19, 0.01)
    out = scale_adult(mx, 0.9)
    assert (out[:6] == mx[:6]).all() and np.allclose(out[6:], 0.009)


def test_solver_inverts_scaling():
    mx = np.linspace(0.001, 0.15, 19)
    f = solve_adult_factor(mx, e0(scale_adult(mx, 0.85)) - e0(mx))
    assert f == pytest.approx(0.85, abs=1e-4)


def test_lower_rates_raise_life_expectancy():
    mx = np.linspace(0.001, 0.15, 19)
    assert e0(mx * 0.9) > e0(mx)
    assert e0(scale_adult(mx, 0.9)) > e0(mx)


def test_table_is_internally_consistent():
    mx = np.linspace(0.001, 0.15, 19)
    t = life_table(mx)
    assert t.lx[0] == 1.0
    assert (np.diff(t.lx) < 0).all()
    assert t.qx[-1] == 1.0
    assert t.Lx[-1] == pytest.approx(t.lx[-1] / mx[-1])
    assert t.ex[0] == pytest.approx(t.Lx.sum())


def test_life_expectancy_at_death_matches_numerical_integration():
    """e at the mean age of death in each band, against a numerical integral of a survivorship
    curve drawn as straight lines between the table's l(x) (constant rate above 85)."""
    mx = 0.0004 * np.exp(0.085 * STARTS)
    mx[:2] = (0.03, 0.002)
    t = life_table(mx)
    ages = np.linspace(0, 300, 600_001)
    surv = np.interp(ages, STARTS, t.lx)
    old = ages >= 85
    surv[old] = t.lx[-1] * np.exp(-mx[-1] * (ages[old] - 85))
    lived = np.concatenate([[0.0], np.cumsum((surv[1:] + surv[:-1]) / 2 * np.diff(ages))])
    remaining = (lived[-1] - lived) / surv
    a = np.diff(STARTS) / 2
    a[0] = (t.Lx[0] - t.lx[1]) / (t.lx[0] - t.lx[1])
    expected = np.append(np.interp(STARTS[:-1] + a, ages, remaining), 1 / mx[-1])
    got = ex_at_death(mx)
    assert got == pytest.approx(expected, rel=1e-5)
    # less than at the start of the band, more than at the start of the next one
    assert (got[:-1] < t.ex[:-1])[2:].all() and (got[:-1] > t.ex[1:])[2:-1].all()
    assert got[-1] == pytest.approx(t.ex[-1])
