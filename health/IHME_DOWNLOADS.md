# IHME downloads (local tier)

IHME files are **never committed**. Save everything into `health/data_local/` (git-ignored)
under exactly the filenames below. There is no fetch script: IHME hands over data by web
query, and the results tool needs a free login. Use of the data is under IHME's free-of-charge
non-commercial user agreement.

Status key: **[confirmed]** = read on a public page on 2026-11-10. **[unconfirmed]** = could not be
checked without logging in; look at what the tool offers and tell us if it differs.

## Status, 2026-11-11 (evening): loaders built

**The loaders are written and read the files as IHME delivers them** (`airhealth/ihme.py`,
`airhealth/ihme_curves.py`; exact paths in `ihme.py`). With these files in place the tool runs
three more curves, `gbd2023`, `gbd2019` and `gemm_5cod`, and a fifth map, `gbd2023`. Without
them it says which files are missing and runs the open tier as before; tests that need them
skip. The filenames in Part A and Part B below are superseded by the table that follows.

How the two traps were settled:

1. **Two scales: settled.** The 2022-dated files (COPD, diabetes, lung cancer) are relative
   risks (start at 1; their mean equals the mean of their ratio-scale draws). The 2025-dated
   files (IHD, stroke, LRI, dementia) are **ln RR**: (a) the GBD 2023 risk-factor appendix
   models log(MRBRT(X)/MRBRT(X_CF)) (appendix 2 to the GBD 2023 Lancet capstone, "Ambient
   particulate matter pollution", "MR-BRT risk splines";
   <https://openaccess.sgul.ac.uk/id/eprint/118199/7/1-s2.0-S014067362501637X-mmc2.pdf>,
   sha256 bc0fd62e…); (b) their layout (`risk`, `draw_0`…) is the output of IHME's
   burden-of-proof code, bopforge, whose `get_draws` writes draws of ln RR "anchored at lnRR
   = 0" (github.com/ihmeuw-msca/bopforge, commit 0d9156ed); (c) each mean file is the mean of
   its draws file and its lower/upper are the draws' 2.5th/97.5th percentiles, symmetric about
   the mean (`tests/test_ihme.py`). Reading them as RR − 1 instead would lower gbd2023's India
   burden by about a ninth (1.61 to 1.43 million on the gbd2023 map), so the choice matters
   but does not explain the gap to GBD's own count (below). The GBD 2023 **information sheet**
   (`IHME_GBD_2023_AIR_POLLUTION_1990_2023_INFO_SHEET_Y2025M12D15.PDF` on the GHDx record)
   needs a login and was not read; worth downloading next time someone is signed in.
2. **State location ids: settled** (table under Part B).

**TMREL.** GBD 2023 keeps GBD 2019's: uniform 2.4 to 5.9 µg/m³ ("The resulting lower/upper
bounds of the distribution for GBD 2023 were 2.4 and 5.9. This has not changed since GBD
2015", appendix 2 as above). The tool uses the midpoint, 4.15, as each GBD curve's floor
(RR = curve(X)/curve(4.15) above it, 1 below), the simplification the GBD 2019 information
sheet describes. The GBD 2019 TMREL draws file (1,000 draws, 2.40 to 5.89, mean 4.16) is
read only to check this.

**Ages.** GBD applies the curves at 25 and over (IHD, stroke, COPD, lung cancer, type 2
diabetes) and at all ages (LRI) (same appendix); dementia is applied from 25 (GBD's dementia
deaths start at 40).

**Locations.** GBD 2023 has one value for Jammu & Kashmir and Ladakh (4854), used for both,
and one for "Other Union Territories" (44538), used for Andaman & Nicobar, Chandigarh,
Dadra & Nagar Haveli, Daman & Diu, Lakshadweep and Puducherry: both for exposure and for
death rates. Goa is GBD's own (4850). India (163) is not read for the map: like every map,
India is the states weighted by the tool's population (53.97 µg/m³ for 2023 against IHME's
54.05; benchmark `gbd2023_india_exposure`).

**Licence handling.** Nothing derived from these files is committed: the map's state values,
the curves and the death rates are read from `data_local/` at run time. Committed: the code,
location ids, result tables in the README and benchmark write-ups (totals only), as the
design allows. GEMM's five-cause parameters are not IHME's; they are committed in
`data/curves_gemm_5cod.csv` (from the authors' DataGEMM workbook, see `data/sources.toml`).

**What these files cannot give: a GBD all-cause death count.** Part B has seven causes and
all NCDs, not all causes, so there is no `deaths=gbd` source. To add one, query the Results
tool for "All causes" deaths (cause_id 294) by state and age, same years. With it, GBD could
also supply the death rates and life tables (also in the Results tool as "All-cause
mortality").

**Not reproduced yet: GBD's own attributable deaths.** GBD 2023 puts India's 2023 deaths
from ambient PM2.5 at 969,726 (Our World in Data's page of GBD 2023 Results,
<https://ourworldindata.org/grapher/absolute-number-of-deaths-from-outdoor-air-pollution>,
read 2026-11-11). This tool on the same curve, map and year gives 1.61 million. The largest
known difference cannot be computed from these files: GBD scores ambient and household PM2.5
jointly and gives ambient air only its share of the joint attributable fraction, by exposure
(appendix 2, "Proportional PAF approach"); in India, where many homes burn solid fuel, that
share is far below ambient air scored alone. Smaller ones: GBD adds neonatal deaths through
birth weight and gestation (not here), works on grid cells (here state means) and draws the
TMREL. To make it a benchmark, download "Household Air Pollution Estimates [CSV]" (13.9 MB,
same GHDx record) and implement the proportional split.

| What | Where under `data_local/ihme_raw/` | Read by |
|---|---|---|
| GBD 2023 exposure CSV | `IHME_GBD_2023_AIR_POLLUTION_1990_2023_PM/IHME_GBD_2023_AIR_POLLUTION_1990_2023_PM_Y20250930.CSV` | `ihme.exposure_table` (map `gbd2023`) |
| GBD 2023 RR means, 7 causes | `IHME_GBD_2023_AIR_POLLUTION_1990_2021_RR_CURVES/*PM_RR_*_MEAN_*.CSV` | `ihme_curves._gbd2023` |
| GBD 2019 RR summaries | `IHME_GBD_2019_PM_RISK_SUMM/` (IHD and stroke 25-95, COPD, LRI, lung cancer, T2 DM) | `ihme_curves._gbd2019` |
| GBD 2019 TMREL draws | `IHME_GBD_2019_PM_RISK_TMREL_DRAWS_Y2021M01D06.csv` | check only |
| GBD 2023 deaths, population | `part_b/gbd2023/IHME-GBD_2023_DATA-0b7890d0-1/…csv`, `…-bccbe428-1/…csv` | `ihme.cause_rates` (all three curves) |

## Status, 2026-11-11 (afternoon)

**Part A is done. Part B is done for GBD 2023 only:** the Results tool no longer offers
GBD 2019 (see "Part B as run" below). The Part A files are in
`health/data_local/ihme_raw/` under IHME's own filenames, with the zips unpacked beside
them. They were **not** renamed to the names Part A asks for: the loader reads the files as
IHME delivers them. Treat the filenames in Part A below as superseded by this table.

| What | Where under `data_local/ihme_raw/` | Read on 2026-11-11 |
|---|---|---|
| GBD 2019 risk curves, means | `IHME_GBD_2019_PM_RISK_SUMM/` (38 CSVs) | Columns `label, exposure_spline, mean, lower, upper`; ratio scale (1 at zero exposure). One file each for COPD, LRI, lung cancer, type 2 diabetes, birth outcomes; IHD and stroke have one file per five-year age from 25 to 95. |
| GBD 2019 TMREL draws | `IHME_GBD_2019_PM_RISK_TMREL_DRAWS_Y2021M01D06.csv` | 1,000 draws, one column `x`. |
| GBD 2019 information sheet | `IHME_GBD_2019_PM_RISK_INFO_SHEET_Y2021M03D18_0.pdf` | Read 2026-11-11: relative risks (ratio scale, not yet scaled to the TMREL); TMREL uniform 2.4-5.9, midpoint 4.15. |
| GBD 2023 risk curves | `IHME_GBD_2023_AIR_POLLUTION_1990_2021_RR_CURVES/` | PM2.5 mean files for **seven causes of death**: COPD, type 2 diabetes, lung cancer, dementia, IHD, LRI, stroke (plus birth weight and gestational age; NO2 and ozone files are not ours). One file per cause, **no age split** for IHD or stroke. Exposure runs 0 to 2,500 in steps of 0.1. |
| GBD 2023 exposure | `IHME_GBD_2023_AIR_POLLUTION_1990_2023_PM/` | One CSV of population-weighted means by `location_id` and year (925 locations, 1990-2023), plus yearly rasters (`.TIF`). |
| Codebook | `IHME_GBD_2021_AIR_POLLUTION_1990_2023_CODEBOOK_Y2024M06D06.csv` | Describes the exposure CSV. Lists India as location 163; **does not list Indian states**. |

Two traps for whoever writes the loader:

1. **The GBD 2023 files are on two scales.** The four dated 2022 (COPD, diabetes, lung
   cancer, birth outcomes) have columns `cause, exposure, mean, lower, upper` and start at 1:
   a risk ratio. The four dated 2025 (IHD, stroke, LRI, dementia) have columns
   `risk, mean, lower, upper` and start at 0: the log of the ratio (settled above).
2. **State location ids are not in the codebook.** Settled by Part B: the query results carry
   `location_id` and `location_name` (table below). All 32 ids appear in the GBD 2023
   exposure CSV. That CSV also has ids 43872-43942, 44539 and 44540, which look like
   urban/rural halves of the states; the Results tool does not offer those, so ignore them.

A first look at the exposure CSV: India (location 163) is **53.6 µg/m³ in 2019 and 54.1 in
2023**. GBD 2019, as printed in Pandey et al. 2021, had 90.9. So IHME's own newer round has
moved most of the way to the satellite maps (AQLI 41.2, ACAG 49.8). This bears on gap G7 in
`lit/gaps.md`. Not yet wired into the tool.

### Part B as run (2026-11-11, GBD Results tool, signed in)

Files are under `data_local/ihme_raw/part_b/gbd2023/`, kept under IHME's own names, each zip
unpacked into a folder of the same name. Each zip holds one CSV and a `citation.txt`. **Not**
renamed to the Part B table's names, for the same reason as Part A.

| What | File (under `part_b/gbd2023/`) | Rows | Contents |
|---|---|---|---|
| Deaths | `IHME-GBD_2023_DATA-0b7890d0-1/IHME-GBD_2023_DATA-0b7890d0-1.csv` | 31,872 | Measure Deaths; metric Number and Rate (rate is per 100,000); 8 causes; 32 locations; 27 ages; sex Both; years 2015, 2019, 2023. |
| Population | `IHME-GBD_2023_DATA-bccbe428-1/IHME-GBD_2023_DATA-bccbe428-1.csv` | 2,592 | Measure Population (measure_id 44); metric Number; same 32 locations, 27 ages, sex Both, 3 years. |

Columns, deaths file: `population_group_id, population_group_name, measure_id,
measure_name, location_id, location_name, sex_id, sex_name, age_id, age_name, cause_id,
cause_name, metric_id, metric_name, year, val, upper, lower`. The population file has the same
columns without `cause_id, cause_name`. `population_group_name` is always "All Population".
No empty values.

Checks done on 2026-11-11: the 31 states and UTs add up exactly to India (population and
deaths, every cause, 2023). The age bands add up exactly to "All ages". India 2023, all ages:
population 1,443.4 M; IHD 1,464,977 deaths; stroke 1,034,796; COPD 1,023,485; LRI
412,055; lung cancer 101,269; type 2 diabetes 578,366; dementia 140,944; all NCDs 6,971,959.

**Causes (cause_id, name as written):** 322 Lower respiratory infections; 409
Non-communicable diseases; 426 Tracheal, bronchus, and lung cancer; 493 Ischemic heart
disease; 494 Stroke; 509 Chronic obstructive pulmonary disease; 543 Alzheimer's disease and
other dementias; 976 Diabetes mellitus type 2.

IHME **leaves out rows** for ages where a cause is not estimated. These are absent, not
zero: IHD, COPD, lung cancer and type 2 diabetes start at 15-19 years; dementia starts at
40-44; LRI, stroke and all NCDs have every age.

**Ages (age_id, name as written):** 22 All ages; 1 <5 years; 2 0-6 days; 3 7-27 days;
388 1-5 months; 389 6-11 months; 238 12-23 months; 34 2-4 years; 6 5-9; 7 10-14; 8 15-19;
9 20-24; 10 25-29; 11 30-34; 12 35-39; 13 40-44; 14 45-49; 15 50-54; 16 55-59; 17 60-64;
18 65-69; 19 70-74; 20 75-79; 30 80-84; 31 85-89; 32 90-94; 235 95+ years. "<5 years" is
the sum of the six under-5 groups, so do not add it to them.

**Locations, GBD 2023 (location_id, name as written):**

| id | name | id | name |
|---|---|---|---|
| 163 | India | 4860 | Maharashtra |
| 4841 | Andhra Pradesh | 4861 | Manipur |
| 4842 | Arunachal Pradesh | 4862 | Meghalaya |
| 4843 | Assam | 4863 | Mizoram |
| 4844 | Bihar | 4864 | Nagaland |
| 4846 | Chhattisgarh | 4865 | Odisha |
| 4849 | Delhi | 4867 | Punjab |
| 4850 | Goa | 4868 | Rajasthan |
| 4851 | Gujarat | 4869 | Sikkim |
| 4852 | Haryana | 4870 | Tamil Nadu |
| 4853 | Himachal Pradesh | 4871 | Telangana |
| 4854 | Jammu & Kashmir and Ladakh | 4872 | Tripura |
| 4855 | Jharkhand | 4873 | Uttar Pradesh |
| 4856 | Karnataka | 4874 | Uttarakhand |
| 4857 | Kerala | 4875 | West Bengal |
| 4859 | Madhya Pradesh | 44538 | Other Union Territories |

That is 30 named states/UTs plus "Other Union Territories". Ladakh is merged with J&K. The
remaining small UTs (Chandigarh, Puducherry, the islands, Dadra/Daman) are pooled in 44538;
the tool does not list them separately. Note that a second "Punjab" (Pakistan) exists in the
tool's location tree; the file has India's, 4867.

**Where the tool differed from the Part B instructions:**

- **Only GBD 2023 is offered.** The tool has no release menu. Its version list holds one
  version (id 8352, gbd_round 2023, dated 2025-10-29). Footer reads "GBD 2023". So run 1
  (GBD 2019) **was not obtained**; an older GBD 2019 tool would be needed.
- GBD Estimate "Cause of death or injury" and "Population" exist under those names. Other
  menu entries: Probability of death by cause, Risk factor, Etiology, Impairment, SEV, HALE,
  Injuries by nature, Fertility, All-cause mortality.
- Measure "Deaths", metrics "Number", "Percent", "Rate": as the doc says. Population's metric
  is "Number" only.
- "Diabetes mellitus type 2" is offered (also "Diabetes mellitus" and type 1); took type 2.
- **Added an eighth cause**, "Alzheimer's disease and other dementias", because the GBD 2023
  risk curves (Part A) include dementia.
- No "India group" shortcut was used; India and its 31 children were ticked one by one. No
  districts or urban/rural splits are offered.
- Under-5 split is 0-6 days, 7-27 days, 1-5 months, 6-11 months, 12-23 months, 2-4 years
  (not "Post Neonatal" / "1-4 years"). Aggregates such as "<1 year", "<28 days", "80+" and
  "Age-standardized" are also offered but were not taken. No single-year ages for deaths.
- Years offered: 1980-2023.
- **Sex: Both only.** Male and Female were not taken: the tool caps rows per user per
  release (the cap is not stated) and adding them would have tripled the deaths file.
- **Delivery:** the Download button sends the query off and says an email with a link will go
  to the account address. A progress page linked from the confirmation showed both files
  ready within a few minutes, and they were downloaded from there in the browser. So nothing
  depended on email, though IHME will also have emailed links. The progress page keeps files
  for 7 days. Query IDs: deaths `0b7890d07e934169cbec1557392feb92`, population
  `bccbe42875baf0561aae5629bed4fdf4`, both submitted about 17:19-17:20 UTC.
- IDs and names were both requested, hence the paired `_id` / `_name` columns.
- Single download per query. Neither was split into parts (deaths ~32k rows; the stated
  per-file maximum is 100,000).

**Still missing:** GBD 2019 deaths and population by state (not in this tool); deaths by
Male / Female, if ever wanted.

## Part A. Relative-risk curves (public, no login)

1. Open https://ghdx.healthdata.org/record/ihme-data/global-burden-disease-study-2019-gbd-2019-particulate-matter-risk-curves
   **[confirmed]** (record lists 8 files; curves cover IHD, stroke, COPD, lung cancer, acute
   lower respiratory infection, type 2 diabetes, plus birth outcomes).
2. Download "Summary/Mean Estimates [CSV]" (about 0.4 MB). Save as
   `health/data_local/gbd2019_pm_rr_summary.csv`.
3. Download "Theoretical Minimum Risk Exposure Level (TMREL) Draws [CSV]" (about 17 KB). Save as
   `health/data_local/gbd2019_pm_tmrel_draws.csv`.
4. Download "Data Release Information Sheet". Save as `health/data_local/gbd2019_pm_release_info.pdf`
   (it documents the column meanings). Skip the 97 MB "Statistical Draws" file unless asked.
5. Open https://ghdx.healthdata.org/node/594794 **[confirmed]** (GBD 2023 Air Pollution Exposure
   Estimates and Risk Curves 1990-2023, published 23 Jan 2026; 7 files).
6. Download "Relative Risk Estimates [CSV]" (about 177 MB). Save as
   `health/data_local/gbd2023_rr.csv`.
7. Download "Codebook [CSV]". Save as `health/data_local/gbd2023_codebook.csv`.
8. Optional, same page: "Ambient Particulate Matter Exposure Estimates [CSV]" (152 MB) as
   `health/data_local/gbd2023_pm_exposure.csv`. Only needed if we later want GBD 2023 exposure.

The page says GBD 2023 relative risks cover "seven causes"; which seven is **[unconfirmed]**
(the 2019 six plus one more is likely, but check the codebook).

## Part B. Deaths, rates and population (GBD Results tool, login required)

Tool: https://vizhub.healthdata.org/gbd-results (free IHME account). All selections below are
**[unconfirmed]**: the tool could not be opened without a login, and menu wording changes
between releases. Pick the closest option and note any difference.

Run the query **three times**, once per GBD release, since each release has its own cause and
location list. For each run, use these selections:

1. Sign in and open GBD Results.
2. GBD Estimate: **Cause of death or injury**.
3. Measure: tick **Deaths**. Metric: tick **Number** and **Rate**. (Percent not needed.)
4. Cause: select these seven only:
   - Ischemic heart disease
   - Stroke
   - Chronic obstructive pulmonary disease
   - Tracheal, bronchus, and lung cancer
   - Lower respiratory infections
   - Diabetes mellitus type 2 (if only "Diabetes mellitus" is offered, take that and tell us)
   - Non-communicable diseases (the all-NCD aggregate)
5. Location: **India** plus **every Indian state and union territory** (use the "India" group
   shortcut in the location tree; the states sit under India as subnational locations). Do not
   add districts if offered.
6. Age: select the **5-year bands** from "<5 years" through "95+ years" individually
   (not "All ages" or "Age-standardized" only). If the tool splits under-5 into
   "Early Neonatal", "Late Neonatal", "Post Neonatal" and "1-4 years", also tick those.
   Also tick "All ages" so we have a total to check against.
7. Sex: **Both** (also tick Male and Female if it costs nothing).
8. Year: pick the years for that run (below).
9. Submit, wait for the email or download link, download the **CSV**, and save it under the
   filename in the table.
10. If the tool splits the result into several zip parts, unzip them and save each part with a
    `_partN` suffix, e.g. `gbd_deaths_2019_part1.csv`.

| Run | GBD release (the tool's "GBD round" or "Release" menu) | Years | Save as |
|---|---|---|---|
| 1 | GBD 2019 | 2015 and 2019 | `gbd2019_deaths_cause_age_state.csv` |
| 2 | GBD 2023 (latest at time of writing) | 2015, 2019 and 2023 | `gbd2023_deaths_cause_age_state.csv` |

If a newer release than GBD 2023 is offered when you do this, use the newest one for run 2 and
say which it is. Whether GBD 2019 state-level results are still offered in the current tool is
**[unconfirmed]**; if they are not, say so and we will look for the older "GBD 2019" tool.

### Population by age

Repeat in the same tool with these changes:

1. GBD Estimate: **Risk factor / Cause / Impairment** is not right; choose **Population**
   if offered (the menu name may be "Population" under "GBD Estimate" or "Demographics").
   **[unconfirmed]**.
2. Measure: Population. Location, Age (5-year bands plus "All ages"), Sex (both) and Years as
   in Part B above.
3. Save as `gbd2019_population_age_state.csv` (years 2015, 2019) and
   `gbd2023_population_age_state.csv` (years 2015, 2019, 2023).

## Checklist of final files in `health/data_local/`

Superseded: the loaders read IHME's own filenames (see the status table at the top).

- [ ] `gbd2019_pm_rr_summary.csv`
- [ ] `gbd2019_pm_tmrel_draws.csv`
- [ ] `gbd2019_pm_release_info.pdf`
- [ ] `gbd2023_rr.csv`
- [ ] `gbd2023_codebook.csv`
- [ ] `gbd2019_deaths_cause_age_state.csv`
- [ ] `gbd2023_deaths_cause_age_state.csv`
- [ ] `gbd2019_population_age_state.csv`
- [ ] `gbd2023_population_age_state.csv`
- [ ] (optional) `gbd2023_pm_exposure.csv`

Do not rename columns or edit the files; the loader checks them as delivered.
