# IHME downloads (local tier)

IHME files are **never committed**. Save everything into `health/data_local/` (git-ignored)
under exactly the filenames below. There is no fetch script: IHME hands over data by web
query, and the results tool needs a free login. Use of the data is under IHME's free-of-charge
non-commercial user agreement.

Status key: **[confirmed]** = read on a public page on 2026-11-10. **[unconfirmed]** = could not be
checked without logging in; look at what the tool offers and tell us if it differs.

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
