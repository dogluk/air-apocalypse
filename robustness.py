"""Robustness checks on analyze.py's Diwali estimates.

1. The post-Diwali "hangover" (k = 3..7): raw ratio vs after season/weather/fire controls.
2. Bengaluru year by year: is the spike missing in rainy years?
3. Placebo: re-run the M1 model with fake Diwali dates (the other years' dates, >= 10 days from
   the real one) to see what size of k=0 "effect" the calendar alone produces.
"""
import warnings

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from config import DATA, DIWALI

warnings.filterwarnings("ignore")
nd = pd.read_parquet(DATA / "nightday.parquet")
win = nd[(nd.nd.dt.strftime("%m-%d") >= "10-01") & (nd.nd.dt.strftime("%m-%d") <= "12-10")].dropna(
    subset=["lpm", "lblh", "wind", "lprecip", "rh"]).copy()
CTRL = "C(year) + bs(doy, df=5) + C(dow)"
WX = "lblh + wind + lprecip + rh"


def kdummies(df, D, ks):
    k = (df.nd - df.year.map(D)).dt.days
    names = []
    for kk in ks:
        n = f"k_{'m' if kk < 0 else 'p'}{abs(kk)}"
        df[n] = (k == kk).astype(int)
        names.append(n)
    return names


# 1. hangover
print("Post-Diwali hangover, % vs counterfactual (M0 season only / M2 + weather + fires):")
for c, d in win.groupby("city"):
    d = d.copy()
    names = kdummies(d, {y: pd.Timestamp(v) for y, v in DIWALI.items()}, range(-3, 8))
    fire = "lfire_local + lfire_ph" if c == "Delhi" else "lfire_local"
    out = {}
    for lab, f in [("M0", f"lpm ~ {' + '.join(names)} + {CTRL}"),
                   ("M2", f"lpm ~ {' + '.join(names)} + {CTRL} + {WX} + {fire}")]:
        m = smf.ols(f, d).fit(cov_type="cluster", cov_kwds={"groups": d.year})
        out[lab] = {n: round(100 * (np.exp(m.params[n]) - 1)) for n in names if n.startswith("k_p")}
    print(c, pd.DataFrame(out).T.to_string(), sep="\n")

# 2. Bengaluru year by year
print("\nBengaluru by year: PM2.5 ratio on Diwali night-day vs rain over k=-1..1 (ERA5 mm):")
b = nd[nd.city == "Bengaluru"]
base = b[b.k.abs().between(8, 21)].groupby("year").pm25.median()
r = pd.DataFrame({
    "ratio_k0": b[b.k == 0].set_index("year").pm25 / base,
    "rain_mm_k-1..1": b[b.k.between(-1, 1)].groupby("year").precip.sum().round(1),
    "rain_mm_baseline_per_day": b[b.k.abs().between(8, 21)].groupby("year").precip.mean().round(1),
    "pm25_k0": b[b.k == 0].set_index("year").pm25.round(0),
}).round(2)
print(r.to_string())
print("corr(ratio, rain k-1..1):", round(r["ratio_k0"].corr(r["rain_mm_k-1..1"]), 2))

# 3. placebo
print("\nPlacebo k=0 effects (M1), fake Diwali = another year's date >= 10 days away:")
dates = sorted({(v.month, v.day) for v in DIWALI.values()})
for c, d in win.groupby("city"):
    real = {y: pd.Timestamp(v) for y, v in DIWALI.items()}
    m = smf.ols(f"lpm ~ {' + '.join(kdummies(d.copy(), real, [0]))} + {CTRL} + {WX}",
                d.assign(**{"k_p0": ((d.nd - d.year.map(real)).dt.days == 0).astype(int)})).fit()
    true_eff = 100 * (np.exp(m.params["k_p0"]) - 1)
    pl = []
    for mo, da in dates:
        fake = {y: pd.Timestamp(y, mo, da) for y in DIWALI}
        if any(abs((fake[y] - real[y]).days) < 10 for y in DIWALI):
            # keep only years where the fake date is far from the real one
            ok = [y for y in DIWALI if abs((fake[y] - real[y]).days) >= 10]
        else:
            ok = list(DIWALI)
        dd = d[d.year.isin(ok)].copy()
        dd["k_p0"] = ((dd.nd - dd.year.map(fake)).dt.days == 0).astype(int)
        mm = smf.ols(f"lpm ~ k_p0 + {CTRL} + {WX}", dd).fit()
        pl.append(100 * (np.exp(mm.params["k_p0"]) - 1))
    pl = np.array(pl)
    print(f"{c}: real {true_eff:+.0f}% | placebo median {np.median(pl):+.0f}%, range {pl.min():+.0f}..{pl.max():+.0f}% "
          f"({len(pl)} fake dates)")
