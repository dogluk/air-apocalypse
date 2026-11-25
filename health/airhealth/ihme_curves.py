"""The local-tier curves: risk by cause of death, applied to IHME's deaths by cause.

  gbd2023    GBD 2023 relative risks for seven causes (IHME, GHDx record 594794).
  gbd2019    GBD 2019 relative risks for six causes, IHD and stroke by five-year age.
  gemm_5cod  GEMM, the five causes of Burnett et al. 2018 (parameters in data/).

All three take their deaths from IHME: the GBD 2023 round's deaths by cause, state and age
(ihme.cause_rates), times the tool's own population in each band. These counts are GBD's,
not the SRS's, and are not scaled to the SRS crude death rate (--deaths does not move them).
GBD 2019-round deaths are no longer served by IHME's Results tool, so gbd2019 is run on the
GBD 2023 round's deaths for the year asked; every result says so.

For a unit (district, state) and age band, deaths averted = Σ over causes of population ×
cause death rate × (1 − RR_c(after) / RR_c(before)). Life expectancy: the band's all-cause rate
loses the averted cause-specific rate, Σ_c rate_c × (1 − ratio_c). Life-years use the tool's
usual remaining life expectancy at the age of death.

The two scales of the GBD 2023 files (IHME_DOWNLOADS.md, "two traps"). The four files dated
2022 (COPD, type 2 diabetes, lung cancer, birth outcomes; columns cause, exposure, mean, lower,
upper) start at 1 and are relative risks: their mean equals the mean of the matching draws
file, which is on the ratio scale. The four dated 2025 (IHD, stroke, LRI, dementia; columns
risk, mean, lower, upper) start at 0 and are the natural log of the relative risk:
  1. IHME's GBD 2023 risk-factor appendix (appendix 2 to GBD 2023 Disease and Injury and Risk
     Factor Collaborators, Lancet 2025, section on ambient particulate matter, "MR-BRT risk
     splines") fits log(MRBRT(X)/MRBRT(X_CF)) to the log effect sizes: the curve is a log RR.
  2. The column layout (`risk`, then `draw_0` ... in the draws files) is the output of IHME's
     burden-of-proof pipeline, bopforge (github.com/ihmeuw-msca/bopforge, continuous_pipeline:
     get_draws writes columns "risk" + "draw_i" = signal × beta, where get_signal "will always
     anchor the curve at lnRR = 0"), i.e. draws of ln RR.
  3. In the files themselves, each 2025 mean file equals the mean of its draws file to four
     decimals for IHD, stroke and LRI, and lower/upper are its 2.5th and 97.5th percentiles,
     symmetric about the mean: what draws of a normal ln RR give.
The GBD 2023 information sheet (GHDx) would say so in words, but it needs an IHME login and
was not read. The dementia mean file (Y2025M11D18) differs from its older draws file
(Y2024M02D07); the mean file is used.

Counterfactual (TMREL). GBD 2019 and GBD 2023 both use a uniform distribution from 2.4 to 5.9
µg/m³ (GBD 2019 information sheet; GBD 2023 appendix 2, ambient PM section: "The resulting
lower/upper bounds of the distribution for GBD 2023 were 2.4 and 5.9. This has not changed
since GBD 2015"). IHME computes RR(X) = MRBRT(X)/MRBRT(TMREL) draw by draw. Here, with mean
curves, the floor is the distribution's midpoint, 4.15: the GBD 2019 information sheet's
second and third strategies ("divide ... by RR predictions at the TMREL midpoint (4.15
ug/m3)"; RR = 1 below it), which it says gives slightly smaller attributable fractions than
the draw-based approach. The TMREL draws file is read only to check the distribution.

Ages. GBD applies the curves at ages 25 and over for IHD, stroke, COPD, lung cancer and type 2
diabetes, and at all ages for LRI (GBD 2023 appendix 2, as above). Dementia gets no age range
there; it is applied from 25, and GBD's dementia deaths start at 40 anyway. GBD 2023's curves
have no age split. GBD 2019's IHD and stroke curves are by five-year age from 25 to 95: band a
uses the curve for a; the tool's open band 85+ uses the 85, 90 and 95 curves, each weighted by
India's GBD 2023 deaths from that cause at 85-89, 90-94 and 95+.

Not included: the deaths GBD attributes to PM2.5 through low birth weight and short gestation
(neonatal deaths), GBD's joint ambient-and-household attribution (GBD splits one PM2.5
attributable fraction between ambient and household air by exposure; here ambient air is
scored alone), and grid-cell exposure (here a state's or district's mean).

Uncertainty (sample): one standard normal z per draw moves every cause's ln RR by z times its
own standard error at each concentration, se = (ln upper − ln lower)/(2 × 1.96) from the mean
file (GEMM: theta + z × se, as gemm_ncd_lri). The causes move together, as the GEMM authors'
calculator moves its ages together; the draws files are not used.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from functools import cache

import numpy as np
import pandas as pd

from . import ihme, paths
from .ages import AGE_STARTS
from .curves import GEMM_CF, Z95, Curve, _scalar_or_array, _set

TMREL_RANGE = (2.4, 5.9)
TMREL_MID = sum(TMREL_RANGE) / 2      # 4.15
TMREL_SOURCE = (
    "GBD 2019 Particulate Matter Risk Curves, Data Release Information Sheet (IHME, updated "
    "18 March 2021), 'Note on Scaling These Curves to the TMREL': uniform 2.4-5.9 µg/m³, midpoint "
    "4.15; GBD 2023 Disease and Injury and Risk Factor Collaborators, Lancet 2025, appendix 2, "
    "'Ambient particulate matter pollution', 'Theoretical minimum risk exposure level': 2.4 and "
    "5.9 for GBD 2023. https://ghdx.healthdata.org/record/ihme-data/global-burden-disease-study-"
    "2019-gbd-2019-particulate-matter-risk-curves; "
    "https://openaccess.sgul.ac.uk/id/eprint/118199/7/1-s2.0-S014067362501637X-mmc2.pdf"
)
GBD_AGES_SOURCE = (
    "GBD 2023 Disease and Injury and Risk Factor Collaborators, Lancet 2025, appendix 2, "
    "'Ambient particulate matter pollution', 'Relative risks and population attributable "
    "fractions': curves applied at ages 25+ for IHD, stroke, COPD, lung cancer and type 2 "
    "diabetes and at all ages for LRI; dementia added in GBD 2023. "
    "https://openaccess.sgul.ac.uk/id/eprint/118199/7/1-s2.0-S014067362501637X-mmc2.pdf"
)
GBD2023_SOURCE = (
    "IHME, Global Burden of Disease Study 2023 (GBD 2023) Air Pollution Exposure Estimates and "
    "Risk Curves 1990-2023 (relative risk files), https://ghdx.healthdata.org/node/594794; "
    "deaths by cause: GBD 2023 Results, https://vizhub.healthdata.org/gbd-results/"
)
GBD2019_SOURCE = (
    "IHME, Global Burden of Disease Study 2019 (GBD 2019) Particulate Matter Risk Curves, "
    "summary files and TMREL draws, https://ghdx.healthdata.org/record/ihme-data/global-burden-"
    "disease-study-2019-gbd-2019-particulate-matter-risk-curves; deaths by cause: GBD 2023 "
    "Results (GBD 2019-round deaths are no longer served), https://vizhub.healthdata.org/gbd-results/"
)
GEMM5_FILE = "curves_gemm_5cod.csv"
GEMM5_SOURCE = (
    "Burnett R, et al. PNAS 2018; 115: 9592-97, https://pmc.ncbi.nlm.nih.gov/articles/PMC6156628/; "
    "cause-specific parameters (including the China cohort) from the authors' deposit, "
    "https://github.com/mszyszkowicz/DataGEMM ('GEMM Calculator (PNAS)_ab.xlsx', sheet 'GEMM fit "
    "parameters'); deaths by cause: GBD 2023 Results, https://vizhub.healthdata.org/gbd-results/"
)
ADULT = 25


# --- one cause ------------------------------------------------------------------------------

@dataclass(frozen=True)
class Risk:
    """One cause's risk curve: ln RR as a function of concentration, by age key."""
    cause: str
    min_age: int

    def key(self, age: int):
        return 0

    def log_h(self, c, key, z):
        raise NotImplementedError

    def ratio(self, c_from, c_to, age: int, z, floor: float):
        """RR(c_to)/RR(c_from) for the band starting at `age`, below the floor counting as it."""
        if age < self.min_age:
            return np.ones(np.broadcast_shapes(np.shape(c_from), np.shape(c_to)))
        k = self.key(age)
        a = np.maximum(np.asarray(c_from, float), floor)
        b = np.maximum(np.asarray(c_to, float), floor)
        return np.exp(self.log_h(b, k, z) - self.log_h(a, k, z))


@dataclass(frozen=True)
class Tabulated(Risk):
    """IHME's tabulated mean curve, held as ln RR (mean) and its standard error on a grid. With
    `by_age`, `curves` is keyed by the first age of each five-year group (GBD 2019 IHD and
    stroke); the 85+ band mixes the 85, 90 and 95 curves with `oldest` weights."""
    grid: np.ndarray = field(default=None, repr=False)
    curves: dict = field(default=None, repr=False)     # key -> (mean ln RR, se ln RR)
    by_age: bool = False
    oldest: dict = field(default_factory=dict, repr=False)   # 85/90/95 -> weight

    def key(self, age: int):
        if not self.by_age:
            return 0
        return min(max(a for a in self.curves if a <= age), 85) if age < 85 else 85

    def log_h(self, c, key, z):
        mean, se = self.curves[key]
        out = np.interp(c, self.grid, mean)
        return out + z * np.interp(c, self.grid, se) if np.any(z) else out

    def ratio(self, c_from, c_to, age, z, floor):
        if not (self.by_age and age >= 85):
            return super().ratio(c_from, c_to, age, z, floor)
        a = np.maximum(np.asarray(c_from, float), floor)
        b = np.maximum(np.asarray(c_to, float), floor)
        return sum(w * np.exp(self.log_h(b, k, z) - self.log_h(a, k, z))
                   for k, w in self.oldest.items())


@dataclass(frozen=True)
class GEMMRisk(Risk):
    """Burnett et al. 2018's cause-specific GEMM: ln RR = theta·ln(1 + z/alpha)/(1 + exp(−(z −
    mu)/nu)), z = max(0, c − 2.4); one parameter row per age group (80+ covers 85+)."""
    params: pd.DataFrame = field(default=None, repr=False, compare=False)

    def key(self, age: int):
        return int(self.params[self.params.age_start <= age].age_start.iloc[-1])

    def log_h(self, c, key, z):
        p = self.params[self.params.age_start == key].iloc[0]
        x = np.maximum(0.0, np.asarray(c, float) - GEMM_CF)
        return (p.theta + p.se_theta * z) * np.log1p(x / p.alpha) / (1 + np.exp(-(x - p.mu) / p.nu))


# --- the curve ------------------------------------------------------------------------------

@dataclass(frozen=True, init=False)
class CauseCurve(Curve):
    """Risk by cause, applied to IHME's deaths by cause (death_scope "causes"; impact.py)."""
    risks: tuple = field(default=(), repr=False, compare=False)
    rates_round: str = "GBD 2023"
    z: float = field(default=0.0, compare=False, repr=False)

    def __init__(self, name, label, source, floor, risks, note=""):
        _set(self, name=name, label=label, kind="relative_risk", floor=float(floor),
             death_scope="causes", source=source, min_age=min(r.min_age for r in risks),
             risks=tuple(risks), rates_round="GBD 2023", z=0.0, _note=note)

    def cause_rates(self, state: str, year: int) -> dict[str, np.ndarray]:
        return ihme.cause_rates(state, year)

    def cause_ratio(self, risk: Risk, c_from, c_to, age: int):
        return risk.ratio(c_from, c_to, age, self.z, max(self.floor, 0.0))

    def deaths_note(self, year: int) -> str:
        causes = ", ".join(ihme.CAUSE_LABELS[r.cause] for r in self.risks)
        return (f"{self.name}: deaths from {causes} are the GBD 2023 round's death rates by "
                f"state, cause and age for {ihme.rates_text(year)} × this tool's population, "
                f"not scaled to the SRS" + (f"; {self._note}" if self._note else ""))

    # All-cause equivalent, for charts and the dashboard: 1 + Σ_c s_c (RR_c − 1), with s_c the
    # cause's share of all deaths in the band, India 2023 (GBD deaths over the tool's deaths).
    def _shares(self, age: int) -> dict[str, float]:
        return _india_shares(self.name, int(max(a for a in AGE_STARTS if a <= age)))

    def rr(self, c, age):
        c = np.maximum(np.asarray(c, float), self.floor)
        floor = np.asarray(self.floor)
        shares = self._shares(age)
        out = 1.0 + sum(shares[r.cause] * (self.cause_ratio(r, floor, c, age) - 1)
                        for r in self.risks)
        return _scalar_or_array(np.asarray(out, float))

    def age_group(self, age: int):
        return None if age < self.min_age else age

    def sample(self, rng):
        return _evolve(self, z=float(rng.standard_normal()))

    def sample_many(self, rng, n):
        return _evolve(self, z=rng.standard_normal((n, 1)))


def _evolve(obj, **changes):
    new = copy.copy(obj)
    _set(new, **changes)
    return new


@cache
def _india_shares(name: str, band: int) -> dict[str, float]:
    from . import baseline
    b = baseline.load("India", 2023)
    k = AGE_STARTS.index(band)
    m = b.mx[k] * b.death_factor[k]
    return {c: float(r[k] / m) for c, r in ihme.cause_rates("India", 2023).items()}


# --- loading --------------------------------------------------------------------------------

def _read_ratio(file: str, x: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    t = pd.read_csv(file).sort_values(x)
    mean = np.log(t["mean"].to_numpy(float))
    se = (np.log(t.upper.to_numpy(float)) - np.log(t.lower.to_numpy(float))) / (2 * Z95)
    return t[x].to_numpy(float), mean, se


def _read_log(file: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    t = pd.read_csv(file).sort_values("risk")
    se = (t.upper.to_numpy(float) - t.lower.to_numpy(float)) / (2 * Z95)
    return t.risk.to_numpy(float), t["mean"].to_numpy(float), se


def _check_starts(file, mean_log):
    if abs(mean_log[0]) > 1e-9:
        raise ValueError(f"{file}: expected ln RR 0 at zero exposure, got {mean_log[0]}")


def files(name: str) -> tuple[str, ...]:
    if name == "gbd2023":
        return (*ihme.DEATHS_FILES, *(f for f, _ in ihme.RR_2023.values()))
    if name == "gbd2019":
        return (*ihme.DEATHS_FILES, ihme.TMREL_2019, *ihme.RR_2019.values())
    if name == "gemm_5cod":
        return ihme.DEATHS_FILES
    raise KeyError(name)


@cache
def _gbd2023(local: str) -> CauseCurve:
    risks = []
    for cause, (rel, scale) in ihme.RR_2023.items():
        f = str(ihme.path(rel))
        grid, mean, se = _read_log(f) if scale == "log" else _read_ratio(f, "exposure")
        _check_starts(rel, mean)
        risks.append(Tabulated(cause, 0 if cause == "lri" else ADULT, grid=grid,
                               curves={0: (mean, se)}))
    return CauseCurve(
        "gbd2023", "GBD 2023 relative risks, seven causes, no age split (IHME, local)",
        GBD2023_SOURCE, TMREL_MID, risks)


@cache
def _gbd2019(local: str) -> CauseCurve:
    risks = []
    for cause in ("ihd", "stroke"):
        curves, grid = {}, None
        for a in ihme.CVD_AGES_2019:
            grid, mean, se = _read_ratio(str(ihme.path(ihme.RR_2019[f"{cause}_{a}"])), "exposure_spline")
            curves[a] = (mean, se)
        risks.append(Tabulated(cause, ADULT, grid=grid, curves=curves, by_age=True,
                               oldest=ihme.oldest_shares(cause)))
    for cause in ("copd", "lung_cancer", "lri", "t2dm"):
        grid, mean, se = _read_ratio(str(ihme.path(ihme.RR_2019[cause])), "exposure_spline")
        risks.append(Tabulated(cause, 0 if cause == "lri" else ADULT, grid=grid,
                               curves={0: (mean, se)}))
    return CauseCurve(
        "gbd2019", "GBD 2019 MR-BRT relative risks, six causes, IHD and stroke by age (IHME, local)",
        GBD2019_SOURCE, TMREL_MID, risks,
        note="GBD 2019-round deaths are no longer published, so the GBD 2023 round's are used")


@cache
def _gemm5(local: str) -> CauseCurve:
    t = pd.read_csv(paths.DATA / GEMM5_FILE)
    risks = [GEMMRisk(cause, int(g.age_start.min()), params=g.sort_values("age_start").reset_index(drop=True))
             for cause, g in t.groupby("cause", sort=False)]
    return CauseCurve(
        "gemm_5cod", "GEMM five causes (Burnett 2018), IHD and stroke by age, with IHME deaths (local)",
        GEMM5_SOURCE, GEMM_CF, risks)


LOADERS = {"gbd2023": _gbd2023, "gbd2019": _gbd2019, "gemm_5cod": _gemm5}


def load(name: str) -> CauseCurve:
    ihme.require(files(name), name)
    return LOADERS[name](str(paths.LOCAL))


def tmrel_draws() -> np.ndarray:
    ihme.require([ihme.TMREL_2019], "gbd2019")
    return pd.read_csv(ihme.path(ihme.TMREL_2019)).x.to_numpy(float)
