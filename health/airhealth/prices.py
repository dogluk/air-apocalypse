"""Costs in 2025 rupees.

Every cost is turned into rupees of one year (BASE_YEAR, 2025) so that costs from different
years can be added and compared. A rupee cost is scaled by how much prices across India's
economy rose between its price year and 2025, measured by the GDP deflator (World Bank
NY.GDP.DEFL.ZS, data/gdp_deflator_ind.csv; only the ratio of two years is used). A dollar
cost is first turned into rupees at the average rate of its own price year
(data/fx_inr_usd.csv), then scaled the same way. Dollars shown in results are 2025 rupees at
the 2025 rate.

A price year missing from either table raises intervention.Invalid naming cost.year.
"""
from __future__ import annotations

from functools import cache

import pandas as pd

from . import intervention, paths

BASE_YEAR = 2025
DEFLATOR_FILE = "gdp_deflator_ind.csv"


@cache
def deflator() -> dict[int, float]:
    """India's GDP deflator by year (World Bank), 2000 to 2025."""
    t = pd.read_csv(paths.DATA / DEFLATOR_FILE)
    return dict(zip(t.year.astype(int), t.deflator.astype(float)))


def _need(table: dict[int, float], year: int, what: str) -> float:
    if year not in table:
        raise intervention.Invalid(
            f"cost.year: no {what} for {year}; the table covers {min(table)}-{max(table)}")
    return table[year]


def to_base_inr(amount, currency: str, year: int):
    """`amount` (a number or numpy array) of `currency` ("INR" or "USD") in `year`'s prices,
    in BASE_YEAR rupees."""
    d = deflator()
    rupees = amount
    if currency == "USD":
        rupees = amount * _need(intervention._inr_per_usd(), year, "rupee-dollar rate")
    elif currency != "INR":
        raise intervention.Invalid(f"cost.currency: must be INR or USD, got {currency!r}")
    return rupees * _need(d, BASE_YEAR, "price index") / _need(d, year, "price index (GDP deflator)")


def usd_per_base_inr() -> float:
    """Dollars per 2025 rupee: 1 over the 2025 rate."""
    return 1 / _need(intervention._inr_per_usd(), BASE_YEAR, "rupee-dollar rate")
