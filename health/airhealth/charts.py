"""Charts in the repo's style (fonts from fonts/, the palette and spare axes of diwali/charts.py)."""
import logging
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib import font_manager as fm  # noqa: E402

from . import paths  # noqa: E402
from .curves import MAX_COHORT_PM25, Curve  # noqa: E402

INK, INK2, MUTED, GRID, BG = "#0b0b0b", "#52514e", "#8a8984", "#e6e5e1", "#fcfcfb"
BAND = "#efeeea"
# Categorical slots in fixed order (validated: CVD and normal-vision separation pass on the light
# surface; aqua and yellow sit under 3:1 contrast, so every line is also labelled directly).
SERIES = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948")
SHORT = {"loglinear_jaganathan": "Jaganathan 2024", "loglinear_brown": "Brown 2022",
         "loglinear_vodonos": "Vodonos 2018", "gemm_ncd_lri": "GEMM NCD+LRI"}
CITE = {"loglinear_jaganathan": "Jaganathan et al. 2024, Lancet Planet Health",
        "loglinear_brown": "Brown et al. 2022, Environ Health Perspect",
        "loglinear_vodonos": "Vodonos et al. 2018, Environ Res",
        "gemm_ncd_lri": "Burnett et al. 2018, PNAS (GEMM)"}

logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)  # DejaVu has no semibold
for _f in paths.FONTS.glob("*.ttf"):
    fm.fontManager.addfont(str(_f))
# The repo fonts lack µ and ³; DejaVu (shipped with matplotlib) fills in those glyphs only.
SANS_FAMILY = ["Instrument Sans", "DejaVu Sans"]
SANS = fm.FontProperties(family=SANS_FAMILY)
SANS_B = fm.FontProperties(family=SANS_FAMILY, weight="semibold")
SERIF = fm.FontProperties(family=["Young Serif", "DejaVu Serif"])
STYLE = {"font.family": SANS_FAMILY, "font.size": 11, "axes.edgecolor": GRID,
         "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
         "figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG}


def _spread(ys: list[float], gap: float) -> list[float]:
    """Nudge label positions apart so none sit closer than `gap`, keeping their order."""
    order = np.argsort(ys)
    out = np.array(ys, dtype=float)
    for a, b in zip(order, order[1:]):
        out[b] = max(out[b], out[a] + gap)
    return list(out)


def curves_chart(curves: list[Curve], marks: dict[str, float], path: Path, age: int = 60,
                 note: str = "") -> Path:
    """Relative risk of death against annual-mean PM2.5 (0-150 µg/m³), one line per curve, at the
    age band starting at `age`, each against its own floor. Places in `marks` are drawn at their
    concentration. Curves without a relative risk (AQLI) are named in the subtitle, not drawn."""
    drawn = [c for c in curves if c.kind == "relative_risk"]
    skipped = [c for c in curves if c.kind != "relative_risk"]
    x = np.linspace(0, 150, 601)

    with plt.rc_context(STYLE):
        fig = plt.figure(figsize=(11, 6.8))
        ax = fig.add_axes([0.07, 0.2, 0.78, 0.55])
        ax.axvspan(MAX_COHORT_PM25, 150, color=BAND, lw=0, zorder=0)
        ends = []
        for k, c in enumerate(drawn):
            colour = SERIES[k % len(SERIES)]
            y = np.asarray(c.rr(x, age), dtype=float)
            ax.plot(x, y, color=colour, lw=2, solid_capstyle="round", zorder=3,
                    label=SHORT.get(c.name, c.name))
            ends.append((y[-1], SHORT.get(c.name, c.name), colour))
        top = max(e[0] for e in ends) if ends else 2.0
        ax.set_ylim(0.9, top * 1.08)
        ax.set_xlim(0, 150)

        span = ax.get_ylim()[1] - ax.get_ylim()[0]
        for (y_end, name, colour), y_lab in zip(ends, _spread([e[0] for e in ends], span * 0.045)):
            ax.plot([150], [y_end], "o", color=colour, ms=8, mec=BG, mew=2, zorder=4, clip_on=False)
            ax.text(153, y_lab, name, color=INK, fontsize=10.5, va="center", fontproperties=SANS)

        band = dict(transform=ax.get_xaxis_transform(), va="top", linespacing=1.25, zorder=2,
                    fontproperties=SANS, bbox=dict(facecolor=BAND, edgecolor="none", pad=1.5))
        ax.text(MAX_COHORT_PM25 + 1.5, 0.975, "no long-term study has\nobserved this range",
                color=INK2, fontsize=10.5, **band)
        ax.text(MAX_COHORT_PM25 + 1.5, 0.86, f"above {MAX_COHORT_PM25:.0f} µg/m³, the most\n"
                "any cohort behind GEMM saw", color=MUTED, fontsize=9, **band)

        for place, c in marks.items():
            ax.axvline(c, color=MUTED, lw=1, ls=(0, (2, 3)), zorder=1)
            ax.plot([c], [0.9], marker="^", color=INK, ms=8, clip_on=False, zorder=5)
            ax.text(c, 1.01, f"{place} {c:.0f}", color=INK, fontsize=10, ha="center",
                    va="bottom", transform=ax.get_xaxis_transform(), fontproperties=SANS_B)

        ax.axhline(1, color=MUTED, lw=1, zorder=2)
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
        ax.grid(axis="y", color=GRID, lw=1)
        ax.set_axisbelow(True)
        ax.tick_params(length=0)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.1f}×"))
        ax.set_xlabel("Annual-mean PM2.5, µg/m³")
        ax.set_ylabel(f"Death rate at age {age}+, × the rate at the floor")
        fig.legend(loc="upper left", bbox_to_anchor=(0.064, 0.845), ncol=len(drawn) or 1,
                   frameon=False, labelcolor=INK2, handlelength=1.6,
                   prop=fm.FontProperties(family=SANS_FAMILY, size=10))

        if marks and drawn:
            place, c = max(marks.items(), key=lambda kv: kv[1])
            rrs = [float(d.rr(c, age)) for d in drawn]
            title = (f"At {place}'s {c:.0f} µg/m³, the curves put the death rate at "
                     f"{min(rrs):.2f}× to {max(rrs):.2f}× clean air")
        else:
            title = "How each curve turns PM2.5 into risk of death"
        fig.text(0.07, 0.935, title, fontsize=17, color=INK, fontproperties=SERIF)
        sub = (f"Relative risk of death at age {age}+ against each curve's own floor (2-5 µg/m³), "
               "where it counts as clean air.\nPast the shaded edge every line is an extrapolation.")
        if skipped:
            sub += (f" Not drawn: {', '.join(c.name for c in skipped)}, which gives life expectancy, "
                    "not a relative risk.")
        fig.text(0.07, 0.915, sub, fontsize=10.5, color=INK2, va="top", linespacing=1.4,
                 fontproperties=SANS)
        src = ("Curves: " + "; ".join(CITE.get(c.name, c.name) for c in drawn) +
               f". Shaded edge at {MAX_COHORT_PM25:.0f} µg/m³: Burnett et al. 2018, PNAS.")
        foot = "\n".join(textwrap.fill(t, 165) for t in (src, note) if t)
        fig.text(0.07, 0.02, foot, fontsize=8.5, color=MUTED,
                 linespacing=1.4, fontproperties=SANS)

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=180)
        plt.close(fig)
    return path
