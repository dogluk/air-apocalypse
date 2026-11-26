# airhealth: what cleaner air would buy India, and why the answers disagree

`airhealth` takes a change in the air an Indian place breathes and says how many deaths it
would postpone, how many years of life it would add, and how much those cost if the change
has a price. It runs from the terminal, and every number it prints names the assumptions it
rests on.

The published answers to "how many people does India's air kill?" differ several-fold. The
differences come from a few choices that are rarely shown side by side: which **risk curve**
turns pollution into deaths, which **exposure map** says how polluted each place is, and how
time and money are counted. This tool makes those choices visible instead of hiding them
inside one number.

The question it was built for: Delhi's air holds around 90 to 100 µg/m³ of fine particles
over a year (88 to 99 on the two satellite maps here, 94 to 105 at its monitors). What if
it went from 100 to 80?

```
$ airhealth compare Delhi --from 100 --to 80
Delhi (state): PM2.5 100 → 80 µg/m³
Population 21.5 M; all-cause deaths 99,440 a year (4.6 per 1,000). Steady state, per year.

curve                  PM2.5 µg/m³  % of deaths  deaths/yr  life exp. yrs  life-years/yr
--------------------  ------------  -----------  ---------  -------------  -------------
loglinear_jaganathan  100.0 → 80.0        15.2%     15,126          +2.25        313,030
loglinear_brown       100.0 → 80.0         1.9%      1,855          +0.24         33,076
loglinear_vodonos     100.0 → 80.0        13.8%     13,744          +1.97        228,651
gemm_ncd_lri          100.0 → 80.0         4.1%      4,031          +0.53         67,113
aqli *                100.0 → 80.0        13.4%     13,330          +1.96        275,862
...
```

Same place (the state of Delhi), same change, same population and death rates: between
1,900 and 15,000 deaths a year, and between a quarter of a year and two and a quarter years
of life expectancy, depending only on the curve. No study has followed people who breathe
air this dirty for years, so every curve is being stretched past its evidence here; the tool
shows how far apart the stretches land rather than picking one.

**A few terms, defined once.**
**PM2.5** is the mass of fine particles (smaller than 2.5 thousandths of a millimetre) in a
cubic metre of air, in micrograms (**µg/m³**). Every number here is an **annual mean**: the
average over a whole year, which is what the long-term studies measure. A
**population-weighted** mean counts each district by how many people live in it.
A **risk curve** says how much the death rate rises at a given PM2.5 level, as a **relative
risk** (1.15 means 15% more deaths than in clean air). Each curve has a **floor**, the level
below which it assumes no further benefit (2 to 5 µg/m³ here). An **exposure map** gives
PM2.5 and population for each district, state or city. **Steady state** means the effect
once the new air has been breathed long enough for the full benefit, at today's population
and age structure. **Life expectancy** is the average age at death if today's death rates
held for a lifetime. **Life-years** are the extra years lived: here, each death postponed
times the years a person of that age would still expect to live. The **crude death rate** is
deaths in a year per 1,000 people. The **SRS** (Sample Registration System) is the
government survey that measures India's death rates.

**Before you quote a number from this tool.** It does not yet reproduce the Global Burden of
Disease's own count for India. GBD 2023 reports 969,726 deaths from outdoor PM2.5 in India in
2023; on GBD's own curve, map and year this tool gives 1.61 million. The likely main reason is
that GBD splits one risk between outdoor air and cooking smoke, and this tool scores outdoor
air alone. That has not been shown with numbers yet (see "The IHME tier" below and
`IHME_DOWNLOADS.md`). No air pollution specialist has reviewed the method yet either; the
calls made along the way are listed under "Known limitations" so that one can.

## Install

```
cd air-apocalypse
python3 -m venv .venv
.venv/bin/pip install -e "health[dev]"
cd health
../.venv/bin/python -m pytest -q
../.venv/bin/airhealth --help
```

Python 3.11 or newer. Everything the commands need is committed under `data/`, with its
source, page and method in `data/sources.toml`. A value that could not be confirmed at its
source is left out and listed in `data/MISSING.md`. The few sourced numbers that live in
code instead of a data file (AQLI's 0.98, GEMM's 2.4, the lag shares and so on) are listed
with their sources by `airhealth.provenance.constants()`, and the tests check both.

## The commands

Add `--json` to any command for the same content as JSON, and `--debug` to see the full
traceback of an error instead of one line. Every table ends with one line naming the
exposure map and its year, how the death counts were scaled (see "How many deaths a year"
below), a city's population year where a city is used, the states that had to borrow
all-India death rates, and the curves that could not run, with why.

### `list`: what the tool knows, each with its source

```
$ airhealth list curves
loglinear_jaganathan  [yes]
  Log-linear, Jaganathan 2024 (Indian districts, all-cause, all ages)
  Source: Jaganathan S, Stafoggia M, Rajiva A, et al. Estimating the effect of annual PM2.5 exposure on mortality in India: a difference-in-differences approach. Lancet Planet Health 2024; 8: e987-96. doi:10.1016/S2542-5196(24)00248-1. https://pmc.ncbi.nlm.nih.gov/articles/PMC11790315/

loglinear_brown  [yes]
  Log-linear, Brown 2022 Million Death Study (non-accidental; studied at ages 15-69, applied from 15, extrapolated above 69)
  Source: Brown PE, Izawa Y, Balakrishnan K, et al. Mortality associated with ambient PM2.5 exposure in India: results from the Million Death Study. Environ Health Perspect 2022; 130(9): 097004. doi:10.1289/EHP9538. https://pmc.ncbi.nlm.nih.gov/articles/PMC9472672/
...
```

`list maps` and `list places` work the same way; `list maps` says which years can give
results (the population projections start in 2011). Places are India, its states and union
territories, its districts, and fifty cities (the 49 airsheds of APnA's source apportionment
plus Delhi; `data/cities.csv`); any common spelling is accepted ("Orissa", "NCT of Delhi"), and a
misspelling gets suggestions.

A bare name that is both a city and a district is the city: `airhealth place Patna`, Gaya, Kota,
Agra, Nagpur, Indore, and also Raipur, Hubli, Asansol, Dhanbad (aliases of their twin-city airshed)
mean the city, which runs on the `cpcb` map with its Census 2011 population, not the AQLI
district. The district needs `--kind district` (`airhealth place Patna --kind district`;
`"Patna, Bihar"` also returns the city). Delhi, Chandigarh and Puducherry are the other way: the
bare name is the state or union territory, and the city (airshed) needs `--kind city`.
Intervention files take bare names, so they get these defaults.

### `causes`: what a city's PM2.5 is made of, every study side by side

```
$ airhealth causes Kanpur
Kanpur: PM2.5 by source, each column one study and season; % of the study's own total, — = not reported
                      apna_2015  iitk_kanpur2022  iitk_kanpur2022  mcduffie2021
                                             pmf              pmf
season                   annual           summer           winter        annual
--------------------  ---------  ---------------  ---------------  ------------
transport                  13.7              7.1             29.9           7.9
residential                33.8                —                —          28.3
...
outside                    22.5                —                —             —
other                         —              3.5              3.5          19.5
total                      99.5              100              100           100

Studies:
  apna_2015: CAMx, sampled 2015, boundary airshed_box, origin inside, region, evidence O
    https://zenodo.org/records/6919069
  ...
```

One column per study and season, one row per source (the harmonised names, in a fixed order), a total row, and a footer naming each study's method, year, boundary, origin, URL and evidence key. By default only complete splits (`covers = all`) are columns; partial estimates such as stubble-only shares are counted and listed under the table so Delhi's twenty-odd groups stay readable, and `--all` makes them columns too (marked `[P]`; emission shares are marked `[E]`). `--study ID` and `--season S` filter. `airhealth causes` alone lists the fifty cities and how many studies each has. `list inputs` shows the entry; choosing a split per run comes later.

### `compare`: one place, one change, every curve

Shown above. `--from` sets the starting level for every district (the map then supplies
only the population); without it, the start is the map's own level for the place, and
`--to` is the new level. A row marked † moves below its curve's floor, where that curve
counts no further benefit.

### `burden`: how many deaths the air above clean causes now

```
$ airhealth burden India
India (country): deaths attributable to PM2.5 above each curve's own floor
Population 1,390.3 M; all-cause deaths 9,365,088 a year (6.7 per 1,000). Steady state, per year.

curve                 PM2.5 µg/m³  % of deaths  deaths/yr  life exp. yrs  life-years/yr
--------------------  -----------  -----------  ---------  -------------  -------------
loglinear_jaganathan   41.2 → 5.0        24.9%  2,330,382          +4.57     52,713,154
loglinear_brown        41.2 → 2.0         3.4%    317,302          +0.49      5,569,093
loglinear_vodonos      41.2 → 5.0        21.5%  2,011,718          +3.71     32,923,691
gemm_ncd_lri           41.2 → 2.4        16.4%  1,531,850          +2.59     24,997,876
aqli *                 41.2 → 5.0        20.1%  1,884,068          +3.55     42,486,945

  loglinear_jaganathan: Log-linear, Jaganathan 2024 (Indian districts, all-cause, all ages)
  loglinear_brown: Log-linear, Brown 2022 Million Death Study (non-accidental; studied at ages 15-69, applied from 15, extrapolated above 69)
  loglinear_vodonos: Log-linear, Vodonos 2018 meta-regression (all-age all-cause in the paper, applied from age 25: the pooled studies are adult cohorts), slope at a study mean of 30 µg/m³ (the published slope falls with concentration; one slope misstates it)
  gemm_ncd_lri: GEMM NCD+LRI (Burnett 2018), age-specific
  aqli: AQLI linear, 0.98 years of life expectancy per 10 µg/m³
  * deaths derived from the life-expectancy change, not a relative risk

Map: aqli 2023 (AQLI 2025 release, districts, satellite PM2.5 with dust and sea salt removed). Deaths scaled to each state's SRS crude death rate for 2020-24: ×0.87 overall, ×0.57 to ×0.95 by state (data/death_reconciliation.csv); life expectancy is from the unscaled life tables. Sources: population by age, projection (default); death rates by age, srs (default); death count, srs (default). All-India death rates used for Andaman & Nicobar Islands, Arunachal Pradesh, Chandigarh, Dadra & Nagar Haveli, Daman & Diu, Goa, Ladakh, Lakshadweep, Manipur, Meghalaya, Mizoram, Nagaland, Puducherry, Sikkim, Tripura (no SRS life table). Not run: gbd2019, gbd2023, gemm_5cod: need IHME files in health/data_local/ (see health/IHME_DOWNLOADS.md).
```

AQLI gives a change in life expectancy, not a relative risk. To put it in the same table,
the tool finds the single multiplier on death rates that produces AQLI's change and reports
the deaths that implies; the star marks those as derived. This is the command the
benchmarks below use. `--counterfactual C` measures against C µg/m³ instead of each curve's
floor.

### `chart`: the curves, with places marked

```
$ airhealth chart Delhi India
/path/to/air-apocalypse/health/charts/curves_delhi.png
```

![The risk curves from 0 to 150 µg/m³, with Delhi and India marked](charts/curves_delhi.png)

The shaded band starts at 84 µg/m³, the highest long-term exposure in any group of people
behind the GEMM curve. Everything to its right is extrapolation.

### `dashboard`: a local page over the same numbers

```
airhealth dashboard            # opens http://127.0.0.1:8765/ ; Ctrl-C to stop
```

One page, served only to this machine, with a place picker, the exposure map and its year, a
source for each demographic input (population, death rates, death count) and From/To
sliders. It shows what the change buys on every curve, the burden at the map's level, a map
of PM2.5 by district with the place outlined, the curve shapes, how the three state-level
maps disagree, and a table of every input the result depends on with its sources. It calls
the same functions as `compare` and `burden`, so the numbers match the terminal
(`tests/test_dashboard.py` checks this).

### Sources: a switch for every input

```
airhealth list inputs                                   # every input, its sources, the default
airhealth compare Delhi --to 40 --use deaths=unwpp
airhealth burden India --use deaths=srs,unwpp,model     # a result for each, then the range
```

Population by age, death rates by age and the death count can each come from the Indian
government's figures (the default) or the UN's World Population Prospects 2024; the death
count can also be left unscaled (`model`). The UN publishes India only, so a UN choice keeps
each state's pattern from the Indian sources and takes India's level, age band by age band,
from the UN. Mixing the two is allowed and the result says so. `--deaths X` is shorthand for
`--use deaths=X`; an intervention file can carry a `[sources]` table with the same keys. Every
result's last line names the source of each input. Across every combination for India
(`--to 20`), deaths averted move by about 15%; across the curves they move by about 8 times.

### `run`: an intervention, with odds, cost and uncertainty

An intervention is a short text file (next section). `run` draws 5,000 versions of it: each
draw takes one value of the PM2.5 change (when the file gives a range), one set of curve
parameters from the published uncertainty, and one value of each cost. This is a **Monte
Carlo** simulation; the **5-95% range** is the span holding the middle 90% of draws. Which
curve and which map are never drawn: each curve is its own row, and a run uses one map.

```
$ airhealth run interventions/november_only_delhi.toml
November-only cut in Delhi
Delhi (state). 2027-2036: 10 years, no ramp, lag epa20, counted over 30 years, discounted at 3% a year; these deliver 10.0 years of the full effect, undiscounted. Probability it works: 50%.
Change: monthly delta: Nov -40 µg/m³; other months 0; annual-mean change -3.29 µg/m³ (PM2.5 88.3 → 85.1, population-weighted; median draw).
Population 21.5 M; all-cause deaths 99,440 a year (4.6 per 1,000). 5,000 draws, seed 0.

If it works, totals over the run (median, 5-95% range):
curve                                      life-years                deaths postponed  life exp. at full effect, yrs
--------------------  -------------------------------  ------------------------------  -----------------------------
loglinear_jaganathan     439,000 (353,000 to 525,000)       26,600 (21,400 to 31,900)         +0.36 (+0.29 to +0.44)
loglinear_brown            43,300 (-10,700 to 96,600)           3,050 (-754 to 6,810)         +0.04 (-0.01 to +0.09)
loglinear_vodonos        321,000 (224,000 to 416,000)       24,300 (16,900 to 31,400)         +0.32 (+0.22 to +0.41)
gemm_ncd_lri               93,900 (79,800 to 108,000)          7,070 (6,010 to 8,160)         +0.09 (+0.08 to +0.11)
aqli *                389,000 (no published interval)  23,600 (no published interval)  +0.32 (no published interval)

Expected = mean if it works × probability it works (0.5). Cost if it works: $16 M ($5.08 M to $54.1 M), in 2025 rupees, ₹87.16 per $ (World Bank 2025 average); all of it spent whether or not it works.
curve                 expected life-years  cost per life-year if it works  expected cost per expected life-year
--------------------  -------------------  ------------------------------  ------------------------------------
loglinear_jaganathan              219,000                           $47.4                                 $94.7
loglinear_brown                    21,700                            $479                                  $958
loglinear_vodonos                 160,000                           $64.8                                  $130
gemm_ncd_lri                       47,000                            $221                                  $442
aqli *                            194,000                           $53.4                                  $107
  (costs per life-year are ratios of means over the draws)

What drives the spread in life-years within each curve (share of variance, each part sampled alone):
curve                 PM2.5 change       curve parameters
--------------------  ------------  ---------------------
loglinear_jaganathan            0%                   100%
loglinear_brown                 0%                   100%
loglinear_vodonos               0%                   100%
gemm_ncd_lri                    0%                   100%
aqli *                          0%  no published interval
Across curves, the largest median life-years is 10.1× the smallest.

  loglinear_jaganathan: Log-linear, Jaganathan 2024 (Indian districts, all-cause, all ages)
  loglinear_brown: Log-linear, Brown 2022 Million Death Study (non-accidental; studied at ages 15-69, applied from 15, extrapolated above 69)
  loglinear_vodonos: Log-linear, Vodonos 2018 meta-regression (all-age all-cause in the paper, applied from age 25: the pooled studies are adult cohorts), slope at a study mean of 30 µg/m³ (the published slope falls with concentration; one slope misstates it)
  gemm_ncd_lri: GEMM NCD+LRI (Burnett 2018), age-specific
  aqli: AQLI linear, 0.98 years of life expectancy per 10 µg/m³
  * deaths derived from the life-expectancy change, not a relative risk

Map: aqli 2023 (AQLI 2025 release, districts, satellite PM2.5 with dust and sea salt removed). Life-years = deaths postponed by age × remaining life expectancy at the age of death, at the map year's population and age structure, summed over the 30-year horizon (the intervention's years and the tail of the lag), discounted at 3% a year. Deaths at ages 45 and over scaled by ×0.72 to the SRS crude death rate for Delhi, 2020-24 (4.5 per 1,000); life expectancy is from the unscaled life table. Sources: population by age, projection (default); death rates by age, srs (default); death count, srs (default). Not run: gbd2019, gbd2023, gemm_5cod: need IHME files in health/data_local/ (see health/IHME_DOWNLOADS.md).
```

How to read it:

- **A November-only cut is small on the annual mean.** Forty µg/m³ off November alone is
  40 × 30/365 = 3.3 µg/m³ off the year, and long-term health follows the year. The sky
  changes a lot for a month; the death rate barely moves.
- **"If it works" and "expected" are kept apart.** The first table assumes the intervention
  succeeds. The probability of success is never drawn at random; it multiplies the mean to
  give the expected life-years.
- **Two cost figures.** *Cost per life-year if it works* is mean cost over mean life-years,
  given success. *Expected cost per expected life-year* charges the cost that is spent
  whether or not it works against the life-years you can expect. By default the whole cost
  is spent either way, so the second is the first divided by the probability. All costs are
  turned into **2025 rupees**: a rupee cost is scaled by how much India's prices rose from the
  file's price year to 2025 (the World Bank's GDP deflator, `data/gdp_deflator_ind.csv`); a
  dollar cost is first turned into rupees at the World Bank's annual average rate for its own
  price year (`data/fx_inr_usd.csv`), then scaled the same way. Years 2000-2025 are covered.
  Dollars shown are 2025 rupees at the 2025 rate. The JSON also gives rupees per life-year and
  life-years per crore (1 crore = 10 million rupees).
- **What drives the spread.** Each part is sampled alone with the other held at its median,
  and its share of the variance is shown. In this file the PM2.5 change is a fixed number,
  so all of the spread within a curve comes from the curve's own published uncertainty.
  AQLI publishes no interval for its coefficient, so its row has one value and says "no
  published interval": that is a gap in the evidence, not certainty. (If a file gives the
  PM2.5 change as a range, AQLI's row gets a range marked "PM2.5 change only".)
- **Brown's range crosses zero, on purpose.** Brown 2022's interval reaches a relative risk
  of 1.00. Each curve's slope is drawn from its published interval on the scale it was
  estimated on (the log of the relative risk) and is not cut off at zero, so about one
  Brown draw in eleven has a negative slope: in those draws cleaner air raises deaths, and
  they are the negative end of Brown's range above. They are kept because dropping them
  would push Brown's average above what the paper found. Read the range as "this study
  cannot rule out no effect", not as evidence that cleaner air does harm.
- **Across curves** the medians differ tenfold, far more than any curve's own range.

`--charts DIR` also draws two charts:

![November-only cut in Delhi: life-years by curve, with 5-95% ranges](charts/run_november_only_delhi.png)

![What drives the spread for Delhi from 100 to 80](charts/spread_delhi_100_to_80.png)

Other flags: `--map M` (default: cpcb when every place is a city with ground monitors,
otherwise aqli), `--curves a,b`, `--n N` draws, `--seed S` (the same seed gives the same
answer), `--discount PCT` (default 3; 0 for none), `--use input=source` (see "Sources" above).

**How time is counted in this version.** The steady-state effect is computed once per
draw. Each year of the intervention then realises a share of it. The **ramp** brings the
change in over `ramp_years` in equal steps. The **cessation lag** is how slowly the death
rate follows the air down: by default the US EPA's 20-year lag (30% of the fall in risk in
the first year, 50% spread over years 2-5, 20% over years 6-20); `immediate` puts it all in
year one. Each step of the ramp starts its own lag clock. Deaths postponed and life-years
are the steady-state figures times the sum of those yearly shares.

**The horizon and the tail.** Every measure is counted over the same kind of horizon: its
duration plus the length of its lag (20 years for `epa20`, nothing extra for `immediate`).
When the intervention ends the air goes back, which is one more step (minus the full
level), and that step starts its own lag too, so the benefit still arriving when a measure
stops keeps arriving. A one-year measure under `epa20` delivers all of one year's effect,
spread over 21 years; the old accounting stopped at the last year and dropped the rest.

**Discounting.** Life-years and costs are both discounted at 3% a year (the WHO-CHOICE
base case; the source is in `provenance.constants()`): a life-year in year t counts
1.03^-t, the one-off cost falls at t = 0 and the annual cost in each year of the
duration. Deaths postponed are not discounted. `--discount PCT` changes the rate (`--discount 0` for none).
Life-years are deaths
postponed × remaining life expectancy at the age of death. People who die in a five-year
age band die on average half-way through it, so each death is credited with the life
expectancy of a person alive at that point (in infancy, at the life table's own average age
of infant death), worked out from the life table's own person-years; the open band of 85
and over uses life expectancy at 85. Taking life expectancy at the start of the band
instead, as an earlier version did, overstates life-years by about 7%. A year-by-year cohort
run to 2050, with the population ageing, replaces this accounting in the next version.

## Measures: the library, scored city by city

A measure is something a city (or region) could do about its air, written as one TOML file in
`interventions/library/` (the file name is its id; `_template.toml` is the commented reference
for the format and must stay valid). An **air** measure cuts causes of PM2.5 (dust, transport,
...) by a fraction; an **exposure** measure (purifiers, masks) cuts what a covered share of
people breathe. Each file gives the years, the odds it works (`p_success`, a judgement with its
basis), the cost per person, household, city or unit, and a `[[evidence]]` entry for every
number (key O read at the source, S seen in a snippet or summary, R recalled) or the number is
listed as a `placeholder`.

```
airhealth measures [--json]            # the library: id, name, kind, scope, cities, odds, placeholders, evidence keys
airhealth score CITY [--measure ID ...] [--study ID] [--map M] [--curves a,b] [--n N] [--seed S]
                     [--discount PCT] [--use input=source] [--json]
airhealth score --region ID [--map M] [--curves a,b] [--n N] [--seed S] [--discount PCT] [--json]
```

`score` scores each measure in the city and prints one block per curve, in library order (it
is not a ranking): status, life-years if it works (median, 5-95%), expected life-years (times
the odds), cost in 2025 rupees (crore, median), life-years per crore if it works and expected,
the odds, and flag codes (PH placeholder, ES/ER evidence seen or recalled, OJ odds are a
judgement, LS long shot, NR cause not reported, AF whole-year share used for part-year cut, BS
borrowed month shape, CO covered people only, RG regional, RB what the source-receptor table
stands for, RF the source-receptor table is a stand-in, UB upper bound, PC the cost leaves out part of what the measure costs, AG one age group reached, counted with its own death rates). A table of PM2.5 change follows; for an exposure
measure it is what the covered people breathe. A measure whose source prices only part of it
(say, the government's enforcement but not what builders spend) says what is left out in
`cost.partial`; that sentence is printed under the table and carried as flag `partial_cost`. Statuses:
`scored`, `no_cost` (no cost given; shown, not ranked), `pays_for_itself` (society saves money
overall; shown apart, no ratios), `not_applicable` (wrong city, or its cause is too small a
share, or a regional source whose table gives the city no change), `not_scored` (no usable
study, or a city outside a regional measure's source-receptor table). `--json` prints exactly what
`score.to_json` returns. Air measures are scored on the city's APnA study unless `--study`
names another; studies that count air from every origin (CSTEP Bengaluru) are scored too,
flagged UB as an upper bound, so score each study with its own `--study` call. `--discount` is
a percent; the default is 3.

A regional measure (stubble, coal power) removes a fraction of a source spread over several
states. How much each district's PM2.5 falls when the whole source goes is read from a
source-receptor table, `data/receptor_<name>.csv` (district, state, delta_pm25_full), built by
`scripts/build_receptor.py`. No published district-level source-receptor result could be used
yet (see `data/MISSING.md`), so two tables come from McDuffie et al. 2021's gridded sector
fractions times ACAG PM2.5: `receptor_stubble.csv` (crop-residue burning) and
`receptor_energy_coal.csv` (coal burned for energy production, wider than power plants alone),
each a sector from every origin, not only the named states (flag RB). Both are stand-ins, and
every result on them carries flag RF (`receptor_fallback`) saying so; the stubble one is about 14
times smaller India-wide than Lan et al. 2022's estimate, so results on it are likely understated.
A third, `receptor_power_cropper2021.csv` (`scripts/build_receptor_cropper.py`), is the PM2.5 of
India's 2018 coal power plants from Cropper et al. 2021's model runs, by state, given to each
district. The library's regional measures: `stubble_pes_upfront`, `happy_seeder_subsidy`,
`punjab_out_of_rice` (all on the stubble table) and `fgd_scrubbers` (on Cropper's). `score CITY` gives the
part that reaches the city (life-years, no cost or ratio: the cost belongs to the whole region);
`score --region ID` scores every district the source reaches, with the measure's whole cost.
`power` is a cause of its own in `data/causes.csv` only where a study gives power plants their
own row (TERI's CMAQ runs for Kolkata, Lucknow and Surat); APnA folds them into industry, so a
city measure cannot target power plants on APnA.

The assumptions printed under every result: share times cut (cutting a cause by x% cuts its
share of PM2.5 by x%); no chemistry (air is not additive); health only (no climate, crop or
time benefits, nothing valued in money); life-years and costs counted over the measure's years
plus the lag tail, discounted at 3% a year; cost is the funder's rupees in 2025 prices.

### What the library holds

Twenty-one measures. Thirteen are Bengaluru's (the city page's chapter 4 scores them), four are
regional, and four are written for the one city where their evidence sits. Odds are the
probability it works at all, each a judgement with its reason in the file. Evidence: O every
number read at its source, S some seen only in a press account or summary. "Partial" means the
cost leaves something out (flag `partial_cost`).

| Measure | Kind | Scope | Where | Odds | | Cost | Evidence |
|---|---|---|---|---|---|---|---|
| `road_vacuum_sweeping` | air | city | Bengaluru | 0.5 | | | O |
| `construction_dust_controls` | air | city | Bengaluru | 0.4 | | partial | O |
| `road_paving` | air | city | Bengaluru | 0.6 | | | O |
| `waste_collection_burning_ban` | air | city | Bengaluru | 0.35 | | partial | O |
| `electric_buses` | air | city | Bengaluru | 0.75 | | | O |
| `old_vehicle_retirement` | air | city | Bengaluru | 0.3 | | | O |
| `electric_two_three_wheelers` | air | city | Bengaluru | 0.6 | | | O |
| `dg_set_replacement` | air | city | Bengaluru | 0.4 | | | O |
| `lpg_refill_subsidy` | air | city | Bengaluru | 0.5 | | | O |
| `home_purifiers` | exposure | city | Bengaluru | 0.3 | | partial | O |
| `school_purifiers` | exposure | city | Bengaluru | 0.35 | | partial | O |
| `n95_winter` | exposure | city | Bengaluru | 0.2 | | partial | O |
| `smog_tower` | exposure | city | Bengaluru | 0.1 | long shot | partial | O, S |
| `stubble_pes_upfront` | air | region | stubble table | 0.5 | | partial | O |
| `happy_seeder_subsidy` | air | region | stubble table | 0.7 | | partial | O |
| `punjab_out_of_rice` | air | region | stubble table | 0.3 | | | O |
| `fgd_scrubbers` | air | region | Cropper power table | 0.6 | | | O |
| `emissions_market` | air | city | Surat | 0.7 | | partial | O |
| `zigzag_kilns` | air | city | Patna | 0.5 | | | O |
| `industrial_fuel_switch` | air | city | Amritsar | 0.5 | | partial | O |
| `winter_cloud_seeding` | exposure | city | Delhi | 0.02 | long shot | | S |

The last four: the Surat particulate emissions market scaled to all 906 solid-fuel plants, at the
20-30% cut its randomised trial found (Greenstone et al. 2025); converting Patna's 300 brick kilns
to zig-zag firing, which pays for itself (the owner earns the conversion back in a season or
two), so it is listed apart, not ranked; Amritsar's industry onto piped gas (UNDP 2025's cost);
and winter cloud seeding over Delhi, a long shot scored on what its promoters claim, at odds of 2%
because the physics is against it (`../bets/README.md`) and the 2025 trials gave no rain.

To run them:

```
airhealth measures                              # the list above, from the files
airhealth score Bengaluru                       # every measure that applies to Bengaluru
airhealth score Bengaluru --study cstep_bengaluru2022_cmb   # the same on another study
airhealth score Surat --measure emissions_market
airhealth score --region fgd_scrubbers          # a regional measure over every district it reaches
```

**Flags a reader must not skip.** They are on every result they apply to, in the text and in
`--json`:

- `partial_cost` (PC): the source prices only part of the measure (often the government's
  enforcement, not what firms or households spend). A cheap-looking ratio may be cheap only
  because of what is left out; the sentence saying what is printed under the table.
- `upper_bound_all_origins` (UB): the study's shares count air from every origin, so a city
  measure is credited with cutting air that partly blows in from outside. Read it as a ceiling.
- `receptor_fallback` (RF): the regional measure's source-receptor table is a stand-in for a
  published result that could not be used. The stubble table is about 14 times smaller
  India-wide than Lan et al. 2022's estimate, so the stubble measures are likely understated.
- `long_shot` (LS): a large effect if it works, low odds that it does.
- `placeholder` (PH): a number is a stand-in, not an estimate. No library measure has one now;
  the flag stays for drafts.
- `odds_judgement` (OJ): the odds are a judgement, not a measurement. Every measure carries it.

**Adding a measure.** Copy `interventions/library/_template.toml` to `<id>.toml`; every field is
explained in it. Every number needs an `[[evidence]]` entry with its source, link, locator (table,
page) and key, or a place in `placeholders`; `measures.check_library()` and `tests/test_library.py`
refuse anything else. Write the lead in `data/MISSING.md` when a source cannot be reached. Then add
the id to a list in `tests/test_library.py` and run `airhealth score CITY --measure ID`.

**Known gaps.**

- **The regional tables are fallbacks.** No district-level source-receptor result for Punjab's
  fires could be used, so the stubble measures run on McDuffie et al.'s all-origin crop-burning
  share (flag RF; it even gives Bengaluru a small change), and Cropper's power-plant table is by
  state, not district. `data/MISSING.md` lists what would replace them.
- **Only an age group can be singled out.** An exposure measure that reaches one age group
  names it (`[exposure] ages = [5, 19]`) and is counted with that group's own death rates (flag
  AG): school purifiers do, and on curves that start at 25 they give children nothing. A group
  defined by something other than age cannot be: N95s reach working people, but their covered
  share is spread over every age, as if it were a slice of the whole city.
- **Rankings are one measure at a time.** See "Ranking" below.

## Ranking

```
airhealth rank [PLACE] [--study ID] [--map M] [--curves a,b] [--n N] [--seed S] [--discount PCT]
               [--use input=source] [--json] [--csv PATH] [--write [DIR]]
```

`airhealth rank` orders the library by **expected life-years per crore** of the funder's rupees
(a crore is 10 million; 2025 rupees), highest first, one table per curve. Expected = the odds it
works times what it gives if it works, over the expected cost (a cost paid only on success is
weighted by the odds). Ties break by measure id; "if it works" has its own rank. Measures are
ranked **one at a time: their benefits do not add up.** Ratios and ranks are never averaged across
curves, studies or maps.

- **Block 1, the grid.** The first thing printed is each measure's rank on every curve, side by
  side, with best-worst and a "curves disagree" mark when the rank moves by 3 places or more
  (`rank.FLIP_PLACES`). A dash means no rank on that curve (a measure for children on a curve that
  starts at age 25 has no curve to count on; the legend says so).
- **Then one table per curve**: rank, measure, expected life-years per crore (`PC` beside it when the
  cost leaves part out, `UB` for an upper bound), the ratio if it works and its rank, life-years if
  it works (median, p5-p95), cost (mean, ₹ crore), society's net cost, odds, the rank among
  measures whose cost is whole (`PC` for those that are not), flags. Then measures that pay for
  themselves, that have no cost given, and those not ranked, with why.
- **PLACE** is a city (one table of that city's measures; regional measures follow in their own
  group, because their ratio is over their whole reach and most of their benefit falls outside the
  city) or `India`/omitted: every city scored on its own study and added up for a measure that
  applies in several, plus each regional measure over its reach; the reach column is beside the
  name. It takes minutes (the regional measures dominate); progress goes to stderr.
- **Output.** `--json` is `rank.to_json`; `--csv PATH` is one row per curve and measure with the
  sources on each row (`evidence`: source | locator | url | key); `--write [DIR]` (default
  `health/out/rank/`, git-ignored) writes `rank_india.json/.csv` and a pair for every city from the
  same run (`rank_<city>.json/.csv`); for a city, only its pair.

## Writing an intervention file

Copy `interventions/_template.toml`; every field is explained there. A mistake is reported
in one line naming the field, for example `airhealth: p_success: must be between 0 and 1,
got 2`. The shape:

```toml
name = "10% cut in Punjab and Haryana"
places = ["Punjab", "Haryana"]   # India, states, districts or cities; overlaps are refused
start_year = 2027
ramp_years = 3                   # years to reach the full change
duration_years = 15
p_success = 0.3                  # probability it works at all
lag = "epa20"                    # or "immediate"
# from_level = 100               # what-if: start every district at this level

[change]                         # exactly one of these
pct = -10                        # delta = -20 | pct = -10 | to = 40 |
                                 # monthly_delta = [12 values] | monthly_pct = [12 values]

[cost]
once = { dist = "lognormal", p5 = 5e9, p95 = 5e10 }
annual = { dist = "lognormal", p5 = 1e9, p95 = 1e10 }
currency = "INR"                 # or "USD"
year = 2025                      # price year; rupees converted at that year's average rate
share_only_on_success = 0.0      # share of the cost spent only if it works
```

Any number in `[change]` or `[cost]` can be a range instead: give its 5th and 95th
percentiles and a shape, `normal`, `lognormal` (skewed, never crossing zero), `uniform`, or
`triangular` (with a `mode`). Twelve monthly values are averaged by days in the month; when
they are ranges they are drawn together, so a draw that is good for November is good for
December too. A drawn change never takes the air below 0 µg/m³. `monthly_pct` weights each month
by the place's own PM2.5 shape: twelve numbers, January first, with a day-weighted mean of 1,
from the CPCB monthly means of 2023-25 (`data/monthly_cpcb.csv`), so a winter-only cut counts for
more where winters are dirtier (a November cut in Delhi, about 2.4 times the annual mean).
A city with all twelve months in its CPCB data uses its own monitors (all of 2016-25 if 2023-25
lacks a month). A city without borrows the largest such city in its state, else the state-wide
shape of all CPCB monitors in its state (`data/monthly_cpcb_state.csv`); a state or district takes
its such cities' population-weighted shape, else the state-wide shape; anywhere with none falls
back to India's. The run says which it used, and where it borrowed. `monthly_delta` is
in µg/m³ and is unaffected. The worked example is `november_pct_delhi.toml`.

The examples: `delhi_100_to_80.toml` (the what-if above, no cost or odds),
`november_only_delhi.toml`, `november_pct_delhi.toml`, and `punjab_haryana_10pct.toml`. Their odds and costs are
illustrative placeholders, said so in each file's notes, and should not be quoted.

## The exposure maps, and how much they disagree

Where a place starts on the curve matters as much as the curve, and the maps disagree
twofold. Population-weighted annual-mean PM2.5 in µg/m³, from this tool:

| Place | `aqli` 2023 | `aqli` 2019 | `acag_total` 2023 | `gbd2019` 2019 | `gbd2023` 2023 | `gbd2023` 2019 |
|---|---:|---:|---:|---:|---:|---:|
| India | 41.2 | 44.6 | 49.8 | 90.9 | 54.0 | 53.3 |
| Delhi | 88.3 | 92.7 | 98.8 | 217.6 | 105.3 | 104.4 |
| Uttar Pradesh | 56.2 | 64.8 | 68.2 | 182.9 | 80.5 | 81.2 |
| Bihar | 60.1 | 68.6 | 64.0 | 167.8 | 73.3 | 75.1 |
| Kerala | 18.5 | 17.1 | 26.1 | 15.8 | 21.8 | 19.7 |

Delhi's own ground monitors (`cpcb`, the city, mean of hourly medians across stations): 104.7
in 2019, 97.5 in 2023, 94.3 in 2025.

- `aqli`: the Air Quality Life Index's district table, from satellites, with dust and sea
  salt removed (the index counts only the pollution people make).
- `acag_total`: the same satellite family (Washington University's ACAG V6) with dust kept,
  averaged to districts by this repo.
- `gbd2019`: the Global Burden of Disease 2019 state values, as printed in Pandey et al. 2021
  (a model fusing satellites, chemistry models and monitors). One value per state.
- `gbd2023`: the Global Burden of Disease 2023 state values, from IHME's own file (local
  tier: read from `data_local/` at run time, never committed; 1990-2023, results from 2011).
  GBD has one value for Jammu & Kashmir and Ladakh, used for both, and one pooled value for
  six small union territories (Andaman & Nicobar, Chandigarh, Dadra & Nagar Haveli, Daman &
  Diu, Lakshadweep, Puducherry), used for each, as `gbd2019` does. India is the states
  weighted by the tool's population: 53.97 for 2023, against IHME's own 54.05.
- `cpcb`: the Central Pollution Control Board's monitors, for the 43 cities that have a CPCB station (not Aurangabad, Jamshedpur, Panaji, Rajkot, Shimla, Vadodara or Ranchi, which fall back to `aqli`).

Keeping dust moves India from 41 to 50: dust explains under a fifth of the gap to GBD's 91.
The rest is concentrated in the northern plain (Uttar Pradesh 56 against 183); in Kerala
the three maps land within 16 to 26. In Delhi the monitors side with the satellites, not with GBD 2019. Why GBD
2019 sits so high is an open question; see G7 in [`../lit/gaps.md`](../lit/gaps.md). IHME's
own newer round has moved most of the way: GBD 2023 puts India at 54 and Uttar Pradesh at 81
for 2019 (GBD 2023 changed its exposure model to the ACAG satellite product calibrated to
monitors), and for Delhi it lands on the monitors (104 for 2019, against 105 at the monitors).

## How many deaths a year? The count is tied to the SRS

Deaths, life-years and cost per life-year all scale with one number: how many people die in
a place each year. The tool takes death rates by age from the SRS life tables for 2020-24
and the number of people at each age from the official population projections. Multiplied
together they give India 7.5 deaths per 1,000 people (2022 population). The SRS's own
published crude death rate for the same five years averages 6.6. For Delhi it is 5.9
against 4.5. An earlier version of this tool printed the higher counts.

**Where the gap is.** It was traced with the SRS's own tables for 2020 to 2024
(`data/srs_*.csv`, each read at the source; `tests/test_baseline.py` repeats the check):

- **Not in the death rates.** The life-table rates are the SRS's age-specific death rates
  for the same years, within 2% at ages 30 to 79. Put on the SRS's own age distribution
  they give back its crude death rate: 6.63 for India.
- **Not in the period.** Both sides are 2020-24, the pandemic year 2021 included (the SRS
  crude rate was 6.0, 7.5, 6.8, 6.4 and 6.4 in the five years).
- **In the age structure.** The projections, made in 2019 from the 2011 Census, have more
  older people than the SRS finds in its sample: 10.5% of Indians are 60 or over in the
  projection for 2022, 9.1% in the SRS's 2020-24 reports. The same holds in every one of the
  22 states with a life table, and all of the excess deaths are at 45 and over; under 45 the
  two agree within 0.1 per 1,000. Delhi's gap is the largest because its age gap is: 9.7%
  aged 60 or over in the projection, 7.2% in the SRS.
- **A little in the oldest band.** The life table closes the 85-and-over band by a model,
  so its rate there differs from the SRS's (India 153 against 148 per 1,000; Delhi 145
  against 123; Kerala 148 against 176), and the tool splits the projection's 80+ group
  between 80-84 and 85+ by the life table, not by the SRS's own split. Together these move
  India's deaths by about 1%.

**What the tool does about it.** By default (`--deaths srs`) each state's death count is
scaled to that state's own mean SRS crude death rate for 2020-24. For India and the 22
states with their own life table the factor applies to deaths at 45 and over, where the
excess is (India ×0.85, Delhi ×0.72, Telangana ×0.73 at one end, Himachal Pradesh ×0.95 at
the other). For the 15 small states and territories that borrow all-India death rates, one
factor applies at every age and brings the borrowed rates to the state's own SRS rate
(Chandigarh ×0.57 to Goa ×0.94). Every state and territory has its own SRS rate; Dadra &
Nagar Haveli and Daman & Diu share the rate of the union territory they were merged into.
The factors are in `data/death_reconciliation.csv`, built by
`scripts/build_death_reconciliation.py`, and the last line of every result names the factor
used. **Life expectancy is never scaled:** it comes from the life table as published, which
this tool reproduces to within 0.09 years. `--deaths model` (or `deaths="model"` in Python)
switches the scaling off and gives projected population × life-table rates.

The factor is measured at the 2022 population and used in every year from 2020 on. In a
later year the count drifts above the SRS rate as the projected population ages (Delhi 2023:
4.6 per 1,000); after 2024 nothing checks it, and every result says so.

**Years before 2020** use that year's own SRS reports (2011-19, transcribed). Mortality then
was higher mostly among young children (India 2011: death rates under 5 were 1.75 to 2.8
times 2020-24's, ages 30-70 about the same) and at 80 and over, so a single factor would put
the extra deaths at the wrong ages. Instead each age band's rate is the 2020-24 rate times
the SRS's rate for that band in the year and a year either side, over its 2020-24 mean (the
state's own, or India's where the state has none: the smaller states, and Telangana and
Uttarakhand before 2014). Life expectancy moves with these rates. The counts are then scaled
at 45 and over to the SRS's crude death rate for that year
(`data/death_reconciliation_by_year.csv`). India's factor is 1.02 in 2011 and falls to 0.78
by 2019: with the year's own rates by age, the only gap left is the projection's age
structure drifting away from the SRS's as it moves on from the 2011 Census. States the SRS
printed no rate for before 2020 (the smaller states and UTs) keep the 2020-24 factor, and
the footer says which. Andhra Pradesh before 2014 is the undivided state in the SRS.

**Which count is right is not settled.** The evidence both ways:

- *For the SRS rate.* It is the official estimate, from the same survey as the death rates,
  and a tool should not report more deaths than the source it takes its rates from. The
  United Nations' estimate for India (World Population Prospects 2024) is close to it for
  recent single years: 6.6 per 1,000 in each of 2022, 2023 and 2024.
- *Against it.* The UN's age structure sides with the projection, not with the SRS: 10.2%
  aged 60 or over in 2022. The SRS's sample already had fewer older people than the Census
  in 2011 (8.1% against 8.4%), and the distance has grown. If India is as old as the UN and
  the projection say, the SRS's own rates imply about 7.5 deaths per 1,000 for 2020-24, and
  the UN's average over those five years is 7.3 (it puts many more deaths in 2021 than the
  SRS does, 9.3 per 1,000 against 7.5). On that reading the scaled count is about a tenth
  too low as a 2020-24 average.

So the scaled count (India 9.4 million deaths in 2023) is the better guide to a normal
recent year, and the unscaled one (10.8 million) to what the SRS's rates would mean if the
population is as old as projected. The next census will say which age structure is right.
Shares of deaths and life expectancy do not depend on any of this.

Sources for the UN figures: United Nations, World Population Prospects 2024, medium
variant, files `WPP2024_Demographic_Indicators_Medium.csv.gz` (crude death rate, deaths)
and `WPP2024_PopulationByAge5GroupSex_Medium.csv.gz` (age structure), both under
<https://population.un.org/wpp/assets/Excel%20Files/1_Indicator%20(Standard)/CSV_FILES/>,
read 2026-11-11 (sha256 286ac36b… and a04d7d14…).

Since 2026-11-11 the UN's figures are a switch (`--use deaths=unwpp`, and population and
death rates; `data/unwpp_*.csv`, `scripts/build_unwpp.py`). Year by year, the UN's crude
death rate for India against the SRS's: within 1% in 2011-14, 4-11% higher in 2015-19, 20%
and 24% higher in 2020 and 2021 (the pandemic), within 3.5% in 2022-24. So "about a tenth"
is a 2020-24 average carried by the pandemic years; in a normal year the two are closer.

## The IHME tier: three more curves, from IHME's files

With IHME's files in `data_local/` (never committed; [`IHME_DOWNLOADS.md`](IHME_DOWNLOADS.md)
says what and how), three more curves run beside the open ones, and a fifth map (`gbd2023`,
above). Without the files they are named as not run, with why.

- `gbd2023`: the Global Burden of Disease 2023 relative risks for **seven causes of death**
  (ischaemic heart disease, stroke, COPD, lung cancer, lower respiratory infection, type 2
  diabetes, dementia). One curve per cause, the same at every age.
- `gbd2019`: GBD 2019's six causes (no dementia), with IHD and stroke by five-year age.
- `gemm_5cod`: Burnett 2018's GEMM for its five causes (IHD and stroke by age), parameters
  from the authors' calculator (committed: `data/curves_gemm_5cod.csv`).

All three take their **deaths from IHME**: the GBD 2023 round's death rates by cause, state
and age, times this tool's population. So for them the death count is GBD's, not the SRS's,
and `--deaths` does not move it; their "% of deaths" is of the tool's all-cause count. GBD
2019-round deaths are no longer served by IHME, so `gbd2019` runs on the GBD 2023 round's
deaths, and every result says so. Each curve is scored against GBD's counterfactual, the
midpoint (4.15 µg/m³) of its 2.4-5.9 range. How the files were read (two of the GBD 2023 files
are relative risks, four are their logarithm) and every source are in `IHME_DOWNLOADS.md` and
the docstring of `airhealth/ihme_curves.py`.

```
$ airhealth compare Delhi --from 100 --to 80        (IHME files present)
curve                  PM2.5 µg/m³  % of deaths  deaths/yr  life exp. yrs  life-years/yr
loglinear_jaganathan  100.0 → 80.0        15.2%     15,126          +2.25        313,030
gemm_ncd_lri          100.0 → 80.0         4.1%      4,031          +0.53         67,113
gbd2019               100.0 → 80.0         1.4%      1,369          +0.14         20,460
gbd2023               100.0 → 80.0         2.2%      2,160          +0.21         27,667
gemm_5cod             100.0 → 80.0         3.3%      3,295          +0.32         50,287

$ airhealth burden India                            (AQLI map, 2023)
gemm_ncd_lri           41.2 → 2.4        16.4%  1,531,850          +2.59     24,997,876
gbd2019                41.2 → 4.2        12.0%  1,123,386          +1.57     17,892,049
gbd2023                41.2 → 4.2        14.9%  1,395,628          +2.04     20,242,495
gemm_5cod              41.2 → 2.4        13.9%  1,299,500          +1.80     18,668,623
```

For Delhi from 100 to 80, IHME's curves give a tenth to a fifth of what the Indian district
study does:
they flatten at high concentrations, and they cover only the causes they name. GBD's own count
for India in 2023, 969,726 deaths from ambient PM2.5, is not reproduced yet: on the same
curve, map and year this tool gives 1.61 million, and the main reason is known but not
computable from these files (GBD splits one attributable fraction between outdoor air and
cooking smoke; here outdoor air is scored alone). See `IHME_DOWNLOADS.md`.

## What causes the PM2.5

`data/causes.csv` puts every published answer to "what is this city's PM2.5 made of" side by side, one row per city, study, season, size fraction and source: UrbanEmissions' APnA runs for the 49 airsheds it covers, McDuffie et al.'s global-model shares for nine of the 50, and the city studies and stubble estimates transcribed by hand from state, NCAP and journal reports (`data/causes_transcribed.csv`; each row's `locator` names the table or figure and the page where the sampling months are stated). It never picks a winner or averages across studies, because they disagree by multiples, not points: Kanpur's household share is 34% in APnA, 25% in McDuffie and 3% (winter biomass) in IIT Kanpur's filter study, and Lucknow's share from outside the city is 30% or 81% (`lit/city-sources.md` section 3). Things to keep in mind when reading it. (1) **`origin` says what a share counts.** `inside` (APnA's sector rows): emissions inside the airshed only, everything from outside is the `outside` row. `all_origins` (CMAQ, GEOS-Chem and WRF-Chem sector splits, McDuffie, receptor CMB/PMF shares, stubble estimates): that sector's contribution from every origin, so "cut Lucknow transport 30%" is not the same quantity there as in APnA. `region` (APnA's `outside` row and the geographic splits): a split by where the pollution comes from, where `local_all` is the city's own sources, all sectors, and the rest is `outside`. Govardhan 2024 is the one hybrid: it splits Delhi's own share into Delhi transport (`transport`) and Delhi's other sectors (`other`), so it has no `local_all` row. Do not apply an inside-the-city cut to an `all_origins` share. (2) **A cause a study does not list is "not reported", never 0.** `airhealth.causes.shares(city, study, season)` returns every harmonised cause with NaN for the unreported ones. (3) **`months`, not `season`, decides which months a share covers.** Kolkata's filter study is labelled `winter+summer campaigns` (months 12,1,4,5), not annual. (4) APnA's `outside` rows already contain stubble smoke from upwind states; `agri_burning` rows with `covers = partial` are stubble-only estimates for a stated October-December window and overlap APnA's `outside`; do not add them. `agri_burning` also appears inside complete splits (ARAI dispersion, Govardhan, TERI Lucknow, Kolkata and Surat CMAQ, Surat CMB, McDuffie), so filter on `covers` too. McDuffie's household share is 28.3% (`residential`, of which biofuel 24.5). (5) "Residential" is not defined the same way everywhere: Kolkata's CMB "cooking" (households and eateries) is `residential`, while Kolkata's CMAQ puts eateries in `other` and McDuffie's commercial sector is `other`. Coal and fly ash is `other` (a mixed factor), and `transport` includes diesel generator sets in IIT Kanpur's Kanpur and Agra studies. (6) Only evidence `O` (read at source) is in the table; press-only numbers are leads in `data/MISSING.md`. (7) Emission shares (`metric = emission_share`) are never mixed with concentration shares. `airhealth.causes.for_city(city, study)` returns the rows; `build_causes.py` rebuilds the file (checking the McDuffie download's sha256) and refuses groups that do not sum to 100 +/- 2.

## Benchmarks: does it reproduce published numbers?

`python benchmarks/run.py` runs each published estimate's curve, counterfactual and year on
the closest map, and writes [`benchmarks/README.md`](benchmarks/README.md) with a paragraph
on every gap. Nothing is tuned to close one. Each case states the ratio it expects (ours ÷
published), worked out from the known differences in inputs, and passes only within a
narrow band of that expectation.

| Case | Measures | Published | Ours | Ratio | Expected |
|---|---|---|---|---|---|
| jaganathan2024_share | share | 24.9% of deaths | 26.0% of deaths | 1.044 | 1 ±10% |
| jaganathan2024_deaths | deaths | 1.50 M deaths/yr | 2.19 M deaths/yr | 1.462 | 1.392 ±8% |
| aqli2025_india_years | years | 3.50 years | 3.55 years | 1.014 | 1 ±3% |
| aqli2025_delhi_years | years | 8.20 years | 8.17 years | 0.996 | 1 ±3% |
| burnett2018_india_maps | deaths | 2.22 M deaths/yr | 1.31 M deaths/yr | 0.591 | 0.619 ±8% |
| burnett2018_india_forced74 | deaths | 2.22 M deaths/yr | 1.82 M deaths/yr | 0.818 | 0.816 ±5% |
| burnett2018_india_5cod_forced74 (IHME tier) | deaths | 1.87 M deaths/yr | 1.57 M deaths/yr | 0.839 | 0.843 ±3% |
| gbd2023_india_exposure (IHME tier) | PM2.5 | 54.05 µg/m³ | 53.97 µg/m³ | 0.999 | 1 ±2% |

In short: the shares and life-expectancy gains match. The counts differ because the papers
counted different sets of deaths. Jaganathan used registered deaths only, which miss many.
Burnett's GEMM paper used the Global Burden of Disease's deaths for 2015, 6.46 million at
ages 25 and over from the causes the curve covers, where this tool, tied to the SRS, has
5.27 million; fed the paper's own deaths, this tool's curve reproduces the paper's 2,219,057
exactly. The paper also put India at 74 µg/m³ against AQLI's 45 for 2015. The same holds
for its five-cause GEMM: fed the paper's deaths, `gemm_5cod` gives its 1,867,342; fed the GBD
2023 round's deaths for 2015 (16% fewer from those causes, mostly COPD and LRI), 0.84 of it.
The two IHME-tier cases skip where the IHME files are absent.

## Known limitations

- **State death rates are applied to every district and city in the state.** A district
  poorer or richer than its state's average is placed wrongly.
- **15 small states and territories use all-India death rates**: Andaman & Nicobar,
  Arunachal Pradesh, Chandigarh, Dadra & Nagar Haveli, Daman & Diu, Goa, Ladakh,
  Lakshadweep, Manipur, Meghalaya, Mizoram, Nagaland, Puducherry, Sikkim and Tripura have
  no life table of their own in the Sample Registration System (SRS). Tables say so.
- **Years before 2020 take their death rates by age from the SRS's annual reports, which
  print rates for India and the bigger states only.** Small states and UTs borrow India's
  change by age and keep the 2020-24 scaling. Single-year SRS rates are noisy for small
  states and young ages (printed to 0.1 per 1,000), which is why three years are averaged.
  The life table's shape within each band, and the cause shares (2021-23), stay 2020-24's.
- **After 2024 the death rates and scaling are 2020-24's**, applied to the projected
  population and checked against nothing; every such result says so.
- **How many deaths India has is itself uncertain by about a tenth**, because the SRS and
  the population projections disagree about how old the population is. See "How many deaths
  a year".
- **City populations are the 2011 Census** (the urban agglomeration), the same in every
  year, while districts and states use the official projection for the map year. A city's
  deaths and life-years are therefore low by however much it has grown since 2011. Every
  result that uses a city's
  population says so on its last line. No newer official city figures have been added
  (`data/MISSING.md`).
- **The 80+ population is split into 80-84 and 85+** in the proportions of the life table's
  stationary population, which puts about half in each; the SRS's own age distribution has
  about 60% of them at 80-84. With counts scaled to the SRS crude death rate this does not
  change a state's total deaths, only how deaths at 45 and over divide by age.
- **Ages 25-29 take the cause shares of the SRS's 15-29 group**, where injuries dominate.
  GEMM, which covers only non-communicable disease and lower respiratory infection, counts
  about a third too few deaths at 25-29 against the Global Burden of Disease; that is about
  1% of its total.
- **Ambient air only.** Smoke from cooking fires is not counted; in states where many homes
  burn solid fuel, people are placed lower on the curve than they really are.
- **The cause-of-death shares are thin.** GEMM covers only non-communicable disease and
  lower respiratory infection; their share of deaths is all-India, by broad age group, from
  the SRS Causes of Death 2021-23 report (a verbal-autopsy survey with no state breakdown),
  not from the Million Death Study, whose fieldwork ended in 2013.
- **Above about 84 µg/m³ every curve is an extrapolation.** No long-term study has observed
  people at those levels. The tool shows how far apart the curves land; it does not resolve
  it.
- **Life-years are deaths postponed × remaining life expectancy at the age of death**, at the map year's
  population and age structure, over the horizon (the intervention's years and the lag's tail), discounted at 3% a year. A cohort run
  to 2050 replaces this; when it comes, the population after 2036 (the end of the official
  projections) will be a crude extension.
- **The uncertainty is partial.** Ranges cover the PM2.5 change, the curve's own published
  uncertainty and the cost. They do not cover the choice of curve or map (shown as separate
  results instead), the death rates, the death count or the population. AQLI has no
  published interval, and its row shows none.
- **Costs are put in 2025 rupees with India's GDP deflator, and dollars converted at one
  annual exchange rate for their price year.** Where a source does not state its price year,
  the measure file says which year was taken.
- **The IHME-tier curves (gbd2019, gbd2023, gemm_5cod) count IHME's deaths, not the SRS's.**
  Their deaths are the GBD 2023 round's rates by cause, state and age times this tool's
  population, unscaled; their share of deaths divides by the tool's (SRS-scaled) all-cause
  count. `gbd2019` uses GBD 2023-round deaths because GBD 2019's are no longer served. Ladakh
  takes GBD's Jammu & Kashmir and Ladakh rates and six small union territories GBD's pooled
  "Other Union Territories". Years between 2015, 2019 and 2023 are interpolated; outside,
  the nearest is used.
- **The IHME-tier curves use mean curves and a point counterfactual.** GBD draws the TMREL
  (2.4-5.9) and the curve together, 1,000 times; here the floor is 4.15 and the curve its mean,
  which IHME says gives slightly smaller attributable fractions. Their Monte Carlo moves every
  cause's log relative risk together by one standard normal times its own standard error.
- **GBD's own burden is not reproduced.** GBD splits one attributable fraction between outdoor
  air and cooking smoke, adds neonatal deaths through birth weight and gestation, and works on
  grid cells; this tool does none of these (see `IHME_DOWNLOADS.md`).
- **No GBD all-cause death count.** The IHME files hold seven causes and all NCDs, not all
  causes, so `--deaths` has no GBD source.

## Not built yet

- **A reproduction of GBD's own India burden** (needs GBD's household air pollution file and
  its joint ambient-household split), and a **GBD all-cause death source** (needs an "All
  causes" query). See `IHME_DOWNLOADS.md`.
- **A switch for every input.** Only the curve, the map, the death-count basis and the
  counterfactual can be switched today. The life table, population, cause shares and the
  rest are fixed in code. Design note: [`../docs/specs/2026-11-11-source-switches.md`](../docs/specs/2026-11-11-source-switches.md).
- **The run to 2050**: a year-by-year cohort simulation with an ageing population, which
  separates the ageing effect from the intervention's.
- **Valuation presets**: putting money values on deaths and life-years (value of a
  statistical life, lost output, multiples of income per head). Only cost per life-year is
  reported now.
- **The Surat case**: reproducing Greenstone et al.'s "benefits at least 25× costs" for
  Surat's emissions trading scheme.
- **A public web page.** `airhealth dashboard` is a local page only. The JSON output
  (`--json`) is the intended interface for a public one.

## Layout

```
airhealth/        the package: places, exposure, baseline, lifetable, curves, impact,
                  intervention, lag, simulate, months, causes, ihme, provenance, report,
                  charts, cli, dashboard (+ .html)
data/             committed tables, each with an entry in data/sources.toml; MISSING.md
data_local/       IHME files, never committed (git-ignored); read by airhealth/ihme.py
interventions/    the template and four examples
benchmarks/       cases.toml, run.py, README.md (generated)
charts/           charts drawn by the commands above
scripts/          the scripts that build data/ from the sources
tests/            pytest
```
