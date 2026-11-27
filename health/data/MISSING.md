# Missing values

Values that could not be found at their source, with what was tried.

This file is the prose record. Each entry carries an `[OW-NNN]` tag: the id of its item in
[`health/open_work.toml`](../open_work.toml), the registry of open work (claim an item by that id; the generated list
is [`docs/open-work.md`](../../docs/open-work.md)). Close the item there when you close the gap here.

## Burnett et al. 2022 "Fusion" risk function: no all-cause or non-accidental parameters [OW-001]

Burnett RT, Spadaro JV, Garcia GR, Pope CA. Designing health impact functions to assess marginal changes in outdoor fine
particulate matter. Environ Res 2022; 204: 112245, https://doi.org/10.1016/j.envres.2021.112245.
Tried, 2026-11-10: the article page on ScienceDirect (open access; abstract and highlights read), PubMed 34687750, Europe PMC
(no PMC copy, no supplement listed). The abstract says the model is fitted "to data for the six specific causes of death
previously examined by the Global Burden of Disease program" (IHD, stroke, COPD, lung cancer, LRI, type 2 diabetes); Wan et al.
2025 (Environ Impact Assess Rev 107823), which used it, describes the same six causes with age-specific parameters for IHD and
stroke. Nothing found gives a Fusion fit to all-cause or non-accidental deaths, so no `fusion` curve is registered. A
cause-specific Fusion curve would need IHME cause-specific deaths and belongs with the local tier. The full text and its
parameter tables were not read (the PDF link did not return text to the tools used); if a later task needs Fusion, read them.

## GEMM supplementary appendix not read directly [OW-002]

The GEMM NCD+LRI parameters (curves_gemm_ncd_lri.csv) were meant to be read from the PNAS SI appendix. It could not be
fetched (PMC and Europe PMC: browser check; pnas.org: HTTP 403). They come instead from the authors' deposited calculator
(DataGEMM), whose India total reproduces PNAS Table 1; see sources.toml. Nothing is missing from the data, but the SI table
itself is unchecked: compare the twelve rows against SI Table S2 (or whichever table holds them) when it can be opened.

## AQLI coefficient: no published uncertainty [OW-003]

AQLI states 0.98 years per 10 µg/m³ PM2.5 with no interval (methodology page, India fact sheet 2025, aqli-update README).
`aqli.sample()` therefore returns the curve unchanged. The interval would have to come from Ebenstein et al. 2017 (PNAS 114:
10384-89, a PM10 estimate) through AQLI's PM10-to-PM2.5 conversion; neither was looked up for this task.

## City populations after 2011: no official source found [OW-004]

cities.csv holds the Census 2011 urban agglomerations and they are used in every year (every result that uses one says so).
Tried, 2026-11-11, briefly: the Technical Group's projections (population_age_state.csv) stop at states and union territories;
the next census's results are not published. No official Indian city or agglomeration figure after 2011 was confirmed. Leads not
checked this session: the United Nations' World Urbanization Prospects (agglomeration estimates, not an Indian official source),
and scaling each city by its state's projected urban growth since 2011 (Technical Group report, urban tables), which would be a
model, to be labelled as one.

## Cause shares for ages 25-29 [OW-005]

The SRS Causes of Death report gives one set of shares for ages 15-29 (cause_share_ncd_lri.csv), dominated by injuries among
the young, and the 25-29 band takes it. Against GBD 2015 (the GEMM authors' workbook) the tool's NCD+LRI deaths at 25-29 are
0.64 of GBD's. No SRS table splits 15-29 further; a split would need the Million Death Study or IHME data.

## GBD 2023 risk-curve information sheet (login) [OW-006]

`IHME_GBD_2023_AIR_POLLUTION_1990_2023_INFO_SHEET_Y2025M12D15.PDF` on GHDx record 594794 is behind IHME's login (tried 2026-11-11,
curl and Exa: sign-in page). The scale of the 2025-dated relative-risk files (ln RR) was settled from the GBD 2023 risk-factor
appendix, IHME's bopforge code and the files themselves (IHME_DOWNLOADS.md, status); the sheet would confirm it in IHME's words.

## GBD all-cause deaths [OW-007]

The Part B query took seven causes and all NCDs, not all causes, so the tool has no GBD all-cause death count and no `deaths=gbd`
source. Needed: GBD Results tool, Cause of death or injury, Deaths, Number, cause "All causes", the same 32 locations, ages and
years as Part B.

## GBD's attributable deaths for India [OW-008]

GBD 2023's 969,726 ambient-PM2.5 deaths for India in 2023 (OWID page of GBD 2023 Results) cannot be reproduced from the files
here: GBD splits one PM2.5 attributable fraction between ambient and household air by exposure, which needs GBD 2023's household
air pollution estimates (GHDx record 594794, 'Household Air Pollution Estimates [CSV]', not downloaded). Pandey et al. 2021's
GBD 2019 figure for India has the same dependency.

## Causes by city: studies and values not transcribed (Task 4, 2026-11-12)

- [OW-009] **Chennai (IIT Madras for TNPCB/GCC).** Only the interim report is public
  (https://chennaicorporation.gov.in/gcc/pdf/Intrim%20report%20SA,EI%20and%20CC,%20IITM.pdf, 29 pages, read in full 2026-11-12). It has
  the site list, a gridded emission inventory for five source groups, wind roses and AERMOD PM10 contour plots at four sites, and says
  the EC/OC, metals and ion analyses are 'in progress'. It prints no source-apportionment shares and no PM2.5 emission shares, so no
  Chennai study row is written (APnA and, where it covers Chennai, other tables remain). Needed: the final IIT Madras report.
- [OW-010] **Ahmedabad (GEMI, 5 Nov 2020, PRANA file Ahmedabad.pdf).** The only shares are of the emission inventory (Table 5.1.1, Fig. 5.1.1: road
  dust 36%, domestic 34%, construction and demolition 16%, point sources 14%, line sources 2%, of 53,873 kg/day), and the report calls the
  pollutant 'PM' with no size cut (its dispersion model is PM10 and its receptor section shows PM10 source contributions only). Not PM2.5,
  so left out (size_fraction must be PM2.5). Needed: a PM2.5 split from GEMI or the NCAP final report.
- [OW-011] **Ludhiana, Amritsar, Chandigarh: Biswal et al. 2025 regional stubble shares** (North Punjab 28/24/11%, Central Haryana 25/31/9%,
  Southwest Punjab 39/48/27% for 16 Oct-30 Nov 2022/23/24; doi 10.1039/d5ea00052a, Sec. 3.4). The rule is that a regional value goes to a city only
  if the paper's own map (Fig. 3, regions drawn as coloured lines over the CUPI-G sites) puts the city in the region. The figure is an
  image on the RSC site, which blocked every automated fetch (HTTP 403, Cloudflare), so no city could be placed and no row is written.
  Table S2 (the sites used per region) is in the supplement, also not reachable. Needed: open Fig. 3 in a browser and say which of these
  three cities (and Patiala, Jalandhar and similar if added) falls inside North Punjab, Southwest Punjab or Central Haryana.
- [OW-012] **Kulkarni et al. 2020 (ES&T 54(8): 4790)**: the 20% is read from the abstract on the publisher page; the ACS full text is paywalled, so
  the year simulated and the figure behind the number were not opened (year_sampled is blank).
- [OW-013] **Lok Sabha written answer of 10 March 2025 (DSS season means 2020-24).** The answer text was not found on sansad.in (search engines
  returned only the 9 Feb 2026 answer on a different question); the values were taken from the Times of India report of the answer and are
  now in the leads section at the end (not in the table).
- [OW-014] **Nagar and Sharma 2022 (Urban Climate 41: 101084)**: the ScienceDirect page gave no abstract to the tools used; Delhi 31% and Kanpur 21%
  are from a Hindustan Times report (19 Jan 2022); now in the leads section at the end (not in the table). Biswal et al. quote the Delhi value for 'October to December', the press
  for October-November.
- [OW-015] **Mumbai AERMOD column (Table 7.1 col. C)** and the other dispersion results of the Maharashtra, Hyderabad and Bengaluru reports are for
  'PM' of unstated size and are not transcribed.
- [OW-011] **Biswal et al. 2025 Fig. 3 needs a person to open it.** A person with a normal browser session should open the RSC article
  (doi 10.1039/d5ea00052a, Fig. 3, the region map) and say which of Ludhiana, Amritsar and Chandigarh lie inside North Punjab,
  Southwest Punjab, Central Haryana or Delhi-NCR; the 2022/2023/2024 values for those regions are already in Sec. 3.4 (see above) and can
  then be written as boundary = region rows.
- [OW-013] **Lok Sabha answer of 10 March 2025 (re-checked in the fix round).** Searches restricted to pib.gov.in, sansad.in, loksabhadocs.nic.in and
  eparlib.nic.in returned only unrelated PIB releases (Nov and Dec 2024 Winter Action Plan material); the answer text is not reachable with the
  normal fetch tools, so the five values are now only in the leads section at the end (evidence S rows were removed from the table).

## Leads to confirm (press-only values taken out of causes.csv)

These were transcribed from press reports (evidence S). The table now accepts only values read at source, and Delhi has O stubble
values (Kulkarni, Biswal 2022-24, Govardhan, ARAI), so they are not in `causes.csv`. Each needs its primary source opened before it can come back.

- [OW-013] **Delhi, DSS stubble contribution to PM2.5, season means (Oct-Nov), Lok Sabha written answer of 10 March 2025:** 2020 13%, 2021 13%,
  2022 9%, 2023 11%, 2024 10.6% (WRF-Chem decision support system, MoES/IITM). Source of the values: Times of India, "Stubble burning
  contributed 10.6% to Delhi's PM2.5 levels in late 2024, Centre's data"
  (https://timesofindia.indiatimes.com/city/chandigarh/stubble-burning-contributed-10-6-to-delhis-pm2-5-levels-in-late-2024-centres-data/articleshow/118856480.cms).
  Not used: the answer text itself was not reachable (sansad.in, pib.gov.in, loksabhadocs.nic.in, eparlib.nic.in returned nothing relevant), and
  this is the only 2020-23 series, so confirming it would fill Delhi's stubble-by-year gap. Confirm by opening the Lok Sabha answer.
- [OW-014] **Delhi 31% and Kanpur 21%, post-monsoon (Oct-Nov, 2013-14), Nagar and Sharma 2022 (Urban Climate 41: 101084):** crop-residue burning's
  share of PM2.5 (via secondary particulate), from Hindustan Times, 19 Jan 2022
  (https://www.hindustantimes.com/india-news/crop-residue-burning-contributes-to-secondary-particulate-matter-study-101642571118252.html).
  Not used: press report of a paper whose abstract was not opened; Delhi has O stubble values. Kanpur has none, so confirming the 21% from the paper
  (ScienceDirect, doi 10.1016/j.uclim.2022.101084 area; check the table) would give Kanpur its only stubble row. Biswal et al. quote the Delhi value for
  October to December, the press for October-November.

## Bengaluru air measures (interventions/library): numbers not found at source

Written while building the first nine Bengaluru measures (2026-11-27). Each measure file says where it leans on these gaps.

- [OW-016] **Buses' share of Bengaluru's transport PM2.5.** `electric_buses` borrows TERI's NCR result (electrifying all buses cuts transport PM2.5
  emissions 23%). CSTEP's 2022 Bengaluru inventory (Sec. 3.2.2.8, Figure 3-35, printed p. 43) lumps buses with trucks (heavy commercial
  vehicles, 56.5% of tailpipe PM together); the APnA Bengaluru report (UrbanEmissions.Info 2018, p. 14) says only that diesel vehicles
  (some 4-wheelers, taxis, buses, HDVs, LDVs) make more than 70%. Would settle it: a Bengaluru inventory by vehicle class with buses alone
  (BMTC fleet x km x emission factor), e.g. the APnA gridded inventory files on Zenodo, or an ICCT or CSTEP bus study.
- [OW-017] **What full door-to-door waste collection would cost Bengaluru.** `waste_collection_burning_ban` uses CSTEP's government cost for the
  policy, "<1" crore (Table 5.11, printed p. 93), which assumes the city's planned treatment capacity exists and leaves out the cost of
  collection reaching every household. Not tried this session: the GBA (formerly BBMP) budget's solid-waste line and the share of households
  without door-to-door collection. Either would give a real incremental cost. Since 2026-11-27 a `[cost.full]` range (Rs 12.1-114 crore a
  year) sits in the measure file for the labelled what-if `full_cost` only; its money figures are newspaper reports of officials (key S),
  so this gap stays open until a primary (GBA/BSWML budget book or tender estimates; the household coverage share) is read.
- [OW-018] **Compliance cost of construction-dust controls in Bengaluru.** `construction_dust_controls` uses CSTEP's government enforcement cost ("<1"
  crore), the funder's cost, which leaves out builders' spending. TERI gives NCR's (Table 34: water tankers, barriers, anti-smog guns, for
  54.04 sq km under construction in 2020), but Bengaluru's area under construction was not found (CSTEP used 235 RERA projects without giving
  their area, Sec. 3.2.2.5). Would settle it: the area under active construction in Bengaluru (RERA or building permissions). Since
  2026-11-27 a `[cost.full]` range (Rs 0.23-13.4 crore a year, from CSTEP's emission factors and three environmental-clearance budgets)
  sits in the measure file for the labelled what-if `full_cost` only; its high end rests on a floor-area ratio seen only in a snippet
  (key S), and no Karnataka clearance gives a dust-only line.
- [OW-019] **Lower ends of CSTEP's "<1 crore" costs.** `construction_dust_controls` and `waste_collection_burning_ban` take Rs 0.1 crore a year as the
  low end, a judgement; CSTEP gives only the upper bound.
- [OW-020] **Not used: Vital Strategies (2024), Accelerating the health benefits of scaling clean household energy in India.** It costs LPG refill
  subsidies per DALY, which is household exposure, the second pass (design spec, "Order" 6); its cost per household was not read (the PDF
  was not opened this session). `lpg_refill_subsidy` uses CSTEP's Bengaluru figures instead.

## Bengaluru exposure measures and the smog tower (interventions/library): numbers not found at source

Written while building `home_purifiers`, `school_purifiers`, `n95_winter` and `smog_tower` (2026-11-27).

- [OW-021] **IIT Bombay's final report on the Connaught Place smog tower (30 September 2023).** `smog_tower` takes its cut (12-18% of PM2.5,
  500 m radius) from the Indian Express (26 Oct 2023) and Hindustan Times (10 Nov 2023) accounts of the report, so the cut is evidence S.
  Not reached: the report went to the DPCC and, per HT, was to go to the Supreme Court; no public copy was found. Would settle it: the
  report itself (DPCC, or the Supreme Court record), especially reductions by distance and direction and the yearly operating cost.
- [OW-022] **Bengaluru's own school enrolment and classrooms.** `school_purifiers` uses Karnataka's UDISE+ 2023-24 enrolment over Karnataka's projected
  2023 population (17.6%) for the share covered, and class sizes of 27-50 from the state pupil-teacher ratio and Delhi KV classes. OpenCity
  publishes school-by-school UDISE+ files for Bengaluru Urban North and South (https://data.opencity.in/dataset/bengaluru-urban-udise-2024-25,
  enrolment and `total_class_rooms` columns), but the site's bot check blocked every download tried. Would settle it: those files, summed.
- [OW-023] **How many people would wear a free N95 every time they go out.** `n95_winter` has no wear or adherence figure; it is folded into the
  odds as a judgement. Would settle it: an Indian or Chinese study of sustained mask wear among people given masks free during pollution
  episodes (wear diaries or sensors), not one-off surveys.
- [OW-024] **Children's share of air-pollution deaths, for school measures.** Closed by commit 5a39e2d: an exposure measure can name the
  ages it covers (`[exposure] ages`), and `school_purifiers` (ages 5-19) is now scored with that group's own death rates and costed
  for that group alone. Still open: `n95_winter` (outdoor workers) names no age group, so it uses all-age death rates. Would settle
  it: an age split of Bengaluru's outdoor workers (PLFS tables by age and occupation), read at source.

## Regional measures: published source-receptor results not usable (2026-11-27)

The receptor tables (data/receptor_*.csv) should come from a published source-receptor result at district level first (spec part 3).
Neither lead gives one, so both tables are built from McDuffie et al. 2021's gridded sector fractions instead (scripts/build_receptor.py),
flagged "sector from every origin, not only the named states".

- [OW-025] **Stubble: Lan et al. 2022, Nat Commun 13:6537, doi 10.1038/s41467-022-34093-z.** Read in full (Europe PMC, PMC9663555, 2026-11-27).
  Its adjoint runs have one receptor, India-wide population-weighted PM2.5 exposure ("the cost function is the India-wide
  population-weighted exposure to PM2.5", Methods), so its district results are by SOURCE district (Supplementary Data 2-4: contributions
  by state and season to national exposure, deaths and cost), not the change in each RECEIVING district. Its 23 forward runs with and
  without residue burning (0.5° x 0.625°) are shown only as maps. The Data availability statement lists inputs only (GFED, IER curves,
  GPW population). Would settle it: the forward runs' gridded difference fields from the authors, averaged to districts.
- [OW-026] **Coal power plants: Cropper et al. 2021, PNAS, "The mortality impacts of current and planned coal-fired power plants in India", doi 10.1073/pnas.2017936118** (the plant-level work behind DCP3
  ch. 13, https://www.ncbi.nlm.nih.gov/books/NBK525204/). Not read: PNAS returned 403, Europe PMC's full text (PMC7865184) returned a
  server error twice, and NCBI Bookshelf served a bot check. Whether it or its data release gives the PM2.5 change by receiving
  district is not known. Would settle it: the paper's SI and data release, read.
  **Update (2026-11-27):** the paper and its SI Appendix were read from co-author Guttikunda's site (urbanemissions.info).
  The SI gives the PM2.5 the 2018 plants add by STATE (Table S2), not by district; that is now
  data/receptor_power_cropper2021.csv (each district takes its state's figure) and fgd_scrubbers uses it. The gridded results are in
  the data release, openICPSR project 130404 (doi 10.3886/E130404V1, cited in the paper's Data Availability), which served a
  Cloudflare check to scripts and to a headless browser (HTTP 403); openICPSR downloads also need a free login. Would settle it:
  download that release by hand and average its CAMx difference field (0.25°) to districts with scripts/build_receptor.py's pixels.
- [OW-027] **A power-only gridded field.** McDuffie's ENEcoal (used for receptor_energy_coal.csv) is "Energy Production (coal combustion only)",
  which the README says also holds fuel production and transformation, so it is wider than power plants. A power-plant-only zero-out
  run (GBD MAPS India stays local-only here) would replace it.
- [OW-025] **Lan et al. 2022's supplementary files (2026-11-27).** All twelve were downloaded from the Nature page and opened
  (Supplementary Tables 1-11 as xlsx, the SI PDF). Every exposure table has the one India-wide receptor: Table 2 and 3 by source state,
  Table 9 the source-state contributions to India's exposure for 2015-19 (Punjab 4.0 of 7.7 µg/m³ in 2019). None gives a receiving
  district. Table 9's source-state shares are what the stubble measures use to take Punjab's (and Haryana's) part of the McDuffie
  table, which counts all crop burning; that share is India-wide, so it is too small near Punjab and too large far away.
- [OW-025] **The stubble table reaches Bengaluru.** Because receptor_stubble.csv counts crop fires from every origin, Bengaluru gets about
  -0.3 µg/m³ from all burning, and a Punjab measure is credited with a share of it (test_library's
  test_stubble_does_not_reach_bengaluru is an expected failure until this is fixed). Would settle it: a source-receptor result for
  Punjab and Haryana's fires alone by receiving district (Lan et al.'s forward runs; or a GEOS-Chem or WRF-Chem tagged run such as
  Kulkarni et al. 2020, ES&T 54: 4790, paywalled).
- [OW-028] **Happy Seeder: Shyamsundar P, Springer NP et al. 2019, Science 365: 536, doi 10.1126/science.aaw4085.** The UC eScholarship copy
  returned 403 to scripts and an empty page to a fetcher; Science is paywalled. Wanted: its costs per hectare of the Happy Seeder and
  other options against burning. happy_seeder_subsidy is built instead from the Government of Punjab's 2023 action plan (spend and
  Happy-Seeder area), and the share of that area that would otherwise have burned is a judgement (a quarter to three quarters); no
  source read here measures what the machinery subsidy did to burning. Would settle it: an evaluation of the CRM scheme's effect on
  fires (for example district fire counts against machines delivered).

## Industry, brick kilns and cloud seeding (interventions/library, 2026-11-27): leads not settled

- [OW-029] **Surat emissions market: how many of the 906 plants it covers now.** Greenstone et al. 2025 (QJE) trialled the market on 162 of
  318 plants (2019-21); `emissions_market` scores putting all 906 solid-fuel plants in (the paper's Table VI scenario) against
  APnA's 2018 shares, which predate the market. If GPCB has already brought many more plants in, part of this benefit is already
  happening. Also not found: the regulator's own cost of running the market (staff, the trading platform), so the cost is flagged
  partial. Would settle it: GPCB's scheme documents or annual report on the Surat market (number of plants, budget).
- [OW-030] **Patna's brick kilns: how many are already zig-zag.** APnA (2017) counts 300 kilns in Patna's airshed and gives them 9.3% of
  PM2.5 for base year 2015. Kilns converted since then shrink what `zigzag_kilns` can still cut; no count of converted kilns in
  or around Patna was found. Would settle it: the Bihar State Pollution Control Board's kiln register, or a satellite count of
  zig-zag against fixed-chimney kilns (the kiln shapes are visible in imagery).
- [OW-031] **Brooks N et al. 2025, Science, doi 10.1126/science.adr7394** (a trial of cheaper changes to how brick kilns are fired, in
  Bangladesh). Not read for this task. A lead for a separate, practices-only measure, which may cost less than conversion.
- [OW-032] **Amritsar: industry's PM2.5 by fuel, and what UNDP's cost includes.** `industrial_fuel_switch` takes TERI's 99% (Delhi-NCR, the
  industries that switch) as the upper cut; the lower cut, 50%, is a judgement because no split of Amritsar's industrial PM2.5
  into fuel smoke and process dust was found. UNDP 2025 (Table 2) gives INR 248.6 million for Amritsar's industries but does not
  say whether the higher gas bill is in it; for Delhi-NCR TERI found the fuel bill is most of the cost. Would settle it: UNDP's
  literature-and-cost review ("available upon request" in the report), or the Punjab Pollution Control Board's count of
  solid-fuel units in Amritsar with their fuel use.
- [OW-033] **IIT Kanpur's report on the October 2025 Delhi cloud-seeding trials.** Only press accounts were read (Hindustan Times, India
  Today, Indian Express, 28-30 Oct 2025), so every number in `winter_cloud_seeding` is key S: the 6-10% fall in PM2.5 the institute
  claimed (which the Indian Express found began before the seeding), clouds one day in ten, and Rs 20-30 crore for a winter. Would
  settle it: the trial report submitted to the Delhi Environment Department, or the parliamentary answers on its cost.

## Measures kept to one city: the per-city source that would widen each (2026-11-27)

A measure goes beyond its one city only when none of its numbers is that city's: the cut a fraction of a cause's share (or an
exposure's hours and cut) read from a source not about the city alone, the cost per person, household or unit at a price not tied
to the city's contract or budget, and no count or ratio for the city or its state. Widened: `home_purifiers` and
`old_vehicle_retirement` (cities = "all"). General variant: `school_purifiers_india` (India's UDISE+ figures, for the 49 cities
other than Bengaluru). Every other city measure stays in its city, with a `city-specific:` line in its notes naming the number
that blocks it. What would widen each (leads, not checked):

- [OW-036] **`dg_set_replacement` (Bengaluru): installed diesel generator capacity (kVA) per city.** The cut (CPCB's 70% device standard)
  and the price per kVA (Haryana's 2026 benchmark) transfer; only the 2,801,180 kVA is Bengaluru's (CSTEP 2022). Would widen it:
  each city's DG-set capacity from a city emission inventory or the state board's consent register, one file per city
  (`dg_set_replacement_<city>.toml`).
- [OW-037] **`zigzag_kilns` (Patna): brick kilns per city airshed.** The cut (70-75%) and the cost and saving per kiln transfer; only the
  300 kilns are Patna's (APnA 2017). Would widen it: kiln counts in the other APnA city reports, or a satellite kiln count, one
  file per city; and how many are already zig-zag (lead above).
- [OW-038] **`emissions_market` (Surat): solid-fuel industrial plants per city.** The cost per plant (US$5,000 a year for monitors)
  transfers; the 906 plants are Surat's (GPCB consent records). Would widen it: each state board's consent records of solid-fuel
  plants per city. The 20-30% cut would then be borrowed from the Surat trial everywhere else.
- [OW-038] **`industrial_fuel_switch` (Amritsar): a cost of switching each city's industry to gas.** UNDP's INR 248.6 million is one total
  for Amritsar. Would widen it: a cost per plant (or per tonne of fuel) of the switch, times each city's count of solid- and
  liquid-fuel plants; TERI 2021 Table 26 gives NCR's totals only.
- [OW-039] **`electric_buses` (Bengaluru): each city's bus fleet, the bus share of its transport PM2.5, and a price per bus not from
  CSTEP's Bengaluru plan.** The NCR effect per share of buses electrified (TERI 2021) could transfer; 2,000 of BMTC's 6,400 buses
  is Bengaluru's. Would widen it: fleet counts of each city's bus undertaking and a national e-bus price (central tenders).
- [OW-039] **`electric_two_three_wheelers` (Bengaluru): the two- and three-wheeler share of each city's transport PM, and each city's
  fleet.** The PM E-DRIVE subsidy per vehicle transfers. Would widen it: a vehicle-type split of each city's transport emissions
  (city inventories) and registrations per city (VAHAN).
- [OW-040] **`road_paving`, `road_vacuum_sweeping`, `construction_dust_controls` (Bengaluru): the split of each city's dust into road dust
  and construction, and each city's main-road length or contract.** The causes table has one `dust` share; each cut is TERI's NCR
  effect on one part of it, split with CSTEP's Bengaluru inventory. Would widen them: a city inventory that splits dust, plus each
  city's arterial road length (paving; TERI's prices per square metre transfer), sweeping contract, or enforcement budget.
- [OW-041] **`lpg_refill_subsidy`, `waste_collection_burning_ban` (Bengaluru): a cut and cost not from CSTEP's Bengaluru scenarios.** Both
  rest on CSTEP's reduction scenarios and BBMP or Karnataka budgets. Would widen them: an evaluation of LPG refill subsidies'
  effect on wood burning with a cost per household, and wood-cooking households per city (Census 2011 houselisting tables, fuel
  used for cooking); for waste burning, a per-household or per-tonne cost of full collection and an effect not tied to one plan.
- [OW-042] **`n95_winter` (Bengaluru): each city's work participation and dirtiest months.** The share covered is urban Bangalore
  district's work participation (Census 2011), and the months are Bengaluru's four dirtiest; cut, hours and mask price transfer.
  Would widen it: each district's urban work participation (Census 2011 Primary Census Abstract) and each city's own monthly
  shape (airhealth.months), one file per city.
- [OW-042] **`smog_tower` (Bengaluru): population density around the site.** Covered and the cost per person are both computed from the
  people within 500 m at urban Bangalore's 2011 density (life-years per crore hardly depends on it). Would widen it: each city's
  urban density (Census 2011 district handbooks), one file per city.
- [OW-042] **`school_purifiers` (Bengaluru) and `school_purifiers_india`: each city's own share of children in school and pupil-teacher
  ratio.** The general variant uses India's (70.4%; 25). UDISE+ 2023-24 Tables 2.2 and 5.1 give both per state, and the UDISE+
  district files per district; a city file with its own figures would replace the general one for that city.
- **`winter_cloud_seeding` (Delhi):** nothing in it was measured outside Delhi's October 2025 trials; it stays in Delhi.

## Licences: files whose licence is not settled (audit, 2026-11-27)

Checked: every file in `health/data/` has a `licence` line in `sources.toml` (36 entries, one per file; the one entry
with no file, `mcduffie2021_supp_data_1.xlsx`, is the McDuffie download the build script keeps outside the repo). The files
under `diwali/data/` are covered by the licence table in `diwali/README.md` (CPCB compilation ODbL; ERA5 CC BY 4.0; FIRMS
public). `cities/` holds no data file: the Bengaluru page is generated, its numbers come from the data above, and its fonts
are the OFL-licensed ones in `fonts/`. IHME files are never committed; only results derived from them appear, and none is
in `health/data/`. APnA and McDuffie are CC BY 4.0 (`causes.csv`, `apna_source_apportionment.csv`, the two receptor tables).

Not settled:

- [OW-034] `diwali/data/trends/*.json` (392 cached Google Trends responses, `diwali/pull_trends.py`). Wanted: the terms under which
  Google Trends data may be redistributed. Tried: nothing beyond the repository's own notes, which give no licence;
  `lit/reading.md` says only that the endpoint used is internal and the official API is in alpha. Would settle it: Google's
  Trends terms of service or a written answer from Google. Until then the cached JSON is a redistribution of unlicensed
  data; the derived `trend_cityyear.csv` (effect sizes, no raw series) is the safer thing to keep.
- [OW-035] `health/charts/*.png` (seven chart images made by the model from the data above). No licence line of their own. The
  inputs are CC BY / ODbL; the repository's MIT/ODbL line in the README is the only statement covering them.
- Several `health/data` entries record "no licence stated" for Government of India documents (SRS, projections, census
  tables) and rely on reproducing facts with attribution. That is stated, not unclear, but it is not a licence grant.
