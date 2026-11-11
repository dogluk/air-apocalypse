"""Every data file must have a sources.toml entry with full provenance, and every number
written into the code instead of a data file must be listed in constants() with its source."""
import tomllib
from pathlib import Path

from . import paths

REQUIRED = ("source", "url", "locator", "retrieved", "licence", "method")
METHODS = ("downloaded", "transcribed", "derived")


def load_sources(path: Path | None = None) -> dict[str, dict]:
    path = path or paths.DATA / "sources.toml"
    with open(path, "rb") as f:
        return tomllib.load(f)


def check(data_dir: Path | None = None, sources_path: Path | None = None) -> list[str]:
    """Return problems found; an empty list means clean."""
    data_dir = data_dir or paths.DATA
    sources = load_sources(sources_path or data_dir / "sources.toml")
    problems = []
    for f in sorted(data_dir.rglob("*.csv")):
        name = f.relative_to(data_dir).as_posix()
        if name not in sources:
            problems.append(f"{name}: no entry in sources.toml")
    for name, entry in sources.items():
        for field in REQUIRED:
            if not entry.get(field):
                problems.append(f"{name}: missing {field}")
        method = entry.get("method")
        if method and method not in METHODS:
            problems.append(f"{name}: method must be one of {METHODS}, got {method!r}")
        if method == "derived" and not entry.get("script"):
            problems.append(f"{name}: derived table needs script")
    if data_dir == paths.DATA:
        problems += check_constants()
    return problems


def constants() -> list[dict]:
    """The sourced numbers that live in code, not in data/: name, value, source."""
    from . import baseline, curves, ihme_curves, lag, lifetable
    aqli = curves.AQLILinear()
    return [
        dict(name="AQLI: years of life expectancy per 10 µg/m³", value=aqli.years_per_10,
             source=curves.AQLI_SOURCE),
        dict(name="AQLI: floor (WHO guideline), µg/m³", value=aqli.floor, source=curves.AQLI_SOURCE),
        dict(name="GEMM: counterfactual, µg/m³", value=curves.GEMM_CF, source=curves.GEMM_SOURCE),
        dict(name="Highest long-term exposure in a cohort behind GEMM, µg/m³",
             value=curves.MAX_COHORT_PM25, source=curves.MAX_COHORT_PM25_SOURCE),
        dict(name="EPA 20-year cessation lag: shares in year 1, years 2-5, years 6-20",
             value=(float(lag._EPA20[0]), float(lag._EPA20[1:5].sum()), float(lag._EPA20[5:].sum())),
             source=lag.EPA_SOURCE),
        dict(name="Infant a0 = intercept + slope × q0",
             value=(lifetable.A0_INTERCEPT, lifetable.A0_SLOPE), source=lifetable.A0_SOURCE),
        dict(name="Age from which deaths are scaled to the SRS crude death rate",
             value=baseline.RECONCILE_FROM_AGE, source=baseline.RECONCILE_SOURCE),
        dict(name="GBD counterfactual (TMREL midpoint), µg/m³", value=ihme_curves.TMREL_MID,
             source=ihme_curves.TMREL_SOURCE),
        dict(name="GBD ages: 25+ for IHD, stroke, COPD, lung cancer, diabetes; LRI all ages",
             value=ihme_curves.ADULT, source=ihme_curves.GBD_AGES_SOURCE),
    ]


def check_constants() -> list[str]:
    """Problems with the constants' sources; an empty list means every one names a source
    with a link."""
    return [f"{c['name']}: source missing or without a link" for c in constants()
            if "http" not in (c.get("source") or "")]
