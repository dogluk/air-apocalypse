"""Cessation lag: how fast the risk falls after the air gets cleaner.

profile(name, years)[k] is the cumulative share of the full (steady-state) change in risk
realised by the end of year k + 1 after exposure falls.

  immediate  the whole change in the first year.
  epa20      the US EPA 20-year segmented lag: 30% in the first year, 50% spread evenly
             over years 2-5, 20% spread evenly over years 6-20 (EPA_SOURCE). This is the
             default for intervention files.
"""
import numpy as np

EPA_SOURCE = (
    "U.S. EPA, Office of Air and Radiation. Estimating PM2.5- and Ozone-Attributable Health "
    "Benefits: 2024 Update (June 2024), section 6.4.2 'Lung Cancer Cessation Lag', p. 129: "
    "'Following guidance from EPA's Science Advisory Board (Ostro 2004), EPA RIAs have applied a "
    "20-year distributed cessation lag model ... 30 percent of the total mortality risk reductions "
    "occur in the first year following the exposure reduction, 50 percent are distributed evenly "
    "among years two through five, and the remaining 20 percent are distributed evenly among years "
    "six through 20.' Section 6.4.1 (p. 128) describes the same lag as the primary analysis of "
    "recent RIAs, 'generally supported by SAB recommendations'. Ostro 2004 is the SAB Health "
    "Effects Subcommittee advisory on the Second Prospective Analysis of the Clean Air Act. "
    "https://www.epa.gov/system/files/documents/2024-06/"
    "estimating-pm2.5-and-ozone-attributable-health-benefits-tsd-2024.pdf "
    "(sha256 6723ead711fc028c9adcdd7e900146e301b9c017723b578639d90e0789e6ed09), read 2026-11-10."
)

# Share of the full change realised in each year of the EPA lag (years 1..20).
_EPA20 = np.concatenate([[0.30], np.full(4, 0.50 / 4), np.full(15, 0.20 / 15)])

PROFILES = {
    "immediate": "the whole change in the first year",
    "epa20": "US EPA 20-year segmented lag (30% year 1, 50% years 2-5, 20% years 6-20)",
}


def profile(name: str, years: int) -> np.ndarray:
    """Cumulative share of the full risk change realised by the end of each of `years` years."""
    if name == "immediate":
        return np.ones(years)
    if name == "epa20":
        cumulative = np.ones(max(years, len(_EPA20)))
        cumulative[:len(_EPA20) - 1] = np.cumsum(_EPA20)[:-1]   # year 20 and after: exactly 1
        return cumulative[:years]
    raise ValueError(f"unknown lag {name!r}; choose from {', '.join(PROFILES)}")
