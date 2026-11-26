"""Build data/gdp_deflator_ind.csv: India's GDP deflator, from the World Bank.

    python scripts/build_deflator.py [DOWNLOAD_DIR]

Source: World Bank, World Development Indicators, NY.GDP.DEFL.ZS 'GDP deflator (base year
varies by country)', India, read through the World Bank API (JSON). The deflator is an index
of prices across the whole economy; only the ratio between two years is used (to turn a
cost in one year's rupees into 2025 rupees), so the base year does not matter.

Output: year, deflator (2000 to 2025).
Checks: every year from 2000 to 2025 is present once; no year is more than 25% away from
the one before.
"""
import json
import sys
from pathlib import Path

import pandas as pd

from _fetch import fetch, workdir

URL = ("https://api.worldbank.org/v2/country/IND/indicator/NY.GDP.DEFL.ZS"
       "?format=json&per_page=100&date=2000:2026")
OUT = Path(__file__).resolve().parents[1] / "data" / "gdp_deflator_ind.csv"


def main() -> None:
    folder = workdir(sys.argv, "deflator")
    path = fetch(URL, folder, "IND_NY.GDP.DEFL.ZS.json")
    meta, rows = json.loads(path.read_text())
    print(f"World Bank last updated {meta['lastupdated']}")
    t = pd.DataFrame([(int(r["date"]), r["value"]) for r in rows if r["value"] is not None],
                     columns=["year", "deflator"]).sort_values("year")
    years = t.year.to_numpy()
    assert (years == range(2000, 2026)).all(), years
    assert (t.deflator.pct_change().abs().fillna(0) < 0.25).all()
    t.to_csv(OUT, index=False)
    print(f"wrote {OUT} ({len(t)} years, {years.min()}-{years.max()})")


if __name__ == "__main__":
    main()
