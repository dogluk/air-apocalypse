# Who works on India's air in the open

*2026-11-11*

**Key.** **[O]** opened and read at source (for GitHub: the README, licence and commit metadata
pulled through the API on the date above). **[S]** seen only in a search snippet or search
summary. **[R]** recalled from memory. As in [`landscape.md`](landscape.md), most [S] items
are leads to confirm, not verified facts. Handles marked [R] in particular need checking
before anyone is contacted.

**How this was searched, and its blind spot.** GitHub: about 70 repository searches, 8 code
searches, and direct listings of the accounts of the groups named in `landscape.md`. X: the
X API returned HTTP 402 on the first pass; a later search (2026-11-12, bottom of this file)
found little. Exa does
not return x.com post pages for these queries; it returns the blogs, op-eds, papers,
LinkedIn posts and news stories that quote X posts. So the people below were found through
their long-form writing, and the "threads" section is mostly not threads. Anyone who argues
about Indian air *only* on X is missing from this file.

## The short version

1. **Open code on Indian air is thin and comes from three or four places.** CREA
   (`energyandcleanair`), UrbanEmissions (`urbanemissionsinfo`), EPIC's AQLI team
   (`aqli-epic`) and IIT Gandhinagar's Sustainability Lab account for nearly all of it.
   Almost every repo has 0 to 15 stars. The rest of GitHub is student AQI dashboards.
2. **The most useful finds for us** are CREA's `creahia` (a health-impact R package that keeps
   GBD 2023, GEMM and Fusion risk curves in one registry, which is the natural benchmark for
   [`health/`](../health/)) and CREA's `pm25ml` (daily 10 km PM2.5 for India, MIT-licensed,
   outputs on Zenodo). CREA's code mostly carries **no licence**, so it can be read and
   compared against, but not legally copied without asking.
3. **Nobody has open-sourced the middle of the chain.** Emissions to concentrations to deaths
   to rupees, for an Indian intervention, does not exist as runnable public code. The
   operational models (IITM's DSS and AQEWS, SAFAR, TERI, IIT Kanpur) are closed. No WRF-Chem,
   CMAQ or CAMx configuration for an Indian domain turned up on GitHub. There is no official
   public national emission inventory.
4. **The people reasoning from physics and arithmetic in public are mostly the same small
   modelling circle:** Guttikunda, CREA (Myllyvirta, Dahiya), Jethva on fires, and the Surat
   economists. They are joined by a few writers (Abhishek Jha at HT, Pulkit Joshi's blog,
   Chetan Bhattacharji's Substack) and funders (Santosh Harish, Rainmatter).
5. **The EA-style "cost per life" conversation about India is still mostly 2020 to 2023
   writing:** Open Phil's cause report, Founders Pledge, one air-purifier BOTEC, the 80,000
   Hours episode. Nothing newer and comparable surfaced. [`prior-rankings.md`](prior-rankings.md)
   covers the cost studies themselves.

## Open code and data

Sorted by how useful each looks for this project. Stars and last push are as of 2026-11-11.
"No licence" means no LICENSE file, which by default reserves all rights.

| Repo | What | Activity | Licence | Reusable for us? | Link |
|---|---|---|---|---|---|
| **CREA `creahia`** | R package for health impact assessment from gridded PM2.5. Each risk curve (GBD 2023, GEMM, Fusion, GBD 2019) is one row in a registry, with its literature reference, plus uncertainty notes. Contributors include Lauri Myllyvirta and Hubert Thieriot. [O] | 6★, pushed 2026-11-06; active | None | **Benchmark, yes.** Run the same Delhi 100→80 case through it and through `airhealth`, and explain the gaps. Copying code needs CREA's permission. | [github](https://github.com/energyandcleanair/creahia) |
| **CREA `pm25ml`** | Daily PM2.5 for India at 10 km from a two-stage ML model. A reimplementation of Kawano et al. 2025 (Stanford), built by CREA. Results on Zenodo, [10.5281/zenodo.17573562](https://doi.org/10.5281/zenodo.17573562). [O] | 5★, pushed 2026-10-29 | MIT ("primarily") | **Yes.** A third exposure map next to ACAG and AQLI, and the only daily one. Directly useful for the Diwali and firecracker-ban DiD in `diwali/`. | [github](https://github.com/energyandcleanair/pm25ml) |
| **CREA `creatrajs`** | HYSPLIT back-trajectories for Indian cities, with VIIRS/MODIS fires (FIRMS) attached along each trajectory. [O] | 0★, pushed 2026-11-02 | None | Yes, as method. Stubble attribution for `diwali/`. | [github](https://github.com/energyandcleanair/creatrajs) |
| **CREA `creapuff`, `india_monthly_snapshot`, `fire_attribution_dashboard`** | CALMET/CALPUFF input builder, the type of model behind CREA's plant-level studies such as Chandrapur; the code behind CREA's monthly India snapshots; a fire-attribution dashboard. [O] | 9★, 0★, 0★; all pushed Oct to Nov 2026 | None | `creapuff` for the FGD bet in [`bets/`](../bets/README.md); the others as reference. | [creapuff](https://github.com/energyandcleanair/creapuff) · [snapshot](https://github.com/energyandcleanair/india_monthly_snapshot) |
| **UrbanEmissions `AQI_bulletins`** | Every CPCB daily AQI bulletin, 2015 to 2024, by city: AQI, number of stations, prominent pollutant. Served on Datasette. [O] | 2★, pushed 2026-11-03 | GPL-3.0 | Yes. A clean city-day panel for trends and DiD. | [github](https://github.com/urbanemissionsinfo/AQI_bulletins) |
| **UrbanEmissions `EmissionRepos`** | Notebooks that pull CEDS emissions, NASA GEOS-CF speciated PM2.5 for India (black carbon, dust, nitrate, OC, SOA, sulphate; 2024), TROPOMI monthly means, a 0.1° India grid and a 755-district shapefile (2023). [O] | 0★, pushed 2025-11-03 | AGPL-3.0 | Yes, for **species** (sulphate vs nitrate vs dust), which `health/` lacks. Mind AGPL if we redistribute. | [github](https://github.com/urbanemissionsinfo/EmissionRepos) |
| **UrbanEmissions `PM25_Interventions`** | One-page JavaScript calculator: coal-plant PM2.5 emission factors (49–68 t/PJ), and what washed coal, FGD and an upgraded ESP remove. Stops at emissions: no concentrations, no health. [O] | 0★, 2026-09-22 | AGPL-3.0 | As a cross-check of the emissions step for a coal bet. | [github](https://github.com/urbanemissionsinfo/PM25_Interventions) |
| **UrbanEmissions `AQNEST`** | Monitor-network siting tool: how many monitors an area needs under CPCB's 2003 population rule, with a network score against LandScan 2024. Ships a CPCB site list dated July 2026. [O] | 0★, 2026-08-13 | AGPL-3.0 | Yes, for the monitoring-gap argument in `landscape.md`. | [github](https://github.com/urbanemissionsinfo/AQNEST) · [tool](https://urbanemissionsinfo.github.io/AQNEST/) |
| UrbanEmissions, other | `AQHARM` (exposure harm maps for Bengaluru and Ethiopia from WUSTL 2023 PM2.5 × LandScan; no README); `pollutioncalculators` (SIM-air Excel tools being ported to Python linear programmes); `TransportEmissions`; `OpenWasteBurning`; `TROPOMI_EXTRACTS`; `Benford` (Benford's-law check on AQI data). Guttikunda also announced an open repository of gridded national and urban inventories in Aug 2026 ([LinkedIn](https://www.linkedin.com/posts/sarath-guttikunda_respository-of-gridded-emissions-for-india-activity-7495121773278113792-1pB5)) [S]. | 0–3★; mostly 2025–26 [O] | AGPL/GPL | Mixed. **Find the gridded-inventory repo:** it may be the closest thing to an open national inventory. | [org](https://github.com/urbanemissionsinfo) |
| **AQLI `aqli-update`** | AQLI data by GADM level 0/1/2, the 2025 release, and 2026 in progress. [O] | 14★, pushed 2026-10-05 | CC-BY-4.0 | Already in use (`exposure_aqli.csv`). Track the 2026 release. | [github](https://github.com/aqli-epic/aqli-update) |
| AQLI `epi.methods.paper`, `epi.meta.analysis` | 2023 repos comparing the GBD IER, meta-regression and GEMM methods with AQLI's, and a meta-analysis of PM2.5 mortality studies. [O] (descriptions only) | 0★, last push 2023 | None | Worth reading. It is the same question as `health/`'s five curves. | [org](https://github.com/aqli-epic) |
| **`Vonter/india-cpcb-aqi`** | 15-minute station-level CPCB measurements, plus hourly AQI, as Parquet/CSV with a fetch script. Vivek ("Vonter") keeps about 67 tidy Indian civic datasets. [O] | 6★, pushed 2026-01-07 | ODbL-1.0 | Yes, for station-level time series. Check how fresh it is: last push was January. | [github](https://github.com/Vonter/india-cpcb-aqi) |
| IIT Gandhinagar Sustainability Lab (Nipun Batra) | `VayuBench`: CPCB 2017–2024 and NCAP funding 2019–22 as pickles, plus an LLM benchmark of 10,034 air-quality questions (Apache-2.0). `gdmi-aqs`: sensor placement by gradient mutual information on WUSTL PM2.5. `sentinelkilndb`: 62,671 hand-validated brick kilns in India, Bangladesh, Pakistan and Afghanistan (NeurIPS 2025). [O] | 0–3★; 2025 | Apache-2.0 / none | The **kiln dataset** is the find: a source inventory nobody else has. NCAP funding data for any "money vs. outcome" look. | [VayuBench](https://github.com/sustainability-lab/VayuBench) · [kilns](https://github.com/sustainability-lab/sentinelkilndb) |
| **`tianjialiu/SAGE-IGP`, `ModL2T-Burned-Area`** | Tina Liu (UBC): agricultural fire emissions for the IGP from fire radiative power, corrected with farmer surveys; and a 30 m burned-area product for NW India (MODIS + Landsat, Earth Engine). [O] | 3★ / 7★, pushed 2026-04-20 | MIT / none | Yes. Better stubble emissions than raw fire counts, which Jethva shows now miss late-afternoon burning (see people). | [SAGE-IGP](https://github.com/tianjialiu/SAGE-IGP) · [ModL2T](https://github.com/tianjialiu/ModL2T-Burned-Area) |
| `ihmeuw-msca/burden-of-proof`, `mrtool` | IHME's meta-regression engine behind GBD risk curves. [O] | 17★ / 4★, 2026 | BSD-2 | Only if we ever fit a curve ourselves. | [github](https://github.com/ihmeuw-msca/burden-of-proof) |
| `openaq/openaq-python`, `openaq-api` | OpenAQ SDK and API. [O] | 25★ / 68★, active | Apache-2.0 / MIT | API key needed (`landscape.md`). | [github](https://github.com/openaq) |
| `USEPA/esat`, `weber-s/pyPMF` | Positive matrix factorisation, the receptor-model method behind source apportionment, in Python. [O] | 0★ / 18★ | Apache-2.0 / none | Only if speciated filter data ever becomes available (see "What's missing"). | [esat](https://github.com/USEPA/esat) |
| `spatialmodel/inmap` | InMAP, a reduced-form PM2.5 model that maps emissions to concentrations cheaply. [O] India coverage not checked. | 75★, active | GPL-3.0 | The architecture an open Indian source-receptor tool would copy. | [github](https://github.com/spatialmodel/inmap) |
| `JGCRI/CEDS`, `geoschem/GCClassic` | Global emission inventory and global chemical transport model; both cover India. [O] | 120★ / 30★ | — / custom | Background inputs, not India-specific. | [CEDS](https://github.com/JGCRI/CEDS) |
| `adithirgis/pollucheck` | Shiny app to explore CPCB/OpenAQ data, by Adithi Upadhya. [O] | 10★, last 2021 | custom | Stale. | [github](https://github.com/adithirgis/pollucheck) |
| `thejeshgn/cpcbccr` | Early CPCB scraper (SQLite). [O] | 21★, last 2022 | GPL-3.0 | Stale; superseded by `Vonter`. | [github](https://github.com/thejeshgn/cpcbccr) |
| `respirer-living-sciences/unicef-os-codebase` | Open-source version of Respirer's APIs and data hub. Respirer is one of the two AMRIT hardware vendors. [O] | 0★, 2026-09 | MIT | Possibly a way into AMRIT sensor data; unexplored. | [github](https://github.com/respirer-living-sciences/unicef-os-codebase) |

**Independent one-off analyses (2026), worth a look but unreviewed.** Each is one person's
notebook or app, 0–2★. The claims are the authors' own, read in their READMEs [O], not
checked.

- [`Prithviarora/stubble-burning-delhi-aqi`](https://github.com/Prithviarora/stubble-burning-delhi-aqi):
  121,561 FIRMS fire detections + CPCB + Open-Meteo, 2015–19, separating smoke from
  seasonal weather.
- [`BoredMongoose/delhi-smog`](https://github.com/BoredMongoose/delhi-smog): weather-normalised
  PM2.5; claims crop fires drive "about 60%" of early-November PM2.5 and Diwali about 2% of
  the season's excess. **The same question as our `diwali/`**: compare methods.
- [`kartikangiras/mordor`](https://github.com/kartikangiras/mordor): a 5 km, 48-hour forecast
  of the stubble-smoke increment, checked against stations the next day (MIT).
- [`sattyamjjain/dhuan`](https://github.com/sattyamjjain/dhuan): 3D globe of FIRMS fires,
  wind and CPCB stations.
- [`williampsun2007/india-pm25-scenario-model`](https://github.com/williampsun2007/india-pm25-scenario-model):
  a U-Net that imitates a physics-based Indian emissions-scenario model. Data not included.
  If the underlying scenario runs exist somewhere, this is the only open hint of an emulator.

**US tools for structure only:** `BenMAPCE/BenMAP-CE` (EPA's health-benefits tool; 20★),
`jinhyokh/pyairhealth` (BenMAP in Python). [O]

## People reasoning about it quantitatively

Public professional information only. A handle tagged [S] was seen in a search result; [R]
is from memory and unchecked.

**Modellers and measurers**

- **Sarath Guttikunda**, @UrbanEmissions [S]. UrbanEmissions.Info; IIT Delhi TRIP Centre.
  Thinks in box models. One Xi'an-size smog tower filters about 0.0003% of the air crossing
  Delhi's winter airshed each hour, so the city would need about 300,000 of them. Blaming one sector is pointless; Delhi needs a 15-year
  regional path from ~100 to 40 µg/m³. Runs most of the open India code above.
  [Smog towers, MDPI 2020](https://www.mdpi.com/2073-4433/11/9/922) [S] ·
  ["Groundhog Day", LinkedIn Nov 2025](https://www.linkedin.com/posts/sarath-guttikunda-3a01149_air-pollution-groundhog-day-every-winter-activity-7395003041944473600-tR2T) [S].
- **Sai Krishna Dammalapati.** UrbanEmissions. Data and code behind the CPCB bulletin
  archive and the 1990–2022 Delhi review; Guttikunda credits him with archiving the
  inventories. Possibly @chaotic__neuron, inferred from a tagged tweet and unverified [S]. A
  builder worth knowing.
- **Lauri Myllyvirta**, @laurimyllyvirta [R]. Co-founder of CREA; Asia Society. Bottom-up
  coal-plant emissions: 4,327 kt SO₂ from 537 units in a year, against 17.8 kt from paddy-straw
  burning; under 8% of capacity had FGD. Contributor to `creahia`.
  [LinkedIn, Nov 2024](https://www.linkedin.com/posts/lauri-myllyvirta-3164703b_indias-coal-power-plants-are-extremely-polluting-activity-7263215636732911617-aEac) [S].
- **Sunil Dahiya**, handle unchecked ([R] @Sunil_Dahiya). Founder and lead analyst at
  Envirocatalysts, formerly CREA. Argues for emission-load targets **in tonnes** per state per
  year rather than concentration targets, restoring FGD within 300 km of Delhi, and treating
  GRAP as the last line of defence.
  [Times Now, 7 Nov 2026](https://www.timesnownews.com/opinion/india/delhi-needs-emission-cuts-in-tonnes-to-reduce-air-pollution-not-emergency-curbs-every-winter-article-156479668) [S].
- **Hiren Jethva**, @hjethva05 [S]. NASA Goddard / Morgan State. Using Korea's geostationary
  GK2A satellite, shows Punjab burning has moved from 1–2 pm to 4–5 pm since 2022, after the
  MODIS/VIIRS overpass. So official fire counts undercount, while aerosol loading has not
  fallen. Posts the charts on X each season [S]. **Directly matters for any stubble number we
  use.** [MDPI 2026](https://www.mdpi.com/2072-4292/18/10/1506) [S] ·
  [NASA Earth Observatory](https://science.nasa.gov/earth/earth-observatory/new-timing-for-stubble-burning-in-india/) [S].
- **Tina (Tianjia) Liu.** UBC Geography. Agricultural fire emissions and burned area for NW
  India, all on GitHub (above) [O].
- **Nipun Batra.** IIT Gandhinagar Sustainability Lab. ML for air quality: brick-kiln
  detection, sensor placement, an LLM benchmark [O]. Open by default; students who could be
  recruited.
- **R. Subramanian ("Subu")** [R affiliation: CSTEP]. Points out that the latest public
  national inventory is probably SMoG-2015, so papers still simulate 2016. Calls for an
  Indian national inventory. Comment on Guttikunda's post above [S].
- **Gufran Beig.** NIAS, founder of SAFAR. Delhi's EV registration policy covers about 35% of
  transport emissions, so roughly 15% of PM2.5; heavy vehicles and buses are about 60% of
  transport. "Talk sources, not processes": secondary aerosol is not a source.
  [Indian Express, Jan 2026](https://indianexpress.com/article/opinion/columns/delhi-air-pollution-january-aqi-stubble-burning-10496537/) [S].
- **Ajay Pillarisetti, Sourangsu Chowdhury, Sagnik Dey.** Household solid fuel is a median
  ~30% of India's *ambient* PM2.5 across seven modelling studies. It is the largest single
  source, about 11× transport nationally.
  [CCAPC brief 2019](https://ccapc.org.in/policy-briefs/2019/5/30/the-contribution-of-household-fuels-to-ambient-air-pollution-in-india-a-comparison-of-recent-estimates) [S].

**Economists**

- **Anant Sudarshan, Rohini Pande, Michael Greenstone, Nicholas Ryan.** The Surat particulate
  market: emissions down 20–30%, abatement cost 11% lower, compliance 99% against 66%,
  benefits at least 25× costs. The Emissions Market Accelerator is scaling it to Maharashtra
  and Rajasthan. [QJE 2025](https://doi.org/10.1093/qje/qjaf009) [S] ·
  [EMA](https://emissionsmarkets.org/evidence-from-india/) [S]. Handles not checked.
- **Teevrat Garg.** UC San Diego. Rural roads pulled labour off farms and raised crop fires
  60%, with infant mortality 5.5% higher downwind.
  [VoxDev](https://www.voxdev.org/topic/energy-environment/constructing-roads-connected-labour-markets-increased-harmful-crop-fires) [S].
- **Gemma Dipoppa and Saad Gulzar.** District officials let fires rise 15% when the wind
  carries smoke to a neighbouring district, and cut them 14.5% when it blows over their own:
  enforcement responds to incentives. [Nature 2024](https://doi.org/10.1038/s41586-024-08046-z) [S].
- **Maureen Cropper** (with Guttikunda). FGD retrofits average about $131k per life saved,
  $67k for the 30 best plants. Plants in the IGP pass the benefit-cost test; the southern
  coastal ones do not. [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC7473063/) [S].
- **Shruti Rajagopalan**, @srajagopalan [R]. Mercatus. A Coasean case: tradable crop-burning
  permits, since farmers' cost of stopping (~₹20,000 crore) is about a tenth of what NCR
  residents lose. [Mint 2019](https://www.livemint.com/opinion/columns/ronald-coase-has-a-solution-for-delhi-s-air-pollution-11573491626858.html) [S].
- **Ajay Shah**, @ajay_shah [R]. XKDR. Repeal Punjab and Haryana's 2009 subsoil-water acts,
  which moved peak burning from 24 Oct to 4 Nov, into worse weather.
  [Blog, 2020](https://www.mayin.org/ajayshah/MEDIA/2020/aq.html) [S].
- **Alex Tabarrok**, @ATabarrok [R]. Marginal Revolution coverage of Surat, read through Hayek
  and Coase. [MR, Sep 2024](https://marginalrevolution.com/marginalrevolution/2024/09/reducing-pollution-in-india-with-a-cap-and-trade-market.html) [S].

**Funders**

- **Santosh Harish**, @santoshharish1 [S]. Leads Coefficient Giving's (ex-Open Philanthropy)
  air-quality programme. Argues for the "scientific plumbing": no public national emission
  inventory, source apportionment repeated every few years, rural monitoring. The obvious
  person to show a finished `health/` to.
  [80,000 Hours #170](https://forum.effectivealtruism.org/posts/txgQDuTiijnNtB7vm/170-how-air-pollution-is-responsible-for-12-of-global-deaths) [S].
- **Nithin Kamath**, @Nithin0dha [R]. Zerodha; Rainmatter Foundation. Launched an open,
  pan-India air-quality data platform in April 2026. Rainmatter funds Asar, CEEW and Climate
  Trends, and gives small grants (₹3–12 lakh a year) that name air pollution.
  [Blog](https://nithinkamath.me/blog/bringing-air-quality-data-closer-to-people/) [S] ·
  [small grants](https://grove.rainmatter.org/t/the-rainmatter-small-grants-programme/133) [S].
- **Tom Barnes.** Founders Pledge cause report: prioritise policy and monitoring in neglected,
  growing regions. [EA Forum 2022](https://forum.effectivealtruism.org/posts/Td4nkg4v2spDgyyKL/air-pollution-founders-pledge-cause-report) [S].

**Writers and data journalists**

- **Abhishek Jha.** Hindustan Times data desk. Took apart IIT Kanpur's cloud-seeding
  "success" report: no units, no averaging period, and the seeding window coincided with
  Delhi's normal afternoon dip.
  [HT, 29 Oct 2025](https://www.hindustantimes.com/india-news/how-iit-k-success-report-ignores-natural-air-patterns-101761763435637.html) [S].
  His editor **Sukumar Ranganathan** writes the same line weekly on
  [Substack](https://hted.substack.com/p/whats-on-my-mind-measures-and-management) [S].
- **Pulkit Joshi.** Computational materials postdoc in Jena [O, GitHub profile], writing
  first-principles explainers on a personal blog. Le Chatelier and ISORROPIA constants: the
  ammonia × nitric acid product needed to keep ammonium nitrate solid is 53× smaller at 10 °C
  than at 25 °C.
  [Blog, 3 Nov 2026](https://joshipulkit.github.io/blog/2026/delhi-winter-smog/) [S]. Exactly
  the tone of [`bets/`](../bets/README.md).
- **Chetan Bhattacharji.** "What Am I Breathing" Substack, built on interviews with
  Guttikunda, Tripathi and others: "target the big chunks".
  [Substack](https://whatamibreathing.substack.com/p/beijing-slashed-its-pollution-heres) [S].
- **Tabish Ansari** (affiliation not checked). A closed-form box-model proof that smog
  towers remove about 10⁻⁶ of what ventilation does.
  [ESSOAr 2025](https://doi.org/10.22541/essoar.174526347.72062267/v1) [S].
- **Akshay Deoras**, @AkshayDeoras [R]. NCAS, University of Reading. Explains cloud-seeding
  physics in public: it cannot make rain "from scratch".
  [ThePrint](https://theprint.in/environment/delhi-govt-claims-cloud-seeding-trial-a-success-but-dont-expect-rain-just-yet-its-not-like-magic/2772199/) [S].
- **Vivek ("Vonter") and Thejesh GN** (@thejeshgn [R]). Bengaluru civic-data builders who
  scrape and publish CPCB data among much else [O]. Not air specialists, but the people to
  ask for help with scrapers.

**Reach, not analysis:** Bryan Johnson (@bryan_johnson [S]) posted in Jan 2025 that India
"would save more years of life" fixing air than curing cancer
([India Today](https://www.indiatoday.in/india/story/air-pollution-bigger-threat-than-cancer-age-reversing-ceo-sounds-alarm-2660717-2025-01-07)) [S].

## Threads worth reading

Most of these are not X threads; see the blind spot at the top.

- [South Asian Air Quality cause investigation](https://forum.effectivealtruism.org/posts/WxpAGzLvBLrZgmTFs/south-asian-air-quality-cause-investigation)
  (Open Phil, 2021). Explicit BOTECs: a $500k source-apportionment study must pull forward
  0.8 µg/m³ by 10 years for a 5M city; coal scrubbers come out at about 1,960×. [S]
- [Cost-effectiveness of air purifiers](https://beta.effectivealtruism.org/posts/umzu3RGBBhA3fefhw/cost-effectiveness-of-air-purifiers-against-pollution)
  (Lukas Trötzmüller, 2020). About $5,230 per DALY in India, with a model attached. [S]
- [80,000 Hours #170, Santosh Harish](https://forum.effectivealtruism.org/posts/txgQDuTiijnNtB7vm/170-how-air-pollution-is-responsible-for-12-of-global-deaths)
  (2023). Rural exposure, the 1981 Air Act's industrial bias, and why command-and-control fails. [S]
- [Wiblin's call for questions for Harish](https://forum.effectivealtruism.org/posts/PubK8PnrLgFet92rx/i-m-interviewing-santosh-harish-open-phil-s-south-asian-air)
  (2023). Comments debate whether air pollution is "legible" enough for GiveWell-style giving. [S]
- [Can we vacuum our air pollution problem?](https://www.mdpi.com/2073-4433/11/9/922)
  (Guttikunda & Jawahar, 2020). The canonical airshed-volume arithmetic. [S]
- [Guttikunda, "Groundhog Day"](https://www.linkedin.com/posts/sarath-guttikunda-3a01149_air-pollution-groundhog-day-every-winter-activity-7395003041944473600-tR2T)
  (LinkedIn, Nov 2025). A Monte-Carlo business-as-usual path for Delhi to 2040; Subu's comment
  on SMoG-2015 underneath. [S]
- [Myllyvirta on coal SO₂](https://www.linkedin.com/posts/lauri-myllyvirta-3164703b_indias-coal-power-plants-are-extremely-polluting-activity-7263215636732911617-aEac)
  (LinkedIn, Nov 2024). Coal plants against stubble, in tonnes. [S]
- [Jethva, "Timing the Flames"](https://www.mdpi.com/2072-4292/18/10/1506) (2026), and his
  season charts on X, reported by
  [Moneycontrol, 10 Nov 2026](https://www.moneycontrol.com/city/farmers-burn-stubble-after-satellites-pass-what-punjab-s-farm-fire-count-is-not-telling-you-article-14075841.html):
  CAQM's count is 4,459 fires to 8 Nov, and iFOREST finds over 90% of large fires start
  after 3 pm. [S]
- [Abhishek Jha on the cloud-seeding report](https://www.hindustantimes.com/india-news/how-iit-k-success-report-ignores-natural-air-patterns-101761763435637.html)
  (HT, 2025). A model of how to read a "PM fell after X" claim. [S]
- [Pulkit Joshi, "How gases add to Delhi's winter particle pollution"](https://joshipulkit.github.io/blog/2026/delhi-winter-smog/)
  (2026). Inversions, ammonium nitrate and ammonium chloride, from first principles. [S]
- [Sagar Wadhwa, "Money Not To Burn"](https://www.sagarwadhwa.com/2024-04-07-money_not_to_burn/)
  (2024). Summary of the Punjab payments RCT: ₹800/acre; upfront payment doubles compliance,
  but only to 18.5%. [S]
- [Rajagopalan, "Ronald Coase has a solution"](https://www.livemint.com/opinion/columns/ronald-coase-has-a-solution-for-delhi-s-air-pollution-11573491626858.html)
  (Mint, 2019). Tradable burning permits. [S]
- [Ajay Shah, "Solving North India's air quality crisis"](https://www.mayin.org/ajayshah/MEDIA/2020/aq.html)
  (2020). The 2009 water law as the cause of the burning surge. [S]
- [Tabarrok on Surat](https://marginalrevolution.com/marginalrevolution/2024/09/reducing-pollution-in-india-with-a-cap-and-trade-market.html)
  (MR, 2024). [S]
- [Arpit Gupta's weekly India thread](https://en.rattibha.com/thread/1599074519561273345)
  (X, Dec 2022, unrolled). The one actual X thread found. It summarises IIT Kanpur's
  apportionment: road dust 38% of PM2.5; stubble 26% in winter. [S]
- [Sunil Dahiya, "emission cuts in tonnes"](https://www.timesnownews.com/opinion/india/delhi-needs-emission-cuts-in-tonnes-to-reduce-air-pollution-not-emergency-curbs-every-winter-article-156479668)
  (Times Now, 7 Nov 2026). Includes the July 2025 FGD exemption for 78% of coal units. [S]
- [Nandi, Ganguly, Habib & Dey, "Delhi cannot clean its air alone"](https://www.nature.com/articles/s44407-026-00065-6)
  (npj Clean Air, 2026). A crop-burning ban inside the NCR alone cuts Delhi's PM2.5 by 2–3%;
  airshed-wide, about 10%. [S]

## What's missing

What nobody has open-sourced, as far as these searches reach:

1. **An Indian source–receptor model.** No public tool turns "cut X tonnes of sector Y in
   region Z" into µg/m³ across India's districts. InMAP is the template, and
   `williampsun2007`'s emulator hints that scenario runs exist somewhere. This is the missing
   middle between UrbanEmissions' emission calculators and `creahia`/`airhealth`.
2. **Any model configuration for an Indian domain.** No WRF-Chem namelist, CMAQ, CAMx or
   GEOS-Chem nested setup for India turned up in GitHub code search. The operational systems
   (IITM's DSS and AQEWS, SAFAR, the TERI and IIT Kanpur studies) are closed. Their daily
   source shares disagree: for 2021, stubble was 12%, 17% and 32% in DSS, SAFAR and
   UrbanEmissions respectively ([CEEW](https://www.ceew.in/sites/default/files/ceew-research-on-air-quality-management-delhi-winter-pollution-case-study-2021.pdf)) [S].
3. **A public, versioned national emission inventory.** Harish and Subramanian both say so
   [S]. UrbanEmissions' gridded release (Aug 2026) is the nearest thing, and it is unofficial.
4. **Speciated measurements.** Filter chemistry from the Delhi supersite and the real-time
   source-apportionment studies is not open, so the PMF tools above have nothing Indian to
   run on.
5. **Open cost-effectiveness code.** IIASA GAINS (behind the World Bank and UP cost curves) is
   closed. TERI's Delhi study is a PDF. `PM25_Interventions` stops at emissions and `creahia`
   stops at deaths. Nothing chains emissions → concentrations → deaths → rupees in the open,
   which is the hole [`prior-rankings.md`](prior-rankings.md) also finds.
6. **Licences.** CREA's most reusable repos (`creahia`, `creatrajs`, `creapuff`) have none.
   One email could fix that.
7. **A geostationary fire product.** Jethva's GK2A fire-detection algorithm is published but
   no code was found. Every open stubble analysis on GitHub, including ours, still uses
   FIRMS overpass counts, which his work says miss the late-afternoon fires.
8. **India-specific low-cost sensor calibration code.** None worth listing, which fits
   `landscape.md`'s finding that open sensor data is thin.
9. **Farm-level stubble economics as code.** The cost numbers (₹800–2,500/acre payments,
   ₹1,500–1,800/t to bale and move straw, Happy Seeder savings) live in papers and PDFs, not
   models.
10. **The X conversation itself.** Searched 2026-11-12 (credits back; see below). Thin.


## X search, 2026-11-12

Eight full-archive searches (since 2017, by relevance) on cost-effectiveness, stubble payments,
source apportionment, effective-altruism framings and winter policy. Result: almost nothing
quantitative. No thread ranks Indian interventions on one metric, which agrees with
[`prior-rankings.md`](prior-rankings.md). Most hits were press releases, political accounts and
Grok replies. What was worth keeping [R unless marked]:

- **Seema Jayachandran's threads on the stubble payment paper** (Nov 2022): pay-after-compliance
  had no effect; part-upfront payment was cost-effective. This is the PES anchor already used.
  J-PAL's earlier ₹2,500/acre transfer result was shared by Saksham Khosla (Oct 2021).
- **TERI, "cost-effective interventions" for Delhi** (reported by India Water Portal, Dec 2021).
  Already in `prior-rankings.md` [O]: ~15 measures in ₹ bn per µg/m³, the closest thing to a
  costed Delhi ranking. A benchmark candidate.
- **A new Delhi-NCR source study at 500 m**, announced 26 Oct 2026 (via a post quoting the
  article). The first in about a decade. Worth tracking as a future input to the causes dataset.
- **CREA on NCAP spending vs outcomes** (Oct 2026, via a post): ₹12,087 cr since 2019, 117 of 130
  cities still above the PM10 limit; Chennai's PM10 up 9.1% on ₹449 cr. A candidate benchmark
  for "money spent vs µg/m³ moved".
- **1.24 lakh deaths a year** attributed to exempting coal plants from FGD (May 2026, via a post;
  likely a CREA figure). Check the source before use.

Raw results: session scratchpad only, not committed.
