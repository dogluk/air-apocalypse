import numpy as np
import pytest

from airhealth import lag


def test_lag_profiles():
    assert (lag.profile("immediate", 30) == 1.0).all()
    epa = lag.profile("epa20", 30)
    assert len(epa) == 30
    assert (np.diff(epa) >= 0).all()
    assert epa[-1] == pytest.approx(1.0)
    assert epa[0] < 0.5


def test_epa20_matches_its_source():
    # EPA 2024 TSD, section 6.4.2: 30% in the first year, 50% evenly over years 2-5,
    # 20% evenly over years 6-20.
    epa = lag.profile("epa20", 25)
    assert epa[0] == pytest.approx(0.30)
    assert epa[1] == pytest.approx(0.425)
    assert epa[4] == pytest.approx(0.80)
    assert epa[5] == pytest.approx(0.80 + 0.20 / 15)
    assert epa[18] < 1.0
    assert epa[19:] == pytest.approx(np.ones(6))


def test_short_horizon_and_unknown_name():
    assert len(lag.profile("epa20", 3)) == 3
    with pytest.raises(ValueError, match="epa20"):
        lag.profile("epa30", 5)
