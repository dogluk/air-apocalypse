"""The findings block at the top of the page: a few short lines, every number computed at build
time from the same runs the chapters use. No digit is typed here: a test reads this file and
fails on one in the text. Nothing is averaged or picked: each line gives a range, with the
curve, map or study at each end.
"""
from __future__ import annotations

import math

from airhealth import curves

from . import burden, measures, names, origins
from .page import esc, fmt
from .measures import _sig


def _toll(city: str) -> str:
    rows = [(r["deaths_averted"], r["curve"], m) for m in burden._maps()
            for r in burden.burden(city, m)["rows"]
            if r["deaths_averted"] is not None and math.isfinite(r["deaths_averted"])]
    if not rows:
        return "No curve gave a death toll for this city."
    lo, hi = min(rows), max(rows)
    n_curves, n_maps = len({r[1] for r in rows}), len({r[2] for r in rows})
    return (f"PM2.5 is behind {fmt(lo[0])} to {fmt(hi[0])} deaths a year in {city}, "
            f"depending on the risk curve and the map: lowest on {names.curve(lo[1])} with the "
            f"{names.exposure_map(lo[2])}, highest on {names.curve(hi[1])} with the "
            f"{names.exposure_map(hi[2])} ({n_curves} curves and {n_maps} maps tried, none preferred).")


def _target(key_start: str):
    return next((t for t in burden.targets() if t.key.startswith(key_start)), None)


def _level(city: str) -> str:
    maps = burden._maps()
    lv = [(burden.level(city, m)[0], m) for m in maps]
    if not lv:
        return ""
    lo, hi = min(lv)[0], max(lv)[0]
    text = (f"Over the year the air holds {lo:.1f} to {hi:.1f} µg/m³ of PM2.5, depending on the "
            f"map ({', '.join(names.exposure_map(m) for _, m in sorted(lv))}).")
    india, who = _target("india"), _target("who")
    if india:
        verdict = ("below it on every map" if hi <= india.pm25 else
                   "above it on every map" if lo > india.pm25 else
                   "above it on some maps and below it on others")
        text += f" India's standard for the yearly mean is {india.pm25:g} µg/m³: {verdict}."
    if who:
        text += (f" WHO's guideline is {who.pm25:g} µg/m³: the air holds {lo / who.pm25:.1f} to "
                 f"{hi / who.pm25:.1f} times that.")
    return text


def _sources(city: str) -> str:
    parts = []
    cols = origins.columns(city)
    for c in cols:
        same = [x for x in cols if x.study == c.study]
        whole = [x for x in same if x.months == origins.YEAR_MONTHS]
        if whole and c not in whole:
            continue                    # a study with a whole-year column: that one speaks for it
        have = [(v, k) for k, v in c.shares.items()
                if k not in origins.BOOKKEEPING and v == v]
        top = sorted(have, reverse=True)[:2]
        if top:
            who = names.study(c.study) + ("" if len(same) == 1 or whole else f", {c.season}")
            parts.append(f"{who}: " + ", ".join(
                f"{origins.PLAIN[k]} {fmt(v, 'pct_points')}" for v, k in top))
    if not parts:
        return ""
    return ("The studies of where it comes from name these first (each on its own, a share of "
            "its own total): " + "; ".join(parts) + ".")


def _ends(vals: dict[tuple[str | None, str], float]):
    lo = min(vals, key=vals.get)
    hi = max(vals, key=vals.get)
    return lo, hi


def _first_full(city: str, full: list, curve_names: list[str]) -> str:
    if not full:
        return "No measure has a full cost yet, so none is ranked on a whole-cost ratio."
    e = full[0]
    vals = {(st, c): v for st, s in e.scores.items()
            for c, v in measures.ratios(s, curve_names).items()}
    first = next(iter(e.scores.values()))
    if not vals:
        return f"The first fully costed measure, {first.name}, has no ratio on any curve."
    lo, hi = _ends(vals)
    src = "" if len(e.scores) < 2 else " and source studies"
    return (f"The first measure with a full cost is {first.name}: {_sig(vals[lo])} to "
            f"{_sig(vals[hi])} expected life-years per crore across the curves{src} "
            f"(lowest on {names.curve(lo[1])}, highest on {names.curve(hi[1])}).")


def _partial_line(part: list, curve_names: list[str]) -> str:
    if not part:
        return ""
    top = part[:3]
    enforce = []
    for e in top:
        texts = [f.text for s in e.scores.values() for f in s.flags if f.code == "partial_cost"]
        if any("enforce" in t.lower() for t in texts):
            enforce.append(next(iter(e.scores.values())).name)
    shown = "; ".join(next(iter(e.scores.values())).name for e in top)
    out = (f"The top measures with partial costs ({shown}) are not comparable with the fully "
           "costed ones")
    if enforce:
        out += (f": {'; '.join(enforce)} rest{'s' if len(enforce) == 1 else ''} on "
                "enforcement-only costs (what the government spends to enforce rules, not what "
                "it costs people to comply).")
    else:
        out += "; each says what its cost leaves out."
    return out


def lines(city: str, entries: list) -> list[str]:
    ran, _ = curves.select()
    names_ = measures.curve_names_of(entries, [c.name for c in ran])
    full, part, _regional = measures.groups(entries, names_)
    out = [_toll(city), _level(city), _sources(city), _first_full(city, full, names_),
           _partial_line(part, names_)]
    return [x for x in out if x]


def block(city: str, entries: list) -> str:
    items = "".join(f"<li>{esc(x)}</li>" for x in lines(city, entries))
    return f'<div class="card findings"><h3>What the page finds</h3><ul>{items}</ul></div>'
