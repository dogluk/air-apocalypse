"""Build data/causes.csv: what causes each city's PM2.5, every study side by side.

    python scripts/build_causes.py

Inputs (all committed, each with its own entry in data/sources.toml):
  data/apna_source_apportionment.csv   APnA, UrbanEmissions.Info: CAMx source shares for 49 airsheds
  data/causes_transcribed.csv          city studies transcribed by hand from their reports
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

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from airhealth import causes, paths  # noqa: E402

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


def main() -> None:
    cities = pd.read_csv(paths.DATA / "cities.csv")
    apna, dropped = apna_rows(cities)
    transcribed = pd.read_csv(paths.DATA / "causes_transcribed.csv", dtype={"months": str})
    parts = [apna, transcribed[list(causes.COLUMNS)]]
    out = pd.concat([p for p in parts if len(p)], ignore_index=True)
    known = set(cities.city)
    unknown = out[~out.city.isin(known)]
    if len(unknown):
        dropped += list(unknown.city)
        out = out[out.city.isin(known)]
    print(f"rows: apna {len(apna)}, transcribed {len(transcribed)}; dropped for unknown places: "
          f"{len(dropped)} {sorted(set(dropped)) or ''}")
    out = out.sort_values(["city", "study", "season", "source_harmonised"]).reset_index(drop=True)
    causes.validate(out)
    out.to_csv(paths.DATA / "causes.csv", index=False)
    print(f"wrote data/causes.csv: {len(out)} rows, {out.city.nunique()} cities, studies {sorted(out.study.unique())}")


if __name__ == "__main__":
    main()
