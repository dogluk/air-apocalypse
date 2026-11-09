"""Summary charts for the metro comparison. Style matches charts.py / respiratory_waves."""
import warnings

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from config import CHARTS, CITIES, DATA, DIWALI

warnings.filterwarnings("ignore")
INK, INK2, MUTED, GRID, BG = "#0b0b0b", "#52514e", "#8a8984", "#e6e5e1", "#fcfcfb"
BLUE, ORANGE = "#2a78d6", "#eb6834"
plt.rcParams.update({"font.family": "Helvetica Neue", "font.size": 12, "axes.edgecolor": GRID,
                     "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
                     "figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG})


def style(ax, grid="x"):
    for s in ["top", "right", "left"]:
        ax.spines[s].set_visible(False)
    ax.grid(axis=grid, color=GRID, lw=1)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)


S = pd.read_csv(DATA / "summary.csv").sort_values("adj_fw_pct").reset_index(drop=True)
S["col"] = [ORANGE if CITIES[c]["ph"] else BLUE for c in S.city]
y = np.arange(len(S))

# ---------- summary: one row per city ----------
fig, axes = plt.subplots(1, 3, figsize=(15, 7.6), sharey=True, gridspec_kw={"width_ratios": [1.35, 1.0, 0.75]})

for ax, (raw, adj, lo, hi), title in [
    (axes[0], ("raw_fw_pct", "adj_fw_pct", "adj_fw_lo", "adj_fw_hi"), "Festival nights (day −1 to +1)"),
    (axes[1], ("raw_post_pct", "adj_post_pct", "adj_post_lo", "adj_post_hi"), "The week after (day +2 to +7)"),
]:
    for i, r in S.iterrows():
        ax.plot([r[lo], r[hi]], [i, i], color=r.col, lw=2, alpha=0.35, solid_capstyle="round", zorder=1)
        ax.plot([r[raw], r[adj]], [i, i], color=MUTED, lw=1, ls=(0, (2, 2)), zorder=1)
        ax.plot(r[raw], i, "o", ms=9, mfc=BG, mec=MUTED, mew=1.8, zorder=2)
        ax.plot(r[adj], i, "o", ms=9, color=r.col, mec=BG, mew=2, zorder=3)
    ax.axvline(0, color=MUTED, lw=1)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:+.0f}%"))
    ax.set_title(title, loc="left", fontsize=13, fontweight="bold", color=INK, pad=10)
    style(ax)
axes[0].set_xlim(-40, 175)
axes[1].set_xlim(-45, 110)
axes[0].set_xlabel("Daily PM2.5 vs what the day would otherwise have been")
axes[1].set_xlabel("Same, for the following week")

from matplotlib.lines import Line2D
axes[0].legend(handles=[
    Line2D([], [], ls="", marker="o", ms=9, mfc=BG, mec=MUTED, mew=1.8, label="Naive before/after"),
    Line2D([], [], ls="", marker="o", ms=9, color=BLUE, mec=BG, label="Adjusted"),
    Line2D([], [], ls="", marker="o", ms=9, color=ORANGE, mec=BG, label="Adjusted, stubble-exposed city"),
    Line2D([], [], color=BLUE, lw=2, alpha=0.35, label="95% CI")],
    loc="lower right", frameon=False, fontsize=9.5, handletextpad=0.3, borderaxespad=0.2)

ax = axes[2]
ax.barh(y, S.excess_ugm3, color=S.col, height=0.55)
for i, r in S.iterrows():
    ax.text(r.excess_ugm3 + 1, i, f"+{r.excess_ugm3:.0f}", va="center", fontsize=10.5, color=INK2)
ax.set_xlim(0, S.excess_ugm3.max() * 1.25)
ax.set_title("Extra PM2.5, µg/m³", loc="left", fontsize=13, fontweight="bold", color=INK, pad=10)
ax.set_xlabel("Adjusted, average over the festival nights")
style(ax)

labels = []
for _, r in S.iterrows():
    thin = "  ·  thin data" if r.years <= 3 or r.stations_median <= 1 else ""
    labels.append(f"{r.city}\n{int(r.years)} Diwalis, ~{int(r.stations_median)} stn{thin}")
axes[0].set_yticks(y)
axes[0].set_yticklabels(labels, fontsize=10.5)
for t, c in zip(axes[0].get_yticklabels(), S.col):
    t.set_color(INK)
axes[0].set_ylim(-0.6, len(S) - 0.2)

fig.text(0.015, 0.965, "Diwali raises PM2.5 by 25–100% in every big Indian city",
         fontsize=16.5, fontweight="bold", color=INK)
fig.text(0.015, 0.925,
         "Hollow: naive comparison with 8–21 days either side. Filled: regression with year effects, a seasonal curve, weekday, "
         "Dussehra/Gurpurab nights,\nboundary-layer height, wind, rain, humidity and MODIS fires (local; plus Punjab–Haryana for "
         "orange cities). Bars: 95% CI, clustered by year. Sorted by adjusted effect.",
         fontsize=10.5, color=INK2, va="top")
fig.text(0.015, 0.015, "Source: CPCB continuous monitors via Vonter/india-cpcb-aqi (city median of stations), Diwalis 2016–2025; "
         "ERA5 via Open-Meteo; NASA FIRMS. Orange = downwind of Punjab–Haryana stubble burning.",
         fontsize=9, color=MUTED)
fig.subplots_adjust(left=0.13, right=0.985, top=0.83, bottom=0.11, wspace=0.08)
fig.savefig(CHARTS / "chart_metros_summary.png", dpi=180)

# ---------- small multiples: hourly PM2.5 ÷ normal around Diwali, median year ----------
c = pd.read_parquet(DATA / "city_hourly.parquet")
c["D"] = c.hour.dt.year.map(lambda yy: pd.Timestamp(DIWALI[yy]))
c["t"] = (c.hour - c.D) / pd.Timedelta(hours=1)
c["hh"] = c.hour.dt.hour
c["k"] = ((c.hour - pd.Timedelta(hours=12)).dt.normalize() - c.D).dt.days
base = c[c.k.abs().between(8, 21)].groupby(["city", c.hour.dt.year, "hh"]).pm25.median().rename("b")
w = c[c.t.between(-36, 84)].copy()
w["yr"] = w.hour.dt.year
w = w.merge(base, left_on=["city", "yr", "hh"], right_index=True)
w["r"] = w.pm25 / w.b
med = w.groupby(["city", "t"]).r.median().reset_index()

order = S.sort_values("adj_fw_pct", ascending=False).city.tolist()
fig, axes = plt.subplots(3, 4, figsize=(15, 9), sharex=True, sharey=True)
for ax, city in zip(axes.flat, order):
    m = med[med.city == city].sort_values("t")
    col = ORANGE if CITIES[city]["ph"] else BLUE
    for x in range(-24, 85, 24):
        ax.axvline(x, color=GRID, lw=0.8, zorder=0)
    ax.axhline(1, color=MUTED, lw=1)
    ax.fill_between(m.t, 1, m.r, where=m.r > 1, color=col, alpha=0.15, lw=0)
    ax.plot(m.t, m.r, color=col, lw=1.8)
    pk = m.loc[m.r.idxmax()]
    thin = "  (1 monitor, 3 yrs)" if city == "Surat" else ""
    ax.set_title(f"{city}", loc="left", fontsize=12.5, fontweight="bold", color=INK, pad=4)
    ax.set_title(f"peak {pk.r:.1f}× at {int(pk.t % 24):02d}:00{thin}", loc="right", fontsize=10, color=INK2, pad=4)
    ax.set_yscale("log")
    ax.set_yticks([0.5, 1, 2, 4, 8, 16])
    ax.set_yticklabels(["½×", "1×", "2×", "4×", "8×", "16×"])
    ax.set_ylim(0.4, 16)
    ax.minorticks_off()
    ax.set_xticks(range(-12, 85, 24))
    ax.set_xticklabels(["Day −1", "Diwali", "Day +1", "Day +2", "Day +3"], fontsize=9.5)
    style(ax, grid="y")
for ax in axes.flat[len(order):]:
    ax.axis("off")
axes.flat[-1].text(0.05, 0.6, "Line: median year, hourly PM2.5\n÷ the same clock hour on normal\ndays "
                   "(8–21 days either side).\nLog scale. Vertical lines\nare midnights.", transform=axes.flat[-1].transAxes,
                   fontsize=10.5, color=INK2, va="top")
fig.text(0.015, 0.97, "Every metro gets a firework spike. Chennai's is the biggest and earliest in the evening; many get a second night.",
         fontsize=16, fontweight="bold", color=INK)
fig.text(0.015, 0.015, "Source: CPCB continuous monitors via Vonter/india-cpcb-aqi, Diwalis 2016–2025 (years with data). "
         "Orange = downwind of Punjab–Haryana stubble burning.", fontsize=9, color=MUTED)
fig.subplots_adjust(left=0.05, right=0.99, top=0.91, bottom=0.07, wspace=0.06, hspace=0.25)
fig.savefig(CHARTS / "chart_metros_hourly.png", dpi=180)
print("written")
