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
"""
from functools import cache

import pandas as pd

from . import paths

HARMONISED = ("transport", "residential", "industry", "dust", "waste_burning", "dg_sets", "brick_kilns",
              "agri_burning", "natural", "secondary_unassigned", "biomass_unassigned", "outside", "other")
COLUMNS = ("city", "study", "institution", "year_sampled", "season", "months", "size_fraction", "method",
           "metric", "boundary", "covers", "source_raw", "source_harmonised", "share_pct", "n_sites",
           "n_days", "url", "locator", "evidence_key")
METRICS = ("concentration_share", "emission_share")
COVERS = ("all", "partial")
GROUP = ["city", "study", "season", "size_fraction", "metric"]
TOLERANCE = 2.0


def known_cities() -> set[str]:
    return set(pd.read_csv(paths.DATA / "cities.csv").city)


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
    for col, allowed in (("metric", METRICS), ("covers", COVERS)):
        bad = sorted(set(df[col]) - set(allowed))
        if bad:
            raise ValueError(f"{col} values not in {list(allowed)}: {bad}")
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
