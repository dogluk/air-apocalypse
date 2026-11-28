"""Year-round CPCB detail (scripts/build_cpcb_city_detail.py): the committed tables must rebuild
the annual and monthly CPCB tables they come from."""
import sys

import pandas as pd
import pytest

from airhealth import paths

sys.path.insert(0, str(paths.HEALTH / "scripts"))


def _detail():
    return pd.read_csv(paths.DATA / "cpcb_city_month_hour.csv")


def test_annual_mean_rebuilds_exposure_cpcb():
    t = _detail()
    e = pd.read_csv(paths.DATA / "exposure_cpcb.csv")
    for (city, year), g in t.groupby(["city", "year"]):
        row = e[(e.city == city) & (e.year == year)]
        if row.empty:            # dropped there for coverage
            continue
        mean = (g.pm25.fillna(0) * g.n_pm25).sum() / g.n_pm25.sum()
        assert mean == pytest.approx(row.pm25.item(), abs=0.06), (city, year)


def test_month_means_match_monthly_cpcb():
    t = _detail()
    m = pd.read_csv(paths.DATA / "monthly_cpcb.csv")
    m = m[m.city.isin(t.city)]
    assert len(m)
    for r in m.itertuples():
        g = t[(t.city == r.city) & (t.year == r.year) & (t.month == r.month)]
        mean = (g.pm25.fillna(0) * g.n_pm25).sum() / g.n_pm25.sum()
        assert mean == pytest.approx(r.pm25, abs=0.06), (r.city, r.year, r.month)


def test_stations_match_exposure_cpcb():
    s = pd.read_csv(paths.DATA / "cpcb_station_month.csv")
    e = pd.read_csv(paths.DATA / "exposure_cpcb.csv")
    for (city, year), g in s.groupby(["city", "year"]):
        row = e[(e.city == city) & (e.year == year)]
        if row.empty:
            continue
        assert g[g.share_pm25 > 0].station_id.nunique() == row.stations.item(), (city, year)


def test_bengaluru_is_covered_2016_to_2025():
    t = _detail()
    assert set(t[t.city == "Bengaluru"].year) == set(range(2016, 2026))
    assert set(t.hour) == set(range(24))


def test_build_on_synthetic_parquet(tmp_path):
    duckdb = pytest.importorskip("duckdb")  # noqa: F841
    from build_cpcb_city_detail import build

    ts = pd.date_range("2024-01-01", "2024-12-31 23:45", freq="15min", tz="UTC")
    n = len(ts)
    k = pd.Series(range(n))
    cols = ["Station ID", "State", "City", "Station Name", "Timestamp", "PM2.5 (µg/m³)", "PM10 (µg/m³)",
            "NO2 (µg/m³)", "SO2 (µg/m³)", "CO (mg/m³)", "Ozone (µg/m³)"]

    def station(sid, name, pm25, so2):
        # values vary from one 15-minute row to the next, so no run of identical values
        return pd.DataFrame({"Station ID": sid, "State": "S", "City": "X", "Station Name": name,
                             "Timestamp": ts, "PM2.5 (µg/m³)": pm25 + (k % 3) * 0.1,
                             "PM10 (µg/m³)": 200.0 + k % 5, "NO2 (µg/m³)": 20.0 + k % 4,
                             "SO2 (µg/m³)": so2, "CO (mg/m³)": 1.0 + (k % 3) * 0.1,
                             "Ozone (µg/m³)": 30.0 + k % 6})

    a = station("a", "Alpha", 10.0, 5.0 + (k % 2))
    b = station("b", "Beta", 30.0, float("nan"))
    day2 = b.Timestamp.dt.day == 2
    b.loc[day2 & (b.Timestamp.dt.month == 1), "PM2.5 (µg/m³)"] = float("nan")
    # a negative reading is dropped, not averaged in
    a.loc[(a.Timestamp.dt.month == 1) & (a.Timestamp.dt.day == 1) & (a.Timestamp.dt.hour == 3),
          "NO2 (µg/m³)"] = -5.0
    pd.concat([a, b])[cols].to_parquet(tmp_path / "cpcb-air-quality-2024.parquet")

    cmh, sm = build(tmp_path, {"X": ["X"]}, [2024])
    jan10 = cmh[(cmh.city == "X") & (cmh.month == 1) & (cmh.hour == 10)].iloc[0]
    # day 1: median of A (10.1) and B (30.1) = 20.1; day 2: A alone = 10.1; the other 29 days 20.1
    assert jan10.n_pm25 == 31
    assert jan10.pm25 == pytest.approx((30 * 20.1 + 10.1) / 31, abs=0.1)
    assert jan10.n_so2 == 31              # from A only, on every day
    assert jan10.so2 == pytest.approx(5.5, abs=0.01)
    assert len(cmh[(cmh.month == 1)]) == 24
    ja = sm[(sm.station_id == "a") & (sm.month == 1)].iloc[0]
    jb = sm[(sm.station_id == "b") & (sm.month == 1)].iloc[0]
    assert ja.station == "Alpha"
    assert ja.share_pm25 == 1.0 and jb.share_so2 == 0.0
    assert ja.share_so2 == 1.0
    assert jb.share_pm25 == pytest.approx(30 / 31, abs=0.01)
    assert jb.pm25 == pytest.approx(30.1, abs=0.1)
    # the one hour of negative NO2 readings at A is dropped, not averaged in
    assert ja.share_no2 == pytest.approx(743 / 744, abs=0.001)


def test_the_eleven_big_cities_are_covered():
    t = _detail()
    s = pd.read_csv(paths.DATA / "cpcb_station_month.csv")
    eleven = {"Delhi", "Mumbai", "Kolkata", "Bengaluru", "Chennai", "Hyderabad", "Ahmedabad",
              "Pune", "Surat", "Jaipur", "Lucknow"}
    assert set(t.city) == eleven and set(s.city) == eleven
    for c in eleven:
        assert t[t.city == c].n_pm25.sum() > 0, c
