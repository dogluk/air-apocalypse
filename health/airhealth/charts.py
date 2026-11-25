"""Charts in the repo's style (fonts from fonts/, the palette and spare axes of diwali/charts.py).

curves_chart: the risk curves with places marked. results_chart: an intervention run, one bar
per curve with its 5-95% range. spread_chart: what drives the spread within each curve, beside
the spread across curves."""
import logging
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib import font_manager as fm  # noqa: E402

from . import baseline, paths  # noqa: E402
from .ages import AGE_STARTS  # noqa: E402
from .curves import MAX_COHORT_PM25, Curve  # noqa: E402

INK, INK2, MUTED, GRID, BG = "#0b0b0b", "#52514e", "#8a8984", "#e6e5e1", "#fcfcfb"
BAND = "#efeeea"
# Categorical slots in fixed order (validated: CVD and normal-vision separation pass on the light
# surface; aqua and yellow sit under 3:1 contrast, so every line is also labelled directly).
SERIES = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948")
SHORT = {"loglinear_jaganathan": "Jaganathan 2024", "loglinear_brown": "Brown 2022",
         "loglinear_vodonos": "Vodonos 2018", "gemm_ncd_lri": "GEMM NCD+LRI", "aqli": "AQLI",
         "gbd2019": "GBD 2019", "gbd2023": "GBD 2023", "gemm_5cod": "GEMM 5 causes"}
CITE = {"loglinear_jaganathan": "Jaganathan et al. 2024, Lancet Planet Health",
        "loglinear_brown": "Brown et al. 2022, Environ Health Perspect",
        "loglinear_vodonos": "Vodonos et al. 2018, Environ Res",
        "gemm_ncd_lri": "Burnett et al. 2018, PNAS (GEMM)"}

# What each line is the risk of: a relative risk applies to the deaths its curve covers.
# A cause-specific (IHME-tier) curve is drawn on all deaths: 1 + Σ share_c × (RR_c − 1), with
# India's 2023 share of deaths from each cause in the band (ihme_curves.CauseCurve.rr).
COVERS = {"all": "all deaths", "ncd_lri": "NCD+LRI deaths only",
          "causes": "all deaths, via its causes (India's 2023 mix)"}


def age_band(age: int) -> str:
    """The band an age falls in, as text: 60 -> 'ages 60-64', 85 -> 'ages 85 and over'."""
    start = max(a for a in AGE_STARTS if a <= age)
    later = [a for a in AGE_STARTS if a > start]
    return f"ages {start}-{later[0] - 1}" if later else f"ages {start} and over"


def line_label(c: Curve) -> str:
    return f"{SHORT.get(c.name, c.name)}: {COVERS[c.death_scope]}"


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
    """Relative risk against annual-mean PM2.5 (0-150 µg/m³), one line per curve, for the age
    band holding `age`, each against its own floor. A line is the risk of the deaths its curve
    covers, and its label says which: all deaths, or NCD+LRI deaths only (GEMM), so the lines
    are not on one scale of "the death rate"; the subtitle gives GEMM's level in all-death
    terms at the highest marked place. Places in `marks` are drawn at their concentration.
    Curves without a relative risk (AQLI) are named in the subtitle, not drawn."""
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
                    label=line_label(c))
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
        ax.set_ylabel(f"Relative risk, {age_band(age)}: × the risk at the curve's floor")
        fig.legend(loc="upper left", bbox_to_anchor=(0.064, 0.845), ncol=len(drawn) or 1,
                   frameon=False, labelcolor=INK2, handlelength=1.6,
                   prop=fm.FontProperties(family=SANS_FAMILY, size=10))

        band_index = max(k for k, a in enumerate(AGE_STARTS) if a <= age)
        share = float(baseline._share_ncd_lri()[band_index])     # NCD+LRI share of deaths, this band
        partial = [d for d in drawn if d.death_scope == "ncd_lri"]
        if marks and drawn:
            place, c = max(marks.items(), key=lambda kv: kv[1])
            # every curve on the same footing for the title: the factor on ALL deaths
            on_all = [1 + (share if d.death_scope == "ncd_lri" else 1.0) * (float(d.rr(c, age)) - 1)
                      for d in drawn]
            title = (f"At {place}'s {c:.0f} µg/m³, the curves put the death rate at "
                     f"{min(on_all):.2f}× to {max(on_all):.2f}× clean air")
        else:
            place = c = None
            title = "How each curve turns PM2.5 into risk of death"
        fig.text(0.07, 0.935, title, fontsize=17, color=INK, fontproperties=SERIF)
        sub = (f"Relative risk at {age_band(age)}, of the deaths each curve covers (see the key), "
               "against the curve's own floor (2-5 µg/m³). Shaded: extrapolation.")
        for d in partial:
            sub += (f"\n{SHORT.get(d.name, d.name)} covers {100 * share:.0f}% of deaths at these ages"
                    + (f": its {float(d.rr(c, age)):.2f}× at {place} is "
                       f"{1 + share * (float(d.rr(c, age)) - 1):.2f}× on all deaths."
                       if place else "."))
        fig.text(0.07, 0.915, sub, fontsize=10.5, color=INK2, va="top", linespacing=1.4,
                 fontproperties=SANS)
        if skipped:
            note = (f"Not drawn: {', '.join(c.name for c in skipped)}, which gives life "
                    f"expectancy, not a relative risk. {note}").strip()
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


# --- intervention runs ----------------------------------------------------------------------

def _label(c: Curve) -> str:
    return SHORT.get(c.name, c.name) + (" *" if c.kind == "life_expectancy" else "")


def _style(ax) -> None:
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.grid(axis="x", color=GRID, lw=1)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:,.0f}"))


FOOT_WIDTH = 170


def _foot_lines(foot: str) -> list[str]:
    return [line for t in foot.split("\n") for line in textwrap.wrap(t, FOOT_WIDTH)]


def _frame(n_rows: int, foot: str, legend: bool = False):
    """A figure sized to its rows, with room above for title, subtitle (and a legend) and
    below for the axis label and the footnote."""
    above = 1.55 + (0.35 if legend else 0)
    below = 0.75 + 0.2 * len(_foot_lines(foot))
    fig = plt.figure(figsize=(11, above + below + 0.62 * n_rows + 0.3))
    h = fig.get_figheight()
    ax = fig.add_axes([0.25, below / h, 0.68, 1 - (above + below) / h])
    return fig, ax


def _texts(fig, title: str, sub: str, foot: str) -> None:
    h = fig.get_figheight()
    fig.text(0.04, 1 - 0.35 / h, title, fontsize=17, color=INK, fontproperties=SERIF, va="top")
    fig.text(0.04, 1 - 0.8 / h, sub, fontsize=10.5, color=INK2, va="top", linespacing=1.4,
             fontproperties=SANS)
    fig.text(0.04, 0.12 / h, "\n".join(_foot_lines(foot)), fontsize=8.5, color=MUTED,
             linespacing=1.4, fontproperties=SANS)


def _run_text(run) -> tuple[str, str]:
    from .report import change_text, run_footer
    iv = run.intervention
    first = next(iter(run.per_curve.values()))
    after = float(np.median(first.pm25_after))
    where = ", ".join(p.name for p in iv.places)
    sub = (f"{where}, {iv.start_year}-{iv.start_year + iv.duration_years - 1}: {change_text(iv)}; "
           f"annual mean {run.pm25_before:.1f} → {after:.1f} µg/m³. Lag {iv.lag}"
           f"{f', ramp {iv.ramp_years} years' if iv.ramp_years else ''}. "
           f"If it works; it works with probability {iv.p_success:g}.")
    cites = [CITE.get(n, n) for n in run.per_curve if n in CITE]
    if "aqli" in run.per_curve:
        cites.append("AQLI (EPIC, Univ. of Chicago)")
    foot = (f"Curves: {'; '.join(cites)}. {run.n:,} draws, seed {run.seed}. "
            "* deaths derived from AQLI's life-expectancy change.\n" + run_footer(run))
    return sub, foot


def results_chart(run, path: Path) -> Path:
    """Life-years over the run if the intervention works: a bar per curve at the median,
    a line over its 5-95% range."""
    from .report import NO_INTERVAL, PM25_ONLY, _interval, _sig
    rows = list(run.per_curve.values())[::-1]            # first curve on top
    med = np.array([np.median(r.life_years) for r in rows])
    lo = np.array([np.percentile(r.life_years, 5) for r in rows])
    hi = np.array([np.percentile(r.life_years, 95) for r in rows])
    y = np.arange(len(rows))
    sub, foot = _run_text(run)

    with plt.rc_context(STYLE):
        fig, ax = _frame(len(rows), foot)
        ax.barh(y, med, height=0.5, color=SERIES[0], lw=0, zorder=2)
        ranged = hi > lo                                 # no whisker where there is no range
        ax.hlines(y[ranged], lo[ranged], hi[ranged], color=INK, lw=1.5, zorder=3)
        for k in (lo, hi):
            ax.plot(k[ranged], y[ranged], "|", color=INK, ms=10, mew=1.5, zorder=3)
        span = max(hi.max(), 0) - min(lo.min(), 0) or 1.0
        for yy, m, h, l, r in zip(y, med, hi, lo, rows):
            x, ha = (h + span * 0.015, "left") if m >= 0 else (l - span * 0.015, "right")
            tail = {"none": f"  ({NO_INTERVAL})", "pm25_change_only": f"  ({PM25_ONLY})",
                    "published": ""}[_interval(r)]
            ax.text(x, yy, _sig(m) + tail, va="center", ha=ha, fontsize=10.5, color=INK,
                    fontproperties=SANS_B)
        ax.set_xlim(min(lo.min(), 0) - span * 0.04, max(hi.max(), 0) + span * 0.3)
        ax.axvline(0, color=MUTED, lw=1, zorder=1)
        ax.set_yticks(y, [_label(r.curve) for r in rows], fontproperties=SANS, fontsize=11,
                      color=INK)
        _style(ax)
        ax.set_xlabel(f"Life-years gained over the {run.intervention.duration_years} years, "
                      "if it works (bar: median; line: 5-95% of draws)")
        top, bottom = max(med, key=abs), min(med, key=abs)
        title = (f"{run.intervention.name}: {_sig(bottom)} to {_sig(top)} life-years, "
                 "depending on the curve")
        _texts(fig, title, textwrap.fill(sub, 150), foot)
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=180)
        plt.close(fig)
    return path


def spread_chart(run, path: Path) -> Path:
    """For each curve, the 5-95% width of life-years when only the PM2.5 change is sampled and
    when only the curve's parameters are, with the range of medians across curves for scale."""
    from .report import _sig
    rows = list(run.per_curve.values())[::-1]
    y = np.arange(len(rows))
    parts = (("pm25_change", "PM2.5 change sampled alone", SERIES[0]),
             ("curve_parameters", "curve parameters sampled alone", SERIES[1]))
    medians = [np.median(r.life_years) for r in rows]
    across = max(medians) - min(medians)
    sub, foot = _run_text(run)

    with plt.rc_context(STYLE):
        fig, ax = _frame(len(rows), foot, legend=True)
        h = 0.3
        for k, (key, label, colour) in enumerate(parts):
            widths = [r.widths[key] for r in rows]
            ax.barh(y + (0.5 - k) * (h + 0.04), widths, height=h, color=colour, lw=0,
                    label=label, zorder=2)
        top = max([across, *(r.widths[k] for r in rows for k, _, _ in parts)]) or 1.0
        for yy, r in zip(y, rows):
            if r.widths["curve_parameters"] == 0 and r.spread["curve_parameters"] == 0:
                ax.text(top * 0.01, yy - 0.5 * (h + 0.04), "no published interval",
                        va="center", fontsize=9.5, color=INK2, fontproperties=SANS)
        if len(rows) > 1:
            ax.axvline(across, color=INK, lw=1.5, ls=(0, (3, 2)), zorder=3)
            ax.text(across, 1.01, f"range of medians across curves, {_sig(across)}",
                    transform=ax.get_xaxis_transform(), ha="right", va="bottom", fontsize=10,
                    color=INK, fontproperties=SANS_B)
        ax.set_xlim(0, top * 1.08)
        ax.set_yticks(y, [_label(r.curve) for r in rows], fontproperties=SANS, fontsize=11,
                      color=INK)
        _style(ax)
        ax.set_xlabel("Width of the 5-95% range of life-years over the run, if it works")
        fh = fig.get_figheight()
        fig.legend(loc="upper left", bbox_to_anchor=(0.04, 1 - 1.45 / fh), ncol=2,
                   frameon=False, labelcolor=INK2, handlelength=1.6,
                   prop=fm.FontProperties(family=SANS_FAMILY, size=10))
        if all(r.widths["pm25_change"] == 0 for r in rows):
            sub += " The PM2.5 change is a fixed number in this file, so it adds no spread."
        within = max(r.widths[k] for r in rows for k, _, _ in parts)
        title = ("Which curve you pick moves the answer more than the uncertainty within any one"
                 if across > within else
                 "The uncertainty within a curve is as large as the choice of curve")
        _texts(fig, title, textwrap.fill(sub, 150), foot)
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=180)
        plt.close(fig)
    return path
