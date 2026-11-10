"""Do Diwali's air-pollution spikes show up in what people search for?

Google Trends is a share of all searches, and Diwali is a holiday that changes what people search
for, so every topic is measured against two negative controls (toothache, back pain): the outcome
is log(topic) - mean(log(controls)). A positive control (burns) checks the method can see a
Diwali effect at all; AQI / air-pollution searches measure attention rather than symptoms.

Part 1, national daily (India, Sep 15 - Dec 20, 2016-2025):
  outcome ~ day-from-Diwali dummies (-3..+7) + year + seasonal spline + weekday
            + Dussehra/Gurpurab + Punjab-Haryana fires (3-day)
  SEs clustered by year, t(G-1).
Part 2, state weekly (9 states, 2016-2025): Diwali week + following week, same controls, then
  dose-response against each state's metro Diwali PM2.5 effect from analyze.py.

Outputs: data/health_daily_effects.csv, data/health_state_effects.csv
"""
import json
import warnings

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats

from config import DATA, DIWALI, DUSSEHRA, GURPURAB

warnings.filterwarnings("ignore")
NEG = ["toothache", "back_pain"]
GROUPS = {
    "Air-related symptoms": ["cough", "sore_throat", "asthma", "breathless", "eye_irritation", "inhaler", "headache"],
    "Cardiac": ["heart_attack", "chest_pain"],
    "Positive control": ["burn"],
    "Attention": ["aqi", "air_pollution"],
}
D_OF = {y: pd.Timestamp(v) for y, v in DIWALI.items()}
STATE_CITY = {"IN-DL": "Delhi", "IN-MH": "Mumbai", "IN-KA": "Bengaluru", "IN-TN": "Chennai", "IN-TG": "Hyderabad",
              "IN-WB": "Kolkata", "IN-GJ": "Ahmedabad", "IN-RJ": "Jaipur", "IN-UP": "Lucknow"}

rows = []
for f in (DATA / "trends").glob("*.json"):
    j = json.loads(f.read_text())
    rows.append(pd.DataFrame({"topic": j["topic"], "geo": j["geo"], "window": j["window"],
                              "date": pd.to_datetime(j["dates"]), "v": j["values"]}))
T = pd.concat(rows)
T["v"] = pd.to_numeric(T.v, errors="coerce")
fires = pd.read_parquet(DATA / "fires_daily.parquet").pivot(index="date", columns="region", values="fires")
ph3 = np.log1p(fires["punjab_haryana"].rolling(3, min_periods=1).sum())


def tcrit(g):
    return stats.t.ppf(0.975, max(g - 1, 1))


# ---------------- Part 1: national daily ----------------
nat = T[(T.geo == "IN") & ~T.window.str.startswith("2016-01-01") & ~T.window.str.startswith("2021-01-01")].copy()
nat["lv"] = np.log(nat.v + 1)
wide = nat.pivot_table(index="date", columns="topic", values="lv")
neg = wide[NEG].mean(axis=1)
d = wide.sub(neg, axis=0)  # each topic relative to the negative controls
d = d.reset_index().melt(id_vars="date", var_name="topic", value_name="y").dropna()
d["year"] = d.date.dt.year
d["k"] = (d.date - d.year.map(D_OF)).dt.days
d["doy"] = d.date.dt.dayofyear
d["dow"] = d.date.dt.dayofweek
d["dus"] = (d.date == d.year.map(lambda y: pd.Timestamp(DUSSEHRA[y]))).astype(int)
d["gur"] = (d.date == d.year.map(lambda y: pd.Timestamp(GURPURAB[y]))).astype(int)
d["fire"] = ph3.reindex(d.date).values
KS = list(range(-3, 8))
for k in KS:
    d[f"k_{'m' if k < 0 else 'p'}{abs(k)}"] = (d.k == k).astype(int)
d["post13"] = d.k.between(1, 3).astype(int)
KD = [f"k_{'m' if k < 0 else 'p'}{abs(k)}" for k in KS]
CTRL = "C(year) + bs(doy, df=4) + C(dow) + dus + gur + fire"

out = []
also_raw = nat.pivot_table(index="date", columns="topic", values="lv").reset_index().melt(
    id_vars="date", var_name="topic", value_name="y_raw").dropna()
for topic, g in d.groupby("topic"):
    if topic in NEG:
        continue
    G = g.year.nunique()
    m = smf.ols(f"y ~ {' + '.join(KD)} + {CTRL}", g).fit(cov_type="cluster", cov_kwds={"groups": g.year})
    m2 = smf.ols(f"y ~ post13 + k_m1 + k_p0 + {CTRL}", g).fit(cov_type="cluster", cov_kwds={"groups": g.year})
    t = tcrit(G)
    rec = dict(topic=topic, years=G)
    for k, kn in zip(KS, KD):
        b, se = m.params[kn], m.bse[kn]
        rec[f"k{k:+d}"] = 100 * (np.exp(b) - 1)
        rec[f"k{k:+d}_p"] = 2 * (1 - stats.t.cdf(abs(b / se), G - 1))
    b, se = m2.params["post13"], m2.bse["post13"]
    rec.update(post13=100 * (np.exp(b) - 1), post13_lo=100 * (np.exp(b - t * se) - 1),
               post13_hi=100 * (np.exp(b + t * se) - 1), post13_p=2 * (1 - stats.t.cdf(abs(b / se), G - 1)))
    out.append(rec)
E = pd.DataFrame(out)
E["group"] = E.topic.map({t: g for g, ts in GROUPS.items() for t in ts})
E = E.sort_values(["group", "post13"], ascending=[True, False])
E.to_csv(DATA / "health_daily_effects.csv", index=False)

pd.set_option("display.width", 220)
print("National daily searches vs negative controls, % change by day from Diwali (adjusted):")
cols = ["group", "topic", "years"] + [f"k{k:+d}" for k in range(-1, 5)] + ["post13", "post13_lo", "post13_hi", "post13_p"]
print(E[cols].round(2).to_string(index=False))

# raw negative-control behaviour (is the holiday itself moving everything?)
rawc = also_raw[also_raw.topic.isin(NEG)].copy()
rawc["year"] = rawc.date.dt.year
rawc["k"] = (rawc.date - rawc.year.map(D_OF)).dt.days
bb = rawc[rawc.k.abs().between(8, 21)].groupby(["topic", "year"]).y_raw.median().rename("b")
rawc = rawc.merge(bb, on=["topic", "year"])
print("\nNegative controls, raw ratio to baseline (median year):")
print((np.exp(rawc.y_raw - rawc.b)).groupby([rawc.topic, rawc.k]).median().unstack(0).loc[-2:4].round(2))

# ---------------- Part 2: state weekly + dose-response ----------------
st = T[T.geo != "IN"].copy()
if len(st):
    st["lv"] = np.log(st.v + 1)
    # Trends weeks start Sunday; normalise within each request window (separate 0-100 scaling)
    wide = st.pivot_table(index=["geo", "window", "date"], columns="topic", values="lv")
    have_neg = [c for c in NEG if c in wide]
    sw = wide.sub(wide[have_neg].mean(axis=1), axis=0).reset_index().melt(
        id_vars=["geo", "window", "date"], var_name="topic", value_name="y").dropna()
    sw = sw[sw.date.dt.month.isin([9, 10, 11, 12])]
    sw["year"] = sw.date.dt.year
    dd = sw.year.map(D_OF)
    sw["wk"] = ((dd - sw.date).dt.days.between(0, 6)).astype(int)        # week containing Diwali
    sw["wk_next"] = ((dd - sw.date).dt.days.between(-7, -1)).astype(int)  # the week after
    sw["woy"] = sw.date.dt.isocalendar().week.astype(int)
    rs = []
    for (geo, topic), g in sw.groupby(["geo", "topic"]):
        if topic in NEG or g.wk.sum() < 4:
            continue
        m = smf.ols("y ~ wk + wk_next + C(year) + bs(woy, df=3)", g).fit(cov_type="cluster",
                                                                       cov_kwds={"groups": g.year})
        both = (m.params["wk"] + m.params["wk_next"]) / 2
        rs.append(dict(geo=geo, topic=topic, wk=100 * (np.exp(m.params["wk"]) - 1),
                       wk_next=100 * (np.exp(m.params["wk_next"]) - 1), two_wk=100 * (np.exp(both) - 1)))
    R = pd.DataFrame(rs)
    S = pd.read_csv(DATA / "summary.csv").set_index("city")
    R["city"] = R.geo.map(STATE_CITY)
    R["dose_pct"] = R.city.map(S.adj_fw_pct)
    R["dose_ugm3"] = R.city.map(S.excess_ugm3)
    R.to_csv(DATA / "health_state_effects.csv", index=False)
    print("\nState weekly: Diwali week + week after vs controls (%), by topic and state:")
    print(R.pivot(index="topic", columns="city", values="two_wk").round(0).to_string())
    print("\nDose-response across states: Spearman rho of search effect vs metro Diwali PM2.5 excess (µg/m³):")
    for topic, g in R.groupby("topic"):
        if len(g) >= 6:
            rho, p = stats.spearmanr(g.dose_ugm3, g.two_wk)
            print(f"  {topic:<15} rho={rho:+.2f}  p={p:.2f}  n={len(g)}")
