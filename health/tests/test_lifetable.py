import numpy as np
import pytest

from airhealth.lifetable import e0, life_table, scale_adult, solve_adult_factor


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
