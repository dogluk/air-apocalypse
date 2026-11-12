import numpy as np
import pandas as pd
import pytest

from airhealth import intervention, paths


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
