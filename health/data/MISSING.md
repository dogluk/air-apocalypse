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

## SRS crude death rates before 2020: not transcribed (death counts for early years)

Death counts are scaled to each state's SRS crude death rate for 2020-24 (death_reconciliation.csv), and the same factor is
used in every year. For years before 2020 that is too strong: a 2014 run has 5.7 deaths per 1,000 and a 2015 run 5.8, where the
SRS recorded 6.7 and 6.5 (SRS Statistical Report 2015, Table 13 and Statement 40, read 2026-11-11; India only, not in a data
file). Follow-up: transcribe Statement 40 from the SRS Statistical Reports for 2011 to 2019 (same catalog, censusindia.gov.in;
2015 is catalog 44371) and scale each year to its own rate. Care needed: Telangana appears from 2014, Ladakh from 2020, and
Dadra & Nagar Haveli and Daman & Diu are separate rows before 2020.

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
