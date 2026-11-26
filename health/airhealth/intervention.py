"""Intervention files: a short TOML file describing a change in PM2.5, its timing, odds and cost.

interventions/_template.toml documents every field. load() reads a file and checks it; any
problem raises Invalid with one line that starts with the field it is about, e.g.
"p_success: must be between 0 and 1, got 1.2".

Any number marked "Dist" may be given as a plain number or as a distribution given by its
5th and 95th percentiles: {dist = "normal" | "lognormal" | "uniform" | "triangular",
p5 = ..., p95 = ...}; triangular also takes its mode. Uniform's ends lie outside p5 and p95
(the 5th and 95th percentiles are 5% of the width in from each end). A lognormal must not
cross zero; a negative one (a cut) is the mirror image of a positive one.

The change is given exactly one way: delta (µg/m³, signed, negative = cleaner), pct (signed
percent of each unit's level), to (a target level), or a twelve-month profile, monthly_delta
or monthly_pct, which becomes an annual delta or pct by annual_from_monthly (day-weighted).
Exposure maps are annual means, so a percent cut has to be turned into an annual one, and
months are not equally polluted: a 20% cut in a month that is 2.4 times the annual mean is a
48% cut of the mean for that month. monthly_pct therefore weights each month by the place's
own PM2.5 shape (airhealth/months.py): twelve numbers, January first, with day-weighted mean 1,
from the CPCB monthly means of 2023-25 (data/monthly_cpcb.csv, data/monthly_cpcb_state.csv; all
of 2016-25 if the window lacks a month). A city with all twelve months in its CPCB data uses its
own monitors; a city without borrows the largest such city in its state, else the state-wide
shape of all CPCB monitors in the state; a state or district takes the population-weighted shape
of its such cities, else the state-wide shape; anywhere with none falls back to India's. Each
result says which (Run.shapes, the report footer). monthly_delta
is in µg/m³ and is unaffected. When
months are given as distributions they are drawn together (one percentile for all twelve in
each draw): an intervention that does better than expected in November is taken to do
better in December too.

Costs are in the currency and price year of the file, and are turned into 2025 rupees
(airhealth/prices.py): rupees are scaled by India's GDP deflator (World Bank, data/gdp_deflator_ind.csv)
from cost.year to 2025; dollars are first turned into rupees at the World Bank's annual average
rate for cost.year (data/fx_inr_usd.csv), then scaled the same way. A cost.year missing from
either table (2000-2025) is Invalid.
"""
from __future__ import annotations

import tomllib
from collections.abc import Sequence
from dataclasses import dataclass, fields
from functools import cache
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
from scipy import optimize, stats

from . import lag as lags
from . import months, paths
from . import places as places_
from .impact import Change
from .inputs import Sources
from .months import MONTH_DAYS, MONTHS  # noqa: F401  (re-exported: tests and callers use them here)
from .places import Place

Z95 = stats.norm.ppf(0.95)
DIST_KINDS = ("normal", "lognormal", "uniform", "triangular")
CHANGE_KEYS = ("delta", "pct", "to", "monthly_delta", "monthly_pct")
TOP_KEYS = ("name", "places", "start_year", "ramp_years", "duration_years", "p_success",
            "from_level", "lag", "notes", "change", "cost", "sources")
COST_KEYS = ("once", "annual", "currency", "year", "share_only_on_success")
CURRENCIES = ("INR", "USD")
FX_FILE = "fx_inr_usd.csv"


class Invalid(ValueError):
    """An intervention file that cannot be used; the message is one line naming the field."""


@cache
def _inr_per_usd() -> dict[int, float]:
    t = pd.read_csv(paths.DATA / FX_FILE)
    return dict(zip(t.year.astype(int), t.inr_per_usd.astype(float)))


def usd_per(currency: str, year: int) -> float:
    """Dollars per unit of `currency` at the annual average rate of `year`."""
    if currency == "USD":
        return 1.0
    rates = _inr_per_usd()
    if year not in rates:
        raise Invalid(f"cost.year: no rupee-dollar rate for {year}; data/{FX_FILE} covers "
                      f"{min(rates)}-{max(rates)} (World Bank annual averages)")
    return 1 / rates[year]


def annual_from_monthly(monthly: Sequence[float]) -> float:
    """Day-weighted mean of twelve monthly changes (January first, a 365-day year)."""
    return float(np.dot(MONTH_DAYS, np.asarray(monthly, dtype=float)) / MONTH_DAYS.sum())


def _number(value, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise Invalid(f"{field}: must be a number, got {value!r}")
    return float(value)


def _integer(value, field: str, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise Invalid(f"{field}: must be a whole number, got {value!r}")
    if minimum is not None and value < minimum:
        raise Invalid(f"{field}: must be at least {minimum}, got {value}")
    return value


def _triangle(p5: float, p95: float, mode: float) -> tuple[float, float]:
    """Ends (a, b) of the triangular distribution with this mode, 5th and 95th percentiles."""
    d1, d2 = mode - p5, p95 - mode

    def gaps(x):                       # x = log(mode - a), log(b - mode)
        left, right = np.exp(x)
        width = left + right
        return [(left - d1) ** 2 - 0.05 * width * left, (right - d2) ** 2 - 0.05 * width * right]

    w = p95 - p5
    sol = optimize.root(gaps, np.log([d1 + 0.3 * w, d2 + 0.3 * w]), tol=1e-12)
    left, right = np.exp(sol.x)
    if not sol.success or max(abs(g) for g in gaps(sol.x)) > 1e-9 * w * w:
        raise ValueError("no triangular distribution has these percentiles")
    return mode - left, mode + right


@dataclass(frozen=True)
class Dist:
    """A number or a distribution, given by its 5th and 95th percentiles."""
    kind: Literal["fixed", "normal", "lognormal", "uniform", "triangular"]
    p5: float
    p95: float
    mode: float | None = None

    @classmethod
    def fixed(cls, value: float) -> Dist:
        return cls("fixed", float(value), float(value))

    @classmethod
    def parse(cls, value, field: str) -> Dist:
        """A Dist from a TOML value (a number or a table); Invalid names `field` on error."""
        if not isinstance(value, dict):
            return cls.fixed(_number(value, field))
        unknown = set(value) - {"dist", "p5", "p95", "mode"}
        if unknown:
            raise Invalid(f"{field}: unknown key {sorted(unknown)[0]!r}; "
                          "a distribution takes dist, p5, p95 and (triangular) mode")
        kind = value.get("dist")
        if kind not in DIST_KINDS:
            raise Invalid(f"{field}: dist must be one of {', '.join(DIST_KINDS)}, got {kind!r}")
        for key in ("p5", "p95"):
            if key not in value:
                raise Invalid(f"{field}: a {kind} distribution needs {key}")
        p5, p95 = _number(value["p5"], f"{field}.p5"), _number(value["p95"], f"{field}.p95")
        if not p5 < p95:
            raise Invalid(f"{field}: p5 ({p5:g}) must be below p95 ({p95:g})")
        mode = None
        if kind == "triangular":
            if "mode" not in value:
                raise Invalid(f"{field}: a triangular distribution needs mode")
            mode = _number(value["mode"], f"{field}.mode")
            if not p5 <= mode <= p95:
                raise Invalid(f"{field}: mode ({mode:g}) must lie between p5 and p95")
        elif "mode" in value:
            raise Invalid(f"{field}: mode is only for a triangular distribution")
        if kind == "lognormal" and not (p5 > 0 or p95 < 0):
            raise Invalid(f"{field}: a lognormal cannot cross zero (p5 {p5:g}, p95 {p95:g})")
        d = cls(kind, p5, p95, mode)
        if kind == "triangular":
            try:
                d._frozen()
            except ValueError as e:
                raise Invalid(f"{field}: {e}") from None
        return d

    def _frozen(self):
        """The scipy distribution (for a negative lognormal: of the magnitude)."""
        p5, p95 = self.p5, self.p95
        if self.kind == "normal":
            return stats.norm((p5 + p95) / 2, (p95 - p5) / (2 * Z95))
        if self.kind == "lognormal":
            lo, hi = sorted((abs(p5), abs(p95)))
            mu, sigma = (np.log(lo) + np.log(hi)) / 2, (np.log(hi) - np.log(lo)) / (2 * Z95)
            return stats.lognorm(sigma, scale=np.exp(mu))
        if self.kind == "uniform":
            width = (p95 - p5) / 0.9
            return stats.uniform(p5 - 0.05 * width, width)
        a, b = _triangle(p5, p95, self.mode)
        return stats.triang((self.mode - a) / (b - a), loc=a, scale=b - a)

    def ppf(self, q) -> np.ndarray:
        """The value at quantile(s) q."""
        q = np.asarray(q, dtype=float)
        if self.kind == "fixed":
            return np.full(q.shape, self.p5)
        if self.kind == "lognormal" and self.p95 < 0:
            return -self._frozen().ppf(1 - q)
        return self._frozen().ppf(q)

    def sample(self, rng: np.random.Generator, n: int) -> np.ndarray:
        return self.ppf(rng.random(n))

    @property
    def median(self) -> float:
        return float(self.ppf(0.5))

    def scaled(self, k: float) -> Dist:
        """Every percentile (and the mode) times k; k = 0 is the fixed value 0."""
        if k < 0:
            raise ValueError(f"scaled: k must not be negative, got {k:g}")
        if k == 0:
            return Dist.fixed(0.0)
        return Dist(self.kind, self.p5 * k, self.p95 * k,
                    None if self.mode is None else self.mode * k)


@dataclass(frozen=True)
class Linear:
    """sum of coef_i x dist_i, every dist drawn at the same quantile (as months are)."""
    terms: tuple[tuple[float, Dist], ...]

    def ppf(self, q) -> np.ndarray:
        return sum(c * d.ppf(q) for c, d in self.terms)

    def sample(self, rng: np.random.Generator, n: int) -> np.ndarray:
        return self.ppf(rng.random(n))

    @property
    def median(self) -> float:
        return float(self.ppf(0.5))


@dataclass(frozen=True)
class Product:
    """Product of dists, every one drawn at the same quantile."""
    factors: tuple[Dist, ...]

    def ppf(self, q) -> np.ndarray:
        out = self.factors[0].ppf(q)
        for d in self.factors[1:]:
            out = out * d.ppf(q)
        return out

    def sample(self, rng: np.random.Generator, n: int) -> np.ndarray:
        return self.ppf(rng.random(n))

    @property
    def median(self) -> float:
        return float(self.ppf(0.5))


@dataclass(frozen=True)
class MonthlyMean:
    """The annual change from twelve monthly ones, drawn together (see module docstring)."""
    months: tuple[Dist | Linear | Product, ...]   # anything with ppf

    def ppf(self, q, weights: np.ndarray | None = None) -> np.ndarray:
        """Weighted sum of the months' quantiles; weights default to days / 365."""
        w = MONTH_DAYS / MONTH_DAYS.sum() if weights is None else weights
        return sum(wi * m.ppf(q) for wi, m in zip(w, self.months))

    def sample(self, rng: np.random.Generator, n: int) -> np.ndarray:
        return self.ppf(rng.random(n))

    @property
    def median(self) -> float:
        return float(self.ppf(0.5))


@dataclass(frozen=True, kw_only=True)
class Intervention:
    name: str
    places: list[Place]
    change_kind: Literal["delta", "pct", "to"]
    change: Dist | MonthlyMean          # annual; a MonthlyMean when given month by month
    monthly: list[Dist] | None
    start_year: int
    ramp_years: int = 0
    duration_years: int
    p_success: float
    cost_once: Dist
    cost_annual: Dist
    cost_currency: Literal["INR", "USD"]
    cost_year: int
    cost_share_only_on_success: float = 0.0
    lag: str = "epa20"
    from_level: float | None = None     # what-if: every unit starts here (pm25_override)
    notes: str = ""
    sources: Sources = Sources()        # [sources]: population, death_rates, deaths
    covered: Dist | None = None         # share of each place's people the change reaches, 0-1
    cost_per_covered: bool = False      # cost Dists are per covered unit: cost x the covered draw
    scale: dict[str, float] | None = None   # Place.label -> multiplier of the annual change

    def as_change(self, value: float) -> Change:
        """The impact.Change for one value (e.g. one draw) of the annual change."""
        return Change(**{self.change_kind: float(value)})

    def annual_change(self, place: Place, q: np.ndarray) -> np.ndarray:
        """The annual change at quantiles q for this place: monthly_pct weights months by the
        place's shape; every other kind ignores the place. When scale is set the result is
        multiplied by scale[place.label] (a place missing from it is a KeyError)."""
        if self.monthly is not None and self.change_kind == "pct":
            out = self.change.ppf(q, MONTH_DAYS * months.shape(place).values / MONTH_DAYS.sum())
        else:
            out = self.change.ppf(q)
        if self.scale is not None:
            if place.label not in self.scale:
                raise KeyError(f"scale: no multiplier for {place.label!r}")
            out = out * self.scale[place.label]
        return out


def _places(value) -> list[Place]:
    if not isinstance(value, list) or not value or not all(isinstance(v, str) for v in value):
        raise Invalid(f"places: must be a list of place names, e.g. [\"Delhi\"], got {value!r}")
    out = []
    for text in value:
        try:
            place = places_.resolve(text)
        except KeyError as e:
            raise Invalid(f"places: {e.args[0]}") from None
        if place in out:
            raise Invalid(f"places: {place.name} is listed twice")
        out.append(place)
    return out


def _check_floor(d: Dist, field: str, floor: float, what: str) -> Dist:
    if d.p5 < floor:
        raise Invalid(f"{field}: {what} cannot go below {floor:g}, got {d.p5:g}")
    return d


def _change(table) -> tuple[str, Dist | MonthlyMean, list[Dist] | None]:
    if not isinstance(table, dict):
        raise Invalid("change: must be a [change] table")
    given = [k for k in table if k in CHANGE_KEYS]
    unknown = [k for k in table if k not in CHANGE_KEYS]
    if unknown:
        raise Invalid(f"change.{unknown[0]}: unknown key; use one of {', '.join(CHANGE_KEYS)}")
    if len(given) != 1:
        raise Invalid(f"change: give exactly one of {', '.join(CHANGE_KEYS)} "
                      f"(got {', '.join(given) or 'none'})")
    key = given[0]
    field = f"change.{key}"
    if key.startswith("monthly_"):
        values = table[key]
        if not isinstance(values, list) or len(values) != 12:
            n = len(values) if isinstance(values, list) else "not a list"
            raise Invalid(f"{field}: needs twelve values, January to December (got {n})")
        months = [Dist.parse(v, f"{field} ({m})") for v, m in zip(values, MONTHS)]
        kind = key.removeprefix("monthly_")
        if kind == "pct":
            for d, m in zip(months, MONTHS):
                _check_floor(d, f"{field} ({m})", -100, "a percent change")
        return kind, MonthlyMean(tuple(months)), months
    d = Dist.parse(table[key], field)
    if key == "pct":
        _check_floor(d, field, -100, "a percent change")
    if key == "to":
        _check_floor(d, field, 0, "a target level")
    return key, d, None


def _cost(table) -> dict:
    if not isinstance(table, dict):
        raise Invalid("cost: missing; give a [cost] table with currency and year")
    unknown = [k for k in table if k not in COST_KEYS]
    if unknown:
        raise Invalid(f"cost.{unknown[0]}: unknown key; use {', '.join(COST_KEYS)}")
    once, annual = (_check_floor(Dist.parse(table.get(k, 0), f"cost.{k}"), f"cost.{k}", 0,
                                 "a cost") for k in ("once", "annual"))
    currency = table.get("currency")
    if currency not in CURRENCIES:
        raise Invalid(f"cost.currency: must be one of {', '.join(CURRENCIES)}, got {currency!r}")
    if "year" not in table:
        raise Invalid("cost.year: missing; give the price year of the costs")
    share = _number(table.get("share_only_on_success", 0.0), "cost.share_only_on_success")
    if not 0 <= share <= 1:
        raise Invalid(f"cost.share_only_on_success: must be between 0 and 1, got {share:g}")
    year = _integer(table["year"], "cost.year")
    from . import prices                        # (imported here: prices imports this module)
    prices.to_base_inr(1.0, currency, year)     # Invalid if either table lacks the year
    return dict(cost_once=once, cost_annual=annual, cost_currency=currency, cost_year=year,
                cost_share_only_on_success=share)


def _sources(table) -> Sources:
    if table is None:
        return Sources()
    if not isinstance(table, dict):
        raise Invalid("sources: must be a table, e.g. [sources] deaths = \"unwpp\"")
    try:
        return Sources(**{k: v for k, v in table.items()})
    except TypeError:
        raise Invalid(f"sources: keys are {', '.join(f.name for f in fields(Sources))}") from None
    except ValueError as e:
        raise Invalid(f"sources.{e}") from None


def load(path: Path | str) -> Intervention:
    """Read and check an intervention file."""
    path = Path(path)
    try:
        with open(path, "rb") as f:
            t = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise Invalid(f"{path.name}: not valid TOML ({e})") from None

    unknown = [k for k in t if k not in TOP_KEYS]
    if unknown:
        raise Invalid(f"{unknown[0]}: unknown field; see interventions/_template.toml")
    for key in ("name", "places", "start_year", "duration_years", "p_success", "change"):
        if key not in t:
            raise Invalid(f"{key}: missing; see interventions/_template.toml")

    name = t["name"]
    if not isinstance(name, str) or not name.strip():
        raise Invalid(f"name: must be a non-empty string, got {name!r}")
    duration = _integer(t["duration_years"], "duration_years", minimum=1)
    ramp = _integer(t.get("ramp_years", 0), "ramp_years", minimum=0)
    if ramp > duration:
        raise Invalid(f"ramp_years: {ramp} is longer than duration_years ({duration})")
    p = _number(t["p_success"], "p_success")
    if not 0 <= p <= 1:
        raise Invalid(f"p_success: must be between 0 and 1, got {p:g}")
    lag = t.get("lag", "epa20")
    if lag not in lags.PROFILES:
        raise Invalid(f"lag: must be one of {', '.join(lags.PROFILES)}, got {lag!r}")
    from_level = t.get("from_level")
    if from_level is not None:
        from_level = _number(from_level, "from_level")
        if from_level < 0:
            raise Invalid(f"from_level: must be at least 0 µg/m³, got {from_level:g}")
    notes = t.get("notes", "")
    if not isinstance(notes, str):
        raise Invalid("notes: must be a string")

    kind, change, monthly = _change(t["change"])
    return Intervention(
        name=name.strip(), places=_places(t["places"]), change_kind=kind, change=change,
        monthly=monthly, start_year=_integer(t["start_year"], "start_year"), ramp_years=ramp,
        duration_years=duration, p_success=p, lag=lag, from_level=from_level,
        notes=notes.strip(), sources=_sources(t.get("sources")), **_cost(t.get("cost")))
