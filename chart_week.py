"""The headline chart: Diwali week across India's 10 biggest cities (16:9, for social).

Left: hourly PM2.5 ÷ normal, Day -3 to Day +4, median of the ten cities (bold) over each city (faint).
Right: each city's festival-nights effect, adjusted for season, weather and crop fires.
Palette and type follow dogl.uk (Young Serif + Instrument Sans). Two themes:
  snow  -> charts/diwali_week.png        (light: snow / night ink / Himalayan blue / sunset)
  night -> charts/diwali_week_night.png  (dark: dogl.uk night tokens, glowing sunset line)
Colours validated with the dataviz palette checker for each surface.
"""
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager as fm

from config import CHARTS, DATA, ROOT

FONTS = ROOT / "fonts"
SERIF = fm.FontProperties(fname=FONTS / "youngserif.ttf")
SANS = fm.FontProperties(fname=FONTS / "instrumentsans-regular.ttf")
SANS_B = fm.FontProperties(fname=FONTS / "instrumentsans-semibold.ttf")
for f in FONTS.glob("*.ttf"):
    fm.fontManager.addfont(str(f))
plt.rcParams.update({"font.family": "Instrument Sans", "font.size": 14})

THEMES = {
    "snow": dict(out="diwali_week.png", bg="#F6F9FC", ink="#12233B", muted="#5A6B83", grid="#DCE5F0",
                 city="#C2D3EA", bar="#2F5E9E", line="#D9622B", fill="#F08A4B", fill_a=0.22, big="#D9622B",
                 band="#E9B45E", band_a=(0.14, 0.30), band_ink="#8A5B12", mark="#2F5E9E", glow=False),
    "night": dict(out="diwali_week_night.png", bg="#111F38", ink="#E9F0F9", muted="#A3B5CE", grid="#1F3354",
                  city="#36588A", bar="#5A8ACB", line="#DC6E2E", fill="#F4A06A", fill_a=0.16, big="#F4A06A",
                  band="#F4A06A", band_a=(0.06, 0.12), band_ink="#F0CD8C", mark="#A9C8EE", glow=True),
}

TEN = ["Delhi", "Mumbai", "Kolkata", "Bengaluru", "Chennai", "Hyderabad", "Ahmedabad", "Pune", "Surat", "Jaipur"]
hc = pd.read_csv(DATA / "tempo_hourly.csv", index_col="t").loc[-72:119]
S = pd.read_csv(DATA / "summary.csv").set_index("city").loc[TEN].sort_values("adj_fw_pct")
daily = pd.read_csv(DATA / "tempo_daily.csv", index_col="day")["all"]
m = hc["all_smooth"]
YMAX = 6.2


def render(T):
    fig = plt.figure(figsize=(16, 9), facecolor=T["bg"])
    ax = fig.add_axes([0.055, 0.15, 0.6, 0.62], facecolor=T["bg"])
    bx = fig.add_axes([0.745, 0.15, 0.225, 0.62], facecolor=T["bg"])

    # festival nights (18:00-06:00): day before, Diwali, day after
    for d, lab in [(-1, "Day before"), (0, "Diwali night"), (1, "Night after")]:
        x0, x1 = 24 * d + 18, 24 * d + 30
        ax.axvspan(x0, x1, color=T["band"], alpha=T["band_a"][d == 0], lw=0, zorder=0)
        ax.text((x0 + x1) / 2, YMAX - 0.12, lab, ha="center", va="top", fontproperties=SANS_B if d == 0 else SANS,
                fontsize=12.5, color=T["band_ink"])
    for x in range(-72, 121, 24):
        ax.axvline(x, color=T["grid"], lw=1, zorder=0)

    # each city, faint; clip the two that go off the chart and say so
    for c in TEN:
        s = hc[c].rolling(3, center=True, min_periods=1).mean()
        ax.plot(s.index, s.clip(upper=YMAX + 1), color=T["city"], lw=1.3, zorder=1, solid_capstyle="round")
        if s.max() > YMAX:
            ax.annotate(f"{c} {s.max():.0f}×", (s.idxmax(), YMAX - 0.55), xytext=(9 if c == "Chennai" else -9, 0),
                        textcoords="offset points", ha="left" if c == "Chennai" else "right", va="center",
                        fontsize=11.5, color=T["muted"], fontproperties=SANS)

    # the ten-city median
    ax.fill_between(m.index, 1, m.values, where=m.values > 1, color=T["fill"], alpha=T["fill_a"], lw=0, zorder=2)
    effects = None
    if T["glow"]:
        effects = [pe.Stroke(linewidth=18, foreground=T["fill"], alpha=0.06),
                   pe.Stroke(linewidth=11, foreground=T["fill"], alpha=0.12),
                   pe.Stroke(linewidth=7, foreground=T["fill"], alpha=0.25), pe.Normal()]
    ax.plot(m.index, m.values, color=T["line"], lw=4.2, zorder=4, solid_capstyle="round", solid_joinstyle="round",
            path_effects=effects)
    ax.axhline(1, color=T["muted"], lw=1.2, zorder=3)
    ax.text(-71, 0.9, "normal", fontsize=12, color=T["muted"], va="top", fontproperties=SANS)

    pk_t, pk = m.idxmax(), m.max()
    ax.plot(pk_t, pk, "o", ms=13, color=T["line"], mec=T["bg"], mew=3, zorder=5)
    ax.annotate(f"{pk:.0f}×", (pk_t, pk), xytext=(-22, 8), textcoords="offset points", ha="right", va="center",
                fontproperties=SERIF, fontsize=44, color=T["big"], zorder=6)
    ax.annotate("normal, at\nmidnight", (pk_t, pk), xytext=(-24, -38), textcoords="offset points", ha="right",
                va="center", fontsize=13, color=T["ink"], fontproperties=SANS, linespacing=1.15)

    def callout(t, text, dx, dy, ha="center", va="bottom"):
        y = m.loc[t]
        ax.plot(t, y, "o", ms=8, color=T["line"], mec=T["bg"], mew=2, zorder=5)
        ax.annotate(text, (t, y), xytext=(dx, dy), textcoords="offset points", ha=ha, va=va, fontsize=13,
                    color=T["ink"], fontproperties=SANS, linespacing=1.15,
                    arrowprops=dict(arrowstyle="-", color=T["muted"], lw=0.9, shrinkA=3, shrinkB=5))

    t_before = m.loc[-24:0].idxmax()
    callout(t_before, f"Builds the evening\nbefore: {m.loc[t_before]:.1f}×", -10, 58, ha="right")
    t_echo = m.loc[36:60].idxmax()
    callout(t_echo, f"A second night:\n{m.loc[t_echo]:.1f}×", 16, 58, ha="left")
    after = m.loc[pk_t:]
    callout(after[after <= 1.25].index.min(), "Mostly clear\nby morning", 14, -26, ha="left", va="top")
    ax.text(101, 1.75, f"Days +3 and +4:\n{daily.loc[3]:.1f}× on average,\nabout normal", ha="center",
            va="bottom", fontsize=13, color=T["ink"], fontproperties=SANS, linespacing=1.15)

    ax.set_xlim(-72, 120)
    ax.set_ylim(0, YMAX)
    ax.set_xticks(range(-60, 120, 24))
    ax.set_xticklabels(["Day −3", "Day −2", "Day −1", "Diwali", "Day +1", "Day +2", "Day +3", "Day +4"])
    for t in ax.get_xticklabels():
        t.set_fontproperties(SANS_B if t.get_text() == "Diwali" else SANS)
        t.set_fontsize(14)
        t.set_color(T["ink"] if t.get_text() == "Diwali" else T["muted"])
    ax.set_yticks([1, 2, 3, 4, 5, 6])
    ax.set_yticklabels(["1×", "2×", "3×", "4×", "5×", "6×"], fontsize=13, color=T["muted"])
    ax.grid(axis="y", color=T["grid"], lw=1)
    ax.set_axisbelow(True)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0, pad=8)
    ax.set_title("Hourly PM2.5 ÷ the same hour on a normal day", loc="left", fontsize=14, color=T["muted"],
                 fontproperties=SANS, pad=12)

    # right: city ranking, adjusted
    bx.barh(np.arange(len(S)), S.adj_fw_pct, color=T["bar"], height=0.62, zorder=2)
    for i, (c, r) in enumerate(S.iterrows()):
        bx.text(r.adj_fw_pct + 3, i, f"+{r.adj_fw_pct:.0f}%", va="center", fontsize=13, color=T["ink"],
                fontproperties=SANS_B)
        bx.text(-4, i, c + ("*" if c == "Surat" else ""), va="center", ha="right", fontsize=14, color=T["ink"],
                fontproperties=SANS)
    bx.set_xlim(0, S.adj_fw_pct.max() * 1.28)
    bx.set_ylim(-0.6, len(S) - 0.4)
    bx.axis("off")
    bx.set_title("Festival nights vs a normal night,\nafter removing season, weather\nand crop-fire smoke",
                 loc="left", fontsize=14, color=T["muted"], fontproperties=SANS, pad=12, x=-0.36, linespacing=1.2)

    fig.text(0.055, 0.915, "Diwali night makes India's city air 4× dirtier",
             fontproperties=SERIF, fontsize=34, color=T["ink"], va="baseline")
    fig.text(0.055, 0.868, "PM2.5 through Diwali week in India's 10 biggest cities, 2016–2025. "
             "Orange: the typical city. Faint lines: each city.",
             fontproperties=SANS, fontsize=16, color=T["muted"], va="baseline")
    fig.text(0.055, 0.045, "Data: CPCB monitors (via Vonter/india-cpcb-aqi), ERA5, NASA FIRMS.  "
             "*Surat: one monitor, three Diwalis.  Method and code: github.com/dogluk/diwali-aqi",
             fontproperties=SANS, fontsize=12, color=T["muted"])
    fig.text(0.97, 0.045, "dogl.uk", fontproperties=SERIF, fontsize=16, color=T["mark"], ha="right")
    fig.savefig(CHARTS / T["out"], dpi=170, facecolor=T["bg"])
    plt.close(fig)
    print("written", CHARTS / T["out"])


for theme in THEMES.values():
    render(theme)
