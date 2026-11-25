# Health model, first version — design

Status: draft for Akash's approval. Nothing is built yet.
Date: 2026-11-10.

## Why this exists

Akash wants an intuition for how large India's air-pollution health problem is, and a way
to ask "if this intervention worked, how much health would it buy?" He found he could not
answer that himself. Research done before this design (three literature sweeps, summarised
under "What the research found") showed why: the published answers differ several-fold, and
the differences come from four assumptions that no public tool exposes together.

The audience is Akash first, then smart people looking for something to build. The longer
aim is a public tool that makes air pollution look tractable to builders. This first version
is the health half of that tool.

## What the research found (the facts the design rests on)

These came from delegated literature sweeps. Items the sweeps marked as recalled or seen
only in a search snippet are **not** verified. The builder must re-read every number at its
source before it enters code or data (see "Provenance rule").

1. **The risk curve dominates.** No long-term study follows people breathing more than about
   84 µg/m³. Above that, every curve is an extrapolation. For Delhi going from 100 to 80
   µg/m³, a straight-line fit on Indian district deaths (Jaganathan et al. 2024, 8.6% per
   10 µg/m³) gives about a 15% fall in mortality, GEMM (Burnett et al. 2018) about 6%, and
   GBD's current curve about 1% or less. The last two figures are unverified arithmetic.
2. **Exposure maps disagree about twofold.** India's population-weighted PM2.5 is put at
   about 39–41 µg/m³ (AQLI, Jaganathan) and 83–92 µg/m³ (GBD / State of Global Air). AQLI
   removes dust and sea salt; that explains some unknown share of the gap.
3. **Valuation spans about 35-fold.** The same 1.67 million deaths (GBD 2019) are priced
   from about $30bn to about $1,070bn a year depending on method.
4. **Demography can outrun clean-up.** HEI's 2018 projection has deaths more than doubling
   by 2050 under aggressive clean-up, because the population ages. Chowdhury, Dey & Smith
   (2018) disagree: falling baseline death rates offset it.
5. **No existing tool does this.** The nearest prior art is CREA's R package `creahia`
   (swappable curves, country level, no interface). Open Philanthropy's public case is three
   one-line calculations. No maintained Python package for PM2.5 health impact was found.

## Goals

- Take a change in annual-mean PM2.5 for a set of Indian places and return deaths averted,
  life-years gained, change in life expectancy, and money value, each with a range.
- Make the four contested assumptions explicit choices: **risk curve, exposure map,
  valuation, demography over time.**
- Let an intervention be described in a short text file, with odds of success, effect on
  PM2.5, timing and cost, and show which part of the chain drives the uncertainty.
- Reproduce published figures closely enough to be trusted, and say where it cannot.
- Cover all Indian states and union territories that the mortality data covers, plus the
  ten cities already in `diwali/config.py`.

## Non-goals for this version

- Turning an intervention into a PM2.5 change (the "air response" layer: source shares,
  transport, chemistry, the dome effect). Here the PM2.5 change is an input.
- A web page. Planned next; this version must not make it harder (see "Constraints").
- Household (cooking-smoke) exposure. Ambient only. Leave a hook: an optional per-place
  "additional exposure" term, default zero.
- Illness that does not kill (birth weight, cognition, productivity, diabetes incidence).
  Allow one optional scalar uplift on life-years for morbidity, default off.
- Black carbon or composition-specific toxicity. PM2.5 mass only.
- Short-term (daily) mortality effects.

## Anti-goals (would make it a failure even if it runs)

- **A single headline number.** The repo's own `lit/gaps.md` says another burden estimate
  adds nothing. Output always shows results across curves; the tool never silently picks one.
- **Precision it does not have.** No point estimate without its range and its curve named.
- **Numbers from memory.** Any parameter that was not read at its source.
- **Publishing IHME data.** See "Data and licences".

## How it is made (decided with Akash)

- A Python library in this repo, run from the terminal, producing numbers and charts.
- A page on dogl.uk later, reading the same intervention files.
- IHME's licence problem is acknowledged and deferred: use the data locally for now.

Everything below this line is my proposal (Claude's call) unless marked otherwise.

## Shape of the thing

A new track `health/` beside `diwali/`, containing an installable package (working name
`airhealth`), its data, example interventions, tests and benchmark cases. It reuses the
repo's fonts and chart style (`diwali/config.py` → `FONTS`, and the look of
`diwali/charts/`). Python 3.12+. TOML for intervention files (standard-library reader).

### The calculation

For each place, age band and year:

1. **Baseline deaths** = population × all-cause death rate, from the state's life table.
2. **Risk ratio** for moving from concentration *c₁* to *c₂* = RR(*c₂*) / RR(*c₁*), from the
   chosen curve. Applied to the age bands and the share of deaths the curve covers.
3. **Deaths averted** = baseline deaths in scope × (1 − risk ratio).
4. **Life-years and life expectancy** by re-running the life table with the changed death
   rates. This, not deaths × a fixed number of years, is the primary method.
5. **Timing.** Risk falls gradually after exposure falls. A lag profile (default: the US
   EPA 20-year distributed lag; option: immediate) spreads the benefit over years.
6. **Money**, by the chosen valuation.

**How the life table and the run to 2050 fit together.** Two modes, sharing the same curve
and rate code:

- *Steady state:* a period life table per state, with and without the change. Gives the
  change in life expectancy and steady-state deaths averted per year. This is what the
  "compare curves at a place" command and most reproduction benchmarks use.
- *Over time:* a simple cohort simulation. Seed each state's population by age from the
  official figures for the start year, then step forward year by year twice — baseline and
  intervention — carrying survivors into older ages. Births come from the official
  projections; no migration. People the intervention saves stay in the model and die later.
  The baseline run will not match the official projections exactly; report the gap.

  The ageing effect is the baseline run compared with a run that freezes today's age
  structure. The intervention effect is intervention minus baseline.

**What counts as a life-year gained.** Headline: extra person-years lived up to the horizon,
plus the remaining life expectancy of the extra people alive at the horizon ("lifetime
accounting"). Always shown beside it: person-years within the horizon only. Deaths are
reported as "postponed", cumulative to the horizon.

Exposure within a state is not uniform and the curves are not straight, so states are
computed as the population-weighted sum over districts, using state death rates for every
district in the state. Cities use the city's concentration, the city's population and its
state's death rates.

### The four dials

**Risk curve** (each is a named, documented option):

| Option | Form | Needs |
|---|---|---|
| Log-linear, user slope | RR = exp(β·Δc). Presets: Jaganathan 2024 (8.6% per 10), Million Death Study (Brown 2022, 1% per 10), Vodonos 2018 | All-cause deaths |
| GEMM NCD+LRI | Burnett 2018, age-specific parameters | Share of deaths that are non-communicable disease or lower respiratory infection, by age |
| GEMM five-cause | Burnett 2018 | Cause-specific deaths (IHME, local only) |
| GBD MR-BRT 2019 and 2023 | IHME tabulated curves, by cause | IHME curve files and cause-specific deaths (local only) |
| Fusion | Burnett 2022 | Include only if parameters are published in usable form |
| AQLI linear | 0.98 life-years per 10 µg/m³, applied to life expectancy directly | Nothing |

AQLI gives years, not deaths. To put it on the same table, solve for the uniform
proportional change in adult death rates that produces AQLI's life-expectancy change, and
report the deaths that implies, labelled as derived.

Curves are shown side by side. A user may give weights across curves to get one blended
answer; there is no default blend.

Every curve also takes a **counterfactual floor** (the concentration below which no further
benefit is assumed), default as published for that curve.

**Exposure map:**

- AQLI state and district series (satellite, dust and sea salt removed, CC BY).
- ACAG V6 total PM2.5, population-weighted to districts and states with WorldPop (CC BY).
- GBD 2019 state values as printed in Pandey et al. 2021.
- CPCB station means for the ten cities, from this repo's own data.

An intervention's change is applied on top of whichever map is selected; the map sets where
on the curve each place starts.

**Valuation:** deaths × value of a statistical life (with income-elasticity transfer, user
elasticity); life-years × value per life-year; lost output (user discount rate); life-years
× a multiple of GDP per head; Open Philanthropy's $50k and $100k per DALY, labelled as
welfare-weighted and not comparable to GDP. Cost per life-year needs no valuation and is the
default cost-effectiveness figure.

Currency: US dollars at market exchange rates, 2019 prices, with rupees shown alongside;
the price year is a setting. Intervention costs may be entered in rupees or dollars with a
stated year and are converted. Presets to ship, each only if its figure is confirmed at
source: lost output at 4/6/8% (Pandey et al. 2021); the World Bank 2022 transferred value of
a statistical life; Viscusi & Masterman 2017 ($275k for India); Majumder & Madheswaran's
Indian wage-based estimate; one and three times GDP per head per life-year; Open
Philanthropy's two figures. A preset that cannot be confirmed is dropped and listed.

**Demography over time:** run from a start year to 2050. Population by age and state from
the official 2011–2036 projections, extended to 2050 by scaling the UN national projection
(crude, labelled so). Baseline death rates either held constant or declining at a user rate.
Separate discount rates for money and for life-years, default 0% for life-years.

### Outputs and their units

Primary: **life-years gained** and **change in life expectancy**. Secondary: deaths averted
per year at steady state and cumulatively to the horizon. Money last. "DALYs" are reported
only when the morbidity uplift is on; otherwise the unit is called life-years. QALYs are not
produced.

### Intervention files

A short TOML file: name; where (states, districts or cities); change in PM2.5 as an absolute
or percentage change in the annual mean, **or** a twelve-month profile from which the annual
mean is computed; start year, ramp-up, duration; probability of success; cost (one-off and
annual); and any of these as a distribution (given by, for example, 5th and 95th
percentiles) instead of a number.

The monthly profile matters: it is how the tool shows that a November-only intervention
moves the annual mean, and so long-term health, far less than it moves the sky.

Ship a handful of examples, including the two worked cases below and a blank template.

### Uncertainty

Monte Carlo with a fixed seed. Sampled: curve parameters (from published standard errors),
intervention inputs, valuation inputs. Not sampled: which curve, which map — those are shown
as separate results.

**Odds of success are not sampled.** The main table is conditional on the intervention
working, and its ranges describe the PM2.5 change, the curve and the valuation. Beside it,
one "expected" column multiplies by the probability of success. The "which link drives the
uncertainty" breakdown covers PM2.5 change, curve parameters and valuation, and shows the
spread *across* curves next to them for scale; the probability is printed as a separate
multiplier.

**Cost.** By default the full cost is spent whether or not it works; a file may mark a
share of cost as spent only on success. Two cost-effectiveness figures are reported: cost
per life-year if it works, and expected cost per expected life-year. The second is the
default headline.

### Terminal commands (behaviour, not exact syntax)

- **Run an intervention file** → table across curves, a JSON result, charts.
- **Compare curves at a place** for a move from one concentration to another.
- **Total burden for a place** against a counterfactual, for checking against publications.
- **List** available curves, maps, valuations and places, each with its source.

### Charts

- The curves drawn on one axis with chosen places marked at their concentrations.
- Results across curves for one intervention, with ranges.
- Deaths and life-years over time to 2050, showing the ageing effect separately from the
  intervention effect.
- Which link drives the uncertainty.

## Benchmarks (the test set)

Two kinds, kept separate from unit tests.

**Reproduction.** With the matching curve, map and year, the tool should land near each
published figure. Where it does not, the mismatch and its likely cause are written down, not
tuned away.

- Burnett 2018, India 2015: 2.22M (GEMM NCD+LRI), 1.87M (GEMM five-cause), 1.02M (IER).
- Jaganathan 2024: about 1.5M deaths a year against 5 µg/m³.
- Sinha, Cropper et al. 2026: 118,000 / 264,000 / 397,000 deaths averted a year by meeting
  40 / 25 / 15 µg/m³, on GBD 2019 curves.
- GBD 2019 India: 0.98M ambient deaths.
- AQLI 2025, Delhi: 8.2 years against 5 µg/m³.

A reasonable target is within about 15% when inputs match; the builder sets and justifies
tolerances per case.

**Worked cases.**

- *Delhi 100 → 80 µg/m³*, across every curve. This is the tool's signature output.
- *Surat's "benefits at least 25× costs"* (Greenstone, Pande, Ryan, Sudarshan, QJE 2025).
  Read how the paper gets from emissions to mortality benefit, reproduce it, then show the
  ratio under each curve and valuation. If the paper's method cannot be mapped onto this
  tool, say so plainly instead of forcing it.

## Data and licences

Two tiers.

- **Open tier, committed to the repo:** exposure series (AQLI, ACAG-derived), population,
  SRS abridged life tables transcribed from the Registrar General's PDFs, published curve
  parameters (GEMM, log-linear presets, AQLI), share of deaths by broad cause and age from
  the SRS cause-of-death reports. With only this tier the log-linear, GEMM NCD+LRI and AQLI
  curves work.
- **Local tier, never committed:** IHME files — GBD risk curves, state deaths by cause. Kept
  in a git-ignored folder. There is no fetch script: IHME delivers by web query behind a
  login. The builder writes an exact download list (which tool, which selections, which
  filenames) and a loader that checks the folder; Akash downloads the files by hand. With
  this tier the GBD and GEMM five-cause curves work.

**What derived from IHME data may be committed** (Claude's call; Akash has said to defer the
licence question): charts that draw a GBD curve, result tables, and benchmark write-ups may
be committed. Tabulated curve values, state cause-of-death tables, and test fixtures that
embed either may not; tests that need them skip when the local tier is absent. Precomputed
results for the web page are decided when the page is built. Nothing is pushed to the public
remote without Akash saying so.

The tool must run with the open tier alone and say clearly which curves are unavailable.
Do not copy IHME-derived files from `creahia` or `PM2.5-attr-mort`; both carry the same
restriction. Those packages are GPL or MIT; read them for method, do not paste GPL code.

## Provenance rule

Every number in a data file or a curve definition carries: source, link, table or page,
date retrieved, licence, and whether it was downloaded or transcribed by hand. Hand-
transcribed tables get a spot check against the source. A parameter that cannot be found at
its source is left out and listed as missing. The research sweeps' reports are leads, not
sources.

## Constraints

- The public repo (`dogluk/air-apocalypse`) must never receive IHME data.
- Keep the calculation separate from file reading and from the terminal interface, and keep
  inputs as plain tables, so the later web page can reuse the logic or its precomputed
  results.
- The open tier should stay small enough to commit (tens of megabytes at most); large
  rasters are processed by a script and only the derived tables are kept.

## Build order

Each stage ends with something runnable. If time runs out, later stages are the ones cut.

1. Open-tier core: life tables, exposure maps, log-linear / GEMM NCD+LRI / AQLI curves,
   steady-state mode. Ends with Delhi 100 → 80 on the open curves and the open-tier
   reproduction benchmarks (Jaganathan, AQLI Delhi, Burnett NCD+LRI).
2. Intervention files, uncertainty, odds of success and cost.
3. Local tier: GBD and GEMM five-cause curves, remaining reproduction benchmarks. Blocked
   until the IHME files are in the folder; the code is written and skips cleanly without them.
4. Run to 2050 and the ageing chart.
5. Valuation presets.
6. The Surat worked case.

Version one is complete when stages 1–2 and 4–6 run on the open tier and stage 3 has been
run at least once against real IHME files.

## Housekeeping that ships with this version

- Fix the equation in `README.md` and `bets/README.md`: concentration ≈ emissions ÷ (mixing
  height × wind speed). As written, "ventilation" counts mixing height twice. Add one line on
  what the equation leaves out (exposure, secondary particles, imported air, removal).
- Revise the "burden-of-disease estimates" line in `lit/gaps.md`: another estimate adds
  nothing, but a tool that exposes why estimates differ does.
- Add `health/` to the tracks table in `README.md`.

## Left to the builder

Module layout; exact command names and flags; file formats for data tables; chart details
within the repo's existing style; number of Monte Carlo draws; the life-table closing
method; how to interpolate tabulated curves; test framework; per-benchmark tolerances;
whether persons-combined or sex-specific life tables are used (persons-combined is fine).

## Known limitations to state in the README

- State death rates are applied to districts and cities.
- Ambient only; in states with heavy solid-fuel use this misplaces people on the curve.
- India's cause-of-death shares rest on a survey that ended in 2013.
- The post-2036 population path is a crude extension.
- All curves above about 84 µg/m³ are extrapolations; the tool shows the disagreement, it
  does not resolve it.
