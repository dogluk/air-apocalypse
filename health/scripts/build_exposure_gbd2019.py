"""Build data/exposure_gbd2019.csv: GBD 2019 state population-weighted ambient PM2.5.

    python scripts/build_exposure_gbd2019.py [DOWNLOAD_DIR]

Source: India State-Level Disease Burden Initiative Air Pollution Collaborators (Pandey
et al.), Lancet Planetary Health 2021;5:e25-38, appendix (mmc1.pdf), table 3 'PM2.5
concentration, use of solid fuels, and ozone concentration in the states of India, 2019',
report p. 18 (PDF p. 19), column 'Population-weighted mean ambient PM2.5 µg/m³ (95% UI)'.
The appendix is fetched from Europe PMC's supplementary-files service (PMC7805008).

The paper reports two groups as one row each (main text, Methods): 'Jammu & Kashmir and
Ladakh', and 'Other small union territories' (Andaman and Nicobar Islands, Chandigarh,
Dadra and Nagar Haveli, Daman and Diu, Lakshadweep, Puducherry). Each member gets the
group's value, with the group named in gbd_region.

Output: state, gbd_region, year, pm25, pm25_lower, pm25_upper.
Checks: 32 rows (India and 31 states, UTs or groups); India 91.7 (69.6-113.9), Kerala 15.8
(13.0-18.7) and Delhi 217.6 (117.9-297.3) equal the figures printed in the main text.
"""
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import pandas as pd

from _fetch import fetch, sha256, workdir
from airhealth.places import canonical_state

URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC7805008/supplementaryFiles"
APPENDIX_SHA256 = "1382e04dae7490e41835dda93461c4eaef35c3f1761151140a155269d619da72"
PAGE = 19
OUT = Path(__file__).resolve().parents[1] / "data" / "exposure_gbd2019.csv"

GROUPS = {
    "Jammu & Kashmir and Ladakh": ["Jammu & Kashmir", "Ladakh"],
    "Other small union territories": ["Andaman & Nicobar Islands", "Chandigarh",
                                      "Dadra & Nagar Haveli", "Daman & Diu", "Lakshadweep",
                                      "Puducherry"],
}
MAIN_TEXT = {"India": (91.7, 69.6, 113.9), "Kerala": (15.8, 13.0, 18.7),
             "Delhi": (217.6, 117.9, 297.3)}
NUM = r"\d+(?:\.\d+)?"


def main() -> None:
    folder = workdir(sys.argv, "gbd2019")
    z = fetch(URL, folder, "PMC7805008_supplementary.zip")
    with zipfile.ZipFile(z) as zf:
        zf.extract("mmc1.pdf", folder)
    pdf = folder / "mmc1.pdf"
    assert sha256(pdf) == APPENDIX_SHA256, "appendix changed; re-check the table"
    text = subprocess.run(["pdftotext", "-layout", "-f", str(PAGE), "-l", str(PAGE), str(pdf), "-"],
                          check=True, capture_output=True, text=True).stdout
    assert "PM₂.₅ concentration, use of solid fuels" in text

    rows = []
    for m in re.finditer(rf"^\s+([A-Z][A-Za-z& ]+?)\s{{2,}}({NUM}) \(({NUM})-({NUM})\)", text, re.M):
        region, v, lo, hi = m.group(1), *map(float, m.groups()[1:])
        if region in MAIN_TEXT:
            assert (v, lo, hi) == MAIN_TEXT[region], (region, v, lo, hi)
        for state in GROUPS[region] if region in GROUPS else [canonical_state(region)]:
            rows.append({"state": state, "gbd_region": region, "year": 2019,
                         "pm25": v, "pm25_lower": lo, "pm25_upper": hi})
    out = pd.DataFrame(rows)
    assert out.gbd_region.nunique() == 32, out.gbd_region.nunique()
    assert not out.state.duplicated().any()
    out.to_csv(OUT, index=False)
    print(f"{out.gbd_region.nunique()} rows printed, {len(out)} states and UTs written")


if __name__ == "__main__":
    main()
