"""Chapter 2: where it comes from. Every source study of the city, side by side, never averaged.

A column is one study in one season. A source a study does not list is NaN ("not reported") and
renders as a dash, never as zero. Concentration shares and emission shares are different
quantities and are shown apart.
"""
from dataclasses import dataclass

import pandas as pd

from airhealth import causes
from airhealth.report import months_text

from . import names, svg
from .page import Section, esc, fmt, table

PLAIN: dict[str, str] = {
    "transport": "road and other transport",
    "residential": "household cooking and heating",
    "industry": "industry",
    "power": "power plants",
    "dust": "dust (roads, construction)",
    "waste_burning": "burning of waste",
    "dg_sets": "diesel generators",
    "brick_kilns": "brick kilns",
    "agri_burning": "burning of crop residue",
    "natural": "natural sources",
    "secondary_unassigned": "formed in the air from gases (secondary), source not assigned",
    "biomass_unassigned": "burning of wood and crop matter, not split further",
    "outside": "from outside the city",
    "local_all": "all sources inside the city, not split",
    "other": "other sources",
}
# Harmonised codes that are bookkeeping, not sources a reader would look for: left out of the
# "does not report" sentence (they stay in the table, where a dash still means not reported).
BOOKKEEPING = ("local_all", "outside", "other", "secondary_unassigned", "biomass_unassigned")
RECEPTOR = ("CMB", "PMF")
MODELS = ("CAMx", "CMAQ", "GEOS-Chem", "WRF-Chem")
YEAR_MONTHS = "1-12"      # how causes.csv writes a whole-year study
LEGEND = "— = the study does not report this source."


@dataclass(frozen=True)
class StudyColumn:
    study: str
    season: str
    months: str
    method: str
    origins: tuple[str, ...]
    boundary: str
    year_sampled: int | None
    n_sites: int | None
    institution: str
    url: str
    locator: str
    shares: pd.Series
    total: float


def _int(v):
    return None if pd.isna(v) else int(v)


def _columns(city: str, metric: str) -> list[StudyColumn]:
    t = causes.for_city(city)
    t = t[(t.covers == "all") & (t.metric == metric)]
    out = []
    for study in causes.studies(city):
        ts = t[t.study == study]
        for season in sorted(ts.season.unique()):
            g = ts[ts.season == season]
            r = g.iloc[0]
            if metric == "concentration_share":
                sh = causes.shares(city, study, season)
            else:
                sh = g.groupby("source_harmonised").share_pct.sum(min_count=1).reindex(
                    list(causes.HARMONISED))
            out.append(StudyColumn(
                study=study, season=season, months=str(r.months), method=r.method,
                origins=tuple(sorted(g.origin.unique())), boundary=r.boundary,
                year_sampled=_int(r.year_sampled), n_sites=_int(r.n_sites), institution=r.institution,
                url=r.url, locator=r.locator, shares=sh, total=float(sh.sum(skipna=True))))
    return out


def columns(city: str) -> list[StudyColumn]:
    return _columns(city, "concentration_share")


def emission_columns(city: str) -> list[StudyColumn]:
    return _columns(city, "emission_share")


def partials(city: str) -> pd.DataFrame:
    t = causes.for_city(city)
    return t[t.covers == "partial"].reset_index(drop=True)


def blind_spots(col: StudyColumn) -> list[str]:
    s, out = col.shares, []
    if col.method in RECEPTOR:
        n = col.n_sites
        where = f"{n} sampling site{'s' if n != 1 else ''}" if n else "its sampling site(s)"
        out.append(f"It reads what reaches {where}, from near and far alike, so it cannot say how "
                   "much came from outside the city.")
        if pd.notna(s["secondary_unassigned"]):
            out.append(f"The {fmt(s['secondary_unassigned'], 'pct_points')} listed as formed in the "
                       "air from gases (secondary particles) is tied to no source.")
    elif col.method in MODELS:
        yr = f"{col.year_sampled}" if col.year_sampled else "its base year"
        out.append(f"It is built from an emissions inventory for {yr}, so it sees only the sources "
                   "the inventory lists.")
        if pd.notna(s["outside"]) and "region" in col.origins:
            out.append(f"Everything from beyond the airshed is one lump "
                       f"({fmt(s['outside'], 'pct_points')} outside) with no split by source.")
    if col.months != YEAR_MONTHS:
        out.append(f"It covers only {months_text(col.months)}.")
    missing = [PLAIN[k] for k in causes.HARMONISED if pd.isna(s[k]) and k not in BOOKKEEPING]
    if missing:
        out.append("It does not report: " + "; ".join(missing) + ".")
    return out


def _label(c: StudyColumn) -> str:
    return f"{names.study(c.study)}, {c.season}"


def _share_table(cols: list[StudyColumn], caption: str) -> str:
    keys = [k for k in causes.HARMONISED if any(pd.notna(c.shares[k]) for c in cols)]
    rows = [[PLAIN[k]] + [fmt(c.shares[k], "pct_points", missing="—") for c in cols] for k in keys]
    rows.append(["total"] + [fmt(c.total, "pct_points") for c in cols])
    head = ["source (% of the study's own total)"] + [_label(c) for c in cols]
    return table(head, rows, caption=caption, numeric=tuple(range(1, len(cols) + 1)))


ORIGIN_WORDS = {"inside": "sources inside the airshed only",
                "all_origins": "every source that reaches the monitor, wherever it started",
                "region": "a split by where the pollution comes from"}


def _card(c: StudyColumn) -> str:
    when = f"sampled {c.year_sampled}, " if c.year_sampled else ""
    org = "; ".join(ORIGIN_WORDS[o] for o in c.origins)
    bs = "".join(f"<li>{esc(b)}</li>" for b in blind_spots(c))
    return (f'<div class="card"><h4>{esc(_label(c))}</h4>'
            f"<p>{esc(c.institution)}. Method {esc(c.method)}, {when}{esc(months_text(c.months))}, "
            f"boundary {esc(c.boundary.replace('_', ' '))}. Counts: {esc(org)}. "
            f'<a href="{esc(c.url)}">source</a>.</p>'
            f"<details><summary>where in the source</summary><p>{esc(c.locator)}</p></details>"
            f"<p>What it cannot see:</p><ul>{bs}</ul></div>")


def render(city: str) -> Section:
    cols, em, part = columns(city), emission_columns(city), partials(city)
    h = ["<p>A <em>source study</em> asks what the particles in a city's air came from. There "
         "are two kinds. An emissions model starts from what is burned (a list of vehicles, "
         "chimneys, fires) and computes where the smoke goes. A receptor model starts from what "
         "landed on a filter and works backwards to the likely sources. They answer slightly "
         "different questions and they disagree. They are shown side by side here, not "
         "averaged.</p>"]
    if cols:
        h.append(_share_table(cols, f"Where {city}'s PM2.5 came from, by study and season"))
        h.append(f'<p class="note">{esc(LEGEND)} Shares are % of each study\'s own total.</p>')
        keys = [k for k in causes.HARMONISED if any(pd.notna(c.shares[k]) for c in cols)]
        vals = [[None if pd.isna(c.shares[k]) else float(c.shares[k]) for c in cols] for k in keys]
        h.append(svg.stacked_bars([_label(c) for c in cols], [k.replace("_", " ") for k in keys],
                                  vals, title=f"{city}: PM2.5 by source, one bar per study"))
        h.append("".join(_card(c) for c in cols))
    if len(part):
        items = "".join(
            f"<li>{esc(PLAIN[r.source_harmonised])}, {esc(months_text(r.months))}: "
            f"{fmt(r.share_pct, 'pct_points')} ({esc(names.study(r.study))})</li>" for r in part.itertuples())
        h.append("<h3>Partial estimates</h3><p>One piece of a split, not the whole picture. They "
                 f"are not columns above and can overlap the outside row.</p><ul>{items}</ul>")
    if em:
        h.append("<h3>Emission shares</h3><p>These are shares of what is emitted, not of what "
                 "people breathe. They are not concentration shares and must not be read "
                 "against the table above.</p>")
        h.append(_share_table(em, "Emission shares"))
        h.append(f'<p class="note">{esc(LEGEND)}</p>')
    return Section("sources", "Where it comes from", "".join(h))
