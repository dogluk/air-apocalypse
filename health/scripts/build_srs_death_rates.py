"""Transcribe the SRS's own death rates, 2020-2024, into health/data/.

    python scripts/build_srs_death_rates.py FOLDER

FOLDER (outside the repo) holds SRS_STAT_2020.pdf ... SRS_STAT_2024.pdf, the Sample
Registration System Statistical Reports, downloaded by hand (URLs in data/sources.toml).
Text is pulled with poppler's `pdftotext -layout`.

Outputs (persons, rural and urban combined: each table's first 'Total' column):
  srs_crude_death_rate.csv           state, year, cdr_per_1000
      Statement 40, 'CDR (Crude Death Rate) by Residence': India and every state and UT.
  srs_age_specific_death_rates.csv   state, year, age_start, rate_per_1000
      Detailed Table 8, 'Age-Specific Death Rate by Sex and Residence': India and the 22
      bigger states/UTs; age_start 0 ('Below 1'), 1 ('1-4'), 5, ..., 85 ('85+').
  srs_population_age_pct.csv         state, year, age_start, pct
      Detailed Table 1, 'Percent Distribution of Estimated population by Age-group, Sex
      and Residence': the same 23 units; age_start 0 ('0-4'), 5, ..., 85 ('85+').

State names are written as each report prints them; airhealth.places maps them.

Checks, every unit and year: Table 8's 'All ages (Crude death rate)' equals Statement 40;
Table 1 sums to 100 within 0.6; the crude rate rebuilt from Table 8's rates and Table 1's
age shares is within 0.35 per 1,000 of the printed one (the shares are printed to 0.1%).
"""
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd

from airhealth.places import canonical_state

DATA = Path(__file__).resolve().parents[1] / "data"
YEARS = range(2020, 2025)
NUM = r"\d+\.\d"
ASDR_LABELS = ["Below 1", "1-4"] + [f"{a}-{a + 4}" for a in range(5, 85, 5)] + ["85+"]
ASDR_STARTS = [0, 1, *range(5, 90, 5)]
AGE_LABELS = [f"{a}-{a + 4}" for a in range(0, 85, 5)] + ["85+"]
AGE_STARTS = list(range(0, 90, 5))
UNITS = 23            # India and 22 bigger states/UTs in Tables 1 and 8
CDR_UNITS = 37        # India and 36 states/UTs in Statement 40
COMBINED_UT = "Dadra and Nagar Haveli and Daman and Diu"


def pages(pdf: Path) -> list[str]:
    out = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], check=True,
                         capture_output=True, text=True)
    return out.stdout.split("\f")


def first_number(line: str) -> float:
    return float(re.search(NUM, line).group())


def parse_cdr(pp: list[str], year: int) -> dict[str, float]:
    """Statement 40: name -> crude death rate (Total)."""
    found = [p for p in pp if re.search(r"Statement\s+40\b", p) and "Lakshadweep" in p
             and re.search(r"by Residence, India and", p, re.I)]
    assert len(found) == 1, (year, len(found))
    out = {}
    lines = found[0].splitlines()
    for k, line in enumerate(lines):
        m = re.match(rf"^\s*([A-Z][A-Za-z& ]+?)\s+({NUM})\s+({NUM})\s+({NUM})\s*$", line)
        if not m:
            continue
        name = " ".join(m.group(1).split())
        if name in ("Dadra and Nagar Haveli and", "Daman and Diu"):
            name = COMBINED_UT          # the name wraps over two lines; the figures sit on one
        elif year == 2020 and name == "Daman":
            # The 2020 layout drops 'Daman and Diu' onto Ladakh's line: the text reads
            # 'Ladakh and Diu' then 'Daman 5.0 5.2 4.4'. On the rendered page (PDF p. 145)
            # the 5.0 row is Ladakh's and the 3.7 row above is the combined UT's.
            assert "Ladakh" in lines[k - 1], lines[k - 1]
            name = "Ladakh"
        out[name] = float(m.group(2))
    if COMBINED_UT not in out:          # figures on the line between the two halves of the name
        for k, line in enumerate(lines):
            if line.strip() == "Dadra and Nagar Haveli and":
                out[COMBINED_UT] = first_number(lines[k + 1])
    assert len(out) == CDR_UNITS, (year, len(out), sorted(out))
    return out


def unit_name(page: str) -> str:
    """Table 8 prints the unit alone on the line under the title."""
    title = re.search(r"Age.Specific Death Rate by Sex and Residence, 20\d\d\s*\n\s*(\S.*?)\s*\n",
                      page, re.I)
    return " ".join(title.group(1).split())


def parse_asdr(pp: list[str], year: int) -> dict[str, tuple[list[float], float]]:
    """Table 8: name -> (rates by ASDR_LABELS, all-ages rate)."""
    out = {}
    for p in pp:
        if not (re.search(r"Age.Specific Death Rate by Sex and Residence", p, re.I)
                and "Below 1" in p and re.search(r"^\s*85\+", p, re.M)):
            continue
        # Not cut at 'Table 9' (the child-mortality table below): the 2020 Telangana page is
        # itself headed 'Table 9' by misprint. None of the labels below occur in that table.
        body = p
        rates = []
        for label in ASDR_LABELS:
            m = re.search(rf"^\s*{re.escape(label)}\s+({NUM})\s", body, re.M)
            assert m, (year, unit_name(p), label)
            rates.append(float(m.group(1)))
        all_ages = re.search(rf"^\s*All ages\s+({NUM})\s", body, re.M)
        out[unit_name(p)] = (rates, float(all_ages.group(1)))
    assert len(out) == UNITS, (year, len(out), sorted(out))
    return out


def parse_age_pct(pp: list[str], year: int) -> dict[str, list[float]]:
    """Table 1: name -> percent of population by AGE_LABELS."""
    out = {}
    for p in pp:
        if not (re.search(r"Percent Distribution of Estimated population by Age-group, Sex and "
                          r"Residence", p, re.I) and re.search(r"^\s*85\+", p, re.M)):
            continue
        # One or two units a page: a name alone on a line, then that unit's 18 rows.
        name, pct = None, []
        for line in p.splitlines():
            alone = re.fullmatch(r"\s*([A-Z][A-Za-z&]+(?: [A-Za-z&]+)*)\s*", line)
            if alone and alone.group(1) not in ("Table", "DETAILED TABLES"):
                name, pct = alone.group(1), []
                continue
            row = re.match(rf"\s*(\d+-\d+|85\+)\s+({NUM})\s", line)
            if row and name:
                assert row.group(1) == AGE_LABELS[len(pct)], (year, name, line)
                pct.append(float(row.group(2)))
                if len(pct) == len(AGE_LABELS):
                    out[name], name = pct, None
    assert len(out) == UNITS, (year, len(out), sorted(out))
    return out


def main(folder: Path) -> None:
    cdr_rows, asdr_rows, age_rows = [], [], []
    for year in YEARS:
        pp = pages(folder / f"SRS_STAT_{year}.pdf")
        cdr, asdr, age = parse_cdr(pp, year), parse_asdr(pp, year), parse_age_pct(pp, year)
        # spellings differ between tables ('Telengana'); compare by canonical name
        cdr_by = {canonical_state(n): v for n, v in cdr.items() if n != COMBINED_UT}
        age_by = {canonical_state(n): v for n, v in age.items()}
        assert {canonical_state(n) for n in asdr} == set(age_by), year
        for name, value in cdr.items():
            cdr_rows.append(dict(state=name, year=year, cdr_per_1000=value))
        for name, (rates, all_ages) in asdr.items():
            assert all_ages == cdr_by[canonical_state(name)], (year, name, all_ages)
            pct = age_by[canonical_state(name)]
            assert abs(sum(pct) - 100) <= 0.6, (year, name, sum(pct))
            # crude rate rebuilt: 0-4 share × the printed 0-4 rate is not in our columns, so
            # weight 'Below 1' and '1-4' as 1:4 within the 0-4 share (close enough for a check)
            by_five = [0.2 * rates[0] + 0.8 * rates[1], *rates[2:]]
            rebuilt = sum(r * s for r, s in zip(by_five, pct)) / sum(pct)
            assert abs(rebuilt - all_ages) <= 0.35, (year, name, rebuilt, all_ages)
            for start, rate in zip(ASDR_STARTS, rates):
                asdr_rows.append(dict(state=name, year=year, age_start=start, rate_per_1000=rate))
        for name, pct in age.items():
            for start, share in zip(AGE_STARTS, pct):
                age_rows.append(dict(state=name, year=year, age_start=start, pct=share))
    pd.DataFrame(cdr_rows).to_csv(DATA / "srs_crude_death_rate.csv", index=False)
    pd.DataFrame(asdr_rows).to_csv(DATA / "srs_age_specific_death_rates.csv", index=False)
    pd.DataFrame(age_rows).to_csv(DATA / "srs_population_age_pct.csv", index=False)
    print(f"{len(cdr_rows)} crude rates, {len(asdr_rows)} age-specific rates, "
          f"{len(age_rows)} age shares written to {DATA}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(Path(sys.argv[1]))
