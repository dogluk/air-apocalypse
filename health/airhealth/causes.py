"""What causes each city's PM2.5: every study side by side (data/causes.csv).

One row per city x study x season x size fraction x source. Studies disagree by factors, not
points (method, boundary, year), so the table keeps them all and the caller chooses. Rows come
from scripts/build_causes.py: APnA (UrbanEmissions, CAMx), McDuffie 2021, and the city studies
hand-transcribed in data/causes_transcribed.csv. Sources and locators: data/sources.toml and
each row's own `locator`.

Shares are of PM2.5 concentration unless metric = 'emission_share'; emission shares are kept
but never summed with concentration shares (validate() refuses a mixed study). A group with
covers = 'all' is a study's whole split and sums to 100 +/- 2; a receptor study's
'unidentified/others' remainder is written as source_harmonised = 'other'. covers = 'partial'
is a piece of a split (e.g. a stubble-only estimate) and is not summed.

What a share means depends on `origin` (the column after `boundary`); do not read one study's
share as another's:
  inside      the sector's emissions inside the city's airshed only; everything from outside it is
              in an `outside` row (APnA sector rows, source_harmonised != outside).
  all_origins that sector's contribution from every origin (all India, or the world for McDuffie):
              CMAQ / GEOS-Chem / WRF-Chem sector splits, receptor-model (CMB, PMF) shares, and
              partial stubble estimates. `outside` there is only what the report separates as
              boundary or international inflow, if anything. A city measure that cuts one sector
              inside the city must not be applied to these shares as if they were all inside.
  region      a split by where the pollution comes from: the APnA `outside` row, and the geographic
              splits (`local_all` = the city's own sources, all sectors, plus `outside` pieces).
              `local_all` appears only in these, and only with `outside` rows beside it (validate()
              refuses anything else). Govardhan 2024 is a hybrid: it splits Delhi's own share into
              Delhi transport (`transport`) and Delhi's other sectors (`other`), then the rest by
              geography, so it has no `local_all` row and its `transport` and `other` rows are
              Delhi's own emissions only, although the group's origin is `region`.

A harmonised cause a group does not list is NOT REPORTED by that study, never 0: use shares(),
which returns NaN for those. `months`, not `season`, says which months a share covers (a
campaign-mean label such as Kolkata's 'winter+summer campaigns' is not 'annual').
`boundary` is the receptor area only: airshed_box, municipal, district, site, grid_cell (a model
cell, McDuffie), region (a multi-district receptor region, Biswal).
Only evidence O (read at source) is allowed in the table for now; press (S) and memory (R)
numbers are kept in data/MISSING.md as leads to confirm.
"""
from functools import cache

import pandas as pd

from . import paths

HARMONISED = ("transport", "residential", "industry", "dust", "waste_burning", "dg_sets", "brick_kilns",
              "agri_burning", "natural", "secondary_unassigned", "biomass_unassigned", "outside", "local_all", "other")
COLUMNS = ("city", "study", "institution", "year_sampled", "season", "months", "size_fraction", "method",
           "metric", "boundary", "origin", "covers", "source_raw", "source_harmonised", "share_pct", "n_sites",
           "n_days", "url", "locator", "evidence_key")
METRICS = ("concentration_share", "emission_share")
COVERS = ("all", "partial")
ORIGINS = ("inside", "all_origins", "region")
EVIDENCE = ("O",)      # S (press) and R (memory) are not allowed until a later plan says so
SIZE_FRACTIONS = ("PM2.5",)
METHODS = ("CAMx", "CMAQ", "GEOS-Chem", "WRF-Chem", "CMB", "PMF", "AERMOD", "GAINS")
BOUNDARIES = ("airshed_box", "municipal", "district", "site", "grid_cell", "region")
GROUP = ["city", "study", "season", "size_fraction", "metric"]
TOLERANCE = 2.0


def known_cities() -> set[str]:
    return set(pd.read_csv(paths.DATA / "cities.csv").city)


def _months_ok(m: str) -> bool:
    if m == "1-12":
        return True
    parts = m.split(",")
    return all(p.isdigit() and 1 <= int(p) <= 12 for p in parts) and len(set(parts)) == len(parts)


def validate(df: pd.DataFrame) -> None:
    """Raise ValueError, naming the offending group, unless df is a well-formed causes table."""
    if tuple(df.columns) != COLUMNS:
        raise ValueError(f"columns must be exactly {list(COLUMNS)}, got {list(df.columns)}")
    unknown = sorted(set(df.city) - known_cities())
    if unknown:
        raise ValueError(f"cities not in cities.csv: {unknown}")
    bad = sorted(set(df.source_harmonised) - set(HARMONISED))
    if bad:
        raise ValueError(f"source_harmonised names not in the list: {bad}")
    for col, allowed in (("metric", METRICS), ("covers", COVERS), ("origin", ORIGINS), ("size_fraction", SIZE_FRACTIONS),
                         ("method", METHODS), ("boundary", BOUNDARIES)):
        bad = sorted(set(df[col]) - set(allowed))
        if bad:
            raise ValueError(f"{col} values not in {list(allowed)}: {bad}")
    bad = sorted(set(df.evidence_key) - set(EVIDENCE))
    if bad:
        raise ValueError(f"evidence_key values {bad} not allowed: only {list(EVIDENCE)} (read at source); "
                         "press and memory numbers belong in data/MISSING.md")
    badm = sorted({m for m in df.months.astype(str) if not _months_ok(m)})
    if badm:
        raise ValueError(f"months must be '1-12' or a comma list of month numbers 1-12, got {badm}")
    local = df[(df.source_harmonised == "local_all") & (df.origin != "region")]
    if len(local):
        raise ValueError("local_all is only for geographic splits (origin = region): "
                         f"{sorted(set(local.study))}")
    names = df.groupby(["city", "study", "season"]).source_harmonised.agg(set)
    beside = {k: sorted(v - {"local_all", "outside"}) for k, v in names.items()
              if "local_all" in v and v - {"local_all", "outside"}}
    if beside:
        raise ValueError("local_all means all of the city's own sources, so its group may hold only "
                         f"local_all and outside rows; found beside local_all: {beside}")
    dup = df[df.duplicated(["city", "study", "season", "source_raw"], keep=False)]
    if len(dup):
        raise ValueError("duplicate (city, study, season, source_raw): "
                         f"{sorted(set(zip(dup.city, dup.study, dup.season, dup.source_raw)))}")
    if df.share_pct.isna().any() or (df.share_pct < 0).any():
        raise ValueError("share_pct must be present and non-negative")
    mixed = df.groupby(["city", "study", "season"]).metric.nunique()
    mixed = mixed[mixed > 1]
    if len(mixed):
        raise ValueError(f"more than one metric in one (city, study, season): {list(mixed.index)}")
    full = df[df.covers == "all"].groupby(GROUP).share_pct.sum()
    off = full[(full - 100).abs() > TOLERANCE]
    if len(off):
        raise ValueError("complete groups (covers = all) must sum to 100 +/- 2; "
                         + "; ".join(f"{dict(zip(GROUP, k))} sum {v:.1f}" for k, v in off.items()))


@cache
def table() -> pd.DataFrame:
    """Every row of data/causes.csv, validated."""
    df = pd.read_csv(paths.DATA / "causes.csv", dtype={"months": str})
    validate(df)
    return df


def for_city(city: str, study: str | None = None) -> pd.DataFrame:
    """The city's rows (all studies, or one). KeyError for a place not in cities.csv."""
    if city not in known_cities():
        raise KeyError(f"{city!r} is not one of the cities in data/cities.csv")
    t = table()
    t = t[t.city == city]
    if study is not None:
        t = t[t.study == study]
    return t.reset_index(drop=True)


def studies(city: str) -> list[str]:
    """Study ids with rows for the city, APnA first, then the rest in name order."""
    ids = sorted(for_city(city).study.unique())
    return sorted(ids, key=lambda s: (not s.startswith("apna"), s))


def shares(city: str, study: str, season: str) -> pd.Series:
    """One group's shares (% of the study's own total) indexed by every HARMONISED name. NaN means the
    study does not report that cause (never 0); a cause listed twice is summed. KeyError for a group
    that does not exist; check origin and covers of the rows (for_city) before using a share."""
    t = for_city(city, study)
    t = t[t.season == season]
    if t.empty:
        raise KeyError(f"no group {city!r} / {study!r} / {season!r} in data/causes.csv")
    got = t.groupby("source_harmonised").share_pct.sum(min_count=1)
    return got.reindex(list(HARMONISED))
