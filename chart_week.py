"""The headline chart: Diwali week across India's 10 biggest cities (16:9, for social).

Left: hourly PM2.5 ÷ normal, Day -3 to Day +4, median of the ten cities (bold) over each city (faint).
Right: each city's festival-nights effect, adjusted for season, weather and crop fires.
Palette and type follow dogl.uk (snow / night ink / Himalayan blue / sunset; Young Serif + Instrument Sans).
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager as fm
from matplotlib.patches import FancyBboxPatch

from config import CHARTS, DATA, ROOT

FONTS = ROOT / "fonts"
SERIF = fm.FontProperties(fname=FONTS / "youngserif.ttf")
SANS = fm.FontProperties(fname=FONTS / "instrumentsans-regular.ttf")
SANS_B = fm.FontProperties(fname=FONTS / "instrumentsans-semibold.ttf")
for f in FONTS.glob("*.ttf"):
    fm.fontManager.addfont(str(f))
plt.rcParams.update({"font.family": "Instrument Sans", "font.size": 14})

BG, INK, MUTED, LINE = "#F6F9FC", "#12233B", "#5A6B83", "#DCE5F0"
BLUE, BLUE_SOFT, CITY = "#2F5E9E", "#E6EEF8", "#C2D3EA"
SUNSET, SUNSET_DEEP, GOLD = "#F08A4B", "#D9622B", "#E9B45E"

TEN = ["Delhi", "Mumbai", "Kolkata", "Bengaluru", "Chennai", "Hyderabad", "Ahmedabad", "Pune", "Surat", "Jaipur"]
hc = pd.read_csv(DATA / "tempo_hourly.csv", index_col="t")
hc = hc.loc[-72:119]
S = pd.read_csv(DATA / "summary.csv").set_index("city").loc[TEN].sort_values("adj_fw_pct")

fig = plt.figure(figsize=(16, 9), facecolor=BG)
ax = fig.add_axes([0.055, 0.15, 0.6, 0.62], facecolor=BG)
bx = fig.add_axes([0.745, 0.15, 0.225, 0.62], facecolor=BG)
YMAX = 6.2

# festival nights (18:00-06:00): day before, Diwali, day after
for d, lab in [(-1, "Day before"), (0, "Diwali night"), (1, "Night after")]:
    x0, x1 = 24 * d + 18, 24 * d + 30
    ax.axvspan(x0, x1, color=GOLD, alpha=0.30 if d == 0 else 0.14, lw=0, zorder=0)
    ax.text((x0 + x1) / 2, YMAX - 0.12, lab, ha="center", va="top", fontproperties=SANS_B if d == 0 else SANS,
            fontsize=12.5, color="#8A5B12")
for x in range(-72, 121, 24):
    ax.axvline(x, color=LINE, lw=1, zorder=0)

# each city, faint; clip the two that go off the chart and say so
for c in TEN:
    s = hc[c].rolling(3, center=True, min_periods=1).mean()
    ax.plot(s.index, s.clip(upper=YMAX + 1), color=CITY, lw=1.3, zorder=1, solid_capstyle="round")
    if s.max() > YMAX:
        tpk = s.idxmax()
        ax.annotate(f"{c} {s.max():.0f}×", (tpk, YMAX - 0.55), xytext=(9 if c == "Chennai" else -9, 0),
                    textcoords="offset points", ha="left" if c == "Chennai" else "right", va="center",
                    fontsize=11.5, color=MUTED, fontproperties=SANS)

# the ten-city median
m = hc["all_smooth"]
ax.fill_between(m.index, 1, m.values, where=m.values > 1, color=SUNSET, alpha=0.22, lw=0, zorder=2)
ax.plot(m.index, m.values, color=SUNSET_DEEP, lw=4.2, zorder=4, solid_capstyle="round", solid_joinstyle="round")
ax.axhline(1, color=MUTED, lw=1.2, zorder=3)
ax.text(-71, 0.9, "normal", fontsize=12, color=MUTED, va="top", fontproperties=SANS)

pk_t, pk = m.idxmax(), m.max()
ax.plot(pk_t, pk, "o", ms=13, color=SUNSET_DEEP, mec=BG, mew=3, zorder=5)
ax.annotate(f"{pk:.0f}×", (pk_t, pk), xytext=(-22, 8), textcoords="offset points", ha="right", va="center",
            fontproperties=SERIF, fontsize=44, color=SUNSET_DEEP, zorder=6)
ax.annotate("normal, at\nmidnight", (pk_t, pk), xytext=(-24, -38), textcoords="offset points", ha="right",
            va="center", fontsize=13, color=INK, fontproperties=SANS, linespacing=1.15)


def callout(t, text, dx, dy, ha="center"):
    y = m.loc[t]
    ax.plot(t, y, "o", ms=8, color=SUNSET_DEEP, mec=BG, mew=2, zorder=5)
    ax.annotate(text, (t, y), xytext=(dx, dy), textcoords="offset points", ha=ha, va="bottom", fontsize=13,
                color=INK, fontproperties=SANS, linespacing=1.15,
                arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.9, shrinkA=3, shrinkB=5))


t_before = m.loc[-24:0].idxmax()
callout(t_before, f"Builds the evening\nbefore: {m.loc[t_before]:.1f}×", -10, 58, ha="right")
t_echo = m.loc[36:60].idxmax()
callout(t_echo, f"A second night:\n{m.loc[t_echo]:.1f}×", 16, 58, ha="left")
clear = m.loc[pk_t:]
t_clear = clear[clear <= 1.25].index.min()
y_clear = m.loc[t_clear]
ax.plot(t_clear, y_clear, "o", ms=8, color=SUNSET_DEEP, mec=BG, mew=2, zorder=5)
ax.annotate("Mostly clear\nby morning", (t_clear, y_clear), xytext=(14, -26), textcoords="offset points",
            ha="left", va="top", fontsize=13, color=INK, fontproperties=SANS, linespacing=1.15,
            arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.9, shrinkA=3, shrinkB=5))
daily = pd.read_csv(DATA / "tempo_daily.csv", index_col="day")["all"]
ax.text(101, 1.75, f"Days +3 and +4:\n{daily.loc[3]:.1f}× on average,\nabout normal", ha="center", va="bottom",
        fontsize=13, color=INK, fontproperties=SANS, linespacing=1.15)

ax.set_xlim(-72, 120)
ax.set_ylim(0, YMAX)
ax.set_xticks(range(-60, 120, 24))
ax.set_xticklabels(["Day −3", "Day −2", "Day −1", "Diwali", "Day +1", "Day +2", "Day +3", "Day +4"])
for t in ax.get_xticklabels():
    t.set_fontproperties(SANS_B if t.get_text() == "Diwali" else SANS)
    t.set_fontsize(14)
    t.set_color(INK if t.get_text() == "Diwali" else MUTED)
ax.set_yticks([1, 2, 3, 4, 5, 6])
ax.set_yticklabels(["1×", "2×", "3×", "4×", "5×", "6×"], fontsize=13, color=MUTED)
ax.grid(axis="y", color=LINE, lw=1)
ax.set_axisbelow(True)
for s in ax.spines.values():
    s.set_visible(False)
ax.tick_params(length=0, pad=8)
ax.set_title("Hourly PM2.5 ÷ the same hour on a normal day", loc="left", fontsize=14, color=MUTED,
             fontproperties=SANS, pad=12)

# right: city ranking, adjusted
y = np.arange(len(S))
bx.barh(y, S.adj_fw_pct, color=BLUE, height=0.62, zorder=2)
for i, (c, r) in enumerate(S.iterrows()):
    bx.text(r.adj_fw_pct + 3, i, f"+{r.adj_fw_pct:.0f}%", va="center", fontsize=13, color=INK, fontproperties=SANS_B)
    bx.text(-4, i, c + ("*" if c == "Surat" else ""), va="center", ha="right", fontsize=14, color=INK,
            fontproperties=SANS)
bx.set_xlim(0, S.adj_fw_pct.max() * 1.28)
bx.set_ylim(-0.6, len(S) - 0.4)
bx.axis("off")
bx.set_title("Festival nights vs a normal night,\nafter removing season, weather\nand crop-fire smoke",
             loc="left", fontsize=14, color=MUTED, fontproperties=SANS, pad=12, x=-0.36, linespacing=1.2)

fig.text(0.055, 0.915, "Diwali night: city air 4× dirtier, mostly gone by morning",
         fontproperties=SERIF, fontsize=32, color=INK, va="baseline")
fig.text(0.055, 0.868, "PM2.5 through Diwali week in India's 10 biggest cities, 2016–2025. "
         "Orange: the typical city. Faint lines: each city.",
         fontproperties=SANS, fontsize=16, color=MUTED, va="baseline")
fig.text(0.055, 0.045, "Data: CPCB monitors (via Vonter/india-cpcb-aqi), ERA5, NASA FIRMS.  "
         "*Surat: one monitor, three Diwalis.  Method and code: github.com/dogluk/diwali-aqi",
         fontproperties=SANS, fontsize=12, color=MUTED)
fig.text(0.97, 0.045, "dogl.uk", fontproperties=SERIF, fontsize=16, color=BLUE, ha="right")
fig.savefig(CHARTS / "diwali_week.png", dpi=170, facecolor=BG)
print("written", CHARTS / "diwali_week.png")
