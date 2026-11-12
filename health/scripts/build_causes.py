"""Build data/causes.csv: what causes each city's PM2.5, every study side by side.

    python scripts/build_causes.py [download folder outside the repo]

Inputs (all committed, each with its own entry in data/sources.toml):
  data/apna_source_apportionment.csv   APnA, UrbanEmissions.Info: CAMx source shares for 49 airsheds
  data/causes_transcribed.csv          city studies transcribed by hand from their reports
  McDuffie et al. 2021 Supplementary Data 1 (xlsx, downloaded to a folder outside the repo)
Rows for a place that is not one of the 50 cities are dropped and counted. The result is
checked by airhealth.causes.validate (the check causes.table() runs); the build raises,
naming the group, if it fails. Sorted by city, study, season, source_harmonised.

APnA
  Categories (Zenodo record 6919069): A all transport, B residential, C industries without
  brick kilns, D all dust, E open waste burning, F diesel generator sets, G brick
  manufacturing, H sea salt (blank where not applicable: no row is written), I outside.
  Annual mean, concentration shares, CAMx, airshed box, whole split (covers = all).
  The CSV's study_uear is the report batch (2017: 20 cities; 2019: 30), not the model year.
  Base years are read in the reports, not the CSV (BASE_YEAR below):
    2017 batch -> 2015: 'Air Pollution Knowledge Assessments (APnA) for Indian cities',
      program booklet (Nov 2017), PDF p. 2 ('emissions ... for year 2015') and p. 6 (table
      'How various sources contributed annually to the modeled ambient PM2.5 concentrations
      in 2015'). https://urbanemissions.info/wp-content/uploads/apna/docs/apna_program_summary_booklet.pdf
    2019 batch -> 2018: 'Air Pollution knowledge assessments for Indian cities', Summary
      report, July 2019, PDF p. 9 ('emissions inventory for each of the cities for year
      2018') and p. 15 (Table 3 'Summary of base year (2018) modeled annual average PM2.5
      concentrations and source contributions'). 
      https://urbanemissions.info/wp-content/uploads/apna/docs/2019-07-APnA30city_summary_report.pdf
  Methods paper: Guttikunda SK, Nishadh KA, Jawahar P. Urban Climate 27 (2019) 124-141,
  doi:10.1016/j.uclim.2018.11.005 (not read here; the two reports above were).
"""
import sys
from pathlib import Path

import openpyxl
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from airhealth import causes, paths  # noqa: E402
import _fetch  # noqa: E402

APNA_COLUMNS = {"A": ("transport", "all transport (road, rail, aviation, shipping)"),
                "B": ("residential", "residential"),
                "C": ("industry", "industries (without brick kilns)"),
                "D": ("dust", "all dust (construction and resuspension)"),
                "E": ("waste_burning", "open waste burning"),
                "F": ("dg_sets", "diesel generator sets"),
                "G": ("brick_kilns", "brick manufacturing"),
                "H": ("natural", "sea salt"),
                "I": ("outside", "outside/regional contribution")}
BASE_YEAR = {2017: 2015, 2019: 2018}
RECORD = "https://zenodo.org/records/6919069"
BASE_YEAR_DOC = {
    2015: "base year 2015 read in the APnA 2017 program booklet (urbanemissions.info/wp-content/uploads/apna/docs/"
          "apna_program_summary_booklet.pdf), PDF p. 2 and the table on p. 6 headed 'in 2015'",
    2018: "base year 2018 read in the APnA July 2019 summary report (urbanemissions.info/wp-content/uploads/apna/"
          "docs/2019-07-APnA30city_summary_report.pdf), PDF p. 9 and Table 3 on p. 15 'base year (2018)'",
}


def apna_rows(cities: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    raw = pd.read_csv(paths.DATA / "apna_source_apportionment.csv")
    by_airshed = dict(zip(cities.apna_airshed, cities.city))
    rows, dropped = [], []
    for _, r in raw.iterrows():
        city = by_airshed.get(r.City)
        if city is None:
            dropped.append(r.City)
            continue
        year = BASE_YEAR[int(r.study_uear)]
        for col, (name, label) in APNA_COLUMNS.items():
            if pd.isna(r[col]):
                continue
            rows.append(dict(
                city=city, study=f"apna_{year}", institution="UrbanEmissions.Info", year_sampled=year,
                season="annual", months="1-12", size_fraction="PM2.5", method="CAMx",
                metric="concentration_share", boundary="airshed_box", covers="all", source_raw=label,
                source_harmonised=name, share_pct=float(str(r[col]).rstrip("%")), n_sites=None, n_days=None,
                url=RECORD,
                locator=f"APnA_50airsheds_PM25_Source_Apportionment_CAMxOutputs.csv, airshed '{r.City}', column "
                        f"{col}; study_uear {int(r.study_uear)} is the report batch, {BASE_YEAR_DOC[year]}",
                evidence_key="O"))
    return pd.DataFrame(rows, columns=causes.COLUMNS), dropped


# McDuffie EE, Martin RV, Spadaro JV, Burnett R, Smith SJ, et al. Source sector and fuel contributions to ambient
# PM2.5 and attributable mortality across multiple spatial scales. Nat Commun 12:3594 (2021),
# doi:10.1038/s41467-021-23853-y (open access, CC BY 4.0). "Supplementary Data 1" is MOESM4 (xlsx, one sheet,
# 'Data File 1: PM2.5 Exposure Estimates, Sectoral Source Contributions, ...'; MOESM5 is Data File 2 by fuel type,
# MOESM6 Data File 3 for 2019). Sheet layout: header row 7 (Excel), then regions, countries and, under each country,
# its sub-national areas named after the nearest city. India's areas sit between the 'India' and 'Nepal' rows.
# Column B is the population-weighted annual mean PM2.5 (ug/m3); C..V are the 20 sector shares (%) of it.
# What the paper says the city value is: annual 2017, GEOS-Chem (24 sensitivity simulations, CEDS GBD-MAPS 2017
# emissions) shares applied to population-weighted PM2.5 over the area's boundary, "defined using T3 urban extent
# data from the Atlas of Urban Expansion" (200 metropolitan areas > 100,000 people in 2010; the model grid is
# 2 x 2.5 degrees outside North America, Europe and East Asia). The urban extent is the nearest of this
# schema's boundaries to `municipal`.
MCDUFFIE_URL = ("https://static-content.springer.com/esm/art%3A10.1038%2Fs41467-021-23853-y/MediaObjects/"
                "41467_2021_23853_MOESM4_ESM.xlsx")
MCDUFFIE_PAPER = "https://www.nature.com/articles/s41467-021-23853-y"
# The file's spellings -> cities.csv names (the file uses the nearest city's name; none differ here, kept explicit)
MCDUFFIE_CITY = {"Jaipur": "Jaipur", "Ahmedabad": "Ahmedabad", "Kanpur": "Kanpur", "Kolkata": "Kolkata",
                 "Mumbai": "Mumbai", "Pune": "Pune", "Hyderabad": "Hyderabad", "Vijayawada": "Vijayawada",
                 "Coimbatore": "Coimbatore"}
# sector column header (without ' Contribution (%)') -> (harmonised name, reason when not obvious). The paper's
# sector definitions are in Fig. 2/3 captions and Methods; the 20 columns plus nothing else sum to 100 +/- 0.2.
MCDUFFIE_SECTORS = {
    "Agriculture": ("other", "non-combustion agriculture (fertiliser/livestock NH3 forming secondary ammonium "
                    "salts); not field burning, and not receptor-model 'secondary_unassigned' since it is assigned "
                    "to a sector here"),
    "Energy Coal": ("industry", "power generation; APnA's industry group includes power plants"),
    "Energy NonCoal": ("industry", "power generation, oil and gas; same as Energy Coal"),
    "Industry Coal": ("industry", ""),
    "Industry NonCoal": ("industry", ""),
    "NonRoad Transport": ("transport", ""),
    "Road Transport": ("transport", ""),
    "Residential Coal Combustion": ("residential", ""),
    "Residential Biofuel Combustion": ("residential", "solid biofuel for cooking and heating"),
    "Residential Other Combustion": ("residential", ""),
    "Commercial Combustion": ("other", "commercial buildings are a separate McDuffie sector from residential; "
                              "kept out of `residential` so that group is homes only"),
    "Other Combustion": ("other", "uncategorised combustion (paper: 'uncategorized combustion sources')"),
    "Solvent": ("other", "solvent use, non-combustion"),
    "Waste": ("waste_burning", "controller ruling: McDuffie's sectors follow CEDS, whose waste sector in South Asia is mostly "
              "open burning. The paper does not define the sector as anything else: Fig. 2 caption lists 'waste "
              "incineration' and the text compares the waste sector's deaths with 'the only previous estimate of "
              "domestic waste burning'"),
    "International Shipping": ("transport", "APnA's transport group includes shipping"),
    "Agricultural Waste Burning": ("agri_burning", "crop-residue burning"),
    "Other Open Fire": ("natural", "paper: deforestation, boreal forest, peat, savannah and temperate forest fires"),
    "AFCID Dust": ("dust", "anthropogenic fugitive, combustion and industrial dust (construction, roads)"),
    "Windblown Dust": ("natural", "natural mineral dust (paper groups it with natural sources); APnA's `dust` is "
                       "construction and resuspension only"),
    "Remaining Sources": ("other", "volcanic SO2, lightning NOx, soil NOx, aircraft, oceanic and biogenic sources: "
                          "mixed natural and anthropogenic"),
}
MCDUFFIE_LOCATOR = ("Supplementary Data 1 (41467_2021_23853_MOESM4_ESM.xlsx), sheet 1, row '{city}' under India, "
                    "column '{col} Contribution (%)'; annual 2017 GEOS-Chem shares of population-weighted PM2.5 over "
                    "the city's Atlas of Urban Expansion T3 urban extent (Nat Commun 12:3594, main text, 'Sub-national "
                    "area boundaries are identified by the nearest dominant city and are defined using T3 urban "
                    "extent data from the Atlas of Urban Expansion'; shares from 'gridded model sensitivity "
                    "simulation results (... 2 x 2.5 degrees elsewhere)' applied 'to the sub-national exposure "
                    "levels'; i.e. Atlas of Urban Expansion T3 urban extent, 2x2.5 deg model downscaled; 2017 base "
                    "year per 'Global and national sector and fuel-type contributions')")


def mcduffie_rows(cities: pd.DataFrame, xlsx: Path) -> tuple[pd.DataFrame, list[str]]:
    ws = openpyxl.load_workbook(xlsx, read_only=True, data_only=True).worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    header = next(r for r in rows if r[0] == "Country Name")
    cols = [str(h).removesuffix(" Contribution (%)") for h in header[2:22]]
    assert cols == list(MCDUFFIE_SECTORS), f"sector columns changed: {cols}"
    names = [r[0] for r in rows]
    area = rows[names.index("India") + 1:names.index("Nepal")]
    out, dropped = [], []
    for r in area:
        city = MCDUFFIE_CITY.get(r[0])
        if city is None or city not in set(cities.city):
            dropped.append(r[0])
            continue
        shares = [float(x) for x in r[2:22]]
        total = sum(shares)
        assert abs(total - 100) <= 0.5, (city, total)  # rounding only, so no remainder row is needed
        for col, share in zip(cols, shares):
            name, why = MCDUFFIE_SECTORS[col]
            out.append(dict(
                city=city, study="mcduffie2021", institution="Dalhousie University / Washington University / "
                "PNNL / Univ. of Toronto et al. (McDuffie et al.)", year_sampled=2017, season="annual",
                months="1-12", size_fraction="PM2.5", method="GEOS-Chem", metric="concentration_share",
                boundary="municipal", covers="all", source_raw=col, source_harmonised=name, share_pct=share,
                n_sites=None, n_days=None, url=MCDUFFIE_PAPER,
                locator=MCDUFFIE_LOCATOR.format(city=r[0], col=col), evidence_key="O"))
    return pd.DataFrame(out, columns=causes.COLUMNS), dropped


def main() -> None:
    cities = pd.read_csv(paths.DATA / "cities.csv")
    apna, dropped = apna_rows(cities)
    folder = _fetch.workdir(sys.argv, "causes")
    mcd, mcd_dropped = mcduffie_rows(cities, _fetch.fetch(MCDUFFIE_URL, folder, "mcduffie2021_supp_data_1.xlsx"))
    transcribed = pd.read_csv(paths.DATA / "causes_transcribed.csv", dtype={"months": str})
    parts = [apna, mcd, transcribed[list(causes.COLUMNS)]]
    out = pd.concat([p for p in parts if len(p)], ignore_index=True)
    known = set(cities.city)
    unknown = out[~out.city.isin(known)]
    if len(unknown):
        dropped += list(unknown.city)
        out = out[out.city.isin(known)]
    print(f"mcduffie: {mcd.city.nunique()} cities kept {sorted(mcd.city.unique())}; dropped {len(mcd_dropped)} "
          f"India areas not among the 50: {mcd_dropped}")
    print(f"rows: apna {len(apna)}, mcduffie {len(mcd)}, transcribed {len(transcribed)}; dropped for unknown places: "
          f"{len(dropped)} {sorted(set(dropped)) or ''}")
    out = out.sort_values(["city", "study", "season", "source_harmonised"]).reset_index(drop=True)
    causes.validate(out)
    out.to_csv(paths.DATA / "causes.csv", index=False)
    print(f"wrote data/causes.csv: {len(out)} rows, {out.city.nunique()} cities, studies {sorted(out.study.unique())}")


if __name__ == "__main__":
    main()
