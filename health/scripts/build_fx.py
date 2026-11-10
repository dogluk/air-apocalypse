"""Build data/fx_inr_usd.csv: rupees per US dollar, annual average, from the World Bank.

    python scripts/build_fx.py [DOWNLOAD_DIR]

Source: World Bank, World Development Indicators, PA.NUS.FCRF 'Official exchange rate (LCU
per US$, period average)', India, read through the World Bank API (JSON). The values are
written as the API gives them, one row per year with a value, 2000 to the latest.

Output: year, inr_per_usd.
Checks: every year from 2000 to the latest is present once; values rise from about 45 to
about 87 with no year more than 15% away from the one before.
"""
import json
import sys
from pathlib import Path

import pandas as pd

from _fetch import fetch, workdir

URL = ("https://api.worldbank.org/v2/country/IND/indicator/PA.NUS.FCRF"
       "?format=json&per_page=100&date=2000:2026")
OUT = Path(__file__).resolve().parents[1] / "data" / "fx_inr_usd.csv"


def main() -> None:
    folder = workdir(sys.argv, "fx")
    path = fetch(URL, folder, "IND_PA.NUS.FCRF.json")
    meta, rows = json.loads(path.read_text())
    print(f"World Bank last updated {meta['lastupdated']}")
    t = pd.DataFrame([(int(r["date"]), r["value"]) for r in rows if r["value"] is not None],
                     columns=["year", "inr_per_usd"]).sort_values("year")
    years = t.year.to_numpy()
    assert (years == range(2000, years.max() + 1)).all(), years
    assert (t.inr_per_usd.pct_change().abs().fillna(0) < 0.15).all()
    t.to_csv(OUT, index=False)
    print(f"wrote {OUT} ({len(t)} years, {years.min()}-{years.max()})")


if __name__ == "__main__":
    main()
