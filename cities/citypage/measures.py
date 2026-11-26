"""Chapter 4: what could work, and what it would buy. Bengaluru's measures from the library.

The seam: this chapter reads only the measure library (health/interventions/library/*.toml,
airhealth.measures) and the scoring engine (airhealth.score: city(), Score, Flag, STATUSES,
ASSUMPTIONS). It does not reach into the engine's internals; if the Score fields change, this
module changes with them.

Rules it keeps:
  - Every causes study of the city is its own column: an air measure is scored once per study
    (score.city(..., study=s)) and the results are never combined. Exposure measures do not use
    a study and are scored once.
  - Every curve that ran is shown; nothing is averaged across curves and no value is picked as
    the middle one. Measures are listed in library order (file name), never sorted by a number.
  - Every flag the engine attaches is printed in plain words, and the ones that change how far a
    ratio can be trusted sit right beside it.
  - A file that cannot be read, or a measure that cannot be run, is listed with its error, never
    dropped quietly.
"""
from __future__ import annotations

import math
import os
import tempfile
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from airhealth import causes, curves, exposure, score
from airhealth import measures as library

from .page import Section, esc, fmt, table
from .svg import _open, _tick

MAP = "acag_total"            # the ranking's default exposure map

# Flags that bear on how far the ratio can be trusted: shown in a box right beside it.
PROMINENT = ("partial_cost", "upper_bound_all_origins", "long_shot", "placeholder",
             "odds_judgement", "evidence_S", "evidence_R")

PARTIAL_HEAD = "Costs that leave things out"

STATUS_WORDS = {
    "scored": "scored",
    "no_cost": "shown without a ratio: no cost given",
    "pays_for_itself": "shown without a ratio: it pays for itself",
    "not_applicable": "does not apply here",
    "not_scored": "not scored",
}

KIND_WORDS = {
    "air": "air measure: cuts a cause of PM2.5 in the outdoor air, for everyone",
    "exposure": ("exposure measure: cuts what some people breathe; the outdoor air is "
                 "unchanged"),
}


@dataclass(frozen=True)
class MeasureFile:
    path: Path
    name: str | None
    error: str | None


@dataclass
class Entry:
    file: MeasureFile
    scores: dict[str | None, score.Score] = field(default_factory=dict)  # study (or None) -> Score
    error: str | None = None


def _one_line(e: BaseException) -> str:
    text = str(e).strip().splitlines()
    return text[0] if text else type(e).__name__


def _raw_applies(path: Path, city: str) -> tuple[bool, str | None]:
    """For a file that failed to load: does its raw `cities` name the city? (A file whose TOML
    cannot be parsed at all is assumed to, so that it is shown, not dropped.)"""
    try:
        raw = tomllib.loads(path.read_text())
    except (tomllib.TOMLDecodeError, OSError, UnicodeDecodeError):
        return True, None
    name = raw.get("name") if isinstance(raw.get("name"), str) else None
    cities = raw.get("cities")
    if cities is None or cities == "all":
        return True, name
    return isinstance(cities, list) and city in cities, name


def find(city: str, folder: Path | None = None) -> list[MeasureFile]:
    """Every measure file in `folder` (default: the library) that applies to the city, in file
    name order, skipping names that start with "_" (the template). A file that fails to load is
    kept, with its one-line error, if its raw `cities` names the city or "all"."""
    folder = Path(folder) if folder is not None else library.LIBRARY
    out = []
    for p in sorted(folder.glob("*.toml")):
        if p.name.startswith("_"):
            continue
        try:
            m = library.load(p)
        except Exception as e:                     # Invalid, or TOML that does not parse
            applies, name = _raw_applies(p, city)
            if applies:
                out.append(MeasureFile(p, name, _one_line(e)))
            continue
        if m.cities is None or city in m.cities:
            out.append(MeasureFile(p, m.name, None))
    return out


def score_all(city: str, folder: Path | None = None, n: int = 2000, seed: int = 0,
              map_name: str = MAP) -> list[Entry]:
    """One Entry per file find() returns. Air measures in a city are scored on every causes
    study of the city, each separately; other measures once (study None)."""
    files = find(city, folder)
    studies = causes.studies(city)
    entries = [Entry(f, error=f.error) for f in files]
    good = [e for e in entries if e.error is None]
    if not good:
        return entries
    # The engine loads a whole folder; give it only the files that load.
    with tempfile.TemporaryDirectory() as tmp:
        for e in good:
            os.symlink(e.file.path.resolve(), Path(tmp) / e.file.path.name)
        for e in good:
            mid = e.file.path.stem
            m = library.load(e.file.path)
            keys = (studies or [None]) if (m.kind == "air" and m.scope == "city") else [None]
            try:
                for st in keys:
                    got = score.city(city, [mid], study=st, map_name=map_name, n=n, seed=seed,
                                     folder=Path(tmp))
                    e.scores[st] = got[0]
            except Exception as ex:                # shown as "could not run", never dropped
                e.scores, e.error = {}, f"{type(ex).__name__}: {_one_line(ex)}"
    return entries


# ---------------------------------------------------------------- formatting

def _sig(x: float | None) -> str:
    """A ratio with sensible precision; no exponent notation."""
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "—"
    if x == 0:
        return "0"
    if abs(x) >= 100:
        return f"{x:,.0f}"
    if abs(x) >= 1:
        return f"{x:.1f}"
    if abs(x) >= 0.01:
        return f"{x:.2f}"
    return "under 0.01"


def _inr(x: float | None) -> str:
    if x is None or not math.isfinite(x):
        return "no data"
    if abs(x) >= 1e7:
        return f"Rs {x / 1e7:,.1f} crore"
    if abs(x) >= 1e5:
        return f"Rs {x / 1e5:,.1f} lakh"
    return f"Rs {x:,.0f}"


def _range(d: dict, f=fmt) -> str:
    return f"{f(d['median'])} ({f(d['p5'])} to {f(d['p95'])})"


def _pm(x: float) -> str:
    return f"{x:+.2f}"


# ---------------------------------------------------------------- chart

def _short(s: str, k: int = 44) -> str:
    return s if len(s) <= k else s[:k - 1] + "…"


def log_dots(rows: list[str], curve_names: list[str], values: list[list[float | None]], *,
             title: str, x_label: str) -> str:
    """One row per measure; one dot per curve (values[row][curve]) on a log scale, joined by a
    thin line from the lowest curve to the highest. No middle value is drawn."""
    L, R, T, rh, width = 270, 170, 34, 24, 720
    bottom = T + rh * len(rows)
    height = max(bottom, T + 16 * len(curve_names)) + 40
    pos = [v for r in values for v in r if v is not None and v > 0]
    lo_e = math.floor(math.log10(min(pos))) if pos else 0
    hi_e = math.ceil(math.log10(max(pos))) if pos else 1
    if hi_e == lo_e:
        hi_e += 1

    def px(v):
        return L + (math.log10(v) - lo_e) / (hi_e - lo_e) * (width - L - R)

    o = [_open(width, height, title)]
    for e in range(lo_e, hi_e + 1):
        t = 10.0 ** e
        o.append(f'<line class="grid" x1="{px(t):.1f}" x2="{px(t):.1f}" y1="{T - 4}" '
                 f'y2="{bottom}"/><text x="{px(t):.1f}" y="{bottom + 14}" '
                 f'text-anchor="middle">{_tick(t)}</text>')
    o.append(f'<text x="{(L + width - R) / 2:.0f}" y="{bottom + 30}" '
             f'text-anchor="middle">{esc(x_label)}</text>')
    for i, (label, vals) in enumerate(zip(rows, values)):
        cy = T + rh * i + rh / 2
        o.append(f'<text class="lab" x="{L - 8}" y="{cy + 4:.1f}" text-anchor="end">'
                 f'<title>{esc(label)}</title>{esc(_short(label))}</text>')
        ok = [v for v in vals if v is not None and v > 0]
        if len(ok) > 1:
            o.append(f'<line class="axis" x1="{px(min(ok)):.1f}" x2="{px(max(ok)):.1f}" '
                     f'y1="{cy:.1f}" y2="{cy:.1f}"/>')
        for c, v in enumerate(vals):
            if v is not None and v > 0:
                o.append(f'<circle class="f{c % 8}" cx="{px(v):.1f}" cy="{cy:.1f}" r="4">'
                         f'<title>{esc(label)}, {esc(curve_names[c])}: {esc(_sig(v))}</title>'
                         f'</circle>')
    for c, name in enumerate(curve_names):
        o.append(f'<circle class="f{c % 8}" cx="{width - R + 14}" cy="{T + 8 + 16 * c}" r="4"/>'
                 f'<text class="lab" x="{width - R + 24}" y="{T + 12 + 16 * c}">'
                 f'{esc(name)}</text>')
    o.append("</svg>")
    return "".join(o)


# ---------------------------------------------------------------- render

def _flag_items(flags) -> str:
    return "".join(f"<li>{esc(f.text)}</li>" for f in flags)


def _partial(e: Entry) -> bool:
    return any(f.code == "partial_cost" for s in e.scores.values() for f in s.flags)


def _prominent(s: score.Score):
    return sorted((f for f in s.flags if f.code in PROMINENT), key=lambda f: PROMINENT.index(f.code))


def _others(s: score.Score):
    return [f for f in s.flags if f.code not in PROMINENT]


def _curve_table(s: score.Score, labels: dict[str, str], caption: str) -> str:
    head = ["Curve", "Life-years if it works, median (5% to 95%)",
            "Deaths postponed if it works, median (5% to 95%)",
            "Life-years per crore if it works", "Expected life-years per crore"]
    rows = []
    for name, d in s.per_curve.items():
        rows.append([name, _range(d["life_years"]),
                     _range(d["deaths_postponed"]),
                     _sig(d["life_years_per_crore_if_works"]),
                     _sig(d["expected_life_years_per_crore"])])
    return table(head, rows, caption=caption, numeric=(1, 2, 3, 4))


def _score_block(s: score.Score, labels: dict[str, str], study_label: str | None) -> str:
    h = []
    if study_label:
        h.append(f"<h4>{esc(study_label)}</h4>")
    if s.status != "scored":
        h.append(f"<p><b>{esc(STATUS_WORDS[s.status])}</b>: {esc(s.reason)}.</p>")
    if s.pm25_change:
        if s.kind == "exposure":
            where = ("in what the covered people breathe (not the city average; everyone else "
                     "breathes the same air as before)")
        else:
            where = "in the city average (the yearly mean, weighted by where people live)"
        h.append(f"<p>PM2.5 change if it works, {where}: {_pm(s.pm25_change['median'])} µg/m³ "
                 f"({_pm(s.pm25_change['p5'])} to {_pm(s.pm25_change['p95'])}).</p>")
    if s.per_curve:
        first = next(iter(s.per_curve.values()))
        if s.status == "no_cost":
            h.append("<p>Cost: not known (the file gives none).</p>")
        else:
            h.append(f"<p>Cost over its years, in the funder's 2025 rupees, discounted: "
                     f"{_range(first['cost_inr'], _inr)}.</p>")
        prom = _prominent(s)
        if prom:
            h.append(f'<div class="caveats"><p><b>Read the ratios below with these:</b></p>'
                     f"<ul>{_flag_items(prom)}</ul></div>")
        cap = f"{s.name}" + (f", {study_label}" if study_label else "") + ", every curve"
        h.append(_curve_table(s, labels, cap))
        others = _others(s)
        if others:
            h.append(f'<p class="note">Also:</p><ul class="note">{_flag_items(others)}</ul>')
    elif s.flags:
        h.append(f'<p class="note">Caveats that would apply:</p>'
                 f'<ul class="note">{_flag_items(s.flags)}</ul>')
    return "".join(h)


def _study_label(st: str | None) -> str | None:
    return None if st is None else f"On study {st}"


def _measure_block(e: Entry, labels: dict[str, str]) -> str:
    first = next(iter(e.scores.values()))
    h = [f'<h3 id="m-{esc(e.file.path.stem)}">{esc(first.name)}</h3>',
         f'<p class="note">{esc(e.file.path.name)}: {esc(KIND_WORDS.get(first.kind, first.kind))}.'
         f"</p>",
         f"<p><b>Who it reaches:</b> {esc(first.who_reaches)}.</p>",
         f"<p><b>Odds that it works:</b> {first.p_success:.0%}. "
         f"<b>Basis:</b> {esc(first.p_success_basis)}.</p>"]
    for st, s in e.scores.items():
        h.append(_score_block(s, labels, _study_label(st)))
    return "".join(h)


def _chart(entries: list[Entry], key, curve_names: list[str], title: str) -> tuple[str, list[str]]:
    rows, vals, left_out = [], [], []
    for e in entries:
        s = e.scores.get(key)
        if s is None:
            continue
        v = [s.per_curve.get(c, {}).get("expected_life_years_per_crore") for c in curve_names]
        if any(x is not None and x > 0 for x in v):
            rows.append(s.name)
            vals.append(v)
        else:
            left_out.append(f"{s.name} ({STATUS_WORDS[s.status]})")
    if not rows:
        return "", left_out
    return log_dots(rows, curve_names, vals, title=title,
                    x_label="expected life-years per crore (log scale)"), left_out


def _empty(city: str) -> str:
    return (f"<p>{esc(city)}'s measures are not yet in the library. The measure library "
            "(health/interventions/library/, one TOML file per measure) is being written; once "
            f"files that list {esc(city)} under <code>cities</code> exist there, rebuilding this "
            "page scores them on every curve and every source study.</p>")


def _broken(entries: list[Entry]) -> str:
    bad = [e for e in entries if e.error]
    if not bad:
        return ""
    items = "".join(f"<li><b>{esc(e.file.name or e.file.path.stem)}</b> "
                    f"({esc(e.file.path.name)}): {esc(e.error)}</li>" for e in bad)
    return ("<h3>Measures that could not run</h3><p>These files name the city but could not "
            f"be read or scored, so they have no numbers here:</p><ul>{items}</ul>")


def render(city: str, folder: Path | None = None, n: int = 2000, seed: int = 0) -> Section:
    entries = score_all(city, folder, n=n, seed=seed)
    ran, missing = curves.select()
    labels = {c.name: c.label for c in ran}
    ok = [e for e in entries if e.scores]
    if not ok:
        return Section("measures", "What could work, and what it would buy",
                       _empty(city) + _broken(entries))

    studies = causes.studies(city)
    runs = [s.run for e in ok for s in e.scores.values() if s.run is not None]
    first_run = runs[0] if runs else None
    curve_names = list(first_run.per_curve) if first_run else [c.name for c in ran]
    h = []

    h.append(
        "<p>A <b>measure</b> is one thing the city could do about its air, written as a file in "
        "the measure library with every number's source. There are two kinds. An <b>air "
        "measure</b> cuts a cause of PM2.5 (dust, vehicles, burning) and so cleans the outdoor "
        "air for everyone; how much it cleans depends on how big that cause is, which comes from "
        "a source study (chapter 2). An <b>exposure measure</b> (purifiers, masks) leaves the "
        "outdoor air as it is and cuts what some people breathe, for some of their hours.</p>")
    h.append(
        "<p>Each measure has <b>odds that it works</b>: the chance it is carried out and does "
        "what it says, mostly a judgement written down with its reasons. Figures marked <b>if it "
        "works</b> assume it does; <b>expected</b> figures multiply the life-years by those odds "
        "(and the cost too, for the part paid only on success). Every figure is a <b>Monte "
        "Carlo range</b>: the measure is run many times with its uncertain inputs (how big the "
        "cut is, the curve's own parameters, the cost) drawn afresh each time; the median is the "
        "middle run and the range covers the middle 90% of runs. <b>Life-years per crore</b> "
        "is life-years gained for every crore (ten million rupees) spent: higher means more "
        "health for the money.</p>")

    if first_run:
        level = (f", where {esc(city)}'s PM2.5, weighted by where people live, is "
                 f"{first_run.pm25_before:.1f} µg/m³ in {first_run.year}")
        h.append(
            f"<p>Every measure is scored on one exposure map, <b>{esc(MAP)}</b> "
            f"({esc(exposure.LABELS[MAP])}){level}. Chapter 1's ground monitors read the city's "
            "air differently, and chapter 3 shows the maps side by side; this chapter uses the "
            "map the ranking across cities uses.</p>")
    h.append(
        f"<p>Air measures are scored on every source study of {esc(city)} that splits PM2.5 by "
        f"cause ({esc(', '.join(studies)) if studies else 'none'}), each on its own; the studies "
        "disagree, and their results are never combined. Exposure measures do not depend on a "
        "study and are scored once.</p>")
    line = "Curves used: " + "; ".join(f"{c} ({labels.get(c, c)})" for c in curve_names) + "."
    if missing:
        line += " Not run: " + "; ".join(f"{k} ({why})" for k, why in missing.items()) + "."
    if first_run:
        line += (f" {first_run.n:,} runs per curve, seed {first_run.seed}, life-years and costs "
                 f"discounted at {first_run.discount:.0%} a year.")
    h.append(f'<p class="note">{esc(line)}</p>')

    h.append("<h3>What the scores assume</h3><ul>"
             + "".join(f"<li>{esc(a)}</li>" for a in score.ASSUMPTIONS)
             + "<li>An exposure measure that reaches only part of the city is scored as if the "
               "people it covers had the whole city's mix of ages and death rates: the engine "
               "spreads them across ages like everyone else. For a measure that reaches only "
               "children, such as purifiers in classrooms, the life-years are therefore likely "
               "overstated, because most deaths from PM2.5 are in adults.</li></ul>")

    h.append("<h3>All measures at a glance</h3>")
    h.append("<p>One row per measure, in library order (by file name), not sorted by any number. "
             "Each dot is one curve's expected life-years per crore; the line runs from the "
             "lowest curve to the highest. The scale is logarithmic: each step to the right is "
             "ten times more. Caveats for each measure are with its own table below.</p>")
    full = [e for e in ok if not _partial(e)]
    part = [e for e in ok if _partial(e)]
    if part:
        h.append("<p>The measures listed under <b>" + PARTIAL_HEAD + "</b> carry a cost that "
                 "leaves out something real, so their ratios are not comparable with the "
                 "others' and sit below them, after every fully costed measure.</p>")

    def charts(group):
        out = []
        keys = [(st, f"{city}: air measures on study {st}") for st in studies]
        keys.append((None, f"{city}: exposure measures (no study needed)"))
        for key, title in keys:
            chart, left_out = _chart(group, key, curve_names, title)
            out.append(chart)
            if left_out:
                out.append(f'<p class="note">Not on the chart "{esc(title)}", because it has no '
                           f"ratio: {esc('; '.join(left_out))}.</p>")
        return "".join(out)
    h.append(charts(full))
    if part:
        h.append(f"<h3>{PARTIAL_HEAD}, at a glance</h3><p>The costs behind these charts leave "
                 "things out, so the ratios are not comparable with each other or with the "
                 "measures above.</p>")
        h.append(charts(part))

    h.append("<h3>Each measure</h3>")
    for e in full:
        h.append(_measure_block(e, labels))
    if part:
        h.append(f"<h3>{PARTIAL_HEAD}</h3><p>Each measure here has a cost that leaves out "
                 "something real (its own caveat says what), so its ratios are not comparable "
                 "with other measures' and are listed after the fully costed ones, in library "
                 "order.</p>")
        for e in part:
            h.append(_measure_block(e, labels))
    h.append(_broken(entries))
    return Section("measures", "What could work, and what it would buy", "".join(h))
