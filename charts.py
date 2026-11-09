"""Charts for the Diwali AQI analysis. Style matches respiratory_waves/charts.py."""
import warnings

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from config import CHARTS, DATA, DIWALI

warnings.filterwarnings("ignore")
INK, INK2, MUTED, GRID, BG = "#0b0b0b", "#52514e", "#8a8984", "#e6e5e1", "#fcfcfb"
BLUE, ORANGE = "#2a78d6", "#eb6834"
COL = {"Bengaluru": BLUE, "Delhi": ORANGE}
LIGHT = {"Bengaluru": "#a9c7ee", "Delhi": "#f5b49a"}
plt.rcParams.update({"font.family": "Helvetica Neue", "font.size": 12, "axes.edgecolor": GRID,
                     "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
                     "figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG})
SRC = "Source: CPCB continuous monitors via Vonter/india-cpcb-aqi (city median of stations), 2016–2025 Diwalis."


def style(ax, grid="y"):
    for s in ["top", "right", "left"]:
        ax.spines[s].set_visible(False)
    ax.grid(axis=grid, color=GRID, lw=1)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)


c = pd.read_parquet(DATA / "city_hourly.parquet")
c["D"] = c.hour.dt.year.map(lambda y: pd.Timestamp(DIWALI[y]))
c["t"] = (c.hour - c.D) / pd.Timedelta(hours=1)  # hours since 00:00 on Diwali day
c["hh"] = c.hour.dt.hour
c["k"] = ((c.hour - pd.Timedelta(hours=12)).dt.normalize() - c.D).dt.days

# ---------- 1. hero: hourly PM2.5 through Diwali, median across 10 years ----------
base = c[c.k.abs().between(8, 21)].groupby(["city", "hh"]).pm25.median().rename("base")
w = c[c.t.between(-48, 96)]
med = w.groupby(["city", "t"]).pm25.median().reset_index()
med["hh"] = (med.t % 24).astype(int)
med = med.merge(base, on=["city", "hh"])

fig, axes = plt.subplots(1, 2, figsize=(13, 5.6), sharey=False)
for ax, city in zip(axes, ["Bengaluru", "Delhi"]):
    m = med[med.city == city].sort_values("t")
    ax.fill_between(m.t, 0, m.base, color=GRID, lw=0, step="mid", label="Normal for that hour")
    for y in DIWALI:
        yy = w[(w.city == city) & (w.hour.dt.year == y)].sort_values("t")
        ax.plot(yy.t, yy.pm25, color=LIGHT[city], lw=0.8, alpha=0.7, zorder=1)
    ax.plot(m.t, m.pm25, color=COL[city], lw=2.2, zorder=3, solid_capstyle="round")
    pk = m.loc[m[m.t.between(12, 36)].pm25.idxmax()]
    ratio = pk.pm25 / pk.base
    ax.plot(pk.t, pk.pm25, "o", color=COL[city], ms=8, mec=BG, mew=2, zorder=4)
    ax.annotate(f"{pk.pm25:.0f} µg/m³ at {int(pk.t % 24):02d}:00\n{ratio:.1f}× normal for that hour",
                (pk.t, pk.pm25), xytext=(-14, 4) if city == "Bengaluru" else (14, 4), textcoords="offset points",
                fontsize=10.5, color=INK, va="bottom", ha="right" if city == "Bengaluru" else "left")
    ax.axvspan(20, 27, color=COL[city], alpha=0.06, lw=0)
    ax.set_xticks(range(-36, 97, 24))
    ax.set_xticklabels(["Day −2", "Day −1", "Diwali\nday", "Day +1", "Day +2", "Day +3"], fontsize=10)
    for x in range(-24, 97, 24):
        ax.axvline(x, color=GRID, lw=0.8, zorder=0)
    if city == "Bengaluru":
        b2 = m.loc[m[m.t.between(36, 52)].pm25.idxmax()]
        ax.annotate("Next night too:\nBali Padyami", (b2.t, b2.pm25), xytext=(12, 85), textcoords="offset points",
                    fontsize=10.5, color=INK, va="bottom",
                    arrowprops=dict(arrowstyle="-", color=MUTED, lw=1, shrinkA=2, shrinkB=6))
    ax.set_xlim(-48, 96)
    ax.set_ylim(0, None)
    ax.set_title(city, loc="left", fontsize=14, fontweight="bold", color=COL[city])
    style(ax)
axes[0].set_ylabel("PM2.5, µg/m³ (hourly)")
axes[0].text(-46, axes[0].get_ylim()[1] * 0.93, "Thin lines: each year 2016–25\nThick: median year\nGrey: normal for that hour",
             fontsize=9.5, color=INK2, va="top")
fig.text(0.04, 0.95, "Diwali night pushes PM2.5 to 3–4× normal in both cities. Delhi's spike starts from a far higher floor.",
         fontsize=16, fontweight="bold", color=INK)
fig.text(0.04, 0.905, "Hourly PM2.5 around Diwali night. Shaded column: 20:00–03:00, the firework hours. Note the different y-axes.",
         fontsize=11, color=INK2)
fig.text(0.04, 0.02, SRC + " Normal = median for that clock hour, 8–21 days either side.", fontsize=9, color=MUTED)
fig.subplots_adjust(left=0.07, right=0.98, top=0.83, bottom=0.15, wspace=0.15)
fig.savefig(CHARTS / "chart_hero.png", dpi=180)

# ---------- 2. pre/post: raw ratio vs model-adjusted effect ----------
nd = pd.read_parquet(DATA / "nightday.parquet")
b = nd[nd.k.abs().between(8, 21)].groupby(["city", "year"]).pm25.median().rename("b")
ev = nd[nd.k.between(-3, 7)].merge(b, on=["city", "year"])
raw = (ev.assign(r=ev.pm25 / ev.b).groupby(["city", "k"]).r.median() - 1) * 100
eff = pd.read_csv(DATA / "effects.csv")
eff = eff[eff.model == "M2 +weather+fires"]

fig, axes = plt.subplots(1, 2, figsize=(13, 5.4), sharey=True)
for ax, city in zip(axes, ["Bengaluru", "Delhi"]):
    r = raw.loc[city]
    e = eff[eff.city == city].sort_values("k")
    ax.plot(r.index, r.values, color=MUTED, lw=2, ls=(0, (3, 2)), marker="o", ms=6, mec=BG, mew=1.5, zorder=2)
    ax.fill_between(e.k, e.lo, e.hi, color=COL[city], alpha=0.13, lw=0)
    ax.plot(e.k, e.pct, color=COL[city], lw=2.2, marker="o", ms=8, mec=BG, mew=2, zorder=3)
    ax.axhline(0, color=MUTED, lw=1)
    ax.axvline(0, color=GRID, lw=1)
    lo_first = r.loc[7] < e.pct.iloc[-1]
    ax.text(7.2, r.loc[7] + (-9 if lo_first else 9), "Raw", color=INK2, fontsize=10, va="center")
    ax.text(7.2, e.pct.iloc[-1] + (9 if lo_first else -9), "Adjusted", color=INK, fontsize=10, va="center",
            fontweight="bold")
    ax.set_xticks(range(-3, 8))
    ax.set_xticklabels([f"{k:+d}" if k else "Diwali" for k in range(-3, 8)], fontsize=10)
    ax.set_xlim(-3.3, 8.6)
    ax.set_title(city, loc="left", fontsize=14, fontweight="bold", color=COL[city])
    style(ax)
axes[0].set_ylabel("PM2.5 above normal, % (noon-to-noon)")
axes[0].yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:+.0f}%"))
fig.text(0.04, 0.95, "Delhi's post-Diwali haze is mostly season and stubble smoke. The Diwali-night spike itself is real in both.",
         fontsize=15, fontweight="bold", color=INK)
fig.text(0.04, 0.9, "Dashed: raw ratio to a ±8–21-day baseline, median year. Solid: regression estimate with 95% CI "
         "(year effects, seasonal curve, weekday,\nboundary-layer height, wind, rain, humidity, MODIS fire counts upwind).",
         fontsize=10.5, color=INK2, va="top")
fig.text(0.04, 0.02, SRC + " Days run noon to noon so a firework night isn't split.", fontsize=9, color=MUTED)
fig.subplots_adjust(left=0.08, right=0.98, top=0.74, bottom=0.12, wspace=0.12)
fig.savefig(CHARTS / "chart_prepost.png", dpi=180)

# ---------- 3. confounders: Bengaluru rain, Delhi stubble timing ----------
fires = pd.read_parquet(DATA / "fires_daily.parquet")
fig, axes = plt.subplots(1, 2, figsize=(13, 5.4), gridspec_kw={"width_ratios": [1, 1.25]})

ax = axes[0]
bn = nd[nd.city == "Bengaluru"]
bb = bn[bn.k.abs().between(8, 21)].groupby("year").pm25.median()
yr = pd.DataFrame({"ratio": bn[bn.k == 0].set_index("year").pm25 / bb,
                   "rain": bn[bn.k.between(-1, 1)].groupby("year").precip.sum()})
ax.plot(yr.rain, yr.ratio, "o", color=BLUE, ms=10, mec=BG, mew=2, zorder=3)
for y, r in yr.iterrows():
    ax.annotate(str(y), (r.rain, r.ratio), xytext=(7, 0), textcoords="offset points", fontsize=10, color=INK2, va="center")
ax.axhline(1, color=MUTED, lw=1)
ax.set_xlabel("Rain over the three Diwali days, mm (ERA5)")
ax.set_ylabel("Diwali-night PM2.5 ÷ normal")
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0f}×" if v == int(v) else f"{v:.1f}×"))
ax.set_title("Bengaluru: rainy Diwalis barely register", loc="left", fontsize=13, fontweight="bold", color=BLUE)
style(ax, grid="both")

ax = axes[1]
ph = fires[fires.region == "punjab_haryana"].copy()
ph["y"] = ph.date.dt.year
ph["md"] = pd.to_datetime("2000-" + ph.date.dt.strftime("%m-%d"))
ph = ph[ph.md.between("2000-10-01", "2000-11-30")]
clim = ph.groupby("md").fires.median().rolling(5, center=True, min_periods=1).mean()
ax.fill_between(clim.index, 0, clim.values, color=ORANGE, alpha=0.18, lw=0)
ax.plot(clim.index, clim.values, color=ORANGE, lw=2.2)
for y, d in DIWALI.items():
    x = pd.Timestamp(2000, d.month, d.day)
    ax.plot([x, x], [0, -12], color=INK2, lw=1.5, solid_capstyle="butt")
ax.text(pd.Timestamp("2000-10-19"), -22, "Diwali dates 2016–25", fontsize=9.5, color=INK2, va="top")
ax.set_ylim(-34, None)
ax.xaxis.set_major_locator(mdates.DayLocator(bymonthday=[1, 15]))
ax.xaxis.set_major_formatter(mdates.DateFormatter("%-d %b"))
ax.set_ylabel("Daily MODIS fire detections")
ax.set_title("Delhi: every Diwali lands on Punjab–Haryana's stubble peak", loc="left", fontsize=13, fontweight="bold",
             color=ORANGE)
style(ax)
fig.text(0.04, 0.95, "Each city has its own confounder: rain in Bengaluru, stubble smoke in Delhi",
         fontsize=16, fontweight="bold", color=INK)
fig.text(0.04, 0.02, "Rain: ERA5 via Open-Meteo, Diwali day ±1. Fires: NASA FIRMS MODIS, Punjab + Haryana box, median year "
         "2016–25, 5-day smoothed. Within 250 km of Bengaluru there are only ~1–4 fires a day.", fontsize=9, color=MUTED)
fig.subplots_adjust(left=0.07, right=0.98, top=0.86, bottom=0.15, wspace=0.22)
fig.savefig(CHARTS / "chart_confounders.png", dpi=180)
print("charts written")
