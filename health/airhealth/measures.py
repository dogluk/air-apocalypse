"""Measure files: the library of things a city or region could do about its air.

A measure file (interventions/library/<id>.toml) describes one measure in general: what it cuts,
whom it reaches, its odds of working, what it costs and where every number came from. The
engine turns it into one run per city. interventions/library/_template.toml documents every
field and is the reference for the format.

Two kinds:
  air       cuts a cause of PM2.5 (dust, transport, ...) by a fraction. A city measure cuts only
            the part of the cause that comes from inside the city ([[targets]]); a region measure
            cuts a source spread over several states and reaches everyone downwind ([region]).
  exposure  cuts what people breathe without touching the air outside (purifiers, masks):
            a share of a city's people, for a share of their hours, breathe less ([exposure]);
            with ages, a share of one age group, counted with that group's own death rates.

The evidence rule: every number in a file is either backed by exactly one [[evidence]] entry
(source, link, where in it, how it was seen) or listed in `placeholders` (a stand-in, not an
estimate), never both. p_success is outside the rule: it is a judgement, and p_success_basis
says why. numbers() gives the dotted names the rule covers.

load() raises Invalid with one line that starts with the field it is about, e.g.
"targets.dust.cut: must lie between 0 and 1, got 1.5".
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass
from datetime import date
from functools import cache
from pathlib import Path

from . import causes, paths
from .ages import AGE_STARTS
from . import lag as lags
from .intervention import Dist, Invalid, _check_floor, _integer, _number

LIBRARY = paths.HEALTH / "interventions" / "library"

KINDS = ("air", "exposure")
SCOPES = ("city", "region")
DRIVERS = ("person", "household", "city", "unit")
CURRENCIES = ("INR", "USD")
EVIDENCE_KEYS = ("O", "S", "R")     # O read at source; S seen in a snippet or summary; R recalled
# Causes a city measure may not target: they are not "inside the city" sources.
NOT_TARGETABLE = ("outside", "local_all", "other", "secondary_unassigned", "biomass_unassigned")
TARGETABLE = tuple(c for c in causes.HARMONISED if c not in NOT_TARGETABLE)

TOP_KEYS = ("name", "kind", "scope", "who_reaches", "cities", "min_share_pct", "start_year",
            "ramp_years", "duration_years", "lag", "p_success", "p_success_basis", "long_shot",
            "placeholders", "notes", "evidence_from", "evidence_note", "targets", "exposure", "region", "cost", "evidence")
TARGET_KEYS = ("cause", "cut", "months")
EXPOSURE_KEYS = ("covered", "hours", "cut", "months", "ages")
REGION_KEYS = ("receptor", "cut")
# A receptor file: one row per district the source-receptor study covers (an explicit 0 where its
# result is 0); delta_pm25_full is the change in that district's annual-mean PM2.5, µg/m³ (negative
# or 0), when the whole source is removed. Built by scripts/build_receptor.py.
RECEPTOR_COLUMNS = ("district", "state", "delta_pm25_full")
COST_KEYS = ("driver", "once", "annual", "units", "unit", "society_net_once",
             "society_net_annual", "currency", "year", "share_only_on_success", "partial", "full")
# [cost.full]: a sourced range for the whole cost of a measure whose [cost] is partial. Never read
# by the default scoring; sensitivity.py's what-if `full_cost` uses it in place of the annual cost.
FULL_KEYS = ("low", "high", "dist", "currency", "year", "adds", "evidence")
FULL_DISTS = ("uniform", "lognormal")
FULL_FIELDS = ("cost.full.low", "cost.full.high")
EVIDENCE_FIELDS = ("fields", "source", "url", "locator", "key", "retrieved", "derivation")
ALL_MONTHS = tuple(range(1, 13))


@dataclass(frozen=True)
class Target:
    cause: str
    cut: Dist                   # fraction of the cause's inside share removed, 0-1
    months: tuple[int, ...]


@dataclass(frozen=True)
class Exposure:
    covered: Dist               # share of the place's people reached, 0-1
    hours: Dist                 # share of their hours it works, 0-1
    cut: Dist                   # fraction cut in what they breathe in those hours, 0-1
    months: tuple[int, ...]
    ages: tuple[int, int] | None = None   # the people reached are this age group (first and last
                                          # age, whole bands); covered is a share of it


@dataclass(frozen=True)
class Region:
    receptor: str               # receptor_<name>.csv: in data/ (or beside the measure file)
    cut: Dist                   # fraction of the source removed, 0-1


@dataclass(frozen=True)
class FullCost:
    """The whole yearly cost per driver unit (same driver as [cost]), from low to high (read as
    the 5th and 95th percentiles of `dist`), in `currency` of `year`. adds: what it adds to the
    partial cost. key: its weakest evidence (O, then S, then R)."""
    low: float
    high: float
    dist: str
    currency: str
    year: int
    adds: str
    evidence: tuple["Evidence", ...]

    @property
    def annual(self) -> Dist:
        return Dist(self.dist, float(self.low), float(self.high))

    @property
    def key(self) -> str:
        return max((e.key for e in self.evidence), key=EVIDENCE_KEYS.index)


@dataclass(frozen=True)
class Cost:
    driver: str                 # person | household | city | unit
    once: Dist                  # per driver unit, at the start (fixed 0 when absent)
    annual: Dist                # per driver unit per year of duration (fixed 0 when absent)
    units: Dist | None          # driver = "unit" only: how many
    unit: str                   # driver = "unit" only: what one unit is ("" otherwise)
    society_net_once: Dist | None
    society_net_annual: Dist | None
    currency: str
    year: int
    share_only_on_success: float
    partial: str = ""           # what the cost leaves out, one plain sentence ("" = nothing said)
    full: FullCost | None = None  # a sourced range for the whole cost (what-ifs only)


@dataclass(frozen=True)
class Evidence:
    fields: tuple[str, ...]
    source: str
    url: str
    locator: str
    key: str
    retrieved: str
    derivation: str


@dataclass(frozen=True)
class Measure:
    id: str                          # file stem
    name: str
    kind: str
    scope: str
    who_reaches: str
    cities: tuple[str, ...] | None   # None = all (city scope); () for region scope
    min_share_pct: float | None
    start_year: int
    ramp_years: int
    duration_years: int
    lag: str
    p_success: float
    p_success_basis: str
    long_shot: bool
    targets: tuple[Target, ...]
    exposure: Exposure | None
    region: Region | None
    cost: Cost | None
    evidence: tuple[Evidence, ...]
    placeholders: tuple[str, ...]
    notes: str
    evidence_from: tuple[str, ...] = ()   # the places whose studies the numbers come from (()
                                          # = the measure's own place); flags borrowed_evidence
                                          # in a city that is none of them (score.evidence_places)
    evidence_note: str = ""          # free text for the flag sentence, e.g. "and field studies
                                     # worldwide"; never used to decide whether the flag shows

    def numbers(self) -> list[str]:
        """Dotted names of every number in the file that the evidence rule covers.
        cost.once and cost.annual count only when given and not zero (absent means 0)."""
        out = [f"targets.{t.cause}.cut" for t in self.targets]
        if self.exposure is not None:
            out += ["exposure.covered", "exposure.hours", "exposure.cut"]
        if self.region is not None:
            out.append("region.cut")
        c = self.cost
        if c is not None:
            for key in ("once", "annual"):
                if getattr(c, key) != Dist.fixed(0.0):
                    out.append(f"cost.{key}")
            for key in ("units", "society_net_once", "society_net_annual"):
                if getattr(c, key) is not None:
                    out.append(f"cost.{key}")
        return out


def _text(value, field: str, *, required: bool = True) -> str:
    if value is None and not required:
        return ""
    if not isinstance(value, str) or not value.strip():
        raise Invalid(f"{field}: must be a non-empty string, got {value!r}")
    return value.strip()


def _evidence_places(value) -> tuple[str, ...]:
    """evidence_from: a list of place names, e.g. ["Delhi-NCR", "Ludhiana"] (one name as a plain
    string is read as a list of one)."""
    if value is None:
        return ()
    if isinstance(value, str):
        value = [value]
    if (not isinstance(value, list) or not value
            or not all(isinstance(v, str) and v.strip() for v in value)):
        raise Invalid('evidence_from: must be a list of place names, e.g. ["Delhi-NCR", '
                      f'"Ludhiana"], got {value!r}')
    if len({v.strip().lower() for v in value}) != len(value):
        raise Invalid("evidence_from: a place is listed twice")
    return tuple(v.strip() for v in value)


def _table(value, field: str, keys: tuple[str, ...]) -> dict:
    if not isinstance(value, dict):
        raise Invalid(f"{field}: must be a table, got {value!r}")
    unknown = [k for k in value if k not in keys]
    if unknown:
        raise Invalid(f"{field}.{unknown[0]}: unknown key; use {', '.join(keys)}")
    return value


def _fraction(value, field: str) -> Dist:
    d = _check_floor(Dist.parse(value, field), field, 0, "a fraction")
    if d.p95 > 1:
        raise Invalid(f"{field}: must lie between 0 and 1, got {d.p95:g}")
    return d


def _months(value, field: str) -> tuple[int, ...]:
    if value is None:
        return ALL_MONTHS
    if (not isinstance(value, list) or not value
            or not all(isinstance(m, int) and not isinstance(m, bool) and 1 <= m <= 12
                       for m in value)
            or len(set(value)) != len(value)):
        raise Invalid(f"{field}: must be a list of distinct month numbers 1-12, got {value!r}")
    return tuple(sorted(value))


def _cities(value, scope: str) -> tuple[str, ...] | None:
    if scope == "region":
        if value is not None:
            raise Invalid("cities: only for city measures; a region measure reaches everyone "
                          "downwind of its source")
        return ()
    if value is None:
        raise Invalid('cities: missing; give "all" or a list of names from data/cities.csv')
    if value == "all":
        return None
    if not isinstance(value, list) or not value or not all(isinstance(v, str) for v in value):
        raise Invalid(f'cities: must be "all" or a list of city names, got {value!r}')
    known = causes.known_cities()
    for name in value:
        if name not in known:
            raise Invalid(f"cities: {name!r} is not in data/cities.csv")
    if len(set(value)) != len(value):
        raise Invalid("cities: a city is listed twice")
    return tuple(value)


def _targets(value) -> tuple[Target, ...]:
    if not isinstance(value, list) or not value:
        raise Invalid("targets: an air measure in a city needs at least one [[targets]] table")
    out, seen = [], set()
    for i, t in enumerate(value):
        t = _table(t, f"targets[{i + 1}]", TARGET_KEYS)
        cause = t.get("cause")
        if not isinstance(cause, str):
            raise Invalid(f"targets[{i + 1}].cause: missing; give a cause name")
        field = f"targets.{cause}"
        if cause in NOT_TARGETABLE:
            raise Invalid(f"{field}: a city measure cuts only causes from inside the city; "
                          f"{cause} is not one (use one of {', '.join(TARGETABLE)})")
        if cause not in TARGETABLE:
            raise Invalid(f"{field}: unknown cause; use one of {', '.join(TARGETABLE)}")
        if cause in seen:
            raise Invalid(f"{field}: listed twice")
        seen.add(cause)
        if "cut" not in t:
            raise Invalid(f"{field}.cut: missing; the fraction of the cause removed, 0 to 1")
        out.append(Target(cause, _fraction(t["cut"], f"{field}.cut"),
                          _months(t.get("months"), f"{field}.months")))
    return tuple(out)


def _exposure(value) -> Exposure:
    t = _table(value, "exposure", EXPOSURE_KEYS)
    parts = {}
    for key in ("covered", "hours", "cut"):
        if key not in t:
            raise Invalid(f"exposure.{key}: missing; a fraction, 0 to 1")
        parts[key] = _fraction(t[key], f"exposure.{key}")
    return Exposure(**parts, months=_months(t.get("months"), "exposure.months"),
                    ages=_ages(t.get("ages")))


def _ages(value) -> tuple[int, int] | None:
    """[first, last] age of the group reached, in whole age bands (ages.AGE_STARTS), or None."""
    if value is None:
        return None
    if (not isinstance(value, list) or len(value) != 2
            or not all(isinstance(v, int) and not isinstance(v, bool) for v in value)):
        raise Invalid(f"exposure.ages: must be [first, last] ages, e.g. [5, 19], got {value!r}")
    lo, hi = value
    if lo not in AGE_STARTS:
        raise Invalid(f"exposure.ages: {lo} is not the start of an age band; use one of "
                      f"{', '.join(map(str, AGE_STARTS))}")
    if hi < lo:
        raise Invalid(f"exposure.ages: the last age ({hi}) is below the first ({lo})")
    if hi + 1 not in AGE_STARTS and hi < AGE_STARTS[-1]:
        raise Invalid(f"exposure.ages: {hi} does not end an age band; the last age must be one "
                      f"less than a band's start (e.g. 19), or {AGE_STARTS[-1]} or more")
    return (lo, hi)


def _region(value) -> Region:
    t = _table(value, "region", REGION_KEYS)
    receptor = t.get("receptor")
    if (not isinstance(receptor, str) or not receptor.startswith("receptor_")
            or not receptor.endswith(".csv") or "/" in receptor):
        raise Invalid(f'region.receptor: must name a data/ file "receptor_<name>.csv", '
                      f"got {receptor!r}")
    if "cut" not in t:
        raise Invalid("region.cut: missing; the fraction of the source removed, 0 to 1")
    return Region(receptor, _fraction(t["cut"], "region.cut"))


def _cost(value) -> Cost:
    t = _table(value, "cost", COST_KEYS)
    driver = t.get("driver")
    if driver not in DRIVERS:
        raise Invalid(f"cost.driver: must be one of {', '.join(DRIVERS)}, got {driver!r}")
    once, annual = (_check_floor(Dist.parse(t.get(k, 0), f"cost.{k}"), f"cost.{k}", 0, "a cost")
                    for k in ("once", "annual"))
    units, unit = None, ""
    if driver == "unit":
        if "units" not in t:
            raise Invalid("cost.units: missing; driver \"unit\" needs how many units "
                          "(e.g. acres, stacks)")
        units = _check_floor(Dist.parse(t["units"], "cost.units"), "cost.units", 0, "a count")
        unit = _text(t.get("unit"), "cost.unit")
    else:
        for key in ("units", "unit"):
            if key in t:
                raise Invalid(f'cost.{key}: only for driver "unit"')
    net = {k: (Dist.parse(t[k], f"cost.{k}") if k in t else None)
           for k in ("society_net_once", "society_net_annual")}
    currency = t.get("currency")
    if currency not in CURRENCIES:
        raise Invalid(f"cost.currency: must be one of {', '.join(CURRENCIES)}, got {currency!r}")
    if "year" not in t:
        raise Invalid("cost.year: missing; give the price year of the costs")
    year = _integer(t["year"], "cost.year")
    from . import prices                        # (imported here: prices imports intervention)
    prices.to_base_inr(1.0, currency, year)     # Invalid if either table lacks the year
    share = _number(t.get("share_only_on_success", 0.0), "cost.share_only_on_success")
    if not 0 <= share <= 1:
        raise Invalid(f"cost.share_only_on_success: must be between 0 and 1, got {share:g}")
    partial = _text(t["partial"], "cost.partial") if "partial" in t else ""
    full = None
    if "full" in t:
        if not partial:
            raise Invalid("cost.full: only for a partial cost; give cost.partial first, saying "
                          "what the default cost leaves out")
        full = _full_cost(t["full"])
    return Cost(driver, once, annual, units, unit, net["society_net_once"],
                net["society_net_annual"], currency, year, share, partial, full)


def _full_cost(value) -> FullCost:
    """[cost.full]: low, high (yearly, per driver unit, at least 0, low below high), dist
    (uniform or lognormal), currency, year, adds (a sentence) and [[cost.full.evidence]] entries
    (one or more, each backing low, high or both; both must be backed)."""
    t = _table(value, "cost.full", FULL_KEYS)
    for key in ("low", "high", "dist", "currency", "year", "adds", "evidence"):
        if key not in t:
            raise Invalid(f"cost.full.{key}: missing; see interventions/library/_template.toml")
    low, high = _number(t["low"], "cost.full.low"), _number(t["high"], "cost.full.high")
    if low < 0:
        raise Invalid(f"cost.full.low: a cost is at least 0, got {low:g}")
    if not low < high:
        raise Invalid(f"cost.full.low: must be below cost.full.high ({low:g} vs {high:g})")
    dist = t["dist"]
    if dist not in FULL_DISTS:
        raise Invalid(f"cost.full.dist: must be one of {', '.join(FULL_DISTS)}, got {dist!r}")
    if dist == "lognormal" and low <= 0:
        raise Invalid("cost.full.low: a lognormal range needs low above 0")
    currency = t["currency"]
    if currency not in CURRENCIES:
        raise Invalid(f"cost.full.currency: must be one of {', '.join(CURRENCIES)}, "
                      f"got {currency!r}")
    year = _integer(t["year"], "cost.full.year")
    from . import prices
    try:
        prices.to_base_inr(1.0, currency, year)
    except Invalid as e:
        raise Invalid(f"cost.full.year: {e}") from None
    adds = _text(t["adds"], "cost.full.adds")
    evidence = _evidence(t["evidence"], "cost.full.evidence")
    if not evidence:
        raise Invalid("cost.full.evidence: give at least one source for the range")
    backed = set()
    for i, e in enumerate(evidence):
        bad = [f for f in e.fields if f not in FULL_FIELDS]
        if bad:
            raise Invalid(f"cost.full.evidence[{i + 1}].fields: {bad[0]!r} is not "
                          f"{' or '.join(FULL_FIELDS)}")
        backed |= set(e.fields)
    for f in FULL_FIELDS:
        if f not in backed:
            raise Invalid(f"{f}: no [[cost.full.evidence]] entry backs it")
    return FullCost(low, high, dist, currency, year, adds, evidence)


def _evidence(value, prefix: str = "evidence") -> tuple[Evidence, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise Invalid(f"{prefix}: must be [[{prefix}]] tables, one per source")
    out = []
    for i, e in enumerate(value):
        where = f"{prefix}[{i + 1}]"
        e = _table(e, where, EVIDENCE_FIELDS)
        names = e.get("fields")
        if (not isinstance(names, list) or not names
                or not all(isinstance(n, str) for n in names)):
            raise Invalid(f"{where}.fields: must be a list of the numbers it backs, "
                          f'e.g. ["targets.dust.cut"], got {names!r}')
        key = e.get("key")
        if key not in EVIDENCE_KEYS:
            raise Invalid(f"{where}.key: must be O (read at source), S (seen in a snippet or "
                          f"summary) or R (recalled), got {key!r}")
        url = _text(e.get("url"), f"{where}.url")
        if not url.startswith(("https://", "http://")):
            raise Invalid(f"{where}.url: must be a web link, got {url!r}")
        retrieved = _text(e.get("retrieved"), f"{where}.retrieved")
        try:
            date.fromisoformat(retrieved)
        except ValueError:
            raise Invalid(f"{where}.retrieved: must be a date, YYYY-MM-DD, got {retrieved!r}") from None
        out.append(Evidence(tuple(names), _text(e.get("source"), f"{where}.source"), url,
                            _text(e.get("locator"), f"{where}.locator"), key, retrieved,
                            _text(e.get("derivation"), f"{where}.derivation", required=False)))
    return tuple(out)


def _placeholders(value) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise Invalid(f'placeholders: must be a list of dotted names, e.g. ["cost.annual"], '
                      f"got {value!r}")
    if len(set(value)) != len(value):
        raise Invalid("placeholders: a name is listed twice")
    return tuple(value)


def _evidence_rule(m: Measure) -> None:
    numbers = m.numbers()
    backed: dict[str, int] = {}
    for i, e in enumerate(m.evidence):
        for name in e.fields:
            if name not in numbers:
                raise Invalid(f"evidence[{i + 1}].fields: {name!r} is not a number in this file "
                              f"(numbers: {', '.join(numbers) or 'none'})")
            if name in backed:
                raise Invalid(f"{name}: backed by two [[evidence]] entries "
                              f"({backed[name]} and {i + 1}); give each number one source")
            backed[name] = i + 1
    for name in m.placeholders:
        if name not in numbers:
            raise Invalid(f"placeholders: {name!r} is not a number in this file "
                          f"(numbers: {', '.join(numbers) or 'none'})")
        if name in backed:
            raise Invalid(f"{name}: both in placeholders and backed by [[evidence]]; "
                          "it is one or the other")
    for name in numbers:
        if name not in backed and name not in m.placeholders:
            raise Invalid(f"{name}: no [[evidence]] entry and not in placeholders; every number "
                          "needs its source, or must be marked a placeholder")


def parse(t: dict, measure_id: str) -> Measure:
    """A Measure from a file's parsed TOML table; Invalid on any problem."""
    unknown = [k for k in t if k not in TOP_KEYS]
    if unknown:
        raise Invalid(f"{unknown[0]}: unknown field; see interventions/library/_template.toml")
    for key in ("name", "kind", "scope", "who_reaches", "start_year", "duration_years",
                "p_success", "p_success_basis"):
        if key not in t:
            raise Invalid(f"{key}: missing; see interventions/library/_template.toml")

    name = _text(t["name"], "name")
    kind, scope = t["kind"], t["scope"]
    if kind not in KINDS:
        raise Invalid(f"kind: must be one of {', '.join(KINDS)}, got {kind!r}")
    if scope not in SCOPES:
        raise Invalid(f"scope: must be one of {', '.join(SCOPES)}, got {scope!r}")
    if kind == "exposure" and scope == "region":
        raise Invalid("scope: an exposure measure reaches a city's people; region scope is "
                      "only for air measures")
    who = _text(t["who_reaches"], "who_reaches")

    start = _integer(t["start_year"], "start_year")
    duration = _integer(t["duration_years"], "duration_years", minimum=1)
    ramp = _integer(t.get("ramp_years", 0), "ramp_years", minimum=0)
    if ramp > duration:
        raise Invalid(f"ramp_years: {ramp} is longer than duration_years ({duration})")
    lag = t.get("lag", "epa20")
    if lag not in lags.PROFILES:
        raise Invalid(f"lag: must be one of {', '.join(lags.PROFILES)}, got {lag!r}")
    p = _number(t["p_success"], "p_success")
    if not 0 <= p <= 1:
        raise Invalid(f"p_success: must be between 0 and 1, got {p:g}")
    basis = t["p_success_basis"]
    if not isinstance(basis, str) or not basis.strip():
        raise Invalid("p_success_basis: must say why p_success is what it is (a judgement "
                      "unless a source is cited)")
    long_shot = t.get("long_shot", False)
    if not isinstance(long_shot, bool):
        raise Invalid(f"long_shot: must be true or false, got {long_shot!r}")
    notes = t.get("notes", "")
    if not isinstance(notes, str):
        raise Invalid("notes: must be a string")

    is_city_air = kind == "air" and scope == "city"
    min_share = t.get("min_share_pct")
    if min_share is not None:
        if not is_city_air:
            raise Invalid("min_share_pct: only for air measures in cities")
        min_share = _number(min_share, "min_share_pct")
        if not 0 <= min_share <= 100:
            raise Invalid(f"min_share_pct: must be between 0 and 100, got {min_share:g}")

    for key, wanted, what in (("targets", is_city_air, "air measures in cities"),
                              ("exposure", kind == "exposure", "exposure measures"),
                              ("region", scope == "region", "region measures")):
        if key in t and not wanted:
            raise Invalid(f"{key}: only for {what}")
    targets = _targets(t.get("targets")) if is_city_air else ()
    exposure = None
    if kind == "exposure":
        if "exposure" not in t:
            raise Invalid("exposure: missing; an exposure measure needs an [exposure] table")
        exposure = _exposure(t["exposure"])
    region = None
    if scope == "region":
        if "region" not in t:
            raise Invalid("region: missing; a region measure needs a [region] table")
        region = _region(t["region"])

    cost = _cost(t["cost"]) if "cost" in t else None
    if exposure is not None and exposure.ages is not None and cost is not None \
            and cost.driver == "household":
        raise Invalid('exposure.ages: households are not an age group; with ages, give the cost '
                      'per "person" (or "unit" or "city")')
    if scope == "region" and cost is not None and cost.driver == "household":
        raise Invalid('cost.driver: "household" needs one city\'s household size; a region '
                      'measure uses "unit", "city" (a total for the whole region) or "person"')

    m = Measure(
        id=measure_id, name=name, kind=kind, scope=scope, who_reaches=who,
        cities=_cities(t.get("cities"), scope), min_share_pct=min_share, start_year=start,
        ramp_years=ramp, duration_years=duration, lag=lag, p_success=p,
        p_success_basis=basis.strip(), long_shot=long_shot, targets=targets, exposure=exposure,
        region=region, cost=cost,
        evidence=_evidence(t.get("evidence")), placeholders=_placeholders(t.get("placeholders")),
        notes=notes.strip(), evidence_from=_evidence_places(t.get("evidence_from")),
        evidence_note=_text(t.get("evidence_note"), "evidence_note", required=False))
    if m.evidence_note and not m.evidence_from:
        raise Invalid("evidence_note: needs evidence_from (the places it adds to)")
    _evidence_rule(m)
    return m


def load(path: Path | str) -> Measure:
    """Read and check a measure file; its id is the file name without .toml. A region measure's
    receptor file must exist (data/, or beside the measure file) and be well formed."""
    path = Path(path)
    try:
        with open(path, "rb") as f:
            t = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise Invalid(f"{path.name}: not valid TOML ({e})") from None
    m = parse(t, path.stem)
    if m.region is not None:
        receptor(m.region.receptor, path.parent)
    return m


def receptor_path(name: str, folder: Path | str | None = None) -> Path:
    """Where a receptor file is: beside the measure files in `folder` if one is there (test
    fixtures), else data/. Invalid if neither has it."""
    for d in ([Path(folder)] if folder is not None else []) + [paths.DATA]:
        if (d / name).is_file():
            return d / name
    raise Invalid(f"region.receptor: no file {name!r} in data/; build it with "
                  "scripts/build_receptor.py (or write the lead in data/MISSING.md)")


def receptor(name: str, folder: Path | str | None = None):
    """The receptor table (RECEPTOR_COLUMNS plus `label`, each district's Place.label), checked:
    exact columns, every district resolves (places.resolve, kind="district") and is listed once,
    every delta a number at or below 0. Invalid naming the file and the problem."""
    path = receptor_path(name, folder)
    stamp = path.stat().st_mtime_ns
    return _receptor(str(path), stamp).copy()


def district(name: str, state: str):
    """The district Place a receptor row names: the one spelled exactly so in data/places.csv
    (two maps' spellings can match the same key, e.g. 'North  & Middle Andaman' and 'North and
    Middle Andaman'), else places.resolve(kind="district"). KeyError if none."""
    from . import places

    st = places.canonical_state(state)
    exact = places.Place("district", name, st)
    t = places._table()
    if ((t.kind == "district") & (t.name == name) & (t.state == st)).any():
        return exact
    return places.resolve(f"{name}, {state}", kind="district")


@cache
def _receptor(path: str, _stamp: int):
    import pandas as pd

    from . import places

    name = Path(path).name
    try:
        t = pd.read_csv(path)
    except (pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError) as e:
        raise Invalid(f"region.receptor: {name} is not a readable CSV ({e})") from None
    if tuple(t.columns) != RECEPTOR_COLUMNS:
        raise Invalid(f"region.receptor: {name} must have exactly the columns "
                      f"{', '.join(RECEPTOR_COLUMNS)}; got {', '.join(map(str, t.columns))}")
    if t.empty:
        raise Invalid(f"region.receptor: {name} has no rows")
    delta = pd.to_numeric(t.delta_pm25_full, errors="coerce")
    bad = t[delta.isna() | ~delta.between(-1e6, 0)]
    if len(bad):
        r = bad.iloc[0]
        raise Invalid(f"region.receptor: {name}: delta_pm25_full must be a number at or below 0 "
                      f"(the change when the source is removed), got {r.delta_pm25_full!r} for "
                      f"{r.district}, {r.state}")
    labels = []
    for r in t.itertuples():
        try:
            labels.append(district(r.district, r.state).label)
        except KeyError as e:
            raise Invalid(f"region.receptor: {name}: {e.args[0]}") from None
    t = t.assign(delta_pm25_full=delta.astype(float), label=labels)
    dup = t[t.label.duplicated()]
    if len(dup):
        raise Invalid(f"region.receptor: {name}: {dup.label.iloc[0]} is listed twice")
    return t


def library(folder: Path | str = LIBRARY) -> dict[str, Measure]:
    """Every measure in `folder` by id, skipping files whose names start with "_" (the template)."""
    return {p.stem: load(p) for p in sorted(Path(folder).glob("*.toml"))
            if not p.name.startswith("_")}


def check_library(folder: Path | str = LIBRARY) -> list[str]:
    """Problems across the library, one line each ("<file>: <problem>"); [] = clean.
    The template is checked too: it must stay a valid measure."""
    problems = []
    for p in sorted(Path(folder).glob("*.toml")):
        try:
            load(p)
        except Invalid as e:
            problems.append(f"{p.name}: {e}")
    return problems


def persons_per_household(city: str) -> float:
    """People per household in the city, Census 2011: its population divided by its number of
    households (data/city_households.csv). The household cost driver uses it to turn a cost per
    household into a cost per person. KeyError for a city not in data/cities.csv."""
    import pandas as pd

    h = pd.read_csv(paths.DATA / "city_households.csv").set_index("city")
    if city not in h.index:
        raise KeyError(f"{city!r} is not one of the cities in data/city_households.csv")
    return float(h.loc[city, "population"] / h.loc[city, "households"])
