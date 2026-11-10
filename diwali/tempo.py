"""The 'tempo' of Diwali week: hourly PM2.5 relative to normal, Day -3 to Day +4, for the ten
largest metros, and the cross-city average.

Per city and year, each hour is divided by the median of the same clock hour on baseline days
(8-21 days either side of Diwali, excluding Dussehra and Gurpurab +/-1). Per city, take the
median across years; across cities, the median of the ten city curves.

Outputs: data/tempo_hourly.csv (t, each city, all-city median), data/tempo_daily.csv
"""
import numpy as np
import pandas as pd

from config import DATA, DIWALI, DUSSEHRA, GURPURAB

TEN = ["Delhi", "Mumbai", "Kolkata", "Bengaluru", "Chennai", "Hyderabad", "Ahmedabad", "Pune", "Surat", "Jaipur"]

c = pd.read_parquet(DATA / "city_hourly.parquet")
c = c[c.city.isin(TEN)].copy()
c["yr"] = c.hour.dt.year
c["D"] = c.yr.map(lambda y: pd.Timestamp(DIWALI[y]))
c["t"] = (c.hour - c.D) / pd.Timedelta(hours=1)          # hours since 00:00 on Diwali day
c["hh"] = c.hour.dt.hour
c["day"] = (c.hour.dt.normalize() - c.D).dt.days          # calendar day relative to Diwali
c["k"] = ((c.hour - pd.Timedelta(hours=12)).dt.normalize() - c.D).dt.days
other = lambda tbl: (c.hour.dt.normalize() - c.yr.map(lambda y: pd.Timestamp(tbl[y]))).dt.days.abs() <= 1
c["is_base"] = c.k.abs().between(8, 21) & ~other(DUSSEHRA) & ~other(GURPURAB)

base = c[c.is_base].groupby(["city", "yr", "hh"]).pm25.median().rename("b")
w = c[c.t.between(-72, 5 * 24 - 1)].merge(base, left_on=["city", "yr", "hh"], right_index=True)
w["r"] = w.pm25 / w.b

# per city: median across years at each hour; require >= 2 years at that hour
g = w.groupby(["city", "t"]).r
city_curve = g.median().where(g.count() >= 2).unstack(0)[TEN]
city_curve["all"] = np.exp(np.log(city_curve[TEN]).median(axis=1))
city_curve["all_smooth"] = city_curve["all"].rolling(3, center=True, min_periods=1).mean()
city_curve.to_csv(DATA / "tempo_hourly.csv")

# daily (calendar day) mean ratio per city, then median across cities
dd = w.groupby(["city", "yr", "day"]).apply(lambda x: x.pm25.mean() / x.b.mean()).rename("r").reset_index()
daily = dd.groupby(["city", "day"]).r.median().unstack(0)[TEN]
daily["all"] = np.exp(np.log(daily[TEN]).median(axis=1))
daily.to_csv(DATA / "tempo_daily.csv")

pd.set_option("display.width", 200)
print("Daily mean PM2.5 ÷ normal (calendar days, median year):")
print(daily.round(2).T.to_string())
s = city_curve["all_smooth"]
pk_t = s.idxmax()
print(f"\nAll-city peak: {s.max():.2f}× at t={pk_t:.0f}h ({int(pk_t % 24):02d}:00, day {int(pk_t // 24)})")
after = s[s.index > pk_t]
settled = after[(after.rolling(12).max() <= 1.2)]
print("back within 1.2× of normal (12h sustained) from t =", settled.index.min() - 11 if len(settled) else None)
for d in range(-3, 5):
    seg = s[(s.index >= 24 * d) & (s.index < 24 * (d + 1))]
    print(f"day {d:+d}: max {seg.max():.2f}× at {int(seg.idxmax() % 24):02d}:00, mean {seg.mean():.2f}×")
print("\nper-city peak ratio (Diwali night, t 12..36):")
print(city_curve.loc[12:36, TEN].max().round(1).sort_values(ascending=False).to_string())
