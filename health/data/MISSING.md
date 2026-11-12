# Missing values

Values that could not be found at their source, with what was tried.

## Burnett et al. 2022 "Fusion" risk function: no all-cause or non-accidental parameters

Burnett RT, Spadaro JV, Garcia GR, Pope CA. Designing health impact functions to assess marginal changes in outdoor fine
particulate matter. Environ Res 2022; 204: 112245, https://doi.org/10.1016/j.envres.2021.112245.
Tried, 2026-11-10: the article page on ScienceDirect (open access; abstract and highlights read), PubMed 34687750, Europe PMC
(no PMC copy, no supplement listed). The abstract says the model is fitted "to data for the six specific causes of death
previously examined by the Global Burden of Disease program" (IHD, stroke, COPD, lung cancer, LRI, type 2 diabetes); Wan et al.
2025 (Environ Impact Assess Rev 107823), which used it, describes the same six causes with age-specific parameters for IHD and
stroke. Nothing found gives a Fusion fit to all-cause or non-accidental deaths, so no `fusion` curve is registered. A
cause-specific Fusion curve would need IHME cause-specific deaths and belongs with the local tier. The full text and its
parameter tables were not read (the PDF link did not return text to the tools used); if a later task needs Fusion, read them.

## GEMM supplementary appendix not read directly

The GEMM NCD+LRI parameters (curves_gemm_ncd_lri.csv) were meant to be read from the PNAS SI appendix. It could not be
fetched (PMC and Europe PMC: browser check; pnas.org: HTTP 403). They come instead from the authors' deposited calculator
(DataGEMM), whose India total reproduces PNAS Table 1; see sources.toml. Nothing is missing from the data, but the SI table
itself is unchecked: compare the twelve rows against SI Table S2 (or whichever table holds them) when it can be opened.

## AQLI coefficient: no published uncertainty

AQLI states 0.98 years per 10 µg/m³ PM2.5 with no interval (methodology page, India fact sheet 2025, aqli-update README).
`aqli.sample()` therefore returns the curve unchanged. The interval would have to come from Ebenstein et al. 2017 (PNAS 114:
10384-89, a PM10 estimate) through AQLI's PM10-to-PM2.5 conversion; neither was looked up for this task.

## City populations after 2011: no official source found

cities.csv holds the Census 2011 urban agglomerations and they are used in every year (every result that uses one says so).
Tried, 2026-11-11, briefly: the Technical Group's projections (population_age_state.csv) stop at states and union territories;
the next census's results are not published. No official Indian city or agglomeration figure after 2011 was confirmed. Leads not
checked this session: the United Nations' World Urbanization Prospects (agglomeration estimates, not an Indian official source),
and scaling each city by its state's projected urban growth since 2011 (Technical Group report, urban tables), which would be a
model, to be labelled as one.

## Cause shares for ages 25-29

The SRS Causes of Death report gives one set of shares for ages 15-29 (cause_share_ncd_lri.csv), dominated by injuries among
the young, and the 25-29 band takes it. Against GBD 2015 (the GEMM authors' workbook) the tool's NCD+LRI deaths at 25-29 are
0.64 of GBD's. No SRS table splits 15-29 further; a split would need the Million Death Study or IHME data.

## GBD 2023 risk-curve information sheet (login)

`IHME_GBD_2023_AIR_POLLUTION_1990_2023_INFO_SHEET_Y2025M12D15.PDF` on GHDx record 594794 is behind IHME's login (tried 2026-11-11,
curl and Exa: sign-in page). The scale of the 2025-dated relative-risk files (ln RR) was settled from the GBD 2023 risk-factor
appendix, IHME's bopforge code and the files themselves (IHME_DOWNLOADS.md, status); the sheet would confirm it in IHME's words.

## GBD all-cause deaths

The Part B query took seven causes and all NCDs, not all causes, so the tool has no GBD all-cause death count and no `deaths=gbd`
source. Needed: GBD Results tool, Cause of death or injury, Deaths, Number, cause "All causes", the same 32 locations, ages and
years as Part B.

## GBD's attributable deaths for India

GBD 2023's 969,726 ambient-PM2.5 deaths for India in 2023 (OWID page of GBD 2023 Results) cannot be reproduced from the files
here: GBD splits one PM2.5 attributable fraction between ambient and household air by exposure, which needs GBD 2023's household
air pollution estimates (GHDx record 594794, 'Household Air Pollution Estimates [CSV]', not downloaded). Pandey et al. 2021's
GBD 2019 figure for India has the same dependency.

## Causes by city: studies and values not transcribed (Task 4, 2026-11-12)

- **Chennai (IIT Madras for TNPCB/GCC).** Only the interim report is public
  (https://chennaicorporation.gov.in/gcc/pdf/Intrim%20report%20SA,EI%20and%20CC,%20IITM.pdf, 29 pages, read in full 2026-11-12). It has
  the site list, a gridded emission inventory for five source groups, wind roses and AERMOD PM10 contour plots at four sites, and says
  the EC/OC, metals and ion analyses are 'in progress'. It prints no source-apportionment shares and no PM2.5 emission shares, so no
  Chennai study row is written (APnA and, where it covers Chennai, other tables remain). Needed: the final IIT Madras report.
- **Ahmedabad (GEMI, 5 Nov 2020, PRANA file Ahmedabad.pdf).** The only shares are of the emission inventory (Table 5.1.1, Fig. 5.1.1: road
  dust 36%, domestic 34%, construction and demolition 16%, point sources 14%, line sources 2%, of 53,873 kg/day), and the report calls the
  pollutant 'PM' with no size cut (its dispersion model is PM10 and its receptor section shows PM10 source contributions only). Not PM2.5,
  so left out (size_fraction must be PM2.5). Needed: a PM2.5 split from GEMI or the NCAP final report.
- **Ludhiana, Amritsar, Chandigarh: Biswal et al. 2025 regional stubble shares** (North Punjab 28/24/11%, Central Haryana 25/31/9%,
  Southwest Punjab 39/48/27% for 16 Oct-30 Nov 2022/23/24; doi 10.1039/d5ea00052a, Sec. 3.4). The rule is that a regional value goes to a city only
  if the paper's own map (Fig. 3, regions drawn as coloured lines over the CUPI-G sites) puts the city in the region. The figure is an
  image on the RSC site, which blocked every automated fetch (HTTP 403, Cloudflare), so no city could be placed and no row is written.
  Table S2 (the sites used per region) is in the supplement, also not reachable. Needed: open Fig. 3 in a browser and say which of these
  three cities (and Patiala, Jalandhar and similar if added) falls inside North Punjab, Southwest Punjab or Central Haryana.
- **Kulkarni et al. 2020 (ES&T 54(8): 4790)**: the 20% is read from the abstract on the publisher page; the ACS full text is paywalled, so
  the year simulated and the figure behind the number were not opened (year_sampled is blank).
- **Lok Sabha written answer of 10 March 2025 (DSS season means 2020-24).** The answer text was not found on sansad.in (search engines
  returned only the 9 Feb 2026 answer on a different question); the values were taken from the Times of India report of the answer and are
  now in the leads section at the end (not in the table).
- **Nagar and Sharma 2022 (Urban Climate 41: 101084)**: the ScienceDirect page gave no abstract to the tools used; Delhi 31% and Kanpur 21%
  are from a Hindustan Times report (19 Jan 2022); now in the leads section at the end (not in the table). Biswal et al. quote the Delhi value for 'October to December', the press
  for October-November.
- **Mumbai AERMOD column (Table 7.1 col. C)** and the other dispersion results of the Maharashtra, Hyderabad and Bengaluru reports are for
  'PM' of unstated size and are not transcribed.
- **Biswal et al. 2025 Fig. 3 needs a person to open it.** A person with a normal browser session should open the RSC article
  (doi 10.1039/d5ea00052a, Fig. 3, the region map) and say which of Ludhiana, Amritsar and Chandigarh lie inside North Punjab,
  Southwest Punjab, Central Haryana or Delhi-NCR; the 2022/2023/2024 values for those regions are already in Sec. 3.4 (see above) and can
  then be written as boundary = region rows.
- **Lok Sabha answer of 10 March 2025 (re-checked in the fix round).** Searches restricted to pib.gov.in, sansad.in, loksabhadocs.nic.in and
  eparlib.nic.in returned only unrelated PIB releases (Nov and Dec 2024 Winter Action Plan material); the answer text is not reachable with the
  normal fetch tools, so the five values are now only in the leads section at the end (evidence S rows were removed from the table).

## Leads to confirm (press-only values taken out of causes.csv)

These were transcribed from press reports (evidence S). The table now accepts only values read at source, and Delhi has O stubble
values (Kulkarni, Biswal 2022-24, Govardhan, ARAI), so they are not in `causes.csv`. Each needs its primary source opened before it can come back.

- **Delhi, DSS stubble contribution to PM2.5, season means (Oct-Nov), Lok Sabha written answer of 10 March 2025:** 2020 13%, 2021 13%,
  2022 9%, 2023 11%, 2024 10.6% (WRF-Chem decision support system, MoES/IITM). Source of the values: Times of India, "Stubble burning
  contributed 10.6% to Delhi's PM2.5 levels in late 2024, Centre's data"
  (https://timesofindia.indiatimes.com/city/chandigarh/stubble-burning-contributed-10-6-to-delhis-pm2-5-levels-in-late-2024-centres-data/articleshow/118856480.cms).
  Not used: the answer text itself was not reachable (sansad.in, pib.gov.in, loksabhadocs.nic.in, eparlib.nic.in returned nothing relevant), and
  this is the only 2020-23 series, so confirming it would fill Delhi's stubble-by-year gap. Confirm by opening the Lok Sabha answer.
- **Delhi 31% and Kanpur 21%, post-monsoon (Oct-Nov, 2013-14), Nagar and Sharma 2022 (Urban Climate 41: 101084):** crop-residue burning's
  share of PM2.5 (via secondary particulate), from Hindustan Times, 19 Jan 2022
  (https://www.hindustantimes.com/india-news/crop-residue-burning-contributes-to-secondary-particulate-matter-study-101642571118252.html).
  Not used: press report of a paper whose abstract was not opened; Delhi has O stubble values. Kanpur has none, so confirming the 21% from the paper
  (ScienceDirect, doi 10.1016/j.uclim.2022.101084 area; check the table) would give Kanpur its only stubble row. Biswal et al. quote the Delhi value for
  October to December, the press for October-November.
