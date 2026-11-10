"""Has the Diwali effect grown over 2016-2025?

Per city, the analyze.py M2 model with the festival-window dummy interacted with year gives one
adjusted effect per city-year. Also a descriptive measure: firework hours (20:00-02:59, days -1..+1)
÷ the same hours on baseline nights.

Trend = within-city slope: WLS of the city-year log-effect on year with city fixed effects
(weights = 1/se²), SEs clustered by city. Sensitivities: drop 2020 (Covid + widespread bans),
add rain, unweighted, the 7 cities with >= 7 years.

Outputs: data/trend_cityyear.csv
"""
import warnings

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from config import CITIES, DATA, DIWALI

warnings.filterwarnings("ignore")
TEN = ["Delhi", "Mumbai", "Kolkata", "Bengaluru", "Chennai", "Hyderabad", "Ahmedabad", "Pune", "Surat", "Jaipur"]
nd = pd.read_parquet(DATA / "nightday.parquet")
win = nd[(nd.nd.dt.strftime("%m-%d") >= "10-01") & (nd.nd.dt.strftime("%m-%d") <= "12-10")].dropna(
    subset=["lpm", "lblh", "wind", "lprecip", "rh"])
ok = win.groupby(["city", "year"]).apply(lambda d: d.fw.sum() >= 2 and d.is_base.sum() >= 10)
win = win.set_index(["city", "year"]).loc[ok[ok].index].reset_index()

BASE = "C(year) + bs(doy, df=4) + C(dow) + dus + gur + lblh + wind + lprecip + rh"
rows = []
for c, d in win.groupby("city"):
    fire = "lfire_local + lfire_ph" if CITIES[c]["ph"] else "lfire_local"
    d = d.copy()
    for y in sorted(d.year.unique()):
        d[f"fw_{y}"] = ((d.fw == 1) & (d.year == y)).astype(int)
    fws = [f"fw_{y}" for y in sorted(d.year.unique())]
    m = smf.ols(f"lpm ~ {' + '.join(fws)} + pre + post + {BASE} + {fire}", d).fit(cov_type="HC1")
    for y in sorted(d.year.unique()):
        rain = d[(d.year == y) & (d.fw == 1)].precip.sum()
        rows.append(dict(city=c, year=y, b=m.params[f"fw_{y}"], se=m.bse[f"fw_{y}"], rain_fw=rain))
T = pd.DataFrame(rows)

# descriptive firework-hours ratio per city-year
h = pd.read_parquet(DATA / "city_hourly.parquet")
h["yr"] = h.hour.dt.year
h["D"] = h.yr.map(lambda y: pd.Timestamp(DIWALI[y]))
h["k"] = ((h.hour - pd.Timedelta(hours=12)).dt.normalize() - h.D).dt.days
fwh = h[h.hour.dt.hour.isin([20, 21, 22, 23, 0, 1, 2])]
r = (fwh[fwh.k.isin([-1, 0, 1])].groupby(["city", "yr"]).pm25.mean()
     / fwh[fwh.k.abs().between(8, 21)].groupby(["city", "yr"]).pm25.median()).rename("fh_ratio")
base_lvl = h[h.k.abs().between(8, 21)].groupby(["city", "yr"]).pm25.median().rename("base_pm25")
T = T.merge(r, left_on=["city", "year"], right_index=True, how="left").merge(
    base_lvl, left_on=["city", "year"], right_index=True, how="left")
T["pct"] = 100 * (np.exp(T.b) - 1)
T["excess"] = T.base_pm25 * (np.exp(T.b) - 1)
T["lfh"] = np.log(T.fh_ratio)
T = T[T.city.isin(TEN)]
T.to_csv(DATA / "trend_cityyear.csv", index=False)

pd.set_option("display.width", 200)
print("Adjusted festival-window effect (%), by city and year:")
print(T.pivot(index="city", columns="year", values="pct").round(0).to_string())
print("\nFirework-hours ratio (×), by city and year:")
print(T.pivot(index="city", columns="year", values="fh_ratio").round(1).to_string())
print("\nMedian across cities with data, by year (n cities):")
g = T.groupby("year").agg(n=("city", "size"), adj_pct=("pct", "median"), fh_ratio=("fh_ratio", "median"),
                          excess=("excess", "median"), base=("base_pm25", "median"), rain=("rain_fw", "median"))
print(g.round(2).to_string())


def slope(d, f="b ~ year + C(city)", w=True, label=""):
    d = d.dropna(subset=["b", "se"])
    kw = dict(weights=1 / d.se ** 2) if w else {}
    m = (smf.wls if w else smf.ols)(f, d, **kw).fit(cov_type="cluster", cov_kwds={"groups": d.city})
    s, se = m.params["year"], m.bse["year"]
    print(f"{label:<44} {100 * (np.exp(s) - 1):+5.1f}%/yr  (95% CI {100 * (np.exp(s - 1.96 * se) - 1):+.1f} "
          f"to {100 * (np.exp(s + 1.96 * se) - 1):+.1f})  n={len(d)}")


print("\nWithin-city trend in the Diwali effect (multiplicative change in the effect ratio per year):")
slope(T, label="All 10 cities, inverse-variance weighted")
slope(T, w=False, label="Unweighted")
slope(T[T.year != 2020], label="Excluding 2020 (Covid, bans)")
slope(T.assign(lr=np.log1p(T.rain_fw)), f="b ~ year + lr + C(city)", label="Controlling for festival rain")
big = T.groupby("city").year.count()
slope(T[T.city.isin(big[big >= 7].index)], label="Cities with >= 7 Diwalis")
slope(T[T.year >= 2018], label="2018 onward (after SC green-cracker order)")
d2 = T.dropna(subset=["lfh"]).assign(b=lambda x: x.lfh, se=1.0)
slope(d2, w=False, label="Descriptive firework-hours ratio, unweighted")
print("\nPer-city slopes (adjusted effect, %/yr, OLS on years):")
for c, d in T.groupby("city"):
    if len(d) >= 5:
        s = np.polyfit(d.year, d.b, 1)[0]
        print(f"  {c:<10} {100 * (np.exp(s) - 1):+5.1f}%/yr  ({len(d)} yrs)")
