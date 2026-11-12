# What pollutes Indian cities outside Delhi

*2026-11-11*

**Key.** **[O]** opened and read at source (PDF, CSV or XLSX downloaded and read, or page fetched).
**[S]** seen only in a search snippet, search summary or news report. **[R]** recalled from memory.
Shares are of **ambient PM2.5 concentration** unless the row says *emissions*. The two are
different things and Indian reports mix them freely (see section 3).

**The short version.**

1. There is already one open, machine-readable "causes by city" table: UrbanEmissions' APnA
   source split for **49 city airsheds** (Zenodo, CC-BY 4.0, a 3.7 kB CSV), including a column
   for **PM2.5 from outside the airshed: 13% (Chennai) to 53% (Amritsar)**. One model, one team,
   base years 2015/2018. [O]
2. The official NCAP studies are now mostly done (107 of 130 cities by one count, 90 by
   another) [S], and **about 60 full reports sit as PDFs on CPCB's PRANA portal at a guessable
   URL** [O]. None ships a table. No licence is stated, and the reports use different methods and
   categories. They are the raw material for a dataset, not a dataset.
3. Methods disagree by **factors, not points**. Kanpur's household share is 34% in the APnA
   model, 25% in the global model, and 3% biomass (winter) in IIT Kanpur's filter study. Lucknow's
   share from outside the city is 30% (APnA) or 81% (TERI). [O]
4. Coarse global models (McDuffie 2021, GBD MAPS 2018) put road transport at **3–8%** in every
   Indian city. City-scale models and filter studies put it at **10–40%**. The global ones are open and cover every
   state; the city ones are local but sparse. [O]
5. Across the Indo-Gangetic Plain, a large share of a city's PM2.5 comes from outside it
   (Lucknow 81%, Kolkata 43–46% from beyond a ~regional domain) [O], so a city-level dataset
   needs an "outside" column or it will mislead.

---

## 1. City table

APnA = UrbanEmissions WRF-CAMx zero-out runs, base 2015 (2017 batch) or 2018 (2019 batch), annual
average, categories A transport, B residential, C industry, D dust, E waste burning, F DG sets,
G bricks, H sea salt, I outside. All APnA numbers below are from the Zenodo CSV
([6919069](https://zenodo.org/records/6919069)) unless marked. McDuffie = GEOS-Chem sensitivity runs
for 2017, from the paper's Supplementary Data 1. PRANA = `https://prana.cpcb.gov.in/ncapDashboard/downloadEmissionFiles/<City>.pdf`.

| City | Studies (who, year, method) | Headline PM2.5 shares (season) | From outside the city | Data open? | Key |
|---|---|---|---|---|---|
| **Mumbai** | NEERI + IIT Bombay for MPCB, final Dec 2023: PMF on filters from 6 sites, **one campaign, May–Jun 2019**; AERMOD on an inventory. APnA 2019. SAFAR inventory 2019-20. NEERI 2010 (CPCB six-city). | **PMF:** marine 26, secondary 22, vehicles 16, road/windblown dust 13, industry/fossil fuel 12, biomass 11 (pre-monsoon only). **APnA:** transport 16.4, industry 15.0, dust 12.6, sea salt 12.1, residential 3.2. **McDuffie:** road 4.3, residential biofuel 18.9. *Emissions* (not concentration): road dust 71% of PM load (NEERI interim) [S]; transport 31%, industry 31% of PM2.5 emissions (SAFAR) [S]. The NEERI report itself notes PMF gives industry 12–20% while its AERMOD run gives <1%, because unregistered small industry ("bhattis") is missing from the inventory. | APnA 32.6% | NEERI: PDF on [MPCB](https://mpcb.gov.in/sites/default/files/inline-files/Final_SA%20%26%20EI%20Report_Mumbai.pdf) and PRANA, no licence. APnA: CSV, CC-BY. | [O] except as marked |
| **Pune** | NEERI + IIT Bombay for MPCB, Jul 2024 (PMF + AERMOD). ARAI 2010 (CPCB; CMB on 7 days per site). APnA 2017. SAFAR 2019-20 inventory (400 m). | **PMF:** industrial 22, fossil fuel combustion 25 [O]. **APnA:** transport 24.0, dust 23.4, industry 9.8, waste 6.4, residential 5.8 [O]. **McDuffie:** road 4.5, residential biofuel 19.4 [O]. SAFAR *emissions*: transport ~40% [S]. ARAI 2010: secondary, vehicles and solid fuel dominate PM2.5, no reliable shares [O]. | APnA 24.7% | PDF on MPCB and PRANA; APnA CSV. SAFAR gridded inventory: no download found. | [O]/[S] |
| **Kolkata** | TERI for WBPCB, 2025: CMB 8.2 on filters **and** WRF-CMAQ zero-out, 2023. NEERI 2019 (inventory + receptor). SAFAR. Bose Institute (PMF). APnA 2019. | **TERI CMB (annual):** cooking (coal/biomass, homes + eateries) 29, industry 21, vehicles 20 [O]. **TERI CMAQ:** road dust 16, vehicles 15–18, industry 17, residential 9 (summer) → 18 (winter) [S, via press; the bar chart in the report agrees]. Vehicle share in other studies: NEERI 23.5, SAFAR 32, Bose 18–22 [S]; APnA 13.5 [O]; McDuffie road 3.4 [O]. Waste burning: NEERI 6.7, Bose 31–41, SAFAR 16 [S]; APnA 12.8 [O]. | **TERI CMAQ:** sources inside the city (KMC) give 40% (summer) / 33% (winter); **46% / 43% comes from beyond the ~regional study domain** [O]. APnA 19% [O]. IIT Delhi preliminary: IGP states up to 55% in winter [S]. | TERI and NEERI: PDFs on [WBPCB](https://www.wbpcb.gov.in/source-apportionment,-emission-inventory-and-carrying-capacity-study-). Kolkata is not on PRANA under that name. | [O]/[S] |
| **Bengaluru** | CSTEP for KSPCB, Feb 2022: CMB on 13 sites, 3 seasons. Guttikunda 2019 (WRF-CAMx). APnA 2017. TERI-ARAI 2010 (CPCB). | **CSTEP CMB (annual):** transport 40, soil dust 25, secondary sulphate+nitrate 16, fuel oil 6, everything else (wood, construction, DG, coal) ~5. **APnA:** transport 26.5, dust 23.0, waste 16.1, residential 9.8. **Guttikunda 2019:** vehicle exhaust 28, dust 23, waste 14. | APnA 15.6%; Guttikunda 2019: 17.2% | CSTEP PDF on PRANA (`Bangalore.pdf`) plus a one-page summary; APnA CSV. | [O] |
| **Chennai** | IIT Madras for TNPCB/GCC under NCAP: only an **interim** report is public. APnA 2017. CPCB six-city (IIT Madras, ~2010). | **APnA:** transport 24.5, dust 23.5, waste 15.5, industry 12.8, residential 3.6, outside 13.3. No final NCAP shares found. | APnA 13.3% (lowest of 49) | APnA only. GCC page links the [interim report](https://chennaicorporation.gov.in/gcc/pdf/Intrim%20report%20SA,EI%20and%20CC,%20IITM.pdf). | [O] |
| **Hyderabad** | IIT Kanpur for TSPCB: PMF on filters, **winter 2021-22 and summer 2022**; AERMOD. APnA 2019. | **IITK, winter PM2.5:** vehicles 29.5, secondary inorganic 21.0, soil/road dust 20.1, MSW burning 8.7, biomass 7.0, construction 5.7, industry 4.7, coal/fly ash 3.3. **Summer:** dust 31.5, biomass 15.8, vehicles 14.0, SIA 12.3, construction 11.8. **APnA:** dust 18.6, transport 16.5, industry 14.8, waste 12.9. **McDuffie:** road 5.0, AFCID dust 16.9. | APnA 25.3% | PDF on PRANA. | [O] |
| **Lucknow** | TERI for UPPCB, 2022: inventory (2019) + WRF-CMAQ zero-out with geographic tagging. IIT Kanpur 2014 inventory. APnA 2019. CSIR-IITR PMF (one residential area, winter 2021-22). | **TERI CMAQ (annual):** residential 23, road dust 22, international 14, transport 12, industry 7, open agri burning 7 (19 post-monsoon), power 6, bricks 4. Secondary particles 42–70% by season. **APnA:** residential 24.3, dust 13.9, transport 13.0. **IITR PMF:** vehicle exhaust 21, road dust 15, cooking fuel 12, waste 12 [S]. | **TERI: 19% from inside city boundary, 81% from outside** (8% rest of district, 2–11% rest of UP, up to 64% rest of India post-monsoon, 11–20% international) [O]. APnA 30.1% [O]. | TERI PDF on [teriin.org](https://www.teriin.org/sites/default/files/files/Estimation_of_Contribution_of_Sources_to_Ambient_PM2.5_Concentration_in_Lucknow_City_&_District.pdf), all rights reserved. Not on PRANA under "Lucknow". | [O] except IITR |
| **Kanpur** | IIT Kanpur for UPPCB: PMF on filters, **winter 2018-19 and summer 2019**; AERMOD. APnA 2017. | **IITK, winter PM2.5:** vehicles+DG 29.9, SIA 18.7, SOA 17.9, coal/fly ash 3.5 (Table 4.8; the 15-16% in the executive summary is Agra's sentence copied), soil/road dust 11.7, MSW 8.8, industry 5.5, **biomass 2.9**. **Summer:** dust 21.9, SOA 15.5, biomass 14.8, construction 11.9. **APnA:** **residential 33.8**, transport 13.7. **McDuffie:** **residential biofuel 24.5**, road 6.0. | APnA 22.5%. World Bank: Kanpur among cities with >50% from outside [S]. | PDF on PRANA and [IITK](https://home.iitk.ac.in/~mukesh/Publications/2022_IIT%20Kanpur_UPPCB_Final-Report-Kanpur-Source%20Apportionment%20and%20Emission%20Inventory.pdf), © IITK + UPPCB; one-page summary on PRANA. | [O] |
| **Varanasi** | IIT Kanpur for UPPCB: CMB, **winter 2020-21, summer 2021**. APnA 2017. | **IITK winter PM2.5:** biomass 29.8, SIA 20.1, soil/road dust 17.7, coal/fly ash 15.5, vehicles 14.1. **Summer:** dust 29, biomass 28.1, vehicles 17.6, coal/fly ash 13. **APnA** (paper table, not in the CSV): residential 20.9, waste 16.2, transport 13.5. | APnA 31.2% [S] | PDF on PRANA; one-page summary. Varanasi is **missing from the APnA CSV** (49 rows, not 50). | [O] / APnA [S] |
| **Patna** | TERI for BSPCB, 2021 (Bloomberg-funded): CMB + PMF, **summer 2019, winter 2019-20**, 7 sites. CCAAP 2019 (dispersion). APnA 2017. World Bank 2022 (GAINS). | **TERI winter PM2.5:** secondary 38 (29–48 by site), biomass 21, transport 18; industry 10–27 across seasons; summer led by dust (29). **CCAAP 2019 dispersion:** domestic 22, transport 19, dust 15, industry 14, bricks 14, waste 11, DG 5. **APnA:** transport 14.8, residential 14.6, waste 12.9, dust 12.1, industry 11.2, **bricks 9.3**. | APnA 19.2% [O]; World Bank: ~25% from a neighbouring state [S]. | TERI PDF on [BSPCB](https://bspcb.bihar.gov.in/Patna-SA%20Study.pdf); not on PRANA under "Patna". | [O] / WB [S] |
| **Agra** | IIT Kanpur for UPPCB, Dec 2021: receptor model, winter 2018-19, summer 2019. APnA 2017. | **IITK winter PM2.5** (one-page summary, pie chart): vehicles 23.4, SIA 18.8, coal/fly ash 15.5, MSW 14.8, soil/road dust 12.6, biomass 7.8, industry 6.3. **Summer:** dust 34.5. Inventory: road dust 9,227 of 13,596 kg/day PM2.5 *emissions*. **APnA:** residential 23.8, transport 13.9, waste 12.4. | APnA 35.9% | PDF + one-page summary on PRANA. | [O] |
| **Ahmedabad** | GEMI (Gujarat govt institute): receptor models + inventory; reports PM as a lump, not PM2.5 (flagged by SFC 2026). SAFAR 2016-17 inventory. APnA 2019. | GEMI inventory, *PM emissions*: road dust 36, domestic 34, C&D 16, point sources 14 [O]. SAFAR *PM2.5 emissions*: transport 36, industry+power 33, windblown dust 21, domestic 7 [S, via NRDC copy]. **APnA:** dust 17.7, transport 14.9, industry 12.4, waste 8.4, residential 6.6. **McDuffie:** road 6.0, AFCID dust 14.7. | APnA 32.8% | GEMI PDF on PRANA; SAFAR report PDF on NRDC site. | [O]/[S] |
| **Surat** | TERI 2021 (Bloomberg): CMB on filters **and** WRF-CMAQ, 2019 inventory. APnA 2019. | **Receptor vs CMAQ, winter PM2.5:** industry/power 46 vs 42, transport 23 vs 15, residential 12 vs 17, dust 9 vs 11. **Summer:** industry 39 vs 35. Receptor alone, winter: secondary 32, industry 27. **APnA:** industry 31.4, transport 16.4, dust 10.3, waste 9.8. | **TERI CMAQ: "international" sources 55% in summer, 9% in winter** (westerlies) [O]. APnA 21.2%. | PDF on PRANA. | [O] |
| **~45 other NCAP cities** | Full reports on PRANA (IIT Kanpur, IIT Delhi, IIT Tirupati, ARAI, NEERI-IITB and others): Prayagraj, Firozabad, Jhansi, Gwalior, Bhopal, Jodhpur, Udaipur, Alwar, Amritsar, Patiala, Khanna, Gobindgarh, Dera Bassi, Naya Nangal, Pathankot, Baddi, Damtal, Kala Amb, Nalagarh, Paonta Sahib, Parwanoo, Sunder Nagar, Angul, Cuttack, Talcher, Rourkela, Kalinga Nagar, Asansol, Durgapur, Barrackpore, Haldia, Nagaon, Nalbari, Sibsagar, Silchar, Byrnihat, Nashik, Navi Mumbai, Aurangabad, Kolhapur, Solapur, Amravati, Rajkot, Vijayawada, Gulburga, Ghaziabad, Anpara, Gajraula, Khurja, Raebareli. | Not extracted. APnA covers 17 of them (Prayagraj, Gwalior, Bhopal, Jodhpur, Amritsar, Asansol-Durgapur, Nashik, Aurangabad, Rajkot, Vijayawada, …). | APnA column I | PDFs, no licence. | [O] that the files exist |

**How the PRANA count was made.** The portal's JavaScript builds the report link as
`downloadEmissionFiles/<City>.pdf` (full report) and `downloadSAEI/<City>.pdf` (a one-page summary:
an inventory table plus seasonal pie charts, as images). Probing ~140 name spellings for the 130
NCAP cities found **60 distinct cities with a full report and 15 with a one-page summary** [O]. The
true number is higher: Kolkata, Lucknow, Patna, Chennai, Jaipur, Nagpur and others returned 404
under the obvious spelling, and the portal's city list comes from an API that wasn't queried.
Khurja has a file although the Indian Express (5 Nov 2026) lists it as pending [S]; it may be an
interim report. Status counts disagree: CPCB review says 107 of 130 done [S]; PRANA as of 30 Dec
2025 says 44 completed, 46 completed and peer-reviewed, 40 in progress (SFC brief) [O]; CREA
2026 says 90 [O]. In Jan 2025 CREA found only **17 cities had published detailed reports** [O];
that has clearly changed.

---

## 2. National and state datasets

| Dataset | What it gives | Spatial unit | Downloadable? | Key |
|---|---|---|---|---|
| **APnA city program** (UrbanEmissions, 2017/2019) | PM2.5 concentration shares by 8 sectors **plus outside-airshed share** | 49 city airsheds (50 claimed; Varanasi missing from the CSV) | **Yes.** [Zenodo 6919069](https://zenodo.org/records/6919069), CSV, CC-BY 4.0. Also 1-km gridded city inventories for 50 airsheds (2018 and 2030, `.rar`, "open-use", no formal licence) and an all-India 0.25° inventory for 2024 by sector (8 CSVs) on the [UEinfo repository](https://urbanemissions.info/india-air-quality/gridded-emission-inventories-for-india/). A revision for all NCAP cities is "underway". | [O] |
| **McDuffie et al. 2021** (GBD-MAPS-Global, *Nat Commun*) | Fractional contribution of 20 sectors and fuels to population-weighted PM2.5, 2017 | 204 countries, and **17 Indian cities** in Supplementary Data 1 (Jaipur, Ahmedabad, Kanpur, Kolkata, Mumbai, Pune, Hyderabad, Belgaum, Coimbatore, Hindupur, Jalna, Kozhikode, Malegaon, Parbhani, Singrauli, Sitapur, Vijayawada). **No Indian states.** | **Yes.** Supplementary XLSX from the [article](https://www.nature.com/articles/s41467-021-23853-y) (open access). Gridded 0.01° fractions on [Zenodo 4739100](https://zenodo.org/records/4739100) (CC-BY 4.0, ~126 GB of CSVs, so clip to India). Scripts on [GitHub](https://github.com/emcduffie/GBD-MAPS-Global). India total: residential biofuel 22.5%, AFCID dust 11.5, agriculture (non-combustion) 9.4, industrial coal 8.2, energy coal 7.0, road 5.7, waste 4.2. | [O] |
| **GBD MAPS India** (HEI Special Report 21, 2018) | Population-weighted PM2.5 share by sector, 2015, plus 2050 scenarios | **All states, split all / rural / urban** (Appendix C, Table C.1) | PDF table only, © HEI ([App C](https://www.healtheffects.org/system/files/GBDMAPS-India-SR21-App-C_0.pdf)). Extractable by hand or with a parser. National: residential biomass 23.9, total dust 38.8 (anthropogenic 8.9), coal 15.7, open burning 5.5, transport 2.1, bricks 2.2. Delhi open burning 18.8, Punjab 17.2, Haryana 17.9; Bihar residential biomass 37.4; Chhattisgarh coal 31.1; Gujarat dust 69.7. | [O] |
| **World Bank, *Striving for Clean Air*** (2022, GAINS model) | Sector of origin and **place of origin** (same city / same state / other states / other countries) of population-weighted PM2.5 | IGP cities and South Asian states | **No data release found.** Shares are in figures 2.6–2.11. Headline: in most South Asian cities more than half of PM2.5 comes from outside; Patna ~25% from a neighbouring state; Punjab (India) ~30% from Pakistani Punjab. Defines six airsheds. | [S] |
| **Kumar, Dey et al. 2025** (*ACS Earth Space Chem*, IIT Delhi + TERI) | Sector shares of primary and secondary PM2.5 per regional airshed and **local airsheds of non-attainment cities**, WRF-CMAQ, NCAP baseline year | 9–11 regional airsheds | Supporting information paywalled when checked. | [S] |
| **SAFAR inventories** (IITM) | Gridded 400 m–1.67 km *emission* inventories | Delhi, Mumbai, Pune, Ahmedabad | Reports as PDFs; no gridded download found. | [S] |
| **WHO source apportionment database** (Karagulian et al. 2015) | Receptor-model records for cities worldwide, 6 categories | Includes Indian studies up to ~2014 | Was on the WHO site; not checked. | [S] |

GitHub (`gh search repos` with six queries) turned up **nothing** for Indian city apportionment or
inventories beyond McDuffie's scripts. [O]

---

## 3. How much the methods disagree

**Three methods, three different questions.**

- **Receptor models (CMB, PMF) on filter samples** ask *what is in the air at this site*. They
  are real chemistry at real sites, but they come from 15–30 sampling days per season at 5–20
  sites. They cannot tell a local truck from a regional one, and they report **"secondary
  aerosol" as a source** (Kanpur winter SIA+SOA ~37%, Patna winter 38%), which hides the sectors
  that emitted the gases. CMB needs source profiles; PMF needs someone to name the factors. "Coal
  and fly ash" and "soil and road dust" are categories set by the profile library, not sectors.
- **Inventory + Gaussian dispersion (AERMOD)**, which most NCAP studies pair with the receptor
  model, only sees what got into the inventory. It has no chemistry and no boundary inflow, so it
  cannot say what comes from outside.
- **Inventory + chemical transport model with zero-out runs (CAMx, CMAQ, GEOS-Chem)** allocates
  secondary PM back to sectors and can tag geography. But it is only as good as the inventory, it
  is non-additive (removing one sector changes the chemistry for the others), and at coarse grid
  sizes it smears city sources out. Guttikunda's APnA paper makes this point itself: transport is
  ~2% in GBD MAPS and ~18% on average in the 20-city runs. [O]

A fourth thing often passed off as apportionment is the **emissions share** (Mumbai "road dust
71%", SAFAR "transport 41%"). That is tonnes emitted, not what people breathe. A coarse,
ground-level source (road dust) is big in emissions and much smaller in PM2.5 concentration. A
curated dataset needs a `metric` column for this.

**Worked example 1: Kanpur's households.** Same city, three numbers for household and biomass
burning:

| Source | Method | Year | Share |
|---|---|---|---|
| APnA | WRF-CAMx zero-out, 1 km | 2015 | residential **33.8%** |
| McDuffie 2021 | GEOS-Chem sensitivity, ~50 km, downscaled | 2017 | residential biofuel **24.5%** |
| IIT Kanpur for UPPCB | PMF, 3 sites | winter 2018-19 | biomass **2.9%** (9.2% of PM10); summer 14.8% |

The IITK study has vehicles+DG at 30% in winter. APnA has transport at 14% and McDuffie has road
at 6%. Part of the gap is categorical: household smoke that has aged into secondary organic
aerosol shows up in IITK's 18% "SOA", and a model's "residential" includes that SOA. Part of it is
which villages fall inside the domain. Either way, a planner choosing between "LPG for homes" and
"fix diesel trucks" gets opposite advice depending on which number they read. [O]

**Worked example 2: Kolkata's vehicles and waste.**

| Study | Vehicles / transport | Waste burning | Key |
|---|---|---|---|
| NEERI 2019 | 23.5 | 6.7 | [S] |
| SAFAR | 32 | 16 | [S] |
| Bose Institute (PMF) | 18–22 | 31–41 | [S] |
| APnA 2019 (CAMx) | 13.5 | 12.8 | [O] |
| TERI 2025, CMB | 20 | (in "cooking" 29) | [O] |
| TERI 2025, CMAQ | 15–18 | not read | [S] |
| McDuffie 2017 (GEOS-Chem) | road 3.4 | waste 2.9 | [O] |

A **tenfold** spread on vehicles (3–32%) and a **tenfold-plus** spread on waste burning (3–41%), for one city, all
published since 2019. NEERI's own interim and final reports disagreed on eateries (about 20% vs
under 5%) [S].

**Worked example 3: how much comes from outside.** Lucknow: APnA 30%, TERI CMAQ 81% [O]. The
difference is mostly about definitions: APnA's "airshed" is a box of tens of km drawn around the
city, while TERI counts everything beyond the municipal boundary. Kolkata: APnA 19% vs TERI
"beyond study domain" 43–46% [O]. So "share from outside" is not one number. It depends on where
the line is drawn, and a dataset must store the boundary used.

**When methods agree.** Surat is the counter-example: TERI ran CMB and CMAQ side by side and got
winter industry 46 vs 42%, dust 9 vs 11% [O]. But the same team built both the inventory and the
source profiles, so the agreement is not independent. ARAI-TERI (Delhi, 2018) made the same claim
for Delhi. Agreement within one team is a weaker test than agreement across teams.

---

## 4. What an open "causes by city" dataset could be built from today

**Buildable now, open, machine-readable:**

1. **APnA 49-airshed CSV** (CC-BY): the spine. Every row already has the outside share.
2. **McDuffie Supplementary Data 1** (17 Indian cities, 20 sectors) and the Zenodo gridded
   fractions (CC-BY): these give a second, independent model estimate for **any** city polygon.
   Clipping the 0.01° grids to the 130 NCAP city boundaries would give a consistent, global-model
   column for every city. That costs ~126 GB of download, or less if only the needed sector files
   are fetched.
3. **GBD MAPS India Table C.1**: state-level all/rural/urban shares, ~100 rows to transcribe from
   one PDF. Copyright HEI, so cite it rather than redistribute it.
4. **UEinfo gridded inventories** (all-India 0.25° for 2024, 50 cities at 1 km): emissions, not
   concentrations, but they allow consistent sector-emissions-per-city numbers.

**Buildable with work (PDF extraction):**

5. **The ~60+ NCAP reports on PRANA**, plus TERI's Kolkata, Lucknow and Patna reports and the
   MPCB set. Each needs: receptor shares by season and by size fraction, the inventory table, the
   dispersion result, sampling dates and sites, and method. The 15 one-page summaries are the
   fastest start (one inventory table and four pies each). Licence is unstated. Facts extracted
   from government reports can be tabulated with citation, but the PDFs themselves shouldn't be
   rehosted.

**Proposed schema** (one row per city × study × season × size fraction × source):
`city, ncap_city_id, study, institution, year_sampled, season, size_fraction, method
(CMB|PMF|AERMOD|CAMx|CMAQ|GEOS-Chem|GAINS), metric (concentration_share|emission_share),
boundary (site|municipal|airshed_box|district|state), source_raw, source_harmonised, share_pct,
outside_share_pct, n_sites, n_days, url, evidence_key`. The `source_raw` → `source_harmonised` map
is where the real work is: "coal and fly ash", "fossil fuel combustion", "SIA/SOA" and
"marine" do not map cleanly onto transport/industry/residential.

**What's missing:**

- **Chennai, and the southern cities generally.** No final NCAP report found. APnA (2015 base)
  is the only number.
- **Time series.** Nearly every city has one campaign. Nobody can say whether a source's share
  went *down* under NCAP, which is the question NCAP was supposed to answer. Kolkata (NEERI 2019 →
  TERI 2025) and Mumbai (NEERI 2010 → 2023) are the only obvious repeat studies.
- **Outside share on a common boundary.** APnA's box, TERI's municipal line and the World Bank's
  state line give answers ranging from 13% to 81%. A consistent run (for example, tagging the
  McDuffie or a CAMx run by NCAP city polygon) does not exist in the open.
- **Secondary aerosol attributed to sectors**, on measured data. Receptor studies stop at
  "secondary 20–38%".
- **Uncertainty.** Almost no NCAP report gives intervals on its shares.
- **Brick kilns and waste burning** are where methods diverge most (Kolkata waste 3–41%).
- **The underlying filter chemistry.** The species-level data (OC/EC, ions, metals by day and
  site) that went into every PMF/CMB run is in tables inside the PDFs, at best. With it, anyone
  could rerun the apportionment. That would be the most valuable thing to free, and it connects
  to G6 in `gaps.md` (ratios as fingerprints).

**Not done in this pass:** the PRANA city-list API wasn't queried; shares from the ~45 other
PRANA reports weren't extracted; GBD MAPS 2050 scenarios, the CEEW Delhi inventory comparison
and the WHO database weren't opened.
