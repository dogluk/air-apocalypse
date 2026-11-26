"""Build the city page: one self-contained HTML file, four chapters, generated from the repo's data
and the airhealth tool. Nothing is typed into the page by hand; every figure is computed at build
time. The output has no build timestamp, so the same data and files give the same bytes.

    PYTHONPATH=health:cities python -m citypage.build --city Bengaluru
"""
from __future__ import annotations

import argparse
from pathlib import Path

from airhealth import paths
from airhealth.provenance import load_sources

from . import burden, ground, measures, origins, svg
from .page import Section, esc, page

# The committed data files the four chapters read (checked against sources.toml by a test).
DATA_FILES = (
    "cpcb_city_month_hour.csv", "cpcb_station_month.csv", "monthly_cpcb.csv", "exposure_cpcb.csv",
    "exposure_aqli.csv", "exposure_acag_total.csv", "causes.csv", "targets.csv", "cities.csv",
    "places.csv", "city_households.csv", "curves_loglinear.csv", "curves_gemm_ncd_lri.csv",
    "curves_gemm_5cod.csv", "cause_share_ncd_lri.csv", "population_age_state.csv",
    "lifetables_srs.csv", "srs_age_specific_death_rates.csv", "death_reconciliation.csv",
    "death_reconciliation_by_year.csv", "fx_inr_usd.csv", "gdp_deflator_ind.csv")

REPO = paths.REPO


def _slug(city: str) -> str:
    return city.lower().replace(" ", "-")


def default_out(city: str) -> Path:
    return REPO / "cities" / _slug(city) / "index.html"


def _intro(city: str, build_line: str) -> str:
    return (
        f"<p>This page follows the air of one city, {esc(city)}, from the ground to what could be "
        "done about it. It is written to understand, not to persuade. Where published sources "
        "disagree, the page shows them side by side and does not average them or pick a winner.</p>"
        "<p>It has four chapters. <b>1. The air itself</b>: what the monitors on the ground and the "
        "satellite maps say about PM2.5, the fine particles (smaller than 2.5 micrometres across) "
        "that do most of the harm to health, measured in micrograms per cubic metre of air "
        "(µg/m³). <b>2. Where it comes from</b>: what the studies of the city's air say the "
        "particles came from. <b>3. What it does to health</b>: the deaths and years of life that "
        "PM2.5 takes, on every published way of turning air into health. <b>4. What could work, and "
        "what it would buy</b>: measures the city could take, with the odds each works and what "
        "it would cost.</p>"
        f'<p class="note">{esc(build_line)}</p>')


def _build_line(city: str, n: int, seed: int) -> str:
    run, missing = burden.curves_status()
    ihme = "absent" if any(w == _ihme_reason() for w in missing.values()) else "present"
    line = f"IHME files: {ihme}. Curves used: {', '.join(run)}."
    if missing:
        line += " Not run: " + "; ".join(f"{k} ({w})" for k, w in missing.items()) + "."
    return (f"Built from {len(DATA_FILES)} data files listed at the foot of the page. {line} "
            f"Chapter 4: n = {n:,} runs per curve, seed = {seed}. Rebuild with "
            f"PYTHONPATH=health:cities python -m citypage.build --city {city}.")


def _ihme_reason() -> str:
    from airhealth import curves
    return curves.IHME_REASON


def _footer(city: str) -> str:
    src = load_sources()
    rows = []
    for f in DATA_FILES:
        e = src[f]
        rows.append(f'<li><code>{esc(f)}</code>: <a href="{esc(e["url"])}">{esc(e["source"])}</a> '
                    f'Licence: {esc(e["licence"])}</li>')
    return (
        "<p><b>Data this page read</b> (each file's source and licence are in "
        "<code>health/data/sources.toml</code>):</p>"
        f'<ul class="note">{"".join(rows)}</ul>'
        "<p>The CPCB-derived tables (monitor readings, city and station summaries) come from the "
        'compilation by <a href="https://github.com/Vonter/india-cpcb-aqi">Vonter/india-cpcb-aqi</a> '
        "of the Central Pollution Control Board's monitor data, under the Open Database Licence "
        "(ODbL 1.0); the tables derived from it are shared under ODbL 1.0 too. Times are Indian "
        "Standard Time wall-clock.</p>"
        "<p>Fonts: Young Serif and Instrument Sans, under the SIL Open Font License 1.1, embedded in "
        "this file (licence texts in <code>fonts/</code>). Not reviewed by a specialist; the modelling "
        "calls are listed in <code>docs/STATUS.md</code>.</p>")


def build(city: str = "Bengaluru", out: Path | None = None, n: int = 5000, seed: int = 0,
          measures_folder: Path | None = None) -> Path:
    out = Path(out) if out is not None else default_out(city)
    svg.reset_ids()
    sections: list[Section] = [
        ground.render(city), origins.render(city), burden.render(city),
        measures.render(city, folder=measures_folder, n=n, seed=seed)]
    title = f"{city}: from the air to what could work"
    html = page(title, _intro(city, _build_line(city, n, seed)), sections, _footer(city))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m citypage.build",
                                 description="Build the one-city HTML page.")
    ap.add_argument("--city", default="Bengaluru")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--n", type=int, default=5000, help="Monte Carlo runs per curve (chapter 4)")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(argv)
    print(build(a.city, a.out, a.n, a.seed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
