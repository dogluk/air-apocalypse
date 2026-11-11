"""Transcribe the SRS's own death rates, 2011-2024, into health/data/.

    python scripts/build_srs_death_rates.py FOLDER

FOLDER (outside the repo) holds SRS_STAT_2011.pdf ... SRS_STAT_2024.pdf, the Sample
Registration System Statistical Reports, downloaded by hand (URLs in data/sources.toml).
Text is pulled with poppler's `pdftotext -layout`.

Outputs (persons, rural and urban combined: each table's first 'Total' column):
  srs_crude_death_rate.csv           state, year, cdr_per_1000
      Statement 40 (Statement 41 in 2011-2013), 'CDR (Crude Death Rate) by Residence':
      India and every state and UT from 2020; India and the bigger states only before
      (20 of them in 2011-2013, 22 in 2014-2019), as the earlier reports print no
      smaller state or UT.
  srs_age_specific_death_rates.csv   state, year, age_start, rate_per_1000
      Detailed Table 8, 'Age-Specific Death Rate by Sex and Residence': India and the
      bigger states/UTs; age_start 0 ('Below 1'), 1 ('1-4'), 5, ..., 85 ('85+').
  srs_population_age_pct.csv         state, year, age_start, pct
      Detailed Table 1, 'Percent Distribution of Estimated population by Age-group, Sex
      and Residence': the same units; age_start 0 ('0-4'), 5, ..., 85 ('85+').

The tables are found by their titles, not their numbers. Every report 2011-2024 prints the
same age bands in Tables 1 and 8, so no year is reshaped. Bigger states: 22 from 2014
(Telangana first printed in the 2014 report); 20 in 2011-2013 (Andhra Pradesh undivided, no
Uttarakhand). Jammu & Kashmir includes Ladakh before 2020.

State names are written as each report prints them; airhealth.places maps them.

Checks, every unit and year: Table 8's 'All ages (Crude death rate)' equals the CDR
statement, and Tables 1, 8 and (before 2020) the statement cover the same units; Table 1
sums to 100 within 0.6; the crude rate rebuilt from Table 8's rates (its printed '0-4' row
for the under-fives) and Table 1's age shares is within 0.25 per 1,000 of the printed one
(the shares are printed to 0.1%). An earlier form of this check weighted 'Below 1' and
'1-4' 1:4 within 0-4, to 0.35; that fails for Assam 2015 (0.43, against 0.20 with the
printed '0-4' row).
"""
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd

from airhealth.places import canonical_state

DATA = Path(__file__).resolve().parents[1] / "data"
YEARS = range(2011, 2025)
NUM = r"\d+\.\d"
ASDR_LABELS = ["Below 1", "1-4"] + [f"{a}-{a + 4}" for a in range(5, 85, 5)] + ["85+"]
ASDR_STARTS = [0, 1, *range(5, 90, 5)]
AGE_LABELS = [f"{a}-{a + 4}" for a in range(0, 85, 5)] + ["85+"]
AGE_STARTS = list(range(0, 90, 5))
COMBINED_UT = "Dadra and Nagar Haveli and Daman and Diu"


def units(year: int) -> int:
    """India and the bigger states/UTs in Tables 1 and 8 (and, before 2020, the statement)."""
    return 21 if year <= 2013 else 23


def cdr_units(year: int) -> int:
    """Rows of the CDR statement: from 2020 India and all 36 states/UTs."""
    return 37 if year >= 2020 else units(year)


def pages(pdf: Path) -> list[str]:
    out = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], check=True,
                         capture_output=True, text=True)
    return out.stdout.split("\f")


def first_number(line: str) -> float:
    return float(re.search(NUM, line).group())


def parse_cdr(pp: list[str], year: int) -> dict[str, float]:
    """The CDR statement: name -> crude death rate (Total)."""
    # Statement 40 (41 in 2011-2013): its heading, then its title on the next printed line.
    # From 2020 it holds the smaller states and UTs too.
    heading = (r"^\s*Statement\s+4[01]\s*\n(\s*\n)*"
               r"\s*CDR \(Crude Death Rates?\) by Residence, India and")
    found = [p for p in pp if re.search(heading, p, re.I | re.M)]
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
    if year >= 2020 and COMBINED_UT not in out:   # figures between the two halves of the name
        for k, line in enumerate(lines):
            if line.strip() == "Dadra and Nagar Haveli and":
                out[COMBINED_UT] = first_number(lines[k + 1])
    assert len(out) == cdr_units(year), (year, len(out), sorted(out))
    return out


def unit_name(page: str) -> str:
    """Table 8 prints the unit alone on the line under the title."""
    title = re.search(r"Age.Specific Death Rate by Sex and Residence, 20\d\d\s*\n\s*(\S.*?)\s*\n",
                      page, re.I)
    return " ".join(title.group(1).split())


def parse_asdr(pp: list[str], year: int) -> dict[str, tuple[list[float], float, float]]:
    """Table 8: name -> (rates by ASDR_LABELS, all-ages rate, the printed 0-4 rate).

    The 0-4 rate is read for the check in main() only; it is not written out."""
    out = {}
    for i, p in enumerate(pp):
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
        if not all_ages:
            # 2011, West Bengal: the page ends at the 85+ row; 'All ages' opens the next page
            all_ages = re.match(rf"\s*All ages\s+({NUM})\s", pp[i + 1])
            assert all_ages, (year, unit_name(p), "All ages")
        under_5 = re.search(rf"^\s*0-4\s+({NUM})\s", body, re.M)
        out[unit_name(p)] = (rates, float(all_ages.group(1)), float(under_5.group(1)))
    assert len(out) == units(year), (year, len(out), sorted(out))
    return out


def parse_age_pct(pp: list[str], year: int) -> dict[str, list[float]]:
    """Table 1: name -> percent of population by AGE_LABELS."""
    out = {}
    title = r"Percent Distribution of Estimated population by Age-group, Sex and Residence"
    on, name, pct = False, None, []
    for p in pp:
        if re.search(title, p, re.I) and re.search(r"^\s*85\+", p, re.M):
            on = True
        elif on and re.search(r"marital status", p, re.I):
            break                       # Table 2 begins
        if not on:
            continue
        # One or two units a page: a name alone on a line, then that unit's 18 rows. In
        # 2011-2013 only the first page carries the title, and a unit can run over a page break.
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
    assert len(out) == units(year), (year, len(out), sorted(out))
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
        if year < 2020:
            assert set(cdr_by) == set(age_by), (year, set(cdr_by) ^ set(age_by))
        for name, value in cdr.items():
            cdr_rows.append(dict(state=name, year=year, cdr_per_1000=value))
        for name, (rates, all_ages, under_5) in asdr.items():
            assert all_ages == cdr_by[canonical_state(name)], (year, name, all_ages)
            pct = age_by[canonical_state(name)]
            assert abs(sum(pct) - 100) <= 0.6, (year, name, sum(pct))
            # crude rate rebuilt from five-year bands: the 0-4 share × the printed 0-4 rate
            # (not written out), then 5-9 ... 85+. Within 0.21 in every unit and year.
            by_five = [under_5, *rates[2:]]
            rebuilt = sum(r * s for r, s in zip(by_five, pct)) / sum(pct)
            assert abs(rebuilt - all_ages) <= 0.25, (year, name, rebuilt, all_ages)
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
