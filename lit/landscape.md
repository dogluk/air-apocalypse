# Who is measuring India's air

*2026-11-10*

**Key.** **[O]** opened and read at source (including two live API pulls on the date above).
**[S]** seen only in a search snippet or search summary. **[R]** recalled from memory.
Most [S] figures are leads to confirm, not verified facts.

**The short version.** Low-cost ambient sensing in India is not crowded. Roughly 5,000–8,000
low-cost nodes are *claimed* as deployed [S]; about 1,360 of them are one philanthropic
project, AMRIT [S]. The only openly machine-readable count that could be confirmed is 34
sensors [O]. The space is crowded with hardware vendors, thin on open data, thin outside a
few cities and UP/Bihar, and close to empty for black carbon, boundary-layer height and
independent stack measurement.

**Corrections to what we had assumed.**

1. The Santosh Harish source is an interview, not an op-ed:
   [On air pollution, we need to get the scientific plumbing right](https://indianexpress.com/article/technology/air-pollution-india-explained-pm25-solutions-tech-interview-10654248/),
   Venkatesh Kannaiah, Indian Express, 25 Apr 2026. He says "around 1,400 low-cost sensors
   across Uttar Pradesh and Bihar, at least 10 times more than what existed earlier", Bihar
   running nearly two years, UP a little over one, and more than $35M committed to air
   quality. [O]
2. The two Sudarshan papers are the same 28 sensors: one Kaiterra network in Delhi,
   2018–2020. A dead research testbed, not a live network. [O]
3. CAAQMS is now about 565–571 stations, not ~500. [S]
4. AMRIT was installed, not just announced: 534 nodes in Bihar and 826 in UP
   ([Airveda](https://www.airveda.com/blog/iit-kanpur)) [S]; Mongabay says 538 in Bihar [O].
   How many still report is not established.

---

## A. Technology and approach

### A1. How low-cost PM sensors work, and what they cost

**Mechanism.** A Plantower PMS5003, Sensirion SPS30 or similar is a small box with a fan, a
laser and a photodiode. Particles scatter light; the chip turns the scattered signal into an
estimated count by size bin, then into mass using a factory assumption about particle density
and shape. It never weighs anything. Most cheap units behave more like a nephelometer (total
scattering) than a true single-particle counter; the Alphasense OPC-N3 is closer to a real
counter and sees coarse particles better. [R]

**Reference instruments.** A BAM (beta attenuation monitor) collects particles on filter tape
and measures how much beta radiation the deposit absorbs — close to a true mass measurement.
A TEOM weighs the deposit via the frequency shift of an oscillating element. A CAAQMS station
is a BAM plus gas analysers, weather mast, air-conditioned shelter, calibration gases and a
maintenance contract. [R]

| Item | Cost | Tag |
|---|---|---|
| CAAQMS station, capital | ~₹1–1.5 crore; Oizom (a sensor vendor) says ₹80–100 lakh | [S]; ₹1.5 crore also in [Bhattacharji 2022](https://whatamibreathing.substack.com/p/indias-battle-for-low-cost-air-pollution) [O] |
| CAAQMS running cost | ~10% of capex per year (2019 paper). BMC: 5 stations with 3-year warranty and 5 years' maintenance for ₹17.5 crore, i.e. ₹3.5 crore per station over the contract | [S] |
| AMRIT node, all-in | [$2.5M (₹19 crore) for ~1,400 nodes over 3 years](https://www.thehindu.com/news/national/iit-kanpur-to-establish-network-of-air-quality-sensors-to-measure-pollution-in-rural-india/article65623953.ece): ~₹1.36 lakh or ~$1,800 per node including solar, calibration, deployment and data | [S] inputs; division is ours |
| Mumbai MANAS sensor | [₹3.8 crore for the IIT Kanpur batch](https://www.freepressjournal.in/mumbai/mumbai-to-install-75-hyperlocal-air-quality-sensors-under-manas-project-40-to-be-operational-by-april-end); snippets disagree whether that covers 40 or 75 units (₹5–9.5 lakh each) | [S] |
| Sudarshan/Kaiterra unit | ~$8,000 for 28 units, ~$285 each | [O], arXiv HTML via a summarising fetch |
| Bare PM module | ~$15–40 | [R] |

A calibrated, solar-powered, maintained node costs roughly 1/50 to 1/100 of a CAAQMS.

**Failure modes in Indian conditions.**

- **Humidity and fog.** Hygroscopic particles swell and scatter more, so sensors over-read as
  humidity rises. Humidity is the largest uncertainty source for optical sensors when the
  aerosol is hygroscopic ([Patel et al., AMT 2024](https://amt.copernicus.org/articles/17/1051/2024/);
  Ouimette et al. 2024). [S] IGP winter fog is the worst case. [R]
- **Season and place dependence.** A calibration trained in Delhi "performed quite poorly in
  Bengaluru"; short-term calibrations do not transfer across seasons
  ([Campmier et al., AMT 2023](https://amt.copernicus.org/articles/16/4357/2023/)). [S]
- **Saturation.** The Kaiterra units topped out near 1,000 µg/m³; Diwali exceeded the
  ceiling. [O] Plantower response goes non-linear above a few hundred µg/m³. [R]
- **Coarse dust.** Cheap optical sensors barely see particles above ~2.5 µm, so their PM10 is
  largely inferred and summer dust storms are under-read. [R]
- **Drift and lifetime.** Laser and fan degrade; typical module life is 1–3 years in dirty
  air. [R]
- **Operations — the real killer.** In the Sudarshan network, low-cost sensors were available
  30% of the time against 90% for government monitors, and only 12 of 28 were still working
  in the test period. [O]

### A2. Calibration, and accuracy actually achieved in India

- **Co-location:** run the sensor beside a BAM for weeks and fit a correction. [R] AMRIT
  co-located every device with a BAM at IIT Kanpur for two weeks before deployment. [S, vendor blog]
- **Humidity correction:** an explicit term for humidity, temperature or dew point. [R]
- **ML calibration:** random forest, Gaussian process or metric learning on the same inputs.
  Better in-sample, worse at transfer. [R]
- **Network or "blind" calibration:** use nearby reference monitors, or the assumption that
  sensors agree at clean, well-mixed hours, to correct nodes that cannot be visited. [R]
  AMRIT lists "network calibration" as an objective. [S]

| Study | Setting | Result | Tag |
|---|---|---|---|
| [Campmier et al., AMT 2023](https://amt.copernicus.org/articles/16/4357/2023/) | PurpleAir vs BAM in Delhi, rural Hamirpur, Bengaluru; 154–335 days | Uncalibrated R² 0.55–0.74, NRMSE ≥ 40%. Calibrated NRMSE 20–30%, R² 0.82–0.95 | [S] |
| [Zheng et al., AMT 2018](https://amt.copernicus.org/articles/11/4823/2018/amt-11-4823-2018.pdf) | Plantower PMS3003, Kanpur | 1-hour error 46% in monsoon, 35% post-monsoon with linear calibration; ~11% at 24-hour averaging | [S] |
| [Zheng et al., AMT 2019](https://amt.copernicus.org/articles/12/5161/2019/amt-12-5161-2019.pdf) | Delhi, 10 low-cost + 22 reference nodes, Gaussian process | ~30% error (RMSE 33 µg/m³) at 24 hours | [S] |
| [Sahu et al., AMT 2021](https://amt.copernicus.org/articles/14/37/2021/amt-14-37-2021.pdf) | Gas sensors, Faridabad and Mumbai, metric learning | R² up to 0.923 for O₃, 0.819 for NO₂ | [S] |
| IIT Kanpur on Airveda units | vs Met One BAM | R² ~0.9 ([testimonial on a vendor page](https://www.airveda.com/blog/iit-kanpur)) | [S] |
| Bihar SPCB chairman on AMRIT | — | Sensors "only about 60% accurate"; Tripathi disputes it ([Mongabay](https://india.mongabay.com/2026/07/the-hidden-burden-of-rural-air-pollution/)) | [O] |

Honest summary: calibrated hourly PM2.5 within ~20–30%, daily within ~10–20%, good
correlation. Enough for spatial patterns and trends, not for compliance against a 60 µg/m³
standard.

### A3. How the two Sudarshan papers work

**[Modeling fine-grained spatio-temporal pollution maps with low-cost sensors](https://www.nature.com/articles/s41612-022-00293-z)**
— Iyer et al., npj Climate and Atmospheric Science 2022. [O]

- **Hardware:** 28 Kaiterra units, mostly south Delhi, volunteer-hosted, plus 32 government
  monitors. May 2018 to May 2020.
- **Model, three steps:** (1) fill gaps with a spatio-temporal hierarchical model; (2) fit a
  per-sensor daily-cycle spline; (3) train a message-passing recurrent neural network on the
  residuals, with every sensor a graph node and distance an edge feature.
- **Claim:** 9.6% MAPE, RMSE 10.1 µg/m³.
- **What that claim is:** a one-hour-ahead forecast at locations that already have a sensor,
  using up to 8 hours of history from the other sensors. Not a test of predicting pollution
  where no sensor exists; the paper says the model "is generalized enough" for that but does
  not test it.
- **Calibration:** manufacturer's chamber calibration plus correlation above 0.8 with the
  nearest government monitor. No BAM co-location numbers.
- **Their own scaling result:** error flattens at ~30 sensors; they "infer that having an even
  denser deployment likely adds little value to the predictive performance". That cuts
  against using this paper as evidence that dense networks are needed.
- **Data:** confidential under an agreement with Kaiterra.
  [Code](https://github.com/shivariyer/epod-nyu-delhi-pollution) is public.

**[Comprehensive Monitoring of Air Pollution Hotspots Using Sparse Sensor Networks](https://arxiv.org/abs/2410.04309)**
— Bhardwaj et al., arXiv, v3 Feb 2025. [O] abstract; body via a summarising fetch covering
the first 100k of 133k characters.

- **Same network,** extended to Nov 2020.
- **Hotspot definition** (Goyal et al. 2021): a site-month counts if PM2.5 exceeds 60 µg/m³ on
  more than 60% of days, or the monthly mean exceeds 90, or it exceeds 90 on three
  consecutive days.
- **Finding:** 660 hotspot site-months on the public network plus 189 "hidden" ones seen only
  by the low-cost sensors.
- **Interpolation test — the honest spatial one:** space-time kriging with sensors held out
  80/20 gives MAPE 30% (RMSE 37 µg/m³). Far worse than the npj headline, because this time
  the task really is predicting at an unseen location.
- **Hotspot recovery:** 95% precision and 88% recall with half the sensors failed.
- **Mechanistic part:** a Gaussian plume model on a rough home-made inventory (kiln and
  industry dots from Guttikunda maps, population, Google Maps traffic colours). MAPE ~104%,
  yet it "explains 65% of transient hotspots".
- **Data:** sensor data not open; code at `ankitbha/hidden_hotspots` on GitHub. Funded by NSF;
  partners Kaiterra, NYU, Yale, Inclusion Economics India.

Read together: 28 sensors is a proof of concept on a network that was 30% available and
mostly dead by the end. It tells you what share of hotspots the official network misses in
south Delhi. It says nothing about whether the space is crowded.

### A4. Other measurement approaches

**Satellite AOD to PM2.5.**

- Satellites measure column aerosol optical depth; a model or statistical scaling converts
  that to surface PM2.5. [R]
- [Dey et al. 2020](https://mdpi.com/2072-4292/12/23/3872) (IIT Delhi, the SAANS portal): 1 km,
  2000–2019, MODIS-MAIAC AOD scaled with MERRA-2. Against CPCB: daily R² 0.8, RMSE
  25.7 µg/m³; annual R² 0.97, RMSE 7.2. [S] Good for annual maps, weak for a given day.
- Fails under cloud and fog — exactly the IGP winter — and has no rural ground truth to train
  on ([CSTEP 2022](https://cstep.in/drupal/sites/default/files/2022-02/Satellite-Based_Quantification_PM2.5_Feb2022.pdf)). [S]
- CREA published a satellite PM2.5 assessment across India's airsheds and districts. [S, title only]
- Global products (van Donkelaar/ACAG, used by AQLI) work on the same principle. Korea's
  geostationary GEMS covers only part of India. [R]

**Mobile monitoring.**

- Bengaluru (ILK Labs, CSTEP, Apte, Marshall): ~150 km of road, ~22 repeat passes per segment,
  30 m maps of black carbon, ultrafine particles and CO₂. Mean on-road black carbon ~10, 22
  and 56 µg/m³ on residential roads, arterials and highways. [S]
- A [companion CSTEP study](https://cstep.in/?p=1288) covered ~10% of city roads plus a
  55-node sensor network. [S]
- No Google Street View or Aclima campaign in India was found.
- Delhi launched "100 Vayu Rakshak" vans in Feb 2026; unclear whether they measure or
  enforce. [S, headline only]
- ICCT is doing roadside remote sensing of vehicle exhaust; early results showed some vehicles
  at ~10× limits, and the Supreme Court ordered an official pilot. [O, Harish interview]

**Stack monitoring (CEMS).**

- Mandated on 17 highly polluting industry categories since 2014. [R]
- CSE's 2021 study [New Systems, Old Habit](https://www.cseindia.org/new-systems-old-habit-10833)
  found very poor data quality. Possible causes listed: tampering, unit-conversion errors,
  calibration errors, bad installation. In Madhya Pradesh only 40–50% of data reached the
  board. The data "remains unused due to the lack of legal provisions". [S]
- [Only about half of state boards published CEMS data](https://www.downtoearth.org.in/pollution/only-50-of-india-s-pollution-authorities-make-real-time-data-public-cse-analysis-73885)
  (CSE, 2020). In Bihar, 29 of 41 units showed as offline. [S]
- A dissenting view (Sanjeev Kanchan): tampering is less prevalent than calibration and
  set-up problems. [S]
- What has moved: CSIR-NPL certification for CEMS is operating (21 models verified); CPCB
  calibration guidelines took effect July 2025. [S]
- PM CEMS infers mass from light scattering or a triboelectric signal and needs a
  site-specific calibration against manual stack samples. That step is where bias enters.
  [R]; consistent with the
  [2018 Greenstone, Pande, Sudarshan and Harish op-ed](https://indianexpress.com/article/opinion/how-india-can-use-better-data-and-regulations-to-stop-industries-from-choking-its-cities/) [S].

**Remote sensing of point sources.**

- [Climate TRACE's plume tool](https://climatetrace.org/news/plumes-frequently-asked-questions)
  covers 9,560 PM2.5 sources in 2,572 urban areas using HYSPLIT dispersion on estimated
  emissions (Carnegie Mellon CREATE Lab). In its own words a model, not a measurement. India
  facility count not confirmed. [S]
- TROPOMI resolves SO₂ and NO₂ plumes from large power plants and smelters; India is
  repeatedly ranked the top SO₂ emitter by this method. Nothing measures particulate from an
  individual stack from orbit. [R]

**Black carbon.**

- Aethalometers (Magee AE33, ~$30–40k) measure light absorption on a filter. [R]
- ISRO's ARFINET has 32 to 40+ observatories depending on source and date; 19 had continuous
  aethalometer data in a [2021 Current Science paper](https://eprints.iisc.ac.in/73996/1/cur_sci_120-2_341-351_2021.pdf). [S]
- IMD runs a separate black carbon network; no station count found. [S]
- Black carbon is not in India's ambient standards and CPCB stations do not report it. [R]
- No fixed low-cost black carbon network in India was found. The Bengaluru mobile work is the
  densest dataset found.

**Boundary-layer height.**

- IITM and IMD installed ["SkyCast"](https://tropmet.res.in/other-pdfs/Press_Release_SkyCast_System.pdf)
  at Delhi airport (reported May 2026): a CL61 lidar ceilometer, radar wind profiler, SODAR
  and microwave radiometer, descended from the WiFEX fog experiment. [S]
- IITM has [Lufft CHM 15k ceilometers](https://blog.otthydromet.com/en/several-lufft-ceilometers-keep-sky-over-india-in-view)
  at Delhi airport and Solapur, with two more requested. [S, vendor blog]
- IIT Delhi ran a ceilometer over Delhi-NCR in 2022. PRL runs an Indian Lidar Network. A
  [Raman lidar ran at Gual Pahari](https://amt.copernicus.org/articles/12/2595/2019/) for
  about a year. [S]
- IMD launches radiosondes at a few dozen stations, nominally twice daily. [R]
- No national ceilometer count and no public real-time mixing-height feed was found. This
  bears directly on [`gaps.md`](gaps.md) G3: the instruments exist at Delhi airport, but as
  aviation and research assets, not open data.

### A5. Regulatory standing of low-cost sensor data

Effectively none, and CPCB has been actively cautious.

- **March 2022:** a CPCB letter said low-cost sensor data "may not be used for public
  information". Indore kept its 20 sensors anyway. A UP official said the test is whether the
  technology is "duly validated by the designated authority".
  ([Bhattacharji, Sep 2022](https://whatamibreathing.substack.com/p/indias-battle-for-low-cost-air-pollution)) [O]
- **Certification:** the CSIR-NPL instrument certification scheme
  [left sensor-based instruments out](https://www.downtoearth.org.in/air/sensor-based-air-quality-monitoring-instruments-left-out-of-new-certification-scheme-66447). [S]
- **July 2023:** a [Lok Sabha reply](https://eparlib.sansad.in/bitstream/123456789/2503579/1/AU472.pdf)
  said expert working groups were preparing specifications, performance criteria and
  calibration protocols for low-cost devices. No published output found. [S]
- **BIS:** a [draft Indian Standard](https://www.services.bis.gov.in/tmp/WCCHD35027689_01102025_1.pdf)
  for sensor-based PM2.5/PM10 instruments exists (drafts dated Nov 2024 and Oct 2025), scoped
  to indicative measurement; it says sensors are "not currently at par with regulatory grade
  instruments". Not confirmed final. [S]
- **NCAP:** the 2019 document envisaged blending manual, continuous, sensor and satellite
  monitoring, but compliance is judged on CPCB stations only. [S]
- **States and cities using sensors anyway, as indicative:**
  - Bihar SPCB co-branded AMRIT devices, though its chairman now questions the data. [O]
  - UP is a partner and [reportedly plans expansion](https://www.theweek.in/news/sci-tech/2025/07/07/ai-powered-air-quality-sensors-in-uttar-pradesh-reveal-disturbing-pollution-trend-iit-kanpur-ibm.html)
    under the World Bank programme. [S]
  - BMC Mumbai is buying sensors (MANAS) and mandates PM monitors at construction sites. [S]
  - Delhi's planned sensor mesh is explicitly "not to be used for overall air quality
    monitoring". [S]
- CSTEP issued [guidance in Nov 2025](https://cstep.in/wp-content/uploads/2025/11/Guidance-for-Evaluating-the-Performance-and-Use-of-Air-Quality-Sensors-for-Construction-Dust-PM10-Monitoring.pdf)
  on evaluating sensors for construction-dust PM10. [S]

---

## B. The landscape

### B1. Government and reference-grade

| Effort | Size and place | Runs / funds | Open data | Status | Tag |
|---|---|---|---|---|---|
| CPCB CAAQMS | 565–571 stations, ~294–299 cities ([CREA 2026](https://energyandcleanair.org/wp/wp-content/uploads/2026/01/CREA_Tracing-the-Hazy-Air-2026_-Progress-Report-on-National-Clean-Air-Programme-NCAP.pdf); CSE Feb 2026) | CPCB, state boards; NCAP and Finance Commission money | Yes: [CPCB portal](https://airquality.cpcb.gov.in/ccr/), data.gov.in, [GitHub mirror](https://github.com/Vonter/india-cpcb-aqi) under ODbL | Live; portal returned HTTP 200 | [S] counts; [O] portal up |
| CPCB manual NAMP | 966–1,035 stations, ~419 cities | CPCB, state boards | Annual summaries; twice-weekly filter samples | Live; NCAP target of 1,500 by 2024 missed | [S] |
| Delhi (DPCC, CPCB, IMD) | ~40–46 stations, 13 more tendered, target 60 by Nov 2026 | Delhi govt | Via CPCB | Live; [siting criticised](https://www.newslaundry.com/2025/12/01/two-thirds-of-delhi-does-not-have-reliable-air-quality-data) | [S] |
| Bihar | 35 reference stations for ~127M people | BSPCB | Via CPCB | Live | [O] |
| UP + Bihar combined | ~110 government monitors | State boards | Via CPCB | Live | [S] |
| Bengaluru | 14 CAAQMS | KSPCB | Via CPCB | Live | [S] |
| [SAFAR](https://safar.tropmet.res.in/?menu_id=264) | ~10 stations each in Delhi, Pune, Mumbai, Ahmedabad | IITM, Ministry of Earth Sciences | Website and app; no bulk API known | [Pune portal](https://ews.tropmet.res.in/pune/index.php) showed live readings Nov 2025; Ahmedabad unclear | [S] |
| US Embassy and consulates | 5 BAMs: Delhi, Mumbai, Kolkata, Chennai, Hyderabad | US State Dept | Was on AirNow | [Stopped 4 Mar 2025](https://aqicn.org/city/india/new-delhi/us-embassy); no restoration found ([CREA](https://energyandcleanair.org/us-embassy-aq-data-halt/)) | [S]; city list [R] |
| ISRO ARFINET (black carbon, AOD) | 32–40+ observatories | ISRO | On request | Live | [S] |

### B2. Low-cost sensor networks

| Effort | Sensors and place | Runs / funds | Open? | Status | Tag |
|---|---|---|---|---|---|
| **[AMRIT](https://atman.urbansciences.in/amrit/)** (ATMAN centre, IIT Kanpur) | ~1,360 installed: 534–538 Bihar, 826 UP, one per block | Tripathi group. Open Philanthropy $2.5M (Jun 2022). Hardware from [Respirer](https://respirer.in/our-projects/project-amrit) (700+) and [Airveda](https://www.airveda.com/blog/iit-kanpur) (690) | No public dashboard, download or licence on the project page. A 2022 press line promised real-time public data | Installed; an ES&T paper on Bihar came out Nov 2025. Grant was 3 years, so at or near its end. Share still reporting unknown | [O] page and Mongabay; [S] counts |
| [ATMAN centre](https://www.iitk.ac.in/establishes-coe-named-atman-for-monitoring-air-quality) | Umbrella for AMRIT, sensor R&D, airshed work | IIT Kanpur; Bloomberg, Open Philanthropy, Clean Air Fund | — | Live | [S] |
| [SATVAM](https://cms.respirer.in/?p=6518) (IIT Kanpur and partners) | ~100 sensors in 7 cities, 2017–2022 | Indo-US science funding, Respirer | Papers only | Ended | [S] |
| Mumbai MANAS (BMC) | [75 planned, cut from 250; 40 due by Apr 2026](https://www.freepressjournal.in/mumbai/mumbai-to-install-75-hyperlocal-air-quality-sensors-under-manas-project-40-to-be-operational-by-april-end) | BMC; IIT Kanpur supplying (one report says IIT Bombay) | Unknown | Partly deployed at best | [S] |
| [Delhi sensor mesh](https://www.magzter.com/stories/Newspaper/Hindustan-Times-Delhi/Delhi-plans-mesh-of-sensors-to-monitor-bad-air-hot-spots) | Proposal for the 13 hotspots; IIT Kanpur MoU reported May 2026 | DPCC, Delhi govt | Stated as not for official use | Announced only | [S] |
| [Google Air View+](https://blog.google/intl/en-in/company-news/using-googles-ai-and-local-ecosystem-to-generate-actionable-air-quality-insights-in-india-with-air-view/) | "150+ cities"; sensor count not published | Google, with Aurassure and Respirer; validation by IIT Delhi, IIT Hyderabad, CSTEP | Visible in Google Maps; no bulk download known | Live since Nov 2024 | [S]; download point [R] |
| Aurassure (Bhubaneswar) | Company claims [2,000–2,400 devices in 200+ Indian cities](https://inc42.com/buzz/climatetech-startup-aurassure-raises-inr-25-cr-to-expand-internationally); includes industrial clients such as SAIL Rourkela. [Says it is Google's largest Air View+ partner](https://yourstory.com/2025/06/aurassure-climate-risk-data-platform) | Venture-funded (₹25 crore, Dec 2025); customers pay | Has an API; terms not verified | Live | [S, company claims] |
| Respirer Living Sciences (Atmos) | Company claims [2,000–2,500 devices](https://yourstory.com/2025/05/respirer-air-quality-india-tech), including ~700 in AMRIT and ~100 for Air View+ | Founder Ronak Sutaria; Open Philanthropy $572K for an NCAP tracker | Dashboards; API terms not verified | Live | [S] |
| Airveda | 690 for AMRIT; "hundreds" via NGOs; a 2019 Gurugram plan for ~200 | Founder Namita Gupta | App and map | Live | [S] |
| Oizom (Ahmedabad) | [129 in 9 Smart Cities](https://prnewswire.com/in/news-releases/oizom-sets-up-129-air-quality-monitors-across-9-smart-cities-in-india-836305727.html) (2022); 300+ construction-site units | Commercial | Client dashboards | Live | [S] |
| Prana Air | Company claims [5,000+ devices](https://yourstory.com/2025/12/startup-prana-air-citizens-air-with-data-and-devices), largely consumer and indoor | Commercial | App | Live | [S] |
| CSTEP Bengaluru | 40-node multipollutant network since Jul 2024 (60 in one abstract; earlier 55-node PM network). [Indi-SET](https://cstep.in/?p=14098) evaluation centre has tested 150+ sensors | CSTEP; Open Philanthropy $2M; Google | CSTEP says the data is "currently not available online" | Live | [S] |
| ILK Labs (Bengaluru) | Mobile lab plus sensors; co-ran the Bengaluru mapping | Small research lab | Papers and code | Active | [S] |
| IIT Delhi, Berkeley and CEEW ("Air Quality Sensors in South Asia") | 80+ sites across 15+ settlements, rural to urban, north India | Open Philanthropy: $700K Berkeley, $410K CEEW, $228K IIT Delhi (2020–21) | PurpleAir-based, so partly on the PurpleAir map | Unknown | [S] |
| Sudarshan, Pande, Subramanian with Kaiterra | 28 in Delhi, 2018–2020 | NYU, Yale, EPoD India; NSF | Confidential | Dead | [O] |
| Indore | 20 sensors | City | Unknown | 2022; unknown now | [O] |
| PurpleAir in India | No national count found | Individuals and research groups | Open map; API needs a key | Live, small | [S] |
| AirGradient in India | 34 public locations, all online; top contributor "BreatheOSS" with 10 | Individuals | [Fully open API](https://api.airgradient.com/public/api/v1/world/locations/measures/current) | Live | [O, live pull] |
| Sensor.Community in India | 0 of 17,701 records | — | [Open](https://data.sensor.community/static/v2/data.json) | Absent | [O, live pull] |
| OpenAQ India | Not verified (API needs a key). Globally 75% of its locations are reference-grade | OpenAQ | Open | Live | [S] |

### B3. Models, data products, others

| Effort | What | Open? | Status | Tag |
|---|---|---|---|---|
| UrbanEmissions (Guttikunda) | Emissions inventories, forecasts, monitoring-needs analysis; Open Philanthropy $650K | Largely open | Active | [S] grant; [R] rest |
| SAANS (IIT Delhi, Dey) | 1 km satellite PM2.5, 2000–2019 | Portal | Published | [S] |
| CREA | Monthly India snapshots, NCAP tracker, satellite PM2.5 by district | Reports | Active | [S] |
| Climate TRACE | Modelled PM2.5 plumes from large facilities | Open | Active; India coverage unverified | [S] |
| Blue Sky Analytics | Satellite-derived air and emissions datasets (BreeZo app) | Commercial | Current status not verified | [S, old] |
| Ambee | Air-quality API blending public and model data | Commercial | Not verified | [R] |
| Kaiterra | Supplied the Delhi 28; now mainly indoor commercial | — | No ambient India network found | [O] role; [R] rest |
| Clarity | Hardware behind Breathe London; India deployments not found | — | Not found | [S] |
| AirVoice | Not found | — | Not found | — |
| EPIC India, J-PAL | Surat and Ahmedabad emissions markets on CEMS; star-rating disclosure schemes; small Open Philanthropy grant to U Chicago ($73K, "Air Quality Monitoring Research") | Papers | Active | [S] grant; [R] rest |
| Microsoft in Bengaluru | Nothing found | — | Not found | — |
| Pune city sensors | Nothing current found | — | Not found | — |
| Breathe London-style replication | Breathe Cities reportedly covers 14 Indian cities ([TERI](https://www.teriin.org/article/clean-air-choked-finance-why-indias-war-air-pollution-running-out-cash)); whether that includes sensor networks is unverified | — | Unverified | [S] |
| Independent industrial emissions verification | No Indian startup found doing third-party particulate or SO₂ stack verification. Nearest: Aurassure and Oizom (the polluter is the customer), Pixxel (hyperspectral, no confirmed PM use), ICCT (vehicles) | — | Open field as far as can be seen | [S] |

### B4. Funders

**Coefficient Giving / Open Philanthropy.** Figures from a
[third-party mirror of the grants database](https://www.longtermwiki.com/organizations/coefficient-giving/divisions/coefficient-giving-air-quality),
not the database itself; it totals $21M against Harish's ">$35M". All [S].

| Recipient | Purpose | Amount | Date |
|---|---|---|---|
| GDi Partners | Air quality governance | $2.6M | Oct 2022 |
| IIT Kanpur | Rural monitoring (AMRIT) | $2.5M | Jun 2022 |
| CSTEP | Centre for Air Pollution Studies | $2M | Aug 2023 |
| World Bank (IBRD) | IGP air quality | $2M | Feb 2023 |
| Asar | Clean Air Hubs | $1.6M | Nov 2022 |
| UC Berkeley, IIT Bombay, CSTEP, U Washington | PAVITRA modelling tool | $1.3M, $648K, $565K, $443K | 2022 |
| WRI | City government support | $1.2M | Jan 2023 |
| UC Berkeley, CEEW, IIT Delhi | Air quality sensors in South Asia | $700K, $410K, $228K | 2020–21 |
| UrbanEmissions | Modelling and forecasting | $650K | May 2022 |
| Respirer | NCAP tracker | $572K | Mar 2023 |
| Health Effects Institute | City assessments | $297K | Sep 2023 |
| IIT Delhi | Truck emissions | $163K | Jan 2025 |
| IISER Mohali | North India research | $104K | Oct 2023 |
| U Chicago | Monitoring research | $73K | Aug 2023 |
| DRIIV Foundation | Sensors in Delhi | $52K | May 2024 |

Measurement hardware is about $4M of this. The rest is governance, modelling and policy,
which matches the note in [`reading.md`](reading.md) §3. Coefficient's own account of the
AMRIT grant: [Cool Things Our GHW Grantees Accomplished in 2023](https://coefficientgiving.org/research/cool-things-our-grantees-accomplished-in-2023/). [S]

**Other funders.**

- **[EPIC Air Quality Fund](https://epic.uchicago.edu/news/new-1-5-million-fund-aims-to-expand-access-to-air-quality-data-to-1-billion-people-by-2030/):**
  seeded with $1.5M from Open Philanthropy; funds outdoor PM2.5 monitors with open-data
  requirements in countries with little monitoring. No Indian grantee found; recent awards
  went to Pakistan, Burkina Faso and others. Lists Aurassure and Airveda among vendors. [S]
- **[Clean Air Fund](https://www.cleanairfund.org/geography/india/):** India is one of its
  oldest and largest portfolios, 14 partners, IGP focus. 2023: $3.5M to India, of which
  $2.38M for data. Grants include IIT Kanpur's centre of excellence and technical assistance
  to UP. [S]
- **Bloomberg Philanthropies:** [2019 NCAP technical-assistance initiative](https://climatesamurai.com/2019/02/12/bloomberg-philanthropies-announces-initiative-to-support-indias-national-clean-air-program/)
  with TERI and Shakti; named supporter of ATMAN; Breathe Cities. [S]
- **Shakti Sustainable Energy Foundation:** funded the 2018–19 Respirer and IIT Kanpur 10-city
  network; wrote a [2022 funding-landscape report](https://shaktifoundation.in/wp-content/uploads/2022/05/Funding-AQ-Action.pdf). [S]
- **World Bank:** [$600M approved 10 Dec 2025](https://www.worldbank.org/en/news/press-release/2025/12/10/india-world-bank-approves-financing-for-programs-to-promote-clean-air-in-haryana-and-uttar-pradesh-states):
  UP Clean Air Management Program $299.66M and Haryana Clean Air Project $300M (Gurugram,
  Sonipat, Faridabad). Monitoring component size not found. [S]
- **TERI estimate:** ~₹220 crore of philanthropic money for clean air in 2021–25; over 90% of
  multilateral money is loans. [S]
- **Rohini Nilekani Philanthropies:** no air-quality grants found; stated environment focus is
  resilience and biodiversity. [S]
- **Ashraya Hastha Trust:** nothing found.
- **USAID:** a "Cleaner Air and Better Health" programme that ended with the 2025 USAID
  wind-down. [R, unverified]

### B5. Researchers and groups

[R] unless tagged.

- **S.N. Tripathi (IIT Kanpur):** runs ATMAN and AMRIT; aerosol science, sensor networks,
  real-time source apportionment. [O/S]
- **Sagnik Dey (IIT Delhi):** satellite-derived PM2.5 and health exposure; SAANS. [S]
- **Sarath Guttikunda (UrbanEmissions):** open emissions inventories, forecasts, and how many
  monitors India actually needs.
- **Anant Sudarshan (Warwick):** CEMS standards, the Surat emissions market; co-author on the
  Delhi sensor papers. [O]
- **Santosh Harish (Coefficient Giving):** leads the Air Quality Fund; previously CPR and EPIC
  India. [O]
- **Pallavi Pant (Health Effects Institute):** health evidence and data access in South Asia.
- **Joshua Apte (UC Berkeley):** mobile monitoring and exposure science; co-author on the
  Bengaluru mapping. [S]
- **Julian Marshall (U Washington):** reduced-complexity models; Bengaluru co-author. [S]
- **Kalpana Balakrishnan (SRIHER Chennai):** household air pollution and health cohorts.
- **Chandra Venkataraman (IIT Bombay):** emissions inventories, black carbon, the PAVITRA
  model. [S for PAVITRA]
- **Bhargav Krishna (Sustainable Futures Collaborative):** air-quality governance and health
  policy.
- **Sachin Ghude (IITM):** forecasting, the Delhi early-warning system, WiFEX fog experiment.
- **Lakshminarayanan Subramanian (NYU), Rohini Pande (Yale):** the Delhi 28-sensor papers. [O]
- **Pratima Singh, V. Sreekanth (CSTEP):** sensor evaluation, Bengaluru network. [S]
- **Adithi Upadhya, Meenakshi Kushwaha (ILK Labs):** mobile monitoring, open tools. [S]
- **Ronak Sutaria (Respirer), Namita Gupta (Airveda):** the two AMRIT hardware suppliers. [S]
- **Michael Greenstone (EPIC):** AQLI, emissions markets.
- **Anumita Roychowdhury (CSE):** monitoring-gap analyses. [S]

---

## The plain answers

### How many low-cost sensors are deployed and publicly readable?

| Stage | Count | Basis |
|---|---|---|
| Announced or claimed | ~5,000–8,000 ambient nodes | Vendor claims: Aurassure ~2,000–2,400; Respirer ~2,000–2,500; Airveda 700+; Oizom a few hundred. AMRIT's 1,360 sit inside the Respirer and Airveda figures; some vendor units are on factory fences or indoors. [S] |
| Documented as installed in a named public network | ~1,600–1,800 | AMRIT ~1,360, CSTEP 40–60, Mumbai 40 or fewer, Indore 20, plus an unpublished Air View+ count. [S] |
| Still reporting | Unknown | No network publishes uptime. The one that did (Sudarshan) ran at 30%. [O] |
| Viewable on a map | Low thousands at most | Google Maps and vendor apps. [S/R] |
| Openly downloadable without an agreement | 34 confirmed | AirGradient 34 [O]; Sensor.Community 0 [O]; PurpleAir and OpenAQ unverified, probably tens to low hundreds. AMRIT has no public feed that could be found. [O] |

### How does that compare?

| Place | Network | Per million people |
|---|---|---|
| India, reference | 565–571 CAAQMS [S] | ~0.4 |
| UP + Bihar, AMRIT | ~1,360 low-cost for roughly 370M [S] | ~3.7 |
| China, reference-grade | 1,734 national plus [10,588 local automatic air stations](https://events.development.asia/sites/default/files/materials/2024/03/202403-air-quality-monitoring-development-and-application-china.pdf) (3,503 county, 7,085 township) [S]; city micro-sensor grids on top [R] | ~9 |
| London, [Breathe London](https://breathelondon.org/about) | ~350 active (428 nodes in 2023), open data [S] | ~40 |
| US, PurpleAir | ~13,000 stations listed by a third-party aggregator [S]; tens of thousands registered, mostly US [R] | tens |

China has about 20× India's reference density. London has about 10× the low-cost density of
India's best-covered states, and it is open.

### Crowded, thin, or lopsided?

Thin, with three qualifications.

- It is crowded with **vendors**. At least five Indian hardware firms sell much the same
  Plantower-class node, so one more sensor box is the wrong entry.
- It is lopsided towards Delhi-NCR, Bengaluru, Mumbai and the AMRIT states. Delhi is the only
  place where reference coverage is dense.
- AMRIT is a single, philanthropically funded three-year project at the end of its grant,
  with a state regulator publicly doubting it and no open feed. One project does not make a
  field.

### Visible holes

1. **Open data.** The largest networks are closed or view-only. An open, documented, licensed
   feed of calibrated sensor data does not exist at scale.
2. **Uptime and quality reporting.** Nobody publishes which sensors are alive, drift, or
   calibration error by season.
3. **Geography.** Rural India outside UP and Bihar; the north-east, central India, Odisha,
   Jharkhand, Chhattisgarh, Rajasthan; small towns generally. [S]
4. **Black carbon.** Not regulated, not in CAAQMS, a few dozen research aethalometers, no
   low-cost network found.
5. **Vertical structure.** A handful of ceilometers and one airport suite; no open
   mixing-height data. [`gaps.md`](gaps.md) G3 depends on exactly this.
6. **Industrial stacks.** CEMS exists but is paid for by the polluter and not legally usable;
   no independent verifier found; satellites cannot see particulate stacks. See
   [`../bets/README.md`](../bets/README.md), "Where a company could exist".
7. **Regulatory pathway.** A BIS draft and working groups, but no finished certification, so
   sensor data cannot trigger enforcement.
8. **Composition.** Sensors give mass only; real-time speciation exists at one or two
   supersites. [S]
9. **Operations after the grant.** Who maintains 1,360 rural nodes once philanthropic money
   ends is unanswered.

---

## What could not be verified

- **Coefficient's own grants database.** A third-party mirror was used; totals disagree ($21M
  vs ">$35M").
- **AMRIT live status and data access.** No dashboard on the project page, but one may exist
  elsewhere. The ES&T paper and its data-availability statement were not opened.
- **Vendor counts** for Aurassure, Respirer, Airveda, Oizom and Prana Air are company claims
  from snippets; the ambient / industrial / indoor split is unknown.
- **Google Air View+ sensor count** and whether any data can be downloaded.
- **PurpleAir and OpenAQ India counts.** Both APIs need keys. With keys this is a ten-minute
  check.
- **Whether CPCB has issued any low-cost sensor guideline since 2023,** and whether the BIS
  draft is final.
- **The CPCB March 2022 letter itself.** Only a journalist's account was read.
- **Mumbai MANAS:** supplier (IIT Kanpur or IIT Bombay), unit cost, how many are live.
- **Delhi sensor mesh and the IIT Kanpur MoU:** dates and scope are from snippets with
  inconsistent dating.
- **Not found at all:** Microsoft in Bengaluru, Pune city sensors, AirVoice, Clarity in India,
  Ashraya Hastha Trust, Rohini Nilekani air grants, any Google Street View or Aclima India
  campaign.
- **Recall only:** USAID programme history, Ambee, Kaiterra's current business, US consulate
  city list, radiosonde station count, hardware module prices, most researcher one-liners.
- **Unconfirmed status:** Blue Sky Analytics; SAFAR Ahmedabad; whether "Vayu Rakshak" vans
  measure anything.
- **IMD black carbon station count** and any national ceilometer inventory.
- **Climate TRACE India facility count.**
- **World Bank programmes:** how much goes to monitoring; the reported UP sensor expansion.
- **arXiv 2410.04309:** the last quarter of the text was not read; the sensor's internal
  module is not named in either paper.
- **Zheng 2018 and 2019, Campmier 2023, Sahu 2021, Dey 2020, CSE CEMS report:** numbers are
  from search summaries, not the papers.
- **Breathe Cities "14 Indian cities"** and whether it includes sensors.
- **China and PurpleAir totals:** China from a snippet of a 2024 official deck; PurpleAir from
  an aggregator plus memory.
