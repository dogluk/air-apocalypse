"""Diwali PM2.5 effect across Indian metros, 2016-2025, and what confounds it.

Unit: the "night-day" = 12:00 on day d to 11:59 on d+1, so a firework night falls inside one
unit. k = night-day minus Lakshmi Puja date (k=0 is Diwali night).

The festival's main cracker night differs by region (Naraka Chaturdashi in Tamil Nadu = k-1,
Lakshmi Puja/Kali Puja = k0, Bali Padyami / Gujarati New Year = k+1), so the headline estimate is a
three-night festival window k in {-1, 0, +1}, alongside per-night k dummies.

Confounders: year effects, seasonal spline, weekday, ERA5 night boundary-layer height, wind,
rain, humidity, MODIS fires within 300 km (+ Punjab-Haryana for northern cities), and dummies
for the two other firework nights inside the baseline (Dussehra ~k-19, Gurpurab k+15).

CIs: SEs clustered by year with a t(G-1) critical value -- wide for cities with few Diwalis.

Outputs (data/): city_hourly.parquet, nightday.parquet, effects.csv, summary.csv
"""
import warnings

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats

from config import CITIES, DATA, DIWALI, DUSSEHRA, GURPURAB

warnings.filterwarnings("ignore")
POLL = ["pm25", "pm10", "so2", "no2", "co", "o3"]
D_OF = {y: pd.Timestamp(v) for y, v in DIWALI.items()}
FW = [-1, 0, 1]

# ---------- 1. station QC -> city-hour medians ----------
h = pd.read_parquet(DATA / "hourly.parquet")
h["year"] = h.hour.dt.year
cov = h[h.hour.dt.month.isin([10, 11])].groupby(["station_id", "year"]).pm25.apply(lambda s: s.notna().mean())
keep = set(cov[cov >= 0.6].index)
h = h[[k in keep for k in zip(h.station_id, h.year)]]
st_years = h.groupby(["city", "year"]).station_id.nunique().unstack(fill_value=0)
print("stations kept per city-year:\n", st_years.to_string())

city = h.groupby(["city", "hour"])[POLL].median()
city["n_st"] = h.groupby(["city", "hour"]).pm25.count()
city = city.reset_index()
city.to_parquet(DATA / "city_hourly.parquet", index=False)

# ---------- 2. night-day panel + weather + fires ----------
w = pd.read_parquet(DATA / "weather_era5.parquet").rename(columns={"time": "hour"})
city = city.merge(w, on=["city", "hour"], how="left")
city["nd"] = (city.hour - pd.Timedelta(hours=12)).dt.normalize()
city["night"] = city.hour.dt.hour.isin(list(range(18, 24)) + list(range(0, 6)))
agg = city.groupby(["city", "nd"]).agg(
    **{p: (p, "mean") for p in POLL}, pm25_n=("pm25", "count"),
    precip=("precipitation", "sum"), wind=("wind_speed_10m", "mean"),
    rh=("relative_humidity_2m", "mean"), temp=("temperature_2m", "mean")).reset_index()
night = city[city.night].groupby(["city", "nd"]).agg(blh_night=("boundary_layer_height", "mean")).reset_index()
nd = agg.merge(night, on=["city", "nd"])
nd = nd[nd.pm25_n >= 18].copy()

fires = pd.read_parquet(DATA / "fires_daily.parquet").pivot(index="date", columns="region", values="fires")
f3 = fires.rolling(3, min_periods=1).sum()  # d-2..d
nd["fires_local"] = [f3.at[d, f"local_{c}"] for c, d in zip(nd.city, nd.nd)]
nd["fires_ph"] = f3.loc[nd.nd, "punjab_haryana"].values

nd["year"] = nd.nd.dt.year
nd["k"] = (nd.nd - nd.year.map(D_OF)).dt.days
nd["doy"] = nd.nd.dt.dayofyear
nd["dow"] = nd.nd.dt.dayofweek
nd["lpm"] = np.log(nd.pm25)
nd["lblh"] = np.log(nd.blh_night.clip(lower=20))
nd["lprecip"] = np.log1p(nd.precip)
nd["lfire_local"] = np.log1p(nd.fires_local)
nd["lfire_ph"] = np.log1p(nd.fires_ph)
nd["dus"] = (nd.nd == nd.year.map(lambda y: pd.Timestamp(DUSSEHRA[y]))).astype(int)
nd["gur"] = (nd.nd == nd.year.map(lambda y: pd.Timestamp(GURPURAB[y]))).astype(int)
for k in range(-3, 8):
    nd[f"k_{'m' if k < 0 else 'p'}{abs(k)}"] = (nd.k == k).astype(int)
nd["fw"] = nd.k.isin(FW).astype(int)
nd["pre"] = nd.k.isin([-3, -2]).astype(int)
nd["post"] = nd.k.between(2, 7).astype(int)
# raw baseline excludes the other festival nights +/-1
nd["is_base"] = nd.k.abs().between(8, 21) & ~(
    (nd.nd - nd.year.map(lambda y: pd.Timestamp(DUSSEHRA[y]))).dt.days.abs().le(1)
    | (nd.nd - nd.year.map(lambda y: pd.Timestamp(GURPURAB[y]))).dt.days.abs().le(1))
nd.to_parquet(DATA / "nightday.parquet", index=False)

KD = [c for c in nd.columns if c.startswith("k_")]
win = nd[(nd.nd.dt.strftime("%m-%d") >= "10-01") & (nd.nd.dt.strftime("%m-%d") <= "12-10")].dropna(
    subset=["lpm", "lblh", "wind", "lprecip", "rh"])
# a year counts only if the festival window and some baseline are observed
ok = win.groupby(["city", "year"]).apply(lambda d: d.fw.sum() >= 2 and d.is_base.sum() >= 10)
win = win.set_index(["city", "year"]).loc[ok[ok].index].reset_index()

BASE = "C(year) + bs(doy, df=4) + C(dow) + dus + gur"
WX = "lblh + wind + lprecip + rh"


def fires_for(c):
    return "lfire_local + lfire_ph" if CITIES[c]["ph"] else "lfire_local"


def fit(f, d):
    m = smf.ols(f, d).fit(cov_type="cluster", cov_kwds={"groups": d.year})
    G = d.year.nunique()
    return m, stats.t.ppf(0.975, G - 1)


def pct(b):
    return 100 * (np.exp(b) - 1)


MODELS = {"M0 season+year": BASE, "M1 +weather": f"{BASE} + {WX}", "M2 +weather+fires": None}

rows, summ = [], []
for c, d in win.groupby("city"):
    G = d.year.nunique()
    specs = {k: (v or f"{BASE} + {WX} + {fires_for(c)}") for k, v in MODELS.items()}
    # per-night effects
    for name, rhs in specs.items():
        m, t = fit(f"lpm ~ {' + '.join(KD)} + {rhs}", d)
        for kn in KD:
            k = int(kn[3:]) * (-1 if kn[2] == "m" else 1)
            b, se = m.params[kn], m.bse[kn]
            rows.append(dict(city=c, model=name, k=k, pct=pct(b), lo=pct(b - t * se), hi=pct(b + t * se),
                             r2=m.rsquared, n=int(m.nobs), years=G))
    # festival window + post-week, raw (M0) vs adjusted (M2)
    res = {}
    for name in ["M0 season+year", "M2 +weather+fires"]:
        m, t = fit(f"lpm ~ fw + pre + post + {specs[name]}", d)
        res[name] = m, t
    m2, t2 = res["M2 +weather+fires"]
    m0, _ = res["M0 season+year"]

    # raw ratios vs +/-8..21 baseline (median across years)
    # computed in logs (geometric means) so it is the same estimand as the regression
    base = d[d.is_base].groupby("year").pm25.median()
    lbase = d[d.is_base].groupby("year").lpm.mean()
    per_year = np.exp(d[d.fw == 1].groupby("year").lpm.mean() - lbase)
    raw_fw = per_year.median()
    raw_post = np.exp(d[d.post == 1].groupby("year").lpm.mean() - lbase).median()
    rain = d[d.fw == 1].groupby("year").precip.sum()
    rho = stats.spearmanr(per_year, rain.reindex(per_year.index)).correlation if G >= 4 else np.nan

    # placebo: fake Diwali = another year's (month, day), >= 10 days from the real one
    pl = []
    for mo, da in sorted({(v.month, v.day) for v in DIWALI.values()}):
        fake = {y: pd.Timestamp(y, mo, da) for y in DIWALI}
        dd = d[[abs((fake[y] - D_OF[y]).days) >= 10 for y in d.year]].copy()
        if dd.year.nunique() < 2:
            continue
        kf = (dd.nd - dd.year.map(fake)).dt.days
        dd["fw_fake"] = kf.isin(FW).astype(int)
        dd = dd[~dd.k.between(-3, 7)]  # drop the real festival so it can't leak in
        try:
            mp = smf.ols(f"lpm ~ fw_fake + {specs['M1 +weather']}", dd).fit()
            pl.append(pct(mp.params["fw_fake"]))
        except Exception:
            pass
    pl = np.array(pl)

    # firework-hours chemistry: 20:00-02:59 on k in -1..1 vs same hours on baseline nights
    ch = city[city.city == c].copy()
    ch["k"] = (ch.nd - ch.hour.dt.year.map(D_OF)).dt.days
    fwh = ch[ch.hour.dt.hour.isin([20, 21, 22, 23, 0, 1, 2])]
    yy = fwh.hour.dt.year
    b_ = fwh[fwh.k.abs().between(8, 21)].groupby(yy)[POLL].median()
    f_ = fwh[fwh.k.isin(FW)].groupby(yy)[POLL].mean()
    fp = (f_ / b_).median()

    bfw, sefw = m2.params["fw"], m2.bse["fw"]
    bpo, sepo = m2.params["post"], m2.bse["post"]
    summ.append(dict(
        city=c, years=G, stations_median=int(st_years.loc[c][st_years.loc[c] > 0].median()),
        base_pm25=base.median(),
        raw_fw_pct=100 * (raw_fw - 1), m0_fw_pct=pct(res["M0 season+year"][0].params["fw"]),
        adj_fw_pct=pct(bfw), adj_fw_lo=pct(bfw - t2 * sefw), adj_fw_hi=pct(bfw + t2 * sefw),
        raw_post_pct=100 * (raw_post - 1), m0_post_pct=pct(m0.params["post"]),
        adj_post_pct=pct(bpo), adj_post_lo=pct(bpo - t2 * sepo), adj_post_hi=pct(bpo + t2 * sepo),
        excess_ugm3=base.median() * (np.exp(bfw) - 1),
        fh_pm25=fp.pm25, fh_so2=fp.so2, fh_no2=fp.no2, fh_co=fp.co,
        rain_rho=rho, rain_fw_mm_median=rain.median(),
        fires_local_daily=d.fires_local.mean() / 3, fires_ph_on_fw_vs_base=(
            d[d.fw == 1].fires_ph.median() / max(d[d.is_base].fires_ph.median(), 1)),
        placebo_median=np.median(pl) if len(pl) else np.nan, placebo_max=pl.max() if len(pl) else np.nan,
        placebo_n=len(pl), placebo_share_ge=(pl >= pct(bfw)).mean() if len(pl) else np.nan,
        coef_lblh=m2.params["lblh"], coef_lprecip=m2.params["lprecip"],
        coef_fire_local=m2.params["lfire_local"], coef_fire_ph=m2.params.get("lfire_ph", np.nan),
    ))

eff = pd.DataFrame(rows)
eff.to_csv(DATA / "effects.csv", index=False)
S = pd.DataFrame(summ).sort_values("adj_fw_pct", ascending=False)
S.to_csv(DATA / "summary.csv", index=False)
pd.set_option("display.width", 220)
print("\nFestival window (k-1..+1) and post-week (k+2..+7), % above counterfactual:")
print(S[["city", "years", "stations_median", "base_pm25", "raw_fw_pct", "m0_fw_pct", "adj_fw_pct", "adj_fw_lo",
         "adj_fw_hi", "excess_ugm3", "raw_post_pct", "m0_post_pct", "adj_post_pct"]].round(0).to_string(index=False))
print("\nConfounders, chemistry and placebo:")
print(S[["city", "fh_pm25", "fh_so2", "fh_no2", "fh_co", "rain_rho", "rain_fw_mm_median", "fires_local_daily",
         "fires_ph_on_fw_vs_base", "coef_lprecip", "coef_fire_local", "coef_fire_ph", "placebo_median",
         "placebo_max", "placebo_share_ge"]].round(2).to_string(index=False))
print("\nPer-night adjusted (M2) effects, %:")
print(eff[(eff.model == "M2 +weather+fires") & eff.k.between(-2, 3)].pivot(index="city", columns="k", values="pct").round(0))
