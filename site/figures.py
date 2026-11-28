"""Figures and numbers for the airhealth.dev landing page, drawn from the model's own outputs.

Writes site/src/fig/*.html (plain HTML fragments, positioned in percent so they reflow), site/data/air.json
(the numbers the page's prose quotes, so prose and figures cannot drift) and the two render pages
site/src/card.html and site/src/film.html (see site/README.md for turning those into the PNG and MP4).
Everything written is committed, so a fresh clone builds the page without rerunning the model.
Nothing here is typed in by hand: every figure value is read from a model output or data file.

    python site/figures.py --from health/out/launch-19fb04c

--from holds rank5000/ (airhealth rank --write), sens2000/sensitivity_bengaluru.json and
stab/stability_bengaluru.json (health/scripts/stability_report.py). Run it with the model's Python
(.venv/bin/python); it calls the airhealth command line of this checkout for the terminal figure,
the toll and the fifty-city figure.

Project rules the figures keep (the model's AGENTS.md): nothing is averaged across curves,
studies or maps; "not reported" is not zero; flags stay beside the numbers they qualify.
"""
import argparse
import csv
import datetime
import html
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent          # site/
ROOT = HERE.parent                                # the repository
SRC = HERE / "src"
FIG = SRC / "fig"
DATA = HERE / "data" / "air.json"
DEFAULT_FROM = ROOT / "health/out/launch-19fb04c"
CITY = "Bengaluru"

# Plain names for the page (labels only; no numbers).
MEASURE = {
    "waste_collection_burning_ban": "Ending open waste burning",
    "construction_dust_controls": "Dust controls at construction sites",
    "lpg_refill_subsidy": "LPG refills for homes cooking on wood",
    "stubble_pes_upfront": "Paying Punjab's farmers not to burn stubble",
    "road_paving": "Paving the edges of main roads",
    "happy_seeder_subsidy": "Subsidising stubble machines in Punjab",
    "fgd_scrubbers": "Scrubbers on India's coal power plants",
    "dg_set_replacement": "Filters on diesel generators",
    "electric_buses": "2,000 electric buses",
    "road_vacuum_sweeping": "Mechanical sweeping of main roads",
    "electric_two_three_wheelers": "Electric two- and three-wheelers",
    "old_vehicle_retirement": "Retiring older trucks and buses",
    "school_purifiers": "HEPA purifiers in classrooms",
    "school_purifiers_india": "HEPA purifiers in classrooms",
    "punjab_out_of_rice": "Paying Punjab and Haryana to grow less paddy",
    "n95_winter": "N95 masks for workers, one winter",
    "home_purifiers": "Free HEPA purifiers for homes",
    "smog_tower": "A smog tower",
    "emissions_market": "A particulate emissions market (Surat)",
    "industrial_fuel_switch": "Industry off coal and oil (Amritsar)",
    "winter_cloud_seeding": "Winter cloud seeding (Delhi)",
    "zigzag_kilns": "Zig-zag brick kilns (Patna)",
}
TAG = {  # flag -> the words that sit beside the row; first two that apply are shown
    "partial_cost": "cost leaves things out",
    "receptor_fallback": "smoke table is a stand-in",
    "long_shot": "long shot",
    "covered_only": "reaches only its users",
}
CARD_TAG = {"partial_cost": "partial cost", "receptor_fallback": "stand-in smoke table",
            "long_shot": "long shot", "covered_only": "users only"}
WORDS = ["no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]
SEASON = {"Dec-Feb": "Dec to Feb", "Mar-May": "Mar to May", "Jun-Sep": "Jun to Sep", "Oct-Nov": "Oct, Nov"}

e = html.escape


def num(v: float) -> str:
    """A count with thousands separators."""
    return f"{round(v):,}"


def ratio(v: float) -> str:
    """Life-years per crore: three figures from 100 up, two below."""
    if v >= 100:
        return f"{float(f'{v:.3g}'):,.0f}"
    s = f"{v:.2g}"
    return f"{float(s):.{max(0, -math.floor(math.log10(abs(float(s)))) + 1)}f}" if "e" in s else s


def pct(x: float) -> str:
    return f"{x:.2f}%"


def rng(lo, hi) -> str:
    return "—" if lo is None else (str(lo) if lo == hi else f"{lo}–{hi}")


def cli(model: Path, *args: str) -> dict:
    r = subprocess.run([sys.executable, "-m", "airhealth.cli", *args, "--json"], capture_output=True,
                       text=True, cwd=model / "health",
                       env={"PYTHONPATH": str(model / "health"), "PATH": "/usr/bin:/bin"})
    if r.returncode:
        sys.exit(f"airhealth {' '.join(args)} failed: {(r.stderr or r.stdout)[-400:]}")
    return json.loads(r.stdout)


def table(head: list[str], rows: list[list[str]], numeric_from: int = 1) -> str:
    th = "".join(f"<th{' class=\"n\"' if i >= numeric_from else ''}>{e(h)}</th>" for i, h in enumerate(head))
    body = "".join("<tr>" + "".join(
        f"<td{' class=\"n\"' if i >= numeric_from else ''}>{c}</td>" for i, c in enumerate(r)) + "</tr>" for r in rows)
    return (f'<details class="af-data"><summary>The numbers</summary><div class="af-scroll"><table>'
            f"<thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div></details>")


def tip(pairs: list[tuple[str, str]]) -> str:
    return e(json.dumps(pairs, ensure_ascii=False), quote=True)


def axis(ticks: list[tuple[float, str]], cls: str = "") -> str:
    return (f'<div class="af-axis {cls}" aria-hidden="true">'
            + "".join(f'<span style="left:{pct(p)}">{e(t)}</span>' for p, t in ticks) + "</div>")


# ---------------------------------------------------------------- 1. the toll, curve by curve

def fig_toll(model: Path, short: dict) -> tuple[str, dict, list[str], list[tuple[str, float]]]:
    b = cli(model, "burden", CITY)
    rows = sorted(b["rows"], key=lambda r: r["deaths_averted"])
    order = [r["curve"] for r in rows]          # the page's curve order: lowest toll first
    top = 12000
    assert rows[-1]["deaths_averted"] < top
    out = ['<figure class="af af-toll">',
           '<figcaption><p class="af-title">Deaths a year from PM2.5 in Bengaluru, on each of eight published risk curves</p>'
           f'<p class="af-sub">Annual mean {rows[0]["pm25_before"]:g} μg/m³ at the government monitors in '
           f'{rows[0]["year"]}, down to each curve\'s own floor ({min(r["floor"] for r in rows):g} to '
           f'{max(r["floor"] for r in rows):g} μg/m³).</p></figcaption>',
           '<div class="af-plot">', '<ol class="af-rows">']
    for r in rows:
        d, share = r["deaths_averted"], r["share_of_deaths_averted"] * 100
        out.append(
            f'<li class="af-row" tabindex="0" data-tip="{tip([(short[r["curve"]], ""), ("deaths a year", num(d)), ("share of all deaths", f"{share:.1f}%"), ("life-years a year", num(r["life_years_averted"])), ("floor, μg/m³", f"{r["floor"]:g}")])}">'
            f'<div class="af-name">{e(short[r["curve"]])}</div>'
            f'<div class="af-track"><i class="af-bar" style="width:{pct(d / top * 100)}"></i>'
            f'<b class="af-val" style="left:{pct(d / top * 100)}">{num(d)}</b></div></li>')
    out += ["</ol>", axis([(v / top * 100, num(v)) for v in range(0, top + 1, 4000)]), "</div>",
            table(["Curve", "Deaths a year", "Share of all deaths", "Life-years a year", "Floor, μg/m³"],
                  [[e(r["label"]), num(r["deaths_averted"]), f'{r["share_of_deaths_averted"] * 100:.1f}%',
                    num(r["life_years_averted"]), f'{r["floor"]:g}'] for r in rows]),
            '<p class="af-src"><code>airhealth burden Bengaluru</code>. Three of the curves '
            "(GBD 2019, GBD 2023, GEMM 5 causes) need IHME files that cannot be redistributed.</p>",
            "</figure>"]
    data = {"pm25": rows[0]["pm25_before"], "year": rows[0]["year"],
            "min": num(rows[0]["deaths_averted"]), "max": num(rows[-1]["deaths_averted"]),
            "min_curve": short[rows[0]["curve"]], "max_curve": short[rows[-1]["curve"]],
            "fold": f'{rows[-1]["deaths_averted"] / rows[0]["deaths_averted"]:.1f}',
            "share_min": f'{rows[0]["share_of_deaths_averted"] * 100:.1f}',
            "share_max": f'{max(r["share_of_deaths_averted"] for r in rows) * 100:.1f}',
            "who_multiple": f'{rows[0]["pm25_before"] / 5:.1f}'}
    return "\n".join(out), data, order, [(short[r["curve"]], r["deaths_averted"]) for r in rows]


def fig_cli(model: Path) -> tuple[str, str]:
    """The command the first figure was drawn from, with what it prints: the tool's own stdout,
    cut after the table (the long footnotes stay in the terminal)."""
    r = subprocess.run([sys.executable, "-m", "airhealth.cli", "burden", CITY], capture_output=True, text=True,
                       cwd=model / "health", env={"PYTHONPATH": str(model / "health"), "PATH": "/usr/bin:/bin"})
    if r.returncode:
        sys.exit(f"airhealth burden failed: {(r.stderr or r.stdout)[-300:]}")
    head = lambda s: "\n\n".join(s.split("\n\n")[:2]).rstrip()  # noqa: E731
    text = head(r.stdout)
    # What a reader gets from the one line: the wheel, with no IHME files beside it.
    shown, src = text, ("What the command prints, cut after the table. Its footnotes say which map, "
                        "which death counts and what was scaled.")
    if shutil.which("uvx") and (model / "health/pyproject.toml").exists():
        pub = subprocess.run(["uvx", "--quiet", "--from", str(model / "health"), "airhealth", "burden", CITY],
                             capture_output=True, text=True, cwd=tempfile.gettempdir(),
                             env={k: v for k, v in os.environ.items() if k != "PYTHONPATH"})  # the wheel, not the checkout
        if pub.returncode == 0 and "curve" in pub.stdout:
            shown = head(pub.stdout)
            n_pub, n_all = shown.count("→"), text.count("→")
            not_run = next((ln for ln in pub.stdout.splitlines() if ln.startswith("Not run:")), "")
            if n_pub < n_all:
                src = (f"What the one line prints on a machine with nothing but the tool: {WORDS[n_pub]} curves"
                       + (", the footnotes left out, and its last line" if not_run else ", cut after the table") + ". "
                       f"The other {WORDS[n_all - n_pub]} curves need IHME files that cannot be redistributed; "
                       "the figure above was drawn with them present.")
            if not_run:
                shown += "\n\n[...]\n" + "\n".join(textwrap.wrap(not_run, 96, subsequent_indent="  "))
    return ('<figure class="af af-cli"><div class="af-term">'
            '<p class="af-cmd"><span aria-hidden="true">$ </span>airhealth burden Bengaluru</p>'
            f'<pre tabindex="0" aria-label="Output of airhealth burden Bengaluru">{e(shown)}</pre></div>'
            f'<p class="af-src">{src}</p></figure>'), text


# ---------------------------------------------------------------- 2. the ladder of measures

def by_measure(rank: dict) -> dict:
    out: dict = {}
    for c, t in rank["tables"].items():
        for row in t["rows"]:
            out.setdefault(row["measure"], {})[c] = row
    return out


def ladder_rows(rank: dict, order: list[str], short: dict, partial: dict) -> list[dict]:
    """One dict per scored measure, in the model's own order (rank.spread)."""
    bym = by_measure(rank)
    rows = []
    for s in rank["spread"]:
        cs = bym[s["measure"]]
        a = next(iter(cs.values()))
        if a["status"] != "scored":
            continue
        vals = {c: cs[c]["expected_ly_per_crore"] for c in order
                if c in cs and cs[c].get("expected_ly_per_crore") and not cs[c].get("curve_gap")}
        rows.append({
            "id": s["measure"], "name": MEASURE.get(s["measure"], a["name"]), "full": a["name"],
            "flags": a["flags"], "comparable": a["comparable"], "p": a["p_success"], "vals": vals,
            "gap": [c for c in order if c not in vals],
            "rank": (s["best"], s["worst"]), "rank_c": (s["comparable_best"], s["comparable_worst"]),
            "partial": partial.get(s["measure"], ""),
            "if_works": {c: cs[c]["ly_per_crore_if_works"] for c in vals},
        })
    return rows


def load_whatifs(sens: dict) -> dict:
    """The sensitivity run's labelled what-ifs, per measure: where its ratio and rank land when one
    named thing is different. Never the default; drawn as a pale band beside the default's dots."""
    words = {"whatif:full_cost": "at full cost", "whatif:stubble_lan2022": "on Lan et al.'s smoke figure"}
    out: dict = {}
    for w in sens.get("whatifs", []):
        by: dict = {}
        for r in w["rows"]:
            by.setdefault(r["measure"], {}).setdefault(r["variant"], []).append(r)
        for m, variants in by.items():
            rs = [r for r in variants.get("whatif", []) if r.get("expected_ly_per_crore")]
            if not rs:
                continue
            vals = [r["expected_ly_per_crore"] for r in rs]
            ranks = [r["rank"] for r in rs if r["rank"] is not None]
            rc = [r["rank_comparable"] for r in rs if r.get("rank_comparable") is not None]
            ends = [r["expected_ly_per_crore"] for v in ("whatif_low", "whatif_high") for r in variants.get(v, [])
                    if r.get("expected_ly_per_crore")]
            worst = [r["rank"] for r in variants.get("whatif_high", []) if r["rank"] is not None]
            out[m] = {"id": w["id"], "words": words.get(w["id"], "what-if"), "lo": min(vals), "hi": max(vals),
                      "rank_worst_end": (min(worst), max(worst)) if worst else (None, None),
                      "rank": (min(ranks), max(ranks)) if ranks else (None, None),
                      "rank_c": (min(rc), max(rc)) if rc else (None, None),
                      "ends": (min(ends), max(ends)) if ends else None, "label": w["label"]}
    return out


def fig_ladder(rank: dict, order: list[str], short: dict, partial: dict, *, title: str, sub: str,
               src: str, lo: int, hi: int, ident: str = "", whatifs: dict | None = None) -> tuple[str, list[dict]]:
    rows = ladder_rows(rank, order, short, partial)
    whatifs = whatifs or {}
    for r in rows:
        r["whatif"] = whatifs.get(r["id"])
    span = hi - lo
    x = lambda v: (math.log10(v) - lo) / span * 100  # noqa: E731
    n_all, n_c = len(rows), sum(r["comparable"] for r in rows)
    # do the curves keep their places within a row? (the lowest-toll curve lowest, the highest highest)
    ends = sum(min(r["vals"], key=r["vals"].get) == order[0] and max(r["vals"], key=r["vals"].get) == order[-1]
               for r in rows)
    sub += (f" On {'every row' if ends == n_all else f'{ends} of the {n_all} rows'} the lowest dot is "
            f"{short[order[0]]} and the highest {short[order[-1]]}.")
    out = [f'<figure class="af af-ladder"{f" id={ident!r}" if ident else ""} style="--decades:{span}">',
           f'<figcaption><p class="af-title">{title}</p><p class="af-sub">{sub}</p></figcaption>',
           '<p class="af-key"><span><i class="af-dot"></i>full cost</span>'
           '<span><i class="af-dot is-hollow"></i>cost leaves things out: not comparable with the rest</span>'
           + ('<span><i class="af-ghost"></i>what-if: the same row at full cost, or on Lan et al.\'s smoke figure</span>'
              if any(r["whatif"] for r in rows) else "") + "</p>",
           '<div class="af-plot">',
           '<div class="af-head" aria-hidden="true"><span></span><span></span>'
           f'<span class="af-rk" title="Rank among all {n_all} measures, lowest to highest across the curves">rank of {n_all}</span>'
           f'<span class="af-rk" title="Rank among the {n_c} measures with a full cost">of the {n_c} fully costed</span></div>',
           '<ol class="af-rows">']
    for r in rows:
        vs = [r["vals"][c] for c in order if c in r["vals"]]
        a, b = x(min(vs)), x(max(vs))
        tags = [TAG[f] for f in TAG if f in r["flags"]][:2]
        if r["gap"]:
            tags = [f'{len(r["gap"])} curves start at age 25: no dot, not zero'] + tags[:1]
        tp = [(r["full"], "")] + [(short[c], ratio(r["vals"][c]) if c in r["vals"] else "not covered") for c in order]
        tp += [("odds it works", f'{r["p"]:.0%}')]
        if r["partial"]:
            tp += [("cost", r["partial"])]
        ghost, wi = "", r["whatif"]
        if wi:
            ga, gb = x(max(wi["lo"], 10 ** lo)), x(min(wi["hi"], 10 ** hi))
            ghost = f'<i class="af-ghost" style="left:{pct(ga)};width:{pct(gb - ga)}"></i>'
            line = f'{wi["words"]}: {ratio(wi["lo"])} to {ratio(wi["hi"])}, rank {rng(*wi["rank"])}'
            tags.append(line)
            tp += [("what-if, not the default", wi["label"])]
            if wi["ends"]:
                tp += [("at the range's two ends", f'{ratio(wi["ends"][0])} to {ratio(wi["ends"][1])}')]
        dots = "".join(f'<i class="af-dot" style="left:{pct(x(r["vals"][c]))}"></i>' for c in order if c in r["vals"])
        out.append(
            f'<li class="af-row{"" if r["comparable"] else " is-partial"}" tabindex="0" data-tip="{tip(tp)}">'
            f'<div class="af-name">{e(r["name"])}'
            + (f'<span class="af-tag">{e(", ".join(tags))}</span>' if tags else "") + "</div>"
            f'<div class="af-track">{ghost}<i class="af-span" style="left:{pct(a)};width:{pct(b - a)}"></i>{dots}</div>'
            f'<div class="af-rk">{rng(*r["rank"])}</div><div class="af-rk">{rng(*r["rank_c"])}</div></li>')
    ticks = [(i / span * 100, f"{10 ** (lo + i):,g}") for i in range(span + 1)]
    out += ["</ol>", '<div class="af-foot" aria-hidden="true"><span></span>' + axis(ticks)
            + "<span></span><span></span></div>",
            '<p class="af-xlab">expected life-years per crore rupees (₹10 million) of a funder\'s money, log scale: each step is ten times more</p>',
            "</div>",
            table(["Measure"] + [short[c] for c in order] + ["Odds", "Rank", "Rank, fully costed", "Flags"],
                  [[e(r["full"])] + [ratio(r["vals"][c]) if c in r["vals"] else "not covered" for c in order]
                   + [f'{r["p"]:.0%}', rng(*r["rank"]), rng(*r["rank_c"]),
                      e(", ".join(f.replace("_", " ") for f in r["flags"]))] for r in rows]),
            f'<p class="af-src">{src}</p>', "</figure>"]
    return "\n".join(out), rows


def card(rows: list[dict], order: list[str], toll: dict, *, lo: int, hi: int, src: str, stab: dict | None = None) -> str:
    """The ladder as one 1600x900 image (open the file in a browser at that size and screenshot it).
    Same rows, marks and flags as the page's figure; the claim in the title is computed, not typed."""
    span = hi - lo
    x = lambda v: (math.log10(v) - lo) / span * 100  # noqa: E731
    same = 0
    for r in rows:                      # how many places from the top are identical on every curve
        if r["rank"][0] != r["rank"][1]:
            break
        same += 1
    lis = []
    for r in rows:
        vs = list(r["vals"].values())
        tags = [CARD_TAG[f] for f in CARD_TAG if f in r["flags"]][:2]
        if r["gap"]:
            tags = [f'{len(r["gap"])} curves do not cover children'] + tags[:1]
        dots = "".join(f'<i class="af-dot" style="left:{pct(x(v))}"></i>' for v in vs)
        wi, ghost = r.get("whatif"), ""
        if wi:
            ga, gb = x(max(wi["lo"], 10 ** lo)), x(min(wi["hi"], 10 ** hi))
            ghost = f'<i class="af-ghost" style="left:{pct(ga)};width:{pct(gb - ga)}"></i>'
        lis.append(f'<li class="af-row{"" if r["comparable"] else " is-partial"}"><div class="af-name">{e(r["name"])}'
                   + (f' <span class="af-tag">{e(", ".join(tags))}</span>' if tags else "") + "</div>"
                   f'<div class="af-track">{ghost}<i class="af-span" style="left:{pct(x(min(vs)))};width:{pct(x(max(vs)) - x(min(vs)))}"></i>{dots}</div>'
                   f'<div class="af-rk">{rng(*r["rank"])}</div></li>')
    ticks = [(i / span * 100, f"{10 ** (lo + i):,g}") for i in range(span + 1)]
    css = ""
    return f"""<!doctype html><html lang="en" data-theme="light"><head><meta charset="utf-8">
<link rel="stylesheet" href="/assets/airhealth.css">{css}
<style>
html, body {{ margin: 0; width: 1600px; height: 900px; overflow: hidden; background: var(--bg); }}
.card {{ box-sizing: border-box; width: 1600px; height: 900px; padding: 46px 64px 0; display: flex; flex-direction: column; }}
.card h1 {{ font-family: var(--display); font-size: 38px; line-height: 1.16; margin: 0 0 10px; color: var(--ink); }}
.card .sub {{ font-size: 19px; color: var(--muted); margin: 0 0 12px; }}
.card .af {{ margin: 0; font-size: 18.5px; --decades: {span}; }}
.card .af .af-row, .card .af .af-head, .card .af .af-foot {{ grid-template-columns: 590px minmax(0, 1fr) 96px; column-gap: 22px; }}
.card .af .af-name {{ padding: 0; white-space: nowrap; }}
.card .af .af-tag {{ display: inline; font-size: 14.5px; margin-left: 8px; }}
.card .af .af-track {{ min-height: 32px; }}
.card .af .af-dot {{ width: 12px; height: 12px; margin: -6px 0 0 -6px; }}
.card .af .af-span {{ height: 3px; top: calc(50% - 1.5px); }}
.card .af .af-axis span, .card .af .af-head span {{ font-size: 14.5px; }}
.card .af .af-key {{ font-size: 16px; margin: 0 0 2px; }}
.card .af .af-key .af-dot {{ position: static; margin: 0 8px 0 0; }}
.card .af .af-ghost {{ top: calc(50% - 8px); height: 16px; border-radius: 8px; }}
.card .af .af-key .af-ghost {{ width: 30px; vertical-align: -3px; }}
.card .foot {{ margin-top: auto; padding: 0 0 22px; display: flex; justify-content: space-between; font-size: 15px; color: var(--muted); }}
</style></head><body><div class="card">
<h1>Eight risk curves put Bengaluru's PM2.5 toll between {toll["min"]} and {toll["max"]} deaths a year. The first {WORDS[same] if same < len(WORDS) else same} measures against it are the same on all eight.</h1>
<p class="sub">Expected life-years per crore rupees of a funder's money, {len(rows)} measures. One dot per curve, log scale.{" Which curve you believe never changes the top " + WORDS[stab["top"]] + "; which study of the city's sources you believe does." if stab and stab.get("same_measures_every_combo") else ""}</p>
<figure class="af af-ladder">
<p class="af-key"><span><i class="af-dot"></i>full cost</span><span><i class="af-dot is-hollow"></i>cost leaves things out: not comparable with the rest</span>{'<span><i class="af-ghost"></i>what-if: at full cost, or on Lan et al. 2022&#39;s smoke figure</span>' if any(r.get("whatif") for r in rows) else ""}</p>
<div class="af-head"><span></span><span></span><span class="af-rk">rank</span></div>
<ol class="af-rows">{"".join(lis)}</ol>
<div class="af-foot"><span></span>{axis(ticks)}<span></span></div>
</figure>
<div class="foot"><span>{src}</span><span>airhealth.dev</span></div>
</div></body></html>
"""


def film(cli_text: str, toll_rows: list[tuple[str, float]], rows: list[dict], order: list[str], short: dict,
         toll: dict, counts: dict, *, lo: int, hi: int, agent_line: str, stab: dict | None = None) -> str:
    """The launch film as one page, 1280x720. render(t) draws the state at t seconds, so the film can
    be re-made whenever the numbers change: open the page with #frame in a scripted browser, call
    render(i / 30) and screenshot for i = 0..DUR*30, then
    `ffmpeg -framerate 30 -i f%04d.png -c:v libx264 -pix_fmt yuv420p -crf 17 film.mp4`.
    Opened without #frame it plays in real time. Every caption with a claim in it is computed."""
    span = hi - lo
    x = lambda v: (math.log10(v) - lo) / span * 100  # noqa: E731
    T_TERM, T_TOLL, T_LAD = 0.0, 5.4, 10.6
    T_END = (T_LAD + 1.2 + len(order) * 0.8 + 0.9 + (5.0 if stab and stab.get("same_measures_every_combo") else 2.6)
             + 3.0 + (3.6 if any(r.get("whatif") for r in rows) else 0))
    T_STOP = T_END + 4.5
    same = 0
    for r in rows:
        if r["rank"][0] != r["rank"][1]:
            break
        same += 1
    first_costed = next((r for r in rows if r["rank_c"] == (1, 1)), None)

    lines = cli_text.split("\n")
    term = "".join(f'<span class="ln" data-at="{T_TERM + 1.9 + i * 0.13:.2f}" data-dur="0.01">{e(ln) or " "}</span>'
                   for i, ln in enumerate(lines))
    top = 12000
    bars = "".join(
        f'<li><span class="nm">{e(n)}</span><span class="tr"><i class="bar" data-at="{T_TOLL + 0.5 + i * 0.22:.2f}" data-dur="0.6" data-grow '
        f'style="width:{pct(d / top * 100)}"></i><b data-at="{T_TOLL + 1.0 + i * 0.22:.2f}" style="left:{pct(d / top * 100)}">{num(d)}</b></span></li>'
        for i, (n, d) in enumerate(toll_rows))
    t_dots = T_LAD + 1.2
    step = 0.8
    lis = []
    for j, r in enumerate(rows):
        vs = [r["vals"][c] for c in order if c in r["vals"]]
        dots = "".join(f'<i class="af-dot" data-at="{t_dots + k * step + j * 0.015:.2f}" data-dur="0.3" data-pop style="left:{pct(x(r["vals"][c]))}"></i>'
                       for k, c in enumerate(order) if c in r["vals"])
        lis.append(f'<li class="af-row{"" if r["comparable"] else " is-partial"}"><div class="af-name" data-at="{T_LAD + 0.2 + j * 0.03:.2f}">{e(r["name"])}</div>'
                   f'<div class="af-track"><i class="af-span" data-at="{t_dots + len(order) * step:.2f}" data-dur="0.6" data-grow '
                   f'style="left:{pct(x(min(vs)))};width:{pct(x(max(vs)) - x(min(vs)))}"></i>{dots}</div>'
                   f'<div class="af-rk" data-at="{t_dots + len(order) * step + 0.9:.2f}">{rng(*r["rank"])}</div></li>')
    t_rank = t_dots + len(order) * step + 0.9
    curve_tags = "".join(f'<span class="cap small" data-from="{t_dots + k * step:.2f}" data-to="{t_dots + (k + 1) * step:.2f}" data-fade="0.12">'
                         f'curve {k + 1} of {len(order)}: {e(short[c])}</span>' for k, c in enumerate(order))
    ticks = [(i / span * 100, f"{10 ** (lo + i):,g}") for i in range(span + 1)]
    t_hollow = t_rank + (5.0 if stab and stab.get("same_measures_every_combo") else 2.6)
    has_ghost = any(r.get("whatif") for r in rows)
    caps = [
        (T_LAD, t_dots + 3 * step, f'{len(rows)} measures against it. Expected life-years per crore rupees, one dot per curve.'),
        (t_dots + 3 * step, t_rank, "A curve that counts more deaths counts more for every measure."),
        (t_rank, t_rank + 2.6, f'The first {WORDS[same] if same < len(WORDS) else same} places are the same on all eight curves.' if same
         else "No place is the same on all eight curves."),
    ]
    if stab and stab.get("same_measures_every_combo"):
        caps.append((t_rank + 2.6, t_hollow, f'On every exposure map and either study of the city\'s sources, the curve never changes the top {WORDS[stab["top"]]}. The study does.'))
    caps.append((t_hollow, t_hollow + 3.0, "Hollow marks: the cost leaves things out."
                 + (f' Among the fully costed, {first_costed["name"][0].lower() + first_costed["name"][1:] if not first_costed["name"].startswith("LPG") else first_costed["name"]} come first on every curve.'
                    if first_costed else "")))
    if has_ghost:
        caps.append((t_hollow + 3.0, T_END, "Pale bands: the same rows at full cost, and on Lan et al.'s larger smoke figure."))
    else:
        caps[-1] = (caps[-1][0], T_END, caps[-1][2])
    for j, r in enumerate(rows):   # the what-if bands arrive with their caption
        wi = r.get("whatif")
        if wi:
            ga, gb = x(max(wi["lo"], 10 ** lo)), x(min(wi["hi"], 10 ** hi))
            lis[j] = lis[j].replace('<div class="af-track">', '<div class="af-track"><i class="af-ghost" data-at="'
                                    f'{t_hollow + 3.2:.2f}" data-dur="0.6" data-grow style="left:{pct(ga)};width:{pct(gb - ga)};transform-origin:left"></i>', 1)
    cap_html = "".join(f'<p class="cap" data-from="{a:.2f}" data-to="{b:.2f}">{e(t)}</p>' for a, b, t in caps)
    css = ""
    return f"""<!doctype html><html lang="en" data-theme="light"><head><meta charset="utf-8"><title>air apocalypse: film</title>
<link rel="stylesheet" href="/assets/airhealth.css">{css}
<style>
html, body {{ margin: 0; width: 1280px; height: 720px; overflow: hidden; background: var(--bg); }}
.film {{ position: relative; width: 1280px; height: 720px; font-family: var(--text); color: var(--ink); }}
.sc {{ position: absolute; inset: 0; box-sizing: border-box; padding: 44px 56px; }}
.cap {{ position: absolute; left: 56px; right: 56px; top: 34px; margin: 0; font-family: var(--display); font-size: 33px; line-height: 1.18; color: var(--ink); }}
.cap.small {{ top: auto; bottom: 22px; left: auto; right: 56px; font-family: var(--text); font-size: 17px; color: var(--muted); }}
.term {{ margin: 70px auto 0; width: 1010px; border: 1px solid var(--line); border-radius: 10px; background: var(--surface); box-shadow: 0 10px 40px rgb(0 0 0 / .08); }}
.term .cmd {{ margin: 0; padding: 14px 20px; border-bottom: 1px solid var(--line); font: 600 19px ui-monospace, "SF Mono", Menlo, monospace; min-height: 24px; }}
.term .cmd span {{ color: var(--muted); font-weight: 400; }}
.term pre {{ margin: 0; padding: 16px 20px 20px; border: 0; background: none; font: 15.5px/1.55 ui-monospace, "SF Mono", Menlo, monospace; color: var(--ink); min-height: 300px; }}
.term .ln {{ display: block; white-space: pre; }}
.toll {{ list-style: none; margin: 150px 0 0; padding: 0; }}
.toll li {{ display: grid; grid-template-columns: 250px 1fr; align-items: center; height: 46px; font-size: 22px; }}
.toll .tr {{ position: relative; height: 100%; margin-right: 150px; border-left: 1px solid var(--accent-line); }}
.toll .bar {{ position: absolute; left: 0; top: 17px; height: 12px; border-radius: 0 6px 6px 0; background: var(--accent); transform-origin: left; }}
.toll b {{ position: absolute; top: 50%; transform: translateY(-50%); margin-left: 12px; font-variant-numeric: tabular-nums; }}
.lad {{ position: absolute; left: 56px; right: 56px; top: 132px; }}
.lad .af {{ margin: 0; font-size: 17px; --decades: {span}; }}
.lad .af .af-row, .lad .af .af-foot {{ grid-template-columns: 420px minmax(0, 1fr) 78px; column-gap: 20px; }}
.lad .af .af-name {{ padding: 0; white-space: nowrap; }}
.lad .af .af-track {{ min-height: 30px; }}
.lad .af .af-dot {{ width: 11px; height: 11px; margin: -5.5px 0 0 -5.5px; }}
.lad .af .af-span {{ height: 3px; top: calc(50% - 1.5px); transform-origin: left; }}
.lad .af .af-axis span {{ font-size: 13.5px; }}
.end {{ display: flex; flex-direction: column; justify-content: center; height: 100%; }}
.end h1 {{ font-family: var(--display); font-size: 64px; line-height: 1.05; margin: 0 0 18px; color: var(--accent); }}
.end p {{ font-size: 25px; margin: 0 0 26px; max-width: 980px; }}
.end code {{ display: block; width: fit-content; font: 17px ui-monospace, "SF Mono", Menlo, monospace; background: var(--surface); border: 1px solid var(--accent-line); border-radius: 8px; padding: 12px 16px; color: var(--ink); }}
.end small {{ display: block; margin-top: 12px; font-size: 16px; color: var(--muted); }}
</style></head><body><div class="film">
<section class="sc" data-from="{T_TERM}" data-to="{T_TOLL}"><div class="term"><p class="cmd"><span>$ </span><b data-type="airhealth burden Bengaluru" data-at="0.4" data-cps="26"></b></p><pre>{term}</pre></div></section>
<section class="sc" data-from="{T_TOLL}" data-to="{T_LAD}">
<p class="cap" data-from="{T_TOLL}" data-to="{T_TOLL + 3.2}">Bengaluru's monitors, {toll["year"]}: {toll["pm25"]} μg/m³ of PM2.5. Eight published risk curves turn that into deaths.</p>
<p class="cap" data-from="{T_TOLL + 3.2}" data-to="{T_LAD}">Between {toll["min"]} and {toll["max"]} deaths a year.</p>
<ol class="toll">{bars}</ol></section>
<section class="sc" data-from="{T_LAD}" data-to="{T_END}">{cap_html}{curve_tags}
<div class="lad"><figure class="af af-ladder"><ol class="af-rows">{"".join(lis)}</ol>
<div class="af-foot"><span></span>{axis(ticks)}<span></span></div></figure></div></section>
<section class="sc" data-from="{T_END}" data-to="{T_STOP + 1}"><div class="end"><h1>airhealth.dev</h1>
<p>An open model of India's air: {counts["cities"]} cities, {len(order)} risk curves, {counts["measures"]} measures, every number read at its source.</p>
<code>{e(agent_line)}</code><small>Paste that into your agent, or run the tool yourself.</small></div></section>
</div>
<script>
var DUR = {T_STOP};
function clamp(v) {{ return Math.max(0, Math.min(1, v)); }}
function ease(p) {{ return 1 - Math.pow(1 - p, 3); }}
function render(t) {{
  document.querySelectorAll("[data-from]").forEach(function (el) {{
    var a = +el.dataset.from, b = +el.dataset.to, f = +(el.dataset.fade || 0.3);
    var o = Math.min(clamp((t - a) / f), clamp((b - t) / f));
    if (a === 0) o = clamp((b - t) / f);
    el.style.opacity = o; el.style.visibility = o > 0 ? "visible" : "hidden";
  }});
  document.querySelectorAll("[data-at]").forEach(function (el) {{
    var p = clamp((t - +el.dataset.at) / +(el.dataset.dur || 0.35));
    if (el.dataset.type !== undefined) {{ el.textContent = el.dataset.type.slice(0, Math.max(0, Math.floor((t - +el.dataset.at) * +el.dataset.cps))); return; }}
    el.style.opacity = p > 0 ? Math.max(p, 0.001) : 0;
    if (el.dataset.grow !== undefined) el.style.transform = "scaleX(" + ease(p) + ")";
    if (el.dataset.pop !== undefined) el.style.transform = "scale(" + (0.3 + 0.7 * ease(p)) + ")";
  }});
}}
window.render = render;
if (location.hash === "#frame") render(0);
else {{ var t0 = performance.now(); (function loop() {{ var t = ((performance.now() - t0) / 1000) % (DUR + 1.5); render(Math.min(t, DUR)); requestAnimationFrame(loop); }})(); }}
</script></body></html>
"""


# ---------------------------------------------------------------- 3. what moves the top five

def unit_label(u: str) -> str:
    kind, _, m = u.partition(":")
    name = MEASURE.get(m, m)
    if name and name[:3] not in ("LPG", "N95", "HEP") and not name[0].isdigit():
        name = name[0].lower() + name[1:]
    return {"effect": f"How much it cuts: {name}", "cost": f"What it costs: {name}",
            "study": "Which study of the city's sources (APnA model or CSTEP's receptor study)",
            "odds": "The odds each measure works (all set to certain)",
            "map": "Which exposure map (four alternatives)",
            "deaths": "Which death counts (two alternatives)",
            "discount": "No discounting, against 3% a year",
            "monthly_curves": "Curves applied month by month",
            "seed": "Another random seed: the noise floor"}[kind]


def fig_moves(sens: dict, order: list[str], short: dict) -> tuple[str, dict]:
    ra = {r["unit"]: r for r in sens["research"]}
    rc = {r["unit"]: r for r in sens["research_comparable"]}
    n_all = sum(1 for s in sens["base"]["spread"] if s["best"] is not None)
    n_c = sum(1 for s in sens["base"]["spread"] if s["comparable_best"] is not None)
    # The model's noise-robust count: a change counts only when it is tied to a measure moving by
    # more than other random seeds move it. (Older runs have only the raw count.)
    robust = "noise_robust" in sens["research"][0]
    cnt = lambda r: r["noise_robust"] if robust else r["curves_top_changed"]  # noqa: E731
    crv = lambda r: r["curves_noise_robust"] if robust else r["curves"]  # noqa: E731
    always = ["map", "deaths", "discount", "monthly_curves"]
    hidden = {"seed"} if robust else set()
    if not robust:
        always.append("seed")
    moving = [u for u in ra if (cnt(ra[u]) or cnt(rc[u])) and u not in always and u not in hidden]
    moving.sort(key=lambda u: (-cnt(ra[u]), -cnt(rc[u]), u))
    still = [u for u in ra if u not in moving and u not in always and u not in hidden]
    tied = sorted({m for ms in sens.get("noise_sets_comparable", {}).values() for m in ms}
                  | {m for ms in sens.get("noise_sets", {}).values() for m in ms})

    def strip(r: dict) -> str:
        on = set(crv(r))
        return ('<div class="af-strip">' + "".join(f'<i class="{"on" if c in on else ""}"></i>' for c in order)
                + f'<b>{cnt(r)}</b></div>')

    k = sens["top"]
    out = ['<figure class="af af-moves">',
           f'<figcaption><p class="af-title">Which inputs change Bengaluru\'s top {k} measures</p>'
           '<p class="af-sub">Each input moved one at a time: an effect or a cost to the low and the high end of its range, '
           "a source swapped for its alternative. One square per risk curve, filled where the top "
           f"{k} changes on that curve" + (" by more than a different random seed changes it" if robust else "")
           + ".</p></figcaption>",
           '<div class="af-plot">',
           '<div class="af-head" aria-hidden="true"><span></span>'
           f'<span class="af-sh">all {n_all} measures</span><span class="af-sh">the {n_c} fully costed</span></div>',
           '<ol class="af-rows">']
    trs = []
    for u in moving + always:
        a, c = ra[u], rc[u]
        cls = " is-null" if u in always else ""
        tp = [(unit_label(u), "")] + [
            (short[cu], ("changes" if cu in crv(a) else "same") + " / " + ("changes" if cu in crv(c) else "same"))
            for cu in order] + [("largest move, places", f'{a["max_abs_delta"]:g} / {c["max_abs_delta"]:g}')]
        out.append(f'<li class="af-row{cls}" tabindex="0" data-tip="{tip(tp)}"><div class="af-name">{e(unit_label(u))}</div>'
                   f"{strip(a)}{strip(c)}</li>")
        trs.append([e(unit_label(u)), f'{cnt(a)} of 8', f'{a["max_abs_delta"]:g}',
                    f'{cnt(c)} of 8', f'{c["max_abs_delta"]:g}'])
    ctx = sens["base"]["context"]
    if robust:
        note = (f"The other {len(still)} effect and cost ranges change neither list on any curve."
                + (f' {" and ".join(MEASURE.get(m, m) for m in tied)} are tied, so a swap between them is not counted.'
                   if tied else ""))
    else:
        note = (f"The other {len(still)} effect and cost ranges change neither list on any curve. "
                "Among the fully costed, a different random seed alone swaps fifth and sixth place on every curve, "
                f"so that boundary is noise at {ctx['n']} runs.")
    out += ["</ol>", "</div>", f'<p class="af-note">{e(note)}</p>',
            table(["Input", f"All measures: curves where the top {k} changes", "Largest move, places",
                   "Fully costed: curves", "Largest move, places"], trs),
            f'<p class="af-src"><code>airhealth rank Bengaluru --sensitivity</code>, {ctx["n"]:,} runs per curve, '
            f'{ctx["map"].replace("acag_total", "ACAG")} map.</p>', "</figure>"]
    data = {"top": k, "n_all": n_all, "n_fully_costed": n_c, "still": len(still), "runs": f'{ctx["n"]:,}',
            "noise_robust": robust,
            "units": {u: {"all": cnt(ra[u]), "costed": cnt(rc[u]),
                          "max_move": f'{max(ra[u]["max_abs_delta"], rc[u]["max_abs_delta"]):g}'} for u in ra}}
    return "\n".join(out), data


# ---------------------------------------------------------------- 3b. is the top the same on every curve?

MAP = {"acag_total": "ACAG, satellite-derived", "aqli": "AQLI, satellite-derived", "cpcb": "CPCB ground monitors"}
STUDY = {"apna": "APnA emissions model", "cstep": "CSTEP receptor study"}


def fig_stability(st: dict) -> tuple[str, dict]:
    """The model's stability report as a table: for each exposure map and each study of the city's
    sources, whether the top of the ranking is the same on all eight curves, and what it is."""
    k = st["top"]

    def cell(c: dict) -> str:
        tops = list(c["top"].values())
        names = [MEASURE.get(m, m) for m in tops[0]]
        if c["same_top"]:
            verdict = "same on every curve"
        elif c["same_members"]:
            verdict = "same measures on every curve, order differs"
            names = sorted({MEASURE.get(m, m) for t in tops for m in t})
        else:
            verdict = "differs between curves"
            names = sorted({MEASURE.get(m, m) for t in tops for m in t})
        return f'<b>{verdict}</b><br>{e("; ".join(names))}'

    rows = []
    for c in st["combos"]:
        study = next((v for p, v in STUDY.items() if c["study"].startswith(p)), c["study"])
        note = "" if c.get("regional_ranked", True) else '<br><span class="af-tag">regional measures cannot be ranked on this map</span>'
        rows.append(f'<tr><td>{e(MAP.get(c["map"], c["map"]))}{note}</td><td>{e(study)}</td>'
                    f'<td>{cell(c["all"])}</td><td>{cell(c["comparable"])}</td></tr>')
    every = all(c[w]["same_members"] for c in st["combos"] for w in ("all", "comparable"))
    exact = sum(c[w]["same_top"] for c in st["combos"] for w in ("all", "comparable"))
    widest = max(st["largest_move"].items(), key=lambda kv: kv[1]["move"])
    out = ['<figure class="af af-stab">',
           f'<figcaption><p class="af-title">Is Bengaluru\'s top {WORDS[k]} the same on all eight risk curves?</p>'
           f'<p class="af-sub">Checked on each exposure map and each study of the city\'s sources, {st["n"]:,} runs per curve.</p></figcaption>',
           '<div class="af-scroll"><table class="af-tbl"><thead><tr><th>Exposure map</th><th>Source study</th>'
           '<th>All measures</th><th>Fully costed only</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>",
           '<p class="af-src"><code>health/scripts/stability_report.py Bengaluru</code>. '
           + " ".join(f"{e(v[0].upper() + v[1:])}." for v in st.get("maps_skipped", {}).values()) + "</p>", "</figure>"]
    tops_all = st["overall"]["all"]["tops"]
    data = {"top": k, "runs": f'{st["n"]:,}', "combos": len(st["combos"]), "maps": len(st["maps"]), "studies": len(st["studies"]),
            "same_measures_every_combo": every, "same_order_cells": exact, "cells": 2 * len(st["combos"]),
            "distinct_tops_all": len(tops_all), "widest_move": widest[1]["move"],
            "widest_move_measure": MEASURE.get(widest[0], widest[0])}
    return "\n".join(out), data


# ---------------------------------------------------------------- 4. where the smoke goes

def fig_smoke(model: Path) -> tuple[str, dict]:
    src = tomllib.loads((model / "health/data/sources.toml").read_text())["receptor_stubble.csv"]
    m = re.search(r"population-weighted ([\d.]+) against ([\d.]+) .g/m³", src["caveat"])
    ours, lan = float(m.group(1)), float(m.group(2))
    line = next(ln for ln in (model / "health/benchmarks/RANKING.md").read_text().splitlines()
                if ln.startswith("| jjkp2025_pes_vs_fgd"))
    cells = [c.strip() for c in line.strip("|").split("|")]
    paper, model_ratio = float(cells[2]), float(cells[3])

    def pair(title: str, unit: str, rows: list[tuple[str, float, str, str]]) -> str:
        top = max(v for _, v, _, _ in rows)
        h = [f'<div class="af-pair"><p class="af-ptitle">{title}</p><ol class="af-rows">']
        for name, v, label, cls in rows:
            h.append(f'<li class="af-row {cls}"><div class="af-name">{name}</div><div class="af-track">'
                     f'<i class="af-bar" style="width:{pct(v / top * 92)}"></i>'
                     f'<b class="af-val" style="left:{pct(v / top * 92)}">{label}</b></div></li>')
        h.append(f'</ol><p class="af-xlab">{unit}</p></div>')
        return "".join(h)

    out = ['<figure class="af af-smoke">',
           '<figcaption><p class="af-title">The model\'s smoke table against the published figures</p>'
           "</figcaption>", '<div class="af-pairs">',
           pair("India's exposure to crop-burning smoke", "μg/m³, population-weighted annual mean",
                [("Lan et al. 2022", lan, f"{lan:g}", ""), ("This model's stand-in table", ours, f"{ours:g}", "is-hole")]),
           pair("Paying farmers not to burn, against scrubbers on coal plants",
                "times as many lives per rupee",
                [("Jack et al. 2023, working paper", paper, f"{paper:.0f}×", ""),
                 ("This model", model_ratio, f"{model_ratio:.1f}×", "is-hole")]),
           "</div>",
           '<p class="af-src">Stand-in table: McDuffie et al. 2021\'s global source shares × 2023 satellite PM2.5 '
           "(<code>health/data/receptor_stubble.csv</code>). Benchmark: <code>health/benchmarks/RANKING.md</code>, "
           "case <code>jjkp2025_pes_vs_fgd</code>. The table is not scaled to close the gap.</p>", "</figure>"]
    data = {"ours": f"{ours:g}", "lan": f"{lan:g}", "fold": f"{lan / ours:.0f}",
            "paper_ratio": f"{paper:.0f}", "model_ratio": f"{model_ratio:.1f}"}
    return "\n".join(out), data


# ---------------------------------------------------------------- 5. Bengaluru through the day

def fig_day() -> tuple[str, dict]:
    from citypage import ground
    series = {s: [float(v) for v in ground.hour_of_day(CITY, "pm25", m).values] for s, m in ground.SEASONS.items()}
    top = 60
    assert max(max(v) for v in series.values()) < top
    X = lambda h: h / 23 * 100  # noqa: E731
    Y = lambda v: 100 - v / top * 100  # noqa: E731
    strong = {"Dec-Feb", "Jun-Sep"}
    paths, labels = [], []
    for s, vs in series.items():
        d = " ".join(f'{"M" if h == 0 else "L"}{X(h):.2f} {Y(v):.2f}' for h, v in enumerate(vs))
        paths.append(f'<path class="{"hi" if s in strong else "lo"}" d="{d}"/>')
        if s in strong:
            labels.append(f'<span class="af-end" style="top:{pct(Y(vs[-1]))}">{e(SEASON[s])}</span>')
    quiet = [s for s in series if s not in strong]   # two lines that end together share one label
    labels.append(f'<span class="af-end lo" style="top:{pct(Y(sum(series[s][-1] for s in quiet) / len(quiet)))}">'
                  f'{e(" and ".join(SEASON[s] for s in quiet))}</span>')
    w, mo = series["Dec-Feb"], series["Jun-Sep"]
    marks = [(w.index(max(w)), max(w), "above"), (w.index(min(w)), min(w), "below"),
             (mo.index(max(mo)), max(mo), "above"), (mo.index(min(mo)), min(mo), "below")]
    dots = "".join(f'<i class="af-dot" style="left:{pct(X(h))};top:{pct(Y(v))}"></i>'
                   f'<b class="af-pt {pos}" style="left:{pct(X(h))};top:{pct(Y(v))}">{v:.0f}</b>' for h, v, pos in marks)
    grid = "".join(f'<i class="af-gl" style="top:{pct(Y(v))}"><b>{v}</b></i>' for v in range(0, top + 1, 20))
    hours = axis([(X(h), f"{h:02d}:00") for h in (0, 6, 12, 18, 23)])
    fm = lambda v: f"{v:.0f}"  # noqa: E731
    out = ['<figure class="af af-day">',
           '<figcaption><p class="af-title">Bengaluru\'s PM2.5 through the day, by season</p>'
           '<p class="af-sub">μg/m³, every monitor-hour from 2016 to 2025 pooled. India\'s annual standard is 40, '
           "the WHO guideline 5.</p></figcaption>",
           '<div class="af-plot"><div class="af-canvas">', grid,
           '<svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">' + "".join(paths) + "</svg>",
           dots, "".join(labels), "</div>", hours, "</div>",
           table(["Hour"] + [SEASON[s] for s in series],
                 [[f"{h:02d}:00"] + [f"{series[s][h]:.1f}" for s in series] for h in range(24)]),
           '<p class="af-src">Central Pollution Control Board monitors, <code>health/data/cpcb_city_month_hour.csv</code>. '
           "The season groupings are a choice made for the chart.</p>", "</figure>"]
    data = {"winter_peak": fm(max(w)), "winter_peak_hour": w.index(max(w)), "winter_low": fm(min(w)),
            "winter_low_hour": w.index(min(w)), "monsoon_low": fm(min(mo)), "monsoon_high": fm(max(mo))}
    return "\n".join(out), data


# ---------------------------------------------------------------- 6. fifty cities

def fig_cities(model: Path, order: list[str], short: dict) -> tuple[str, dict]:
    cities = [r["city"] for r in csv.DictReader(open(model / "health/data/cities.csv"))]
    rows = []
    for c in cities:
        b = cli(model, "burden", c, "--kind", "city", "--map", "acag_total")
        by = {r["curve"]: r for r in b["rows"]}
        rows.append({"city": c, "pm": b["rows"][0]["pm25_before"], "year": b["rows"][0]["year"],
                     "share": {k: by[k]["share_of_deaths_averted"] * 100 for k in order if k in by},
                     "deaths": {k: by[k]["deaths_averted"] for k in order if k in by}})
    rows.sort(key=lambda r: -r["pm"])
    top = 60
    assert max(max(r["share"].values()) for r in rows) < top
    out = ['<figure class="af af-cities">',
           '<figcaption><p class="af-title">Share of all deaths attributed to PM2.5 in fifty cities, on the same eight curves</p>'
           f'<p class="af-sub">Dirtiest first. Annual mean PM2.5 in {rows[0]["year"]} from the ACAG satellite-derived map, '
           "so that all fifty are measured the same way; each curve down to its own floor.</p></figcaption>",
           '<div class="af-plot">',
           '<div class="af-head" aria-hidden="true"><span></span><span class="af-pm">μg/m³</span><span></span></div>',
           '<ol class="af-rows">']
    for r in rows:
        vs = list(r["share"].values())
        tp = [(r["city"], f'{r["pm"]:.0f} μg/m³')] + [(short[c], f'{r["share"][c]:.1f}% · {num(r["deaths"][c])} deaths') for c in order]
        dots = "".join(f'<i class="af-dot" style="left:{pct(v / top * 100)}"></i>' for v in vs)
        out.append(f'<li class="af-row{" is-city" if r["city"] == CITY else ""}" tabindex="0" data-tip="{tip(tp)}">'
                   f'<div class="af-name">{e(r["city"])}</div><div class="af-pm">{r["pm"]:.0f}</div>'
                   f'<div class="af-track"><i class="af-span" style="left:{pct(min(vs) / top * 100)};'
                   f'width:{pct((max(vs) - min(vs)) / top * 100)}"></i>{dots}</div></li>')
    out += ["</ol>", '<div class="af-foot" aria-hidden="true"><span></span><span></span>'
            + axis([(v / top * 100, f"{v}%") for v in range(0, top + 1, 20)]) + "</div>",
            "</div>",
            table(["City", "PM2.5"] + [short[c] for c in order],
                  [[e(r["city"]), f'{r["pm"]:.1f}'] + [f'{r["share"][c]:.1f}%' for c in order] for r in rows]),
            '<p class="af-src"><code>airhealth burden CITY --map acag_total</code>. City populations are Census 2011, '
            "scaled to the map's year.</p>", "</figure>"]
    blr = next(r for r in rows if r["city"] == CITY)
    data = {"n": len(rows), "year": rows[0]["year"], "dirtiest": rows[0]["city"], "dirtiest_pm": f'{rows[0]["pm"]:.0f}',
            "cleanest": rows[-1]["city"], "cleanest_pm": f'{rows[-1]["pm"]:.0f}',
            "dirtiest_share_min": f'{min(rows[0]["share"].values()):.0f}',
            "dirtiest_share_max": f'{max(rows[0]["share"].values()):.0f}',
            "above_40": sum(r["pm"] > 40 for r in rows), "bengaluru_place": rows.index(blr) + 1}
    return "\n".join(out), data


# ---------------------------------------------------------------- main

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="src", type=Path, default=DEFAULT_FROM,
                    help="directory of canonical model outputs (default: health/out/launch-19fb04c)")
    ap.add_argument("--model", type=Path, default=ROOT, help="air-apocalypse checkout (default: this repository)")
    ap.add_argument("--rank", type=Path, help="override <from>/rank5000")
    ap.add_argument("--sensitivity", type=Path, help="override <from>/sens2000")
    ap.add_argument("--stability", type=Path, help="override <from>/stab/stability_bengaluru.json")
    ap.add_argument("--rank-commit", help="the commit the rank directory was run at, if not the model's")
    ap.add_argument("--only", default="", help="comma-separated figure names, to skip the slow ones")
    ap.add_argument("--commit", help="the model's commit, when --model is an export and not a checkout")
    a = ap.parse_args()
    a.src = a.src.expanduser().resolve()
    a.rank = a.rank or a.src / "rank5000"
    a.sensitivity = a.sensitivity or a.src / "sens2000"
    a.stability = a.stability or a.src / "stab/stability_bengaluru.json"
    a.film, a.card = SRC / "film.html", SRC / "card.html"
    for need in (a.rank / "rank_bengaluru.json", a.rank / "rank_india.json"):
        if not need.exists():
            sys.exit(f"missing {need}: pass --from a directory of model outputs (see --help)")
    model = a.model.expanduser().resolve()
    sys.path[:0] = [str(model / "health"), str(model / "cities")]
    from airhealth.charts import SHORT as short

    inc = FIG
    inc.mkdir(parents=True, exist_ok=True)
    data_path = DATA
    data = json.loads(data_path.read_text()) if data_path.exists() else {}
    only = set(filter(None, a.only.split(",")))
    want = lambda k: not only or k in only  # noqa: E731

    toll_html, toll, order, toll_rows = fig_toll(model, short)
    cli_html, cli_text = fig_cli(model)
    if want("toll"):
        (inc / "toll.html").write_text(toll_html + "\n")
        data["toll"] = toll
        (inc / "cli.html").write_text(cli_html + "\n")

    partial = {}
    for f in (model / "health/interventions/library").glob("[!_]*.toml"):
        partial[f.stem] = tomllib.loads(f.read_text()).get("cost", {}).get("partial", "")

    stab_html, stab = (fig_stability(json.loads(a.stability.read_text()))
                       if a.stability and a.stability.exists() else ("", None))
    sens_path = (a.sensitivity or a.rank) / "sensitivity_bengaluru.json"
    sens = json.loads(sens_path.read_text()) if sens_path.exists() else {}
    whatifs = load_whatifs(sens)

    if want("ladder"):
        rank = json.loads((a.rank / "rank_bengaluru.json").read_text())
        ctx = rank["context"]
        h, rows = fig_ladder(
            rank, order, short, partial, ident="ladder", lo=-2, hi=4, whatifs=whatifs,
            title="What a crore buys in Bengaluru: 17 measures, each on eight risk curves".replace(
                "17", str(sum(1 for s in rank["spread"] if s["best"] is not None))),
            sub="Each dot is one curve's answer. The line runs from the lowest curve to the highest. "
                "Expected means the life-years if the measure works times the odds that it does; the odds are judgements.",
            src=f'<code>airhealth rank Bengaluru</code>, {ctx["n"]:,} runs per curve, seed {ctx["seed"]}, ACAG map, '
                f'APnA source shares, costs in 2025 rupees discounted at {ctx["discount"]:.0%}. '
                "Regional measures (stubble, scrubbers, paddy) carry their whole region's ratio. "
                "Measures are ranked one at a time; their benefits do not add up.")
        (inc / "ladder.html").write_text(h + "\n")
        by = {r["id"]: r for r in rows}
        lo_hi = lambda r: {"lo": ratio(min(r["vals"].values())), "hi": ratio(max(r["vals"].values()))}  # noqa: E731
        data["ladder"] = {"n_scored": len(rows), "n_fully_costed": sum(r["comparable"] for r in rows),
                          "runs": f'{ctx["n"]:,}',
                          "same_rank_everywhere": sum(r["rank"][0] == r["rank"][1] for r in rows),
                          "top3_same": all(r["rank"][0] == r["rank"][1] for r in rows[:3]),
                          "max_span": max(r["rank"][1] - r["rank"][0] for r in rows),
                          "measures": {k: lo_hi(r) | {"rank": rng(*r["rank"]), "rank_costed": rng(*r["rank_c"])}
                                       for k, r in by.items()}}
        data["library"] = {"n": len(partial)}
        if a.card:
            a.card.parent.mkdir(parents=True, exist_ok=True)
            a.card.write_text(card(rows, order, toll, lo=-2, hi=4, stab=stab,
                                   src=f'Toll at the {toll["year"]} monitor mean, {toll["pm25"]} μg/m³. '
                                       f'airhealth rank Bengaluru, {ctx["n"]:,} runs per curve. Odds are judgements; '
                                       "measures are ranked one at a time."))
        # where each measure can be scored at all: the ranking is deep in one city, thin across fifty
        india = json.loads((a.rank / "rank_india.json").read_text())
        where: dict = {}
        for cname, part in india.get("parts", {}).items():
            for row in next(iter(part["tables"].values()))["rows"]:
                if row["status"] == "scored" and row["scope"] != "region":
                    where.setdefault(row["measure"], set()).add(cname)
        n_cities = len(india.get("parts", {}))
        data["coverage"] = {
            "cities": n_cities,
            "wide": sorted(k for k, v in where.items() if len(v) >= n_cities - 1),
            "single": sorted(k for k, v in where.items() if len(v) == 1),
            "in_bengaluru_only": sum(1 for v in where.values() if v == {CITY}),
            "regional": sorted({s["measure"] for s in india["spread"]
                                if "regional" in by_measure(india)[s["measure"]][order[0]]["flags"]}),
            "counts": {k: len(v) for k, v in sorted(where.items())}}
        if a.film:
            agent_line = json.loads((SRC / "page.json").read_text())["agent_line"]
            a.film.parent.mkdir(parents=True, exist_ok=True)
            a.film.write_text(film(cli_text, toll_rows, rows, order, short, toll,
                                   {"cities": n_cities, "measures": len(partial)}, lo=-2, hi=4, agent_line=agent_line,
                                   stab=stab))

    if want("ladder"):
        data["whatif"] = {m: {"words": w["words"], "lo": ratio(w["lo"]), "hi": ratio(w["hi"]), "rank": rng(*w["rank"]),
                              "rank_costed": rng(*w["rank_c"]), "id": w["id"],
                              "rank_worst_end": rng(*w["rank_worst_end"]) if w["rank_worst_end"][0] else "",
                              "ends_lo": ratio(w["ends"][0]) if w["ends"] else "", "ends_hi": ratio(w["ends"][1]) if w["ends"] else ""}
                          for m, w in whatifs.items()}
        data["whatif_runs"] = f'{sens["base"]["context"]["n"]:,}' if sens else ""
    if want("moves") and sens:
        h, d = fig_moves(sens, order, short)
        (inc / "moves.html").write_text(h + "\n")
        data["moves"] = d
    if want("moves") and stab:
        (inc / "stability.html").write_text(stab_html + "\n")
        data["stability"] = stab
    if want("smoke"):
        h, d = fig_smoke(model)
        (inc / "smoke.html").write_text(h + "\n")
        data["smoke"] = d
    if want("day"):
        h, d = fig_day()
        (inc / "day.html").write_text(h + "\n")
        data["day"] = d
    if want("cities"):
        h, d = fig_cities(model, order, short)
        (inc / "cities.html").write_text(h + "\n")
        data["cities"] = d

    ow_path = model / "docs/open-work.json"
    if ow_path.exists():  # the model's registry of claimable open work (ids are stable)
        ow = json.loads(ow_path.read_text())
        data["open_work"] = {"n": len(ow["items"]), "ordered_by": ow.get("ordered_by", ""),
                             "first": [{"id": i["id"], "title": i["title"], "size": i.get("size", "")} for i in ow["items"][:8]]}

    pages = sorted((model / "cities").glob("*/index.html"))   # the model's generated city pages, served as they are
    data["city_pages"] = [p.parent.name for p in pages]

    commit = a.commit or subprocess.run(["git", "-C", str(model), "rev-parse", "--short", "HEAD"],
                                        capture_output=True, text=True).stdout.strip()
    data["meta"] = {"model_commit": commit, "rank_commit": a.rank_commit or commit,
                    "generated": datetime.date.today().isoformat(),
                    "curves": [short[c] for c in order]}
    data_path.parent.mkdir(exist_ok=True)
    data_path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    print("wrote", sorted(p.name for p in inc.glob("*.html")), "and", data_path.relative_to(ROOT))


if __name__ == "__main__":
    main()
