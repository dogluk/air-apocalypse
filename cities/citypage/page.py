"""The page shell: one self-contained HTML document (fonts embedded, no scripts, light and dark),
plus small helpers for tables and number formatting."""
import base64
import html
import math
from dataclasses import dataclass
from functools import lru_cache

from airhealth import paths
from airhealth.report import zero

SECTION_IDS = ("ground", "sources", "health", "measures")

# Palette of health/airhealth/charts.py (light), with the dark swaps fixed by the design.
LIGHT = {"ink": "#0b0b0b", "ink2": "#52514e", "muted": "#8a8984", "grid": "#e6e5e1",
         "bg": "#fcfcfb", "band": "#efeeea"}
DARK = {"ink": "#f0efea", "ink2": "#c3c2bc", "muted": "#8a8984", "grid": "#33322f",
        "bg": "#141413", "band": "#22211f"}
SERIES = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948")

esc = html.escape


@dataclass(frozen=True)
class Section:
    id: str      # one of SECTION_IDS
    title: str
    html: str


def _b64(name: str) -> str:
    return base64.b64encode((paths.FONTS / name).read_bytes()).decode("ascii")


@lru_cache(maxsize=1)
def _css() -> str:
    faces = "".join(
        f"@font-face{{font-family:'{fam}';font-weight:{w};font-style:normal;font-display:swap;"
        f"src:url(data:font/ttf;base64,{_b64(f)}) format('truetype')}}\n"
        for fam, w, f in (("Young Serif", 400, "youngserif.ttf"),
                          ("Instrument Sans", 400, "instrumentsans-regular.ttf"),
                          ("Instrument Sans", 600, "instrumentsans-semibold.ttf")))
    light = "".join(f"--{k}:{v};" for k, v in LIGHT.items()) + \
        "".join(f"--s{i}:{c};" for i, c in enumerate(SERIES))
    dark = "".join(f"--{k}:{v};" for k, v in DARK.items())
    series = "".join(f"svg .s{i}{{stroke:var(--s{i})}} svg .f{i}{{fill:var(--s{i})}} "
                     for i in range(8))
    return f"""{faces}
:root{{{light}}}
@media (prefers-color-scheme: dark){{:root{{{dark}}}}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);
 font:16px/1.55 'Instrument Sans','Helvetica Neue',Arial,sans-serif}}
main{{max-width:46rem;margin:0 auto;padding:2rem 16px 4rem}}
h1,h2,h3{{font-family:'Young Serif',Georgia,serif;font-weight:400;line-height:1.2}}
h1{{font-size:2.2rem;margin:0 0 .5rem}} h2{{font-size:1.6rem;margin:2.5rem 0 .75rem}}
h3{{font-size:1.2rem;margin:1.75rem 0 .5rem}}
a{{color:var(--s0)}} p{{margin:.7rem 0}}
nav.contents ol{{padding-left:1.2rem;margin:.5rem 0}}
section{{border-top:1px solid var(--grid);margin-top:2rem}}
.tablewrap{{overflow-x:auto;margin:1rem 0}}
table{{border-collapse:collapse;width:100%;font-size:.9rem}}
caption{{text-align:left;color:var(--ink2);padding-bottom:.4rem}}
th,td{{padding:.3rem .6rem;border-bottom:1px solid var(--grid);text-align:left;vertical-align:top}}
th{{font-weight:600;color:var(--ink2)}}
td.num,th.num{{text-align:right;font-variant-numeric:tabular-nums}}
.chart{{overflow-x:auto;margin:1rem 0}} .chart.narrow{{display:none}}
@media (max-width:600px){{.chart.wide{{display:none}} .chart.narrow{{display:block}}}}
svg .sm{{font-size:10px}}
svg{{display:block;max-width:100%;height:auto;font-family:inherit}}
svg text{{fill:var(--ink2);font-size:11px}}
svg .ttl{{fill:var(--ink);font-family:'Young Serif',Georgia,serif;font-size:14px}}
svg .lab{{fill:var(--ink)}} svg .muted{{fill:var(--muted)}}
svg .grid{{stroke:var(--grid);stroke-width:1;fill:none}}
svg .axis{{stroke:var(--muted);stroke-width:1;fill:none}}
svg .hatch{{stroke:var(--muted);stroke-width:1}} svg .nodata{{fill:var(--band)}}
svg .cellink{{fill:var(--ink)}} svg .cellink.on{{fill:var(--bg)}}
{series}
svg .ln{{fill:none;stroke-width:2}} svg .bar{{stroke-width:6;stroke-linecap:round}}
.note{{color:var(--ink2);font-size:.9rem}}
.caveats{{border-left:3px solid var(--s1);background:var(--band);padding:.2rem .9rem;margin:.8rem 0}}
.caveats ul{{margin:.3rem 0;padding-left:1.1rem}}
.card{{border:1px solid var(--grid);background:var(--band);border-radius:6px;padding:.2rem 1rem .6rem;margin:1rem 0}}
.card h4{{margin:.7rem 0 .3rem}} .card ul{{margin:.3rem 0;padding-left:1.1rem}}
details{{margin:.5rem 0;color:var(--ink2)}} summary{{cursor:pointer;color:var(--s0)}}
details p{{margin:.4rem 0 .4rem 1rem}}
h4{{font-size:1.02rem;margin:1.2rem 0 .3rem}}
footer{{border-top:1px solid var(--grid);margin-top:3rem;padding-top:1rem;color:var(--ink2);font-size:.9rem}}
"""


def page(title: str, intro_html: str, sections: list[Section], footer_html: str) -> str:
    toc = "".join(f'<li><a href="#ch-{s.id}">{esc(s.title)}</a></li>' for s in sections)
    body = "".join(f'<section id="ch-{s.id}"><h2>{esc(s.title)}</h2>{s.html}</section>'
                   for s in sections)
    return (f'<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{esc(title)}</title><style>{_css()}</style></head><body><main>'
            f'<h1>{esc(title)}</h1>{intro_html}'
            f'<nav class="contents" aria-label="Contents"><ol>{toc}</ol></nav>'
            f'{body}<footer>{footer_html}</footer></main></body></html>\n')


def table(head: list[str], rows: list[list[str]], *, caption: str | None = None,
          numeric: tuple[int, ...] = ()) -> str:
    def cell(tag, i, v):
        return f'<{tag}{" class=num" if i in numeric else ""}>{esc(str(v))}</{tag}>'
    cap = f"<caption>{esc(caption)}</caption>" if caption else ""
    th = "".join(cell("th", i, h) for i, h in enumerate(head))
    tr = "".join("<tr>" + "".join(cell("td", i, v) for i, v in enumerate(r)) + "</tr>"
                 for r in rows)
    return (f'<div class="tablewrap"><table>{cap}<thead><tr>{th}</tr></thead>'
            f'<tbody>{tr}</tbody></table></div>')


def fmt(x: float | None, kind: str = "int", missing: str = "no data") -> str:
    """A number as text; a value that rounds to nothing is 0, never -0."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return missing
    return zero(_fmt(x, kind))


def _fmt(x: float, kind: str) -> str:
    if kind == "int":
        return f"{x:,.0f}"
    if kind == "1dp":
        return f"{x:,.1f}"
    if kind == "pct":
        return f"{x * 100:.1f}%"
    if kind == "pct_points":
        return f"{x:.1f}%"
    if kind == "usd":
        if abs(x) >= 1e6:
            return f"${x / 1e6:,.1f} M"
        return f"${x:,.0f}" if abs(x) >= 1000 else f"${x:,.1f}"
    if kind == "years":
        return f"{x:+.2f}"
    raise ValueError(f"unknown format kind {kind!r}")
