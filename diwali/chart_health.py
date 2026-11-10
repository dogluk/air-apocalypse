"""What Google sees on Diwali: searches on Diwali day + the day after vs a normal day (India, daily,
2016-2025), adjusted for year, season and weekday. 95% CIs clustered by year, t(9)."""
import json
import warnings

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from matplotlib import font_manager as fm
from scipy import stats

from config import CHARTS, DATA, DIWALI, FONTS

warnings.filterwarnings("ignore")
SERIF = fm.FontProperties(fname=FONTS / "youngserif.ttf")
SANS = fm.FontProperties(fname=FONTS / "instrumentsans-regular.ttf")
SANS_B = fm.FontProperties(fname=FONTS / "instrumentsans-semibold.ttf")
BG, INK, MUTED, GRID = "#F6F9FC", "#12233B", "#5A6B83", "#DCE5F0"
BLUE, ORANGE = "#2F5E9E", "#D9622B"

LABEL = {"aqi": "Air quality index", "air_pollution": "Air pollution", "burn": "Burns",
         "toothache": "Toothache", "cough": "Cough", "sore_throat": "Sore throat", "back_pain": "Back pain",
         "chest_pain": "Chest pain", "asthma": "Asthma", "headache": "Headache", "heart_attack": "Heart attack",
         "inhaler": "Inhaler", "breathless": "Shortness of breath"}
GROUP = {"aqi": "What people notice", "air_pollution": "What people notice", "burn": "What people notice",
         "cough": "Symptoms", "sore_throat": "Symptoms",
         "asthma": "Symptoms", "breathless": "Symptoms",
         "inhaler": "Symptoms", "headache": "Symptoms",
         "heart_attack": "Heart", "chest_pain": "Heart",
         "toothache": "Unrelated (controls)", "back_pain": "Unrelated (controls)"}
ORDER = ["What people notice", "Symptoms", "Heart", "Unrelated (controls)"]

rows = []
for f in (DATA / "trends").glob("*__IN__*.json"):
    j = json.loads(f.read_text())
    rows.append(pd.DataFrame({"topic": j["topic"], "date": pd.to_datetime(j["dates"]), "v": j["values"]}))
T = pd.concat(rows)
T["v"] = pd.to_numeric(T.v, errors="coerce")
T = T[T.topic.isin(LABEL)].dropna(subset=["v"])
T["year"] = T.date.dt.year
T["k"] = (T.date - T.year.map(lambda y: pd.Timestamp(DIWALI[y]))).dt.days
T["doy"], T["dow"], T["y"] = T.date.dt.dayofyear, T.date.dt.dayofweek, np.log(T.v + 1)
T["fw"] = T.k.between(0, 1).astype(int)
T["pre"] = (T.k == -1).astype(int)
T["post"] = T.k.between(2, 4).astype(int)

res = []
for t, g in T.groupby("topic"):
    g = g.reset_index(drop=True)
    m = smf.ols("y ~ pre + fw + post + C(year) + bs(doy, df=4) + C(dow)", g).fit(
        cov_type="cluster", cov_kwds={"groups": g.year.values})
    tc = stats.t.ppf(0.975, g.year.nunique() - 1)
    b, se = m.params.fw, m.bse.fw
    res.append(dict(topic=t, pct=100 * (np.exp(b) - 1), lo=100 * (np.exp(b - tc * se) - 1),
                    hi=100 * (np.exp(b + tc * se) - 1)))
R = pd.DataFrame(res)
R["group"] = R.topic.map(GROUP)
R.to_csv(DATA / "health_chart.csv", index=False)

# layout: groups top to bottom, sorted within group
ys, labels, y = [], [], 0
R["grank"] = R.group.map({g: i for i, g in enumerate(ORDER)})
R = R.sort_values(["grank", "pct"], ascending=[False, True]).reset_index(drop=True)
pos = {}
for gi, g in enumerate(ORDER[::-1]):
    sub = R[R.group == g]
    for _, r in sub.iterrows():
        pos[r.topic] = y
        y += 1
    pos[f"__{g}"] = y + 0.15
    y += 1.4

fig = plt.figure(figsize=(16, 9), facecolor=BG)
ax = fig.add_axes([0.22, 0.17, 0.72, 0.64], facecolor=BG)
ax.set_xscale("symlog", linthresh=100)
for _, r in R.iterrows():
    yy = pos[r.topic]
    col = ORANGE if r.group == "What people notice" else (BLUE if r.group != "Unrelated (controls)" else MUTED)
    ax.plot([r.lo, r.hi], [yy, yy], color=col, lw=3, alpha=0.3, solid_capstyle="round")
    ax.plot(r.pct, yy, "o", ms=12, color=col, mec=BG, mew=2.5, zorder=3)
    ax.text(-66, yy, LABEL[r.topic], ha="right", va="center", fontsize=15, color=INK, fontproperties=SANS)
    if r.pct > 0:
        ax.text(r.hi * 1.15 + 4, yy, f"{r.pct:+.0f}%", va="center", ha="left", fontsize=13.5, color=INK,
                fontproperties=SANS_B)
    else:
        ax.text(r.lo - 1.5, yy, f"{r.pct:+.0f}%".replace("-", "−"), va="center", ha="right", fontsize=13.5,
                color=INK, fontproperties=SANS_B)
for g in ORDER:
    ax.text(-66, pos[f"__{g}"], g.upper(), ha="right", va="center", fontsize=11.5, color=MUTED,
            fontproperties=SANS_B)
ax.axvline(0, color=MUTED, lw=1.2)
ax.set_xlim(-50, 600)
ax.set_xticks([-40, -20, 0, 25, 50, 100, 200, 400])
ax.set_xticklabels(["−40%", "−20%", "0", "+25%", "+50%", "+100%", "+200%", "+400%"], fontsize=13, color=MUTED)
ax.set_yticks([])
ax.set_ylim(-0.8, y - 1.0)
ax.grid(axis="x", color=GRID, lw=1)
ax.set_axisbelow(True)
for s in ax.spines.values():
    s.set_visible(False)
ax.tick_params(length=0, pad=8)
ax.set_xlabel("Google searches on Diwali day and the day after, vs a normal day", fontsize=14, color=MUTED,
              fontproperties=SANS, labelpad=12)

fig.text(0.055, 0.915, "Google sees Diwali's fireworks and smog, not its coughs",
         fontproperties=SERIF, fontsize=34, color=INK, va="baseline")
fig.text(0.055, 0.868, "India, daily search interest 2016–2025, adjusted for year, season and weekday. "
         "Lines: 95% intervals.", fontproperties=SANS, fontsize=16, color=MUTED, va="baseline")
fig.text(0.055, 0.035, "Data: Google Trends topics (all languages), India. Method and code: github.com/dogluk/diwali-aqi",
         fontproperties=SANS, fontsize=12, color=MUTED)
fig.text(0.97, 0.035, "dogl.uk", fontproperties=SERIF, fontsize=16, color=BLUE, ha="right")
fig.savefig(CHARTS / "diwali_searches.png", dpi=170, facecolor=BG)
print(R[["topic", "pct", "lo", "hi"]].round(1).to_string(index=False))
