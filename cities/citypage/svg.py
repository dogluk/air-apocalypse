"""Hand-written inline SVG charts. Colours come only from CSS classes (variables defined by
page.page), so they follow light and dark. Every chart has role="img" and a <title>."""
import itertools
import math
from dataclasses import dataclass

from .page import esc, fmt

_ids = itertools.count()


def reset_ids() -> None:
    """Restart the pattern-id counter, so a rebuild gives the same bytes."""
    global _ids
    _ids = itertools.count()


@dataclass
class Series:
    name: str
    x: list[float]
    y: list[float | None]
    kind: str = "line"      # "line" or "points"
    colour: int = 0


def _ok(v) -> bool:
    return v is not None and not (isinstance(v, float) and math.isnan(v))


def nice_ticks(lo: float, hi: float, n: int = 5) -> list[float]:
    """4-6 round steps covering [lo, hi]."""
    if hi <= lo:
        hi = lo + 1
    raw = (hi - lo) / n
    mag = 10 ** math.floor(math.log10(raw))
    step = next((m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw), 10 * mag)
    t = math.floor(lo / step) * step
    out = []
    while t <= hi + step * 1e-9:
        out.append(round(t, 10))
        t += step
    return out


def _tick(v: float) -> str:
    return f"{v:g}"


def _open(width, height, title):
    return (f'<svg viewBox="0 0 {width} {height}" width="{width}" role="img" '
            f'aria-label="{esc(title)}" xmlns="http://www.w3.org/2000/svg"><title>{esc(title)}</title>'
            f'<text class="ttl" x="0" y="14">{esc(title)}</text>')


def line_chart(series: list[Series], *, title: str, x_label: str, y_label: str,
               x_ticks: list[tuple[float, str]] | None = None, y_min: float | None = 0,
               width: int = 640, height: int = 300) -> str:
    L, R, T, B = 52, 120, 30, 44
    xs = [x for s in series for x, y in zip(s.x, s.y) if _ok(y)] or [0, 1]
    ys = [y for s in series for y in s.y if _ok(y)] or [0, 1]
    x0, x1 = min(xs), max(xs)
    if x1 == x0:
        x1 = x0 + 1
    ylo = min(ys) if y_min is None else y_min
    yt = nice_ticks(ylo, max(ys))
    ylo, yhi = yt[0], yt[-1]

    def px(x):
        return L + (x - x0) / (x1 - x0) * (width - L - R)

    def py(y):
        return T + (yhi - y) / (yhi - ylo) * (height - T - B)

    o = [_open(width, height, title)]
    for t in yt:
        o.append(f'<line class="grid" x1="{L}" x2="{width - R}" y1="{py(t):.1f}" y2="{py(t):.1f}"/>'
                 f'<text x="{L - 6}" y="{py(t) + 4:.1f}" text-anchor="end">{_tick(t)}</text>')
    for v, lab in (x_ticks or [(t, _tick(t)) for t in nice_ticks(x0, x1)]):
        if x0 <= v <= x1:
            o.append(f'<text x="{px(v):.1f}" y="{height - B + 16}" text-anchor="middle">{esc(lab)}</text>')
    o.append(f'<line class="axis" x1="{L}" x2="{width - R}" y1="{height - B}" y2="{height - B}"/>')
    o.append(f'<text x="{L + (width - L - R) / 2:.0f}" y="{height - 6}" text-anchor="middle">{esc(x_label)}</text>')
    mid = T + (height - T - B) / 2
    o.append(f'<text x="12" y="{mid:.0f}" text-anchor="middle" transform="rotate(-90 12 {mid:.0f})">'
             f'{esc(y_label)}</text>')
    for s in series:
        c = s.colour % 8
        last = None
        if s.kind == "line":
            seg: list[str] = []

            def flush():
                if seg:
                    o.append(f'<polyline class="ln s{c}" points="{" ".join(seg)}">'
                             f'<title>{esc(s.name)}</title></polyline>')
            for x, y in zip(s.x, s.y):
                if _ok(y):
                    seg.append(f"{px(x):.1f},{py(y):.1f}")
                    last = (x, y)
                else:
                    flush()
                    seg = []
            flush()
        else:
            for x, y in zip(s.x, s.y):
                if _ok(y):
                    o.append(f'<circle class="f{c}" cx="{px(x):.1f}" cy="{py(y):.1f}" r="3.5">'
                             f'<title>{esc(s.name)}: {_tick(round(y, 2))}</title></circle>')
                    last = (x, y)
        if last:
            o.append(f'<text class="lab" x="{px(last[0]) + 6:.1f}" y="{py(last[1]) + 4:.1f}">{esc(s.name)}</text>')
    o.append("</svg>")
    return "".join(o)


def heatmap(row_labels: list[str], col_labels: list[str], values: list[list[float | None]], *,
            title: str, value_label: str, fmt_kind: str = "1dp") -> str:
    L, T, cw, ch = 110, 48, 44, 22
    width = L + cw * len(col_labels) + 8
    height = T + ch * len(row_labels) + 8
    flat = [v for r in values for v in r if _ok(v)]
    lo, hi = (min(flat), max(flat)) if flat else (0.0, 1.0)
    span = (hi - lo) or 1.0
    pid = f"hatch{next(_ids)}"
    o = [_open(width, height, title)]
    o.append(f'<defs><pattern id="{pid}" width="5" height="5" patternUnits="userSpaceOnUse" '
             f'patternTransform="rotate(45)"><line class="hatch" x1="0" y1="0" x2="0" y2="5"/></pattern></defs>')
    o.append(f'<text class="muted" x="0" y="30">{esc(value_label)}</text>')
    for j, c in enumerate(col_labels):
        o.append(f'<text x="{L + cw * j + cw / 2}" y="{T - 6}" text-anchor="middle">{esc(c)}</text>')
    for i, r in enumerate(row_labels):
        y = T + ch * i
        o.append(f'<text class="lab" x="{L - 6}" y="{y + 15}" text-anchor="end">{esc(r)}</text>')
        for j in range(len(col_labels)):
            v = values[i][j]
            x = L + cw * j
            if not _ok(v):
                o.append(f'<g><title>{esc(r)}, {esc(col_labels[j])}: no data</title>'
                         f'<rect class="nodata" x="{x}" y="{y}" width="{cw - 1}" height="{ch - 1}"/>'
                         f'<rect fill="url(#{pid})" x="{x}" y="{y}" width="{cw - 1}" height="{ch - 1}"/></g>')
            else:
                f = (v - lo) / span
                pct = round(8 + 92 * f)
                txt = fmt(v, fmt_kind)
                o.append(f'<g><title>{esc(r)}, {esc(col_labels[j])}: {esc(txt)}</title>'
                         f'<rect x="{x}" y="{y}" width="{cw - 1}" height="{ch - 1}" '
                         f'style="fill:color-mix(in srgb, var(--s0) {pct}%, var(--band))"/>'
                         f'<text class="cellink{" on" if f > 0.55 else ""}" x="{x + cw / 2 - .5}" y="{y + 15}" '
                         f'text-anchor="middle">{esc(txt)}</text></g>')
    o.append("</svg>")
    return "".join(o)


def dot_rows(row_labels: list[str], groups: list[tuple[str, list[float | None]]], *, title: str,
             x_label: str, lo: list[list[float | None]] | None = None,
             hi: list[list[float | None]] | None = None) -> str:
    """lo/hi, if given, are indexed [group][row] like groups."""
    L, R, T, rh = 160, 150, 34, 24
    width = 640
    height = T + rh * len(row_labels) + 40
    vals = [v for _, g in groups for v in g if _ok(v)]
    for grid in (lo, hi):
        vals += [v for r in (grid or []) for v in r if _ok(v)]
    xt = nice_ticks(0, max(vals) if vals else 1)
    xmax = xt[-1]
    bottom = T + rh * len(row_labels)

    def px(v):
        return L + v / xmax * (width - L - R)

    o = [_open(width, height, title)]
    for t in xt:
        o.append(f'<line class="grid" x1="{px(t):.1f}" x2="{px(t):.1f}" y1="{T - 4}" y2="{bottom}"/>'
                 f'<text x="{px(t):.1f}" y="{bottom + 14}" text-anchor="middle">{_tick(t)}</text>')
    o.append(f'<text x="{(L + width - R) / 2:.0f}" y="{height - 4}" text-anchor="middle">{esc(x_label)}</text>')
    for i, r in enumerate(row_labels):
        cy = T + rh * i + rh / 2
        o.append(f'<text class="lab" x="{L - 8}" y="{cy + 4:.1f}" text-anchor="end">{esc(r)}</text>')
        for g, (gname, gv) in enumerate(groups):
            c = g % 8
            if lo and hi and _ok(lo[g][i]) and _ok(hi[g][i]):
                o.append(f'<line class="bar s{c}" x1="{px(lo[g][i]):.1f}" x2="{px(hi[g][i]):.1f}" '
                         f'y1="{cy:.1f}" y2="{cy:.1f}" opacity=".35"><title>{esc(gname)}: range '
                         f'{_tick(round(lo[g][i], 2))} to {_tick(round(hi[g][i], 2))}</title></line>')
            if _ok(gv[i]):
                o.append(f'<circle class="f{c}" cx="{px(gv[i]):.1f}" cy="{cy:.1f}" r="4">'
                         f'<title>{esc(r)}, {esc(gname)}: {_tick(round(gv[i], 2))}</title></circle>')
    for g, (gname, _) in enumerate(groups):
        o.append(f'<circle class="f{g % 8}" cx="{width - R + 14}" cy="{T + 8 + 16 * g}" r="4"/>'
                 f'<text class="lab" x="{width - R + 24}" y="{T + 12 + 16 * g}">{esc(gname)}</text>')
    o.append("</svg>")
    return "".join(o)


def stacked_bars(col_labels: list[str], part_labels: list[str], values: list[list[float | None]], *,
                 title: str) -> str:
    """values[p][c] is part p of column c (0-100). None parts are left out, never padded."""
    L, R, T, bh = 110, 150, 34, 22
    width = 640
    bottom = T + (bh + 8) * len(col_labels)
    height = bottom + 30

    def px(v):
        return L + v / 100 * (width - L - R)

    o = [_open(width, height, title)]
    for t in (0, 25, 50, 75, 100):
        o.append(f'<line class="grid" x1="{px(t):.1f}" x2="{px(t):.1f}" y1="{T - 4}" y2="{bottom}"/>'
                 f'<text x="{px(t):.1f}" y="{bottom + 14}" text-anchor="middle">{t}</text>')
    for c, cl in enumerate(col_labels):
        y = T + (bh + 8) * c
        o.append(f'<text class="lab" x="{L - 8}" y="{y + 15}" text-anchor="end">{esc(cl)}</text>')
        x = 0.0
        for p, pl in enumerate(part_labels):
            v = values[p][c]
            if not _ok(v):
                continue
            o.append(f'<rect class="f{p % 8}" x="{px(x):.1f}" y="{y}" width="{px(x + v) - px(x):.1f}" '
                     f'height="{bh}"><title>{esc(cl)}, {esc(pl)}: {_tick(round(v, 1))}</title></rect>')
            x += v
    for p, pl in enumerate(part_labels):
        o.append(f'<rect class="f{p % 8}" x="{width - R + 8}" y="{T + 16 * p}" width="10" height="10"/>'
                 f'<text class="lab" x="{width - R + 24}" y="{T + 9 + 16 * p}">{esc(pl)}</text>')
    o.append("</svg>")
    return "".join(o)
