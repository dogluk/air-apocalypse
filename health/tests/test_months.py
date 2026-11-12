import numpy as np
import pandas as pd
import pytest

from airhealth import intervention, months, paths, places


def test_monthly_means_rebuild_the_annual_ones():
    m = pd.read_csv(paths.DATA / "monthly_cpcb.csv")
    a = pd.read_csv(paths.DATA / "exposure_cpcb.csv")
    for city, year in [("Delhi", 2024), ("Mumbai", 2024), ("Bengaluru", 2023)]:
        months = m[(m.city == city) & (m.year == year)].sort_values("month")
        assert len(months) == 12
        hours = intervention.MONTH_DAYS * 24 * months.hours_share.to_numpy()
        rebuilt = np.dot(hours, months.pm25) / hours.sum()     # hour-weighted, as the annual is
        annual = a[(a.city == city) & (a.year == year)].pm25.item()
        assert rebuilt == pytest.approx(annual, rel=0.005)


def test_delhi_winter_is_dirtier_than_monsoon():
    m = pd.read_csv(paths.DATA / "monthly_cpcb.csv")
    d = m[(m.city == "Delhi") & m.year.between(2023, 2025)].groupby("month").pm25.mean()
    assert d[11] / d[7] > 4


# --- shapes (Task 4) ---------------------------------------------------------------------

def _row(city, month, pm25, year=2024):
    return {"city": city, "year": year, "month": month, "pm25": pm25, "hours_share": 1.0}


def test_shape_is_normalised():
    for p in (places.resolve("Delhi"), places.resolve("Chennai"), places.resolve("Bihar"),
              places.resolve("India"), places.resolve("Patna", kind="district"),
              places.resolve("Ranchi"), places.resolve("Surat")):
        s = months.shape(p).values
        assert len(s) == 12 and np.dot(months.MONTH_DAYS, s) / 365 == pytest.approx(1)


def test_delhi_own_shape():
    c = months.shape(places.resolve("Delhi", kind="city"))
    assert not c.borrowed and c.values[10] > 2 and c.values[6] < 0.5
    assert c.basis == "Delhi, CPCB 2023-25"
    s = months.shape(places.resolve("Delhi"))      # the state: one monitored city, rule 3
    assert s.borrowed and np.allclose(s.values, c.values)


def test_city_without_monitor_borrows():
    s = months.shape(places.resolve("Rajkot"))      # Gujarat; no CPCB data
    assert s.borrowed and "borrowed from" in s.basis
    assert s.basis == "borrowed from Ahmedabad"     # largest Gujarat city with a profile
    assert np.allclose(s.values, months.shape(places.resolve("Ahmedabad")).values)


def test_no_state_profile_borrows_india():
    s = months.shape(places.resolve("Ranchi"))      # Jharkhand has no complete city
    assert s.borrowed and "India" in s.basis
    assert np.allclose(s.values, months.shape(places.resolve("India")).values)


def test_missing_month_falls_back(monkeypatch):
    t = months._table()
    cut = t[~((t.city == "Gaya") & (t.month == 7))]     # Gaya loses July in every year
    monkeypatch.setattr(months, "_table", lambda: cut)
    s = months.shape(places.resolve("Gaya"))
    assert s.borrowed and s.basis == "borrowed from Patna"


def test_missing_month_in_window_widens_to_all_years(monkeypatch):
    # No real city completes by widening (Surat has 9 months in all its years), so give Surat
    # the months it lacks in 2019: the 2023-25 window is still short, 2016-25 is complete.
    t = months._table()
    extra = pd.DataFrame([_row("Surat", m, 50.0, year=2019) for m in (6, 7, 9)])
    monkeypatch.setattr(months, "_table", lambda: pd.concat([t, extra], ignore_index=True))
    s = months.shape(places.resolve("Surat"))
    assert not s.borrowed and s.basis == "Surat, CPCB 2016-25"


def test_incomplete_city_borrows_from_state():
    s = months.shape(places.resolve("Surat"))       # 9 months in every year it has
    assert s.borrowed and s.basis == "borrowed from Ahmedabad"


def test_state_shape_is_population_weighted(monkeypatch):
    cities = pd.DataFrame({"city": ["Big", "Small"], "state": ["Testland"] * 2,
                           "population": [3_000_000, 1_000_000]})
    rows = [_row("Big", m, 10.0 + (m == 1) * 10) for m in range(1, 13)]
    rows += [_row("Small", m, 10.0 + (m == 2) * 10) for m in range(1, 13)]
    monkeypatch.setattr(months, "_table", lambda: pd.DataFrame(rows))
    monkeypatch.setattr(months, "_cities", lambda: cities)
    a = months._normalise(np.array([20.0] + [10.0] * 11))
    b = months._normalise(np.array([10.0, 20.0] + [10.0] * 10))
    s = months.shape(places.Place("state", "Testland", "Testland"))
    assert s.borrowed and s.basis == "Testland: 2 monitored cities"
    assert np.allclose(s.values, months._normalise(0.75 * a + 0.25 * b))
