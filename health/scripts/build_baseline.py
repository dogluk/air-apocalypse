"""Build the three baseline tables in health/data/ from the official PDFs.

    python scripts/build_baseline.py LIFE_TABLES_PDF PROJECTIONS_PDF CAUSES_PDF

The PDFs are downloaded by hand (URLs in data/sources.toml) to a folder outside the
repo. Text is pulled with poppler's `pdftotext -layout`; every table is checked
against a total or a second printing in the same report before it is written.

Outputs (all persons, never sex-specific):
  lifetables_srs.csv        state, period, age_start, qx, lx, Lx, ex      (transcribed)
  population_age_state.csv  state, year, age_start, population            (derived)
  cause_share_ncd_lri.csv   age_group, age_from, age_to, *_pct            (transcribed)

State names are written as each source prints them; airhealth.baseline maps them.
"""
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from airhealth.places import canonical_state

DATA = Path(__file__).resolve().parents[1] / "data"
NUM = r"[\d,]+(?:\.\d+)?"


def pdf_text(pdf: Path, first: int, last: int) -> str:
    out = subprocess.run(
        ["pdftotext", "-layout", "-f", str(first), "-l", str(last), str(pdf), "-"],
        check=True, capture_output=True, text=True,
    )
    return out.stdout


def num(s: str) -> float:
    return float(s.replace(",", ""))


# --- SRS Abridged Life Tables 2020-24 -------------------------------------------------
# PDF pages 25-47 hold one table each (India, then 22 states/UTs); the "Total" block
# comes first and its first four columns are persons: nqx, lx, nLx, ex.
LT_PAGES = range(25, 48)
LT_AGES = ["0-1", "1-5"] + [f"{a}-{a + 5}" for a in range(5, 85, 5)] + ["85+"]
LT_STATEMENT3_PAGE = 11  # Statement 3: e0 by sex and residence, the cross-check


def parse_lifetables(pdf: Path) -> pd.DataFrame:
    rows = []
    for page in LT_PAGES:
        text = pdf_text(pdf, page, page)
        title = re.search(r"^\s*(\S.*?),\s*(20\d\d-\d\d)\s*$", text, re.M)
        state, period = title.group(1), title.group(2)
        total = text.split("Rural")[0]
        for label in LT_AGES:
            m = re.search(rf"^\s*{re.escape(label)}\s+(\.\.\.|{NUM})\s+({NUM})\s+({NUM})\s+({NUM})\s",
                          total, re.M)
            if not m:
                raise ValueError(f"page {page} ({state}): no row {label}")
            q, l, L, e = m.groups()
            rows.append(dict(state=state, period=period,
                             age_start=int(re.match(r"\d+", label).group()),
                             qx=None if q == "..." else num(q),
                             lx=int(num(l)), Lx=num(L), ex=num(e)))
    t = pd.DataFrame(rows)
    check_lifetables(t, pdf_text(pdf, LT_STATEMENT3_PAGE, LT_STATEMENT3_PAGE))
    return t


def check_lifetables(t: pd.DataFrame, statement3: str) -> None:
    for state, g in t.groupby("state", sort=False):
        lx, qx = g.lx.to_numpy(), g.qx.to_numpy(dtype=float)
        # l(x+n) = l(x) * (1 - q(x)) to printed rounding
        implied = lx[:-1] * (1 - qx[:-1])
        assert np.allclose(implied, lx[1:], atol=3), state
        # e0 printed in the table equals the one in Statement 3
        name = canonical_state(state)  # Statement 3 spells Telangana; the table heading does not
        label = "India*" if name == "India" else name
        m = re.search(rf"^\s*{re.escape(label)}\s+({NUM})\s", statement3, re.M)
        assert m and num(m.group(1)) == g.ex.iloc[0], (state, m and m.group(1))


# --- Population Projections for India and States 2011-2036 ---------------------------
# Table 11: total persons as on 1st July, every year, every state and UT ('000).
# The page layout is read by eye; the column numbers printed under the header are
# checked so a wrong page fails loudly.
T11_PAGES = {  # PDF page: (first printed column number, three units in order)
    86: (2, ["INDIA", "JAMMU & KASHMIR (UT)", "HIMACHAL PRADESH"]),
    87: (11, ["PUNJAB", "HARYANA", "NCT OF DELHI"]),
    88: (20, ["RAJASTHAN", "UTTAR PRADESH", "BIHAR"]),
    89: (29, ["ASSAM", "WEST BENGAL", "JHARKHAND"]),
    90: (38, ["ODISHA", "CHHATTISGARH", "MADHYA PRADESH"]),
    91: (47, ["GUJARAT", "MAHARASHTRA", "ANDHRA PRADESH"]),
    92: (56, ["KARNATAKA", "KERALA", "TAMIL NADU"]),
    93: (65, ["CHANDIGARH", "UTTARAKHAND", "SIKKIM"]),
    94: (74, ["ARUNACHAL PRADESH", "NAGALAND", "MANIPUR"]),
    95: (83, ["MIZORAM", "TRIPURA", "MEGHALAYA"]),
    96: (92, ["DAMAN & DIU", "DADRA & NAGAR HAVELI", "GOA"]),
    97: (101, ["LAKSHADWEEP", "PUDUCHERRY", "ANDAMAN & NICOBAR ISLANDS"]),
    98: (110, ["TELANGANA", "LADAKH"]),
}
YEARS = range(2011, 2037)
NE_STATES = {"ARUNACHAL PRADESH", "MANIPUR", "MEGHALAYA", "MIZORAM", "NAGALAND",
             "SIKKIM", "TRIPURA"}  # the report's "North-East States (excluding Assam)"
NE_COMBINED = "NORTH-EAST STATES (EXCLUDING ASSAM)"
T18_YEARS = [2011, 2016, 2021, 2026, 2031, 2036]
T18_GROUPS = ["0-1", "0-4"] + [f"{a}-{a + 4}" for a in range(5, 80, 5)] + ["80+", "Total"]


def parse_table11(pdf: Path) -> pd.DataFrame:
    rows = []
    for page, (col0, units) in T11_PAGES.items():
        text = pdf_text(pdf, page, page)
        if page == 86:
            text = text.split("TABLE – 11", 1)[1]
        text = text.split("TABLE – 12")[0]
        cols = r"\s+".join(["1", *(str(c) for c in range(col0, col0 + 3 * len(units)))])
        header = re.search(rf"^\s*{cols}\s*$", text, re.M)
        assert header, f"page {page}: column numbers {col0}.. not found"
        tokens = [t for t in text[header.end():].split() if re.fullmatch(NUM, t)]
        i = 0
        for year in YEARS:
            assert tokens[i] == str(year), (page, year, tokens[i:i + 4])
            vals = tokens[i + 1:i + 1 + 3 * len(units)]
            for k, unit in enumerate(units):
                rows.append(dict(state=unit, year=year, total_000=num(vals[3 * k])))
                # persons = male + female, to rounding
                p, m, f = (num(v) for v in vals[3 * k:3 * k + 3])
                assert abs(p - m - f) <= 2, (page, year, unit, p, m, f)
            i += 1 + 3 * len(units)
    return pd.DataFrame(rows)


def parse_table18(pdf: Path) -> pd.DataFrame:
    """Projected persons by age group as on 1st March, every fifth year ('000).

    Each unit's block opens with Table 17 ("Projected Population Characteristics"),
    whose heading names the unit; Table 18 follows. The unit is taken from Table 17
    because one Table 18 heading is misprinted (Uttarakhand's reads "PUNJAB"), and
    Table 18's totals must equal Table 17's.
    """
    text = pdf_text(pdf, 164, 260)
    rows = []
    for block in text.split("Projected Population Characteristics")[1:]:
        unit = next(line for line in block.splitlines()[1:] if line.strip()).strip().upper()
        # the six totals sit on the "Total" line, or (Rajasthan) on the line above it
        span = re.search(r"Population \(000'\)(.*?)^\s*Male", block, re.S | re.M).group(1)
        t17_totals = [num(v) for v in re.findall(NUM, span)]
        assert len(t17_totals) == 6, (unit, t17_totals)
        section = block.split("TABLE-18")[1].split("TABLE-19")[0]
        found = []
        for line in section.splitlines():
            m = re.match(r"^\s*(0-1|0-4|\d+-\d+|80\+|Total)\s+((?:[\d,]+\s+){8}[\d,]+)\s*$", line)
            if m:
                found.append((m.group(1), [num(v) for v in m.group(2).split()]))
        assert [g for g, _ in found] == T18_GROUPS * 2, (unit, [g for g, _ in found])
        t18_totals = found[18][1][::3] + found[37][1][::3]
        assert t18_totals == t17_totals, (unit, t18_totals, t17_totals)
        for half, years in ((found[:19], T18_YEARS[:3]), (found[19:], T18_YEARS[3:])):
            for group, vals in half:
                for k, year in enumerate(years):
                    rows.append(dict(state=unit, year=year, group=group,
                                     persons_000=vals[3 * k]))
    t = pd.DataFrame(rows)
    for (unit, year), g in t.groupby(["state", "year"]):
        v = g.set_index("group").persons_000
        five_year = v.drop(["0-1", "Total"]).sum()
        assert abs(five_year - v["Total"]) <= 0.001 * v["Total"] + 10, (unit, year)
    return t


def age_shares(t18: pd.DataFrame, unit: str) -> pd.DataFrame:
    """Shares of the unit's total by band (0, 1, 5, ..., 75, 80=80+), per Table-18 year."""
    g = t18[t18.state == unit].pivot(index="year", columns="group", values="persons_000")
    bands = pd.DataFrame(index=g.index)
    bands[0] = g["0-1"]
    bands[1] = g["0-4"] - g["0-1"]
    for a in range(5, 80, 5):
        bands[a] = g[f"{a}-{a + 4}"]
    bands[80] = g["80+"]
    return bands.div(bands.sum(axis=1), axis=0)


def build_population(t11: pd.DataFrame, t18: pd.DataFrame) -> pd.DataFrame:
    """1st July population by band for every unit and year 2011-2036.

    Age shares are those of the unit's own Table 18 where it has one, otherwise of
    the combined North-East table (the seven NE states) or of India (other small
    states and UTs). Shares are interpolated linearly in time between the 1st March
    tables and held after March 2036, then applied to the unit's 1st July total.
    """
    own = set(t18.state)
    shares = {u: age_shares(t18, u) for u in own}
    march = np.array(T18_YEARS) + 59 / 365  # 1st March as a fraction of the year
    rows = []
    for unit, g in t11.groupby("state", sort=False):
        donor = unit if unit in own else NE_COMBINED if unit in NE_STATES else "INDIA"
        s = shares[donor]
        for year, total in zip(g.year, g.total_000):
            t = year + 181 / 365  # 1st July
            interp = [np.interp(t, march, s[band].to_numpy()) for band in s.columns]
            interp = np.array(interp) / sum(interp)
            for band, share in zip(s.columns, interp):
                rows.append(dict(state=unit, year=year, age_start=band,
                                 population=round(total * 1000 * share)))
    return pd.DataFrame(rows)


# --- SRS Causes of Death 2021-2023 ---------------------------------------------------
# Table 1.3A (PDF page with "Table 1.3A - Distribution of Deaths in India: 2021-2023,
# Person"): percent of deaths in each broad age group by cause, all-India, persons.
COD_GROUPS = ["0-4", "05-14", "15-29", "30-44", "45-54", "55-69", "70+"]
COD_ROWS = {
    "cmpn_pct": "Communicable, maternal, perinatal and nutritional conditions",
    "resp_infections_pct": "Respiratory infections",
    "injuries_pct": "Injuries",
    "ncd_pct": "Non-Communicable diseases",
    "ill_defined_pct": "Symptoms, signs and Ill-defined conditions",
}


def parse_causes(pdf: Path) -> pd.DataFrame:
    pages = int(re.search(r"Pages:\s+(\d+)", subprocess.run(
        ["pdfinfo", str(pdf)], capture_output=True, text=True, check=True).stdout).group(1))
    table = None
    for page in range(1, pages + 1):
        text = pdf_text(pdf, page, page)
        if "Table 1.3A - Distribution of Deaths in India: 2021-2023, Person" in text:
            table = text
            break
    assert table, "Table 1.3A not found"
    values = {}
    for col, label in COD_ROWS.items():
        m = re.search(rf"^\s*{re.escape(label)}\s+((?:{NUM}\s+){{7}}{NUM})\s*$", table, re.M)
        assert m, label
        values[col] = [float(v) for v in m.group(1).split()][1:]  # drop all-ages column
    t = pd.DataFrame(values)
    t.insert(0, "age_group", COD_GROUPS)
    t.insert(1, "age_from", [0, 5, 15, 30, 45, 55, 70])
    t.insert(2, "age_to", [4, 14, 29, 44, 54, 69, None])
    t["age_to"] = t["age_to"].astype("Int64")
    groups = t[["cmpn_pct", "injuries_pct", "ncd_pct", "ill_defined_pct"]].sum(axis=1)
    assert ((groups - 100).abs() <= 0.25).all(), groups.tolist()
    return t


def main(life_pdf: str, proj_pdf: str, cod_pdf: str) -> None:
    lt = parse_lifetables(Path(life_pdf))
    lt.to_csv(DATA / "lifetables_srs.csv", index=False)

    t11 = parse_table11(Path(proj_pdf))
    t18 = parse_table18(Path(proj_pdf))
    india = t11[t11.state == "INDIA"].set_index("year").total_000
    units = t11[t11.state != "INDIA"].groupby("year").total_000.sum()
    print("Table 11: sum of states and UTs / India, by year:",
          (units / india).round(4).agg(["min", "max"]).tolist())
    pop = build_population(t11, t18)
    pop.to_csv(DATA / "population_age_state.csv", index=False)

    cod = parse_causes(Path(cod_pdf))
    cod.to_csv(DATA / "cause_share_ncd_lri.csv", index=False)
    print(f"wrote {len(lt)} life-table rows, {len(pop)} population rows, {len(cod)} cause rows")


if __name__ == "__main__":
    main(*sys.argv[1:])
