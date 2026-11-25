"""Risk curves: how mortality (or life expectancy) changes with annual-mean PM2.5 (µg/m³).

Open tier (parameters committed in data/, sources in data/sources.toml):
  loglinear_jaganathan  Jaganathan et al. 2024, Indian districts, 8.6% per 10 µg/m³.
  loglinear_brown       Brown et al. 2022, Million Death Study, RR 1.01 per 10.
  loglinear_vodonos     Vodonos et al. 2018 meta-regression, slope at a study mean of 30.
  gemm_ncd_lri          Burnett et al. 2018 GEMM, NCD+LRI deaths, age-specific.
  aqli                  AQLI, 0.98 years of life expectancy per 10 µg/m³ above 5.
Local tier (IHME files in data_local/, see IHME_DOWNLOADS.md): gbd2019, gbd2023,
gemm_5cod, risk by cause of death applied to IHME's deaths by cause (ihme_curves.py). get()
raises Unavailable while their files are missing.

Each curve applies from its own min_age; younger bands get a relative risk of 1.0. The
log-linear curves carry min_age in data/curves_loglinear.csv (Jaganathan 0: all-age deaths;
Brown 15: studied at 15-69; Vodonos 25). GEMM starts at its first parameter row (25). AQLI has
no relative risk; its min_age (0) is where the derived-deaths step applies its multiplier on
death rates, because AQLI's estimate is all-age life expectancy. A curve's floor is the
concentration below which no further benefit is assumed: rr(c) compares max(c, floor) with
the floor itself.

Uncertainty (sample): a log-linear slope is drawn on the scale the interval was estimated
on, the log of the relative risk: ln RR per 10 µg/m³ ~ Normal(ln(1 + pct_per_10/100),
se_log_per_10), with se_log_per_10 = (ln upper − ln lower) / (2 × 1.959964) from the printed
95% interval, both bounds first put on the per-10 µg/m³ scale. The draw is not truncated at
zero: where an interval reaches a relative risk of 1.00 (Brown 2022: 1.01, 1.00 to 1.03),
about one draw in eleven has a negative slope, cleaner air raising deaths, and is kept as
drawn, because cutting those draws off would move the mean above the published estimate.
se_pct_per_10 is the same interval on the percent scale, kept for reference. GEMM draws
theta_age + se_age × Z with one Z shared by all ages (the authors' calculator moves every
age together, theta ± 2 se). AQLI publishes no interval, so its sample() is the curve
unchanged.

sample_many(rng, n) draws n curves at once: the result is one curve whose sampled parameter
is an array of shape (n, 1), so rr() and ratio() broadcast over draws along the first axis
(a concentration of shape (units,) or (n, units) gives (n, units)). It draws from the same
distribution as sample(), one draw per row.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from functools import cache
from typing import Literal

import numpy as np
import pandas as pd

from . import ihme, paths
from .ages import ADULT_FROM

Z95 = 1.959964

# Highest long-term PM2.5 observed in any cohort behind GEMM: the Chinese male cohort.
MAX_COHORT_PM25 = 84.0
MAX_COHORT_PM25_SOURCE = (
    "Burnett R, et al. Global estimates of mortality associated with long-term exposure to "
    "outdoor fine particulate matter. PNAS 2018; 115: 9592-97, Results: 'a study of Chinese men "
    "with long-term outdoor PM2.5 exposures up to 84 µg/m3' (exposure range 15-84 µg/m3); "
    "Methods fit the GEMM over 2.4-84 µg/m3. https://pmc.ncbi.nlm.nih.gov/articles/PMC6156628/"
)

GEMM_CF = 2.4  # GEMM counterfactual: lowest concentration in any of the 41 cohorts
GEMM_SOURCE = (
    "Burnett R, Chen H, Szyszkowicz M, et al. Global estimates of mortality associated with "
    "long-term exposure to outdoor fine particulate matter. PNAS 2018; 115: 9592-97, "
    "https://pmc.ncbi.nlm.nih.gov/articles/PMC6156628/. Age-specific NCD+LRI parameters "
    "(all regions, including the China male cohort) as deposited by the authors: "
    "https://github.com/mszyszkowicz/DataGEMM, 'GEMM Calculator (PNAS)_ab.xlsx', "
    "sheet 'GEMM fit parameters'."
)
AQLI_SOURCE = (
    "Air Quality Life Index (EPIC, University of Chicago), India fact sheet 2025: 'an additional "
    "10 µg/m3 of PM2.5 reduces life expectancy by 0.98 years', against the WHO guideline of "
    "5 µg/m3. https://aqli.epic.uchicago.edu/files/India%20FactSheet_2025_GlobalWV.pdf; "
    "methodology https://aqli.epic.uchicago.edu/about/methodology/"
)


Unavailable = ihme.Unavailable   # a registered curve whose input files are not in data_local/


def _scalar_or_array(x: np.ndarray) -> float | np.ndarray:
    return x.item() if x.ndim == 0 else x


def _set(obj, **values):
    for k, v in values.items():
        object.__setattr__(obj, k, v)


def _evolve(obj, **changes):
    """A copy of a frozen curve with some attributes changed."""
    new = copy.copy(obj)
    _set(new, **changes)
    return new


@dataclass(frozen=True)
class Curve:
    name: str
    label: str
    kind: Literal["relative_risk", "life_expectancy"]
    floor: float
    death_scope: Literal["all", "ncd_lri"]
    source: str
    min_age: int  # youngest age band the curve applies to; younger bands get rr = 1

    def _log_h(self, c: np.ndarray, age: int) -> np.ndarray:
        """Log hazard ratio at absolute concentration c (vs. the curve's own zero)."""
        raise NotImplementedError

    def _clamp(self, c) -> np.ndarray:
        return np.maximum(np.asarray(c, dtype=float), max(self.floor, 0.0))

    def rr(self, c: float | np.ndarray, age: int) -> float | np.ndarray:
        """Relative risk at c against the floor, for the age band starting at `age`."""
        c = self._clamp(c)
        if age < self.min_age:
            return _scalar_or_array(np.ones_like(c))
        floor = np.asarray(max(self.floor, 0.0))
        return _scalar_or_array(np.exp(self._log_h(c, age) - self._log_h(floor, age)))

    def age_group(self, age: int):
        """A key shared by ages whose risk is the same function of concentration (None for
        ages below min_age, where rr is 1). Lets callers compute a ratio once per group."""
        return None if age < self.min_age else 0

    def ratio(self, c_from, c_to, age: int) -> float | np.ndarray:
        """rr(c_to) / rr(c_from): the factor on death rates when air moves from c_from to c_to."""
        out = np.asarray(self.rr(c_to, age)) / np.asarray(self.rr(c_from, age))
        return _scalar_or_array(out)

    def sample(self, rng: np.random.Generator) -> Curve:
        raise NotImplementedError

    def sample_many(self, rng: np.random.Generator, n: int) -> Curve:
        raise NotImplementedError

    def with_floor(self, floor: float) -> Curve:
        return _evolve(self, floor=float(floor))


@dataclass(frozen=True, init=False)
class LogLinear(Curve):
    """rr = exp(beta · (c − floor)), beta = ln(1 + pct/100) / 10. se_log_per_10 is the
    standard error of ln RR per 10 µg/m³, the scale sample() draws on; if not given it is
    taken from se_pct_per_10 (se_pct / (100 + pct))."""
    pct_per_10: float = 0.0
    se_pct_per_10: float = 0.0
    se_log_per_10: float = 0.0

    def __init__(self, name: str, pct_per_10: float, se_pct_per_10: float, floor: float,
                 label: str = "", source: str = "", death_scope: str = "all",
                 min_age: int = ADULT_FROM, se_log_per_10: float | None = None):
        if se_log_per_10 is None:
            se_log_per_10 = float(se_pct_per_10) / (100 + float(pct_per_10))
        _set(self, name=name, label=label or name, kind="relative_risk", floor=float(floor),
             death_scope=death_scope, source=source, min_age=int(min_age),
             pct_per_10=float(pct_per_10), se_pct_per_10=float(se_pct_per_10),
             se_log_per_10=float(se_log_per_10))

    @property
    def beta(self) -> float:
        return np.log1p(self.pct_per_10 / 100) / 10

    def _log_h(self, c, age):
        return self.beta * c

    def _draw_pct(self, rng, size=None):
        """pct_per_10 for draws of ln RR per 10 ~ Normal; not truncated (module docstring)."""
        log_rr = rng.normal(np.log1p(self.pct_per_10 / 100), self.se_log_per_10, size)
        return np.expm1(log_rr) * 100

    def sample(self, rng):
        return _evolve(self, pct_per_10=float(self._draw_pct(rng)))

    def sample_many(self, rng, n):
        return _evolve(self, pct_per_10=self._draw_pct(rng, (n, 1)))


@dataclass(frozen=True, init=False)
class GEMM(Curve):
    """Burnett et al. 2018: rr = exp(theta · ln(1 + z/alpha) / (1 + exp(−(z − mu)/nu))),
    z = max(0, c − 2.4), with theta by age band (params: age_start, theta, se_theta, alpha,
    mu, nu). An age takes the row with the largest age_start not above it (80+ covers 85+).
    z shifts every theta by z standard errors (0 for the published curve; sample_many sets
    it to an (n, 1) array)."""
    params: pd.DataFrame = field(default=None, compare=False, repr=False)
    z: float = field(default=0.0, compare=False, repr=False)

    def __init__(self, params: pd.DataFrame, name: str = "gemm_ncd_lri",
                 label: str = "GEMM NCD+LRI (Burnett 2018), age-specific",
                 source: str = GEMM_SOURCE, floor: float = GEMM_CF):
        p = params.sort_values("age_start").reset_index(drop=True)
        _set(self, name=name, label=label, kind="relative_risk", floor=float(floor),
             death_scope="ncd_lri", source=source, min_age=int(p.age_start.iloc[0]), params=p,
             z=0.0)

    def age_group(self, age: int):
        return None if age < self.min_age else int(self._row(age).age_start)

    def _row(self, age: int) -> pd.Series:
        rows = self.params[self.params.age_start <= age]
        if rows.empty:
            raise ValueError(f"GEMM has no parameters for age {age}")
        return rows.iloc[-1]

    def _log_h(self, c, age):
        p = self._row(age)
        z = np.maximum(0.0, c - GEMM_CF)
        theta = p.theta + p.se_theta * self.z
        return theta * np.log1p(z / p.alpha) / (1 + np.exp(-(z - p.mu) / p.nu))

    def sample(self, rng):
        z = rng.standard_normal()
        drawn = self.params.assign(theta=self.params.theta + self.params.se_theta * z)
        return _evolve(self, params=drawn)

    def sample_many(self, rng, n):
        return _evolve(self, z=rng.standard_normal((n, 1)))


@dataclass(frozen=True, init=False)
class AQLILinear(Curve):
    """Life expectancy, not relative risk: years gained = years_per_10/10 × clamped fall."""
    years_per_10: float = 0.98

    def __init__(self, years_per_10: float = 0.98, floor: float = 5.0,
                 name: str = "aqli",
                 label: str = "AQLI linear, 0.98 years of life expectancy per 10 µg/m³",
                 source: str = AQLI_SOURCE):
        # min_age 0: AQLI's estimate is all-age life expectancy, so the derived-deaths step
        # (impact) applies its multiplier on death rates from birth.
        _set(self, name=name, label=label, kind="life_expectancy", floor=float(floor),
             death_scope="all", source=source, min_age=0, years_per_10=float(years_per_10))

    def delta_e0(self, c_from, c_to) -> float | np.ndarray:
        """Change in life expectancy (years) moving from c_from to c_to; positive = gained.
        Arrays broadcast."""
        fall = self._clamp(c_from) - self._clamp(c_to)
        return _scalar_or_array(self.years_per_10 / 10 * fall)

    def rr(self, c, age):
        raise TypeError("aqli gives life expectancy, not a relative risk; use delta_e0()")

    def sample(self, rng):
        return self  # AQLI publishes no interval for its coefficient

    def sample_many(self, rng, n):
        return self


# --- registry -----------------------------------------------------------------------------

IHME = {
    "gbd2019": ("GBD 2019 MR-BRT relative risks, six causes, IHD and stroke by age (IHME, local)",
                "IHME, GBD 2019 particulate matter risk curves, https://ghdx.healthdata.org/record/"
                "ihme-data/global-burden-disease-study-2019-gbd-2019-particulate-matter-risk-curves; "
                "deaths by cause from the GBD 2023 Results tool, https://vizhub.healthdata.org/gbd-results"),
    "gbd2023": ("GBD 2023 relative risks, seven causes, no age split (IHME, local)",
                "IHME, GBD 2023 air pollution exposure estimates and risk curves 1990-2023, "
                "https://ghdx.healthdata.org/node/594794; deaths by cause from the GBD 2023 "
                "Results tool, https://vizhub.healthdata.org/gbd-results"),
    "gemm_5cod": ("GEMM five causes (Burnett 2018), IHD and stroke by age, with IHME deaths (local)",
                  "Burnett et al. 2018, https://pmc.ncbi.nlm.nih.gov/articles/PMC6156628/; deaths "
                  "by cause from IHME GBD Results, https://vizhub.healthdata.org/gbd-results"),
}
LOGLINEAR_FILE = "curves_loglinear.csv"
GEMM_FILE = "curves_gemm_ncd_lri.csv"


def _pct_per_10(value: float, scale: str, per: float) -> float:
    pct = (value - 1) * 100 if scale == "rr" else value
    return ((1 + pct / 100) ** (10 / per) - 1) * 100


@cache
def _loglinear() -> dict[str, LogLinear]:
    t = pd.read_csv(paths.DATA / LOGLINEAR_FILE)
    out = {}
    for r in t.itertuples():
        pct, lo, hi = (_pct_per_10(v, r.scale, r.per_ugm3) for v in (r.estimate, r.lower, r.upper))
        se_log = (np.log1p(hi / 100) - np.log1p(lo / 100)) / (2 * Z95)
        out[r.name] = LogLinear(r.name, pct, (hi - lo) / (2 * Z95), r.floor, label=r.label,
                                source=f"{r.source}. {r.url}", min_age=r.min_age,
                                se_log_per_10=se_log)
    return out


@cache
def _gemm() -> GEMM:
    return GEMM(pd.read_csv(paths.DATA / GEMM_FILE))


def _open() -> dict[str, Curve]:
    return {**_loglinear(), "gemm_ncd_lri": _gemm(), "aqli": AQLILinear()}


def ihme_files(name: str) -> tuple[str, ...]:
    """The IHME files (relative to data_local/) a local-tier curve reads."""
    from . import ihme_curves
    return ihme_curves.files(name)


def get(name: str) -> Curve:
    curves = _open()
    if name in curves:
        return curves[name]
    if name in IHME:
        from . import ihme_curves
        return ihme_curves.load(name)          # raises Unavailable while files are missing
    raise KeyError(f"unknown curve {name!r}; choose from {', '.join([*curves, *IHME])}")


IHME_REASON = "need IHME files in health/data_local/ (see health/IHME_DOWNLOADS.md)"
NOT_BUILT = "IHME files present, but the curve is not built yet"


def select(names: list[str] | None = None) -> tuple[list[Curve], dict[str, str]]:
    """The curves that can run, and the reason each of the rest cannot. names=None means
    every registered curve. An unknown name raises KeyError."""
    names = names or [*(c.name for c in available()), *IHME]
    run, unavailable = [], {}
    for name in dict.fromkeys(names):
        try:
            run.append(get(name))
        except Unavailable:
            unavailable[name] = IHME_REASON
        except NotImplementedError:
            unavailable[name] = NOT_BUILT
    return run, unavailable


def available() -> list[Curve]:
    """The open-tier curves, which always run (the local tier: select())."""
    return list(_open().values())


def catalogue() -> pd.DataFrame:
    rows = []
    files = {LogLinear: f"data/{LOGLINEAR_FILE}", GEMM: f"data/{GEMM_FILE}", AQLILinear: ""}
    for c in available():
        rows.append(dict(name=c.name, label=c.label, available=True,
                         needs=files[type(c)], source=c.source))
    for name, (label, source) in IHME.items():
        try:
            get(name)
            ok = True
        except Unavailable:
            ok = False
        rows.append(dict(name=name, label=label, available=ok,
                         needs=f"data_local/ (IHME files; {len(ihme_files(name))} of them, "
                               "see IHME_DOWNLOADS.md)", source=source))
    return pd.DataFrame(rows, columns=["name", "label", "available", "needs", "source"])
