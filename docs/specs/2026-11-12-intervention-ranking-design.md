# Ranking interventions, city by city: design

Status: **for Akash's approval, 2026-11-12** (reviewed by a builder; two questions answered by Akash). Decisions marked *(Akash)* are his; *(Claude's call)*
marks a technical choice made so he can wave it through or overrule it. Nothing here is built.

## What it is for

`airhealth` answers "if PM2.5 in place X goes from A to B, how many deaths and life-years?" on
eight risk curves side by side. This stage adds the question that matters for action: **which
measures buy the most life-years per rupee, in which city, and how sure are we?** For each of
about 50 Indian cities, it ranks a library of measures (long shots included) by expected
life-years per rupee, on every curve, and shows where the curves disagree on the order.

It is part of the model, not a report *(Akash: "we're integrating this into our model")*: new
data in `health/data/`, a library of intervention files, a `rank` command, a dashboard tab and
benchmarks in the existing suite. Everything the ranking needs flows through the existing
`intervention.load` → `simulate.run` path.

**Who reads it first** *(Akash)*: researchers who can check it (CREA; Sarath Guttikunda, whose
APnA dataset is the backbone of the causes layer, so he will be checking his own numbers as we
used them) and smart friends. So every number must trace to a source in one click, and the top
layer must make sense in a minute.

## Goals

1. **Thin and wide** *(Akash)*: ~50 cities (APnA's 49 airsheds), not one airshed in depth.
2. **Causes by city**, every study side by side, never one winner, with the share that blows in
   from outside the city as its own column.
3. **A library of measures**, ~25 in the first pass *(Claude's call)*, each stating what it cuts,
   in which months, by how much (a range), what it costs (a range, scaling with city size), the
   odds it works, and citations. Includes measures that cut exposure rather than the air
   *(Akash: "yeah bc reducing exposure reduces deaths")* and long shots with low odds.
4. **Month by month throughout** (stubble is Oct-Nov, heating is winter, dust is pre-monsoon).
   Winter-only measures are scored by what they do to the annual mean, using each city's own
   monthly profile.
5. **A ranking per city per curve**, expected value (× odds) and "if it works" both shown,
   with flips between curves flagged.
6. **Benchmarks** against published cost-per-life figures, in the existing benchmark suite.

## Non-goals (this stage)

- No emissions-to-concentration chemistry. "Share × cut" assumes cutting a cause by x% cuts its
  share of PM2.5 by x%. Real chemistry is non-additive (secondary particles, ammonia limits) and
  the dome effect is ignored. Said on every result. (The air-response layer is a later stage.)
- No co-benefits (climate, crop yields, time saved). Health only, and the README says so.
- No political-feasibility model beyond the odds number.
- No public page, and nothing pushed until Akash says.
- No valuation in money (VSL); the metric is life-years and deaths per rupee.

## Anti-goals (would make it a failure even if it runs)

- One confident "best measure" that hides an ~8× disagreement between curves.
- Placeholder numbers that look like estimates. Every placeholder is flagged as one in the data
  and in the output.
- A ranking that quietly favours measures with better data (a measure with no cost estimate is
  shown as unranked, not dropped).
- A city credited with cutting air that blows in from elsewhere.

## Constraints (carried from the project)

- No number enters code or data unless read at its source; each data row carries the
  `[O]/[S]/[R]` evidence key from `lit/`. [S] and [R] values may be used only flagged as such.
- IHME data is never committed; the IHME curves run only where `data_local/` exists, as today.
- Licences: APnA is CC BY 4.0 (attribute). NCAP reports: facts may be tabulated with citation,
  PDFs not rehosted. GBD MAPS India (HEI): copyrighted; keep any transcription in `data_local/`
  until the licence is checked *(Claude's call)*.
- Commit locally on `main`; no push.

## The parts

### 1. Cities and their months

- Add APnA's 49 airsheds to `data/cities.csv` (today 11), each mapped to its districts on the
  AQLI and ACAG maps, with Census 2011 population as now.
- **Monthly profile per city**: mean PM2.5 by month from CPCB monitors (the raw yearly files the
  `diwali/` analysis downloaded), 2023-25 by default. Computed for 11 cities on 2026-11-12:
  Delhi Nov 235 / Jul 35 / annual 100, with 60% of the year's exposure in Oct-Jan. Cities with no
  monitor borrow the nearest monitored city in the same state, flagged.
- The profile is a *shape* (each month ÷ the annual mean). The annual level still comes from the
  chosen exposure map. Places that are not cities (states, rural districts, which regional
  measures reach) take the population-weighted shape of the monitored cities in their state,
  or the nearest state's, flagged *(Claude's call)*.
- **Ranking map: `acag_total` by default** *(Claude's call)*. APnA's shares are shares of
  *total* PM2.5, including dust and sea salt; AQLI removes both, so AQLI × APnA would understate
  every dust measure. Other maps stay available as a switch, with a note that they mismatch.
- **Fixes a known bug**: `monthly_pct` today assumes every month is as dirty as the average
  (README and `report.py` warn about it). With profiles, a 20% November cut in Delhi is
  20% × 2.35 × the annual mean × 30/365, not 20% × the annual mean × 30/365, about 2.4× larger.

### 2. Causes by city (`data/causes.csv`)

One row per city × study × season × source, the schema already proposed in
`lit/city-sources.md` §5: `city, study, institution, year_sampled, season, size_fraction,
method, metric, boundary, source_raw, source_harmonised, share_pct, outside_share_pct, n_sites,
n_days, url, evidence_key`.

- **First pass:** APnA for all 49 (the spine); McDuffie 2021 Supplementary Data 1 (17 cities);
  the NCAP/TERI/CSTEP reports already read for the big cities in `lit/city-sources.md`.
- **Harmonised causes** *(Claude's call)*: transport, residential (cooking and heating), industry
  (incl. power), road and construction dust, waste burning, diesel generators, brick kilns,
  agricultural burning, natural (sea salt, desert dust), secondary-unassigned, outside.
- **Only concentration shares are used** to rank. Emissions shares are kept with
  `metric = emission_share` and shown, never used.
- **Seasons:** where a study gives seasons, its shares apply to those months; an annual share
  applies flat across the year, flagged.
- **Which study the ranking uses** is a source switch like the others (`--use causes=apna`,
  default APnA because it is the only one covering every city), and a run can ask for several
  to see if the order changes.
- **Known gap: stubble.** APnA has no agricultural-burning column; it sits inside "outside".
  Stubble measures need a monthly share for IGP cities in Oct-Nov (candidates: IITM's Delhi
  decision support system, SAFAR daily stubble shares, Lan et al. 2022). Sourcing this is part
  of the build.

### 3. The library (`interventions/library/*.toml`)

The existing intervention format, extended. A library file describes a measure in general; the
ranking turns it into one intervention per city.

- **`kind`**: `air` (cuts a cause) or `exposure` (cuts what people breathe).
- **`scope`**: `city` (acts inside a city; benefits that city's population) or `region` (acts on
  named states, e.g. Punjab stubble or IGP power plants). A city measure can only cut the
  inside-city share. **A regional measure's benefit counts everyone who breathes the result,
  downwind included** (stubble in Punjab reaches Delhi, Haryana, UP, Bihar), urban and rural
  *(Claude's call)*. The PM2.5 change by district comes from a published source-receptor result
  where one exists (stubble: Lan et al. 2022, district-level, adjoint model; coal plants: the
  plant-level work behind Cropper et al. / DCP3), else from McDuffie 2021's gridded sector
  fractions clipped to districts (CC BY; fetch only the needed sector files, not all ~126 GB).
  GBD MAPS India stays a local-only cross-check. A regional measure is ranked once for its
  whole reach; city tables show the part that reaches the city, marked "regional".
- **`[targets]`** (air): which harmonised causes, cut by what fraction (Dist), in which months,
  in which cities (all, a list, or every city where the cause's share exceeds a threshold).
- **`[exposure]`** (exposure): share of people covered, share of hours it works, cut in what
  they breathe during those hours (Dists). **Applied to the covered people only** *(Claude's
  call)*: the population is split into covered and not covered, and the covered group's
  exposure falls by hours × cut. Averaging over everyone (coverage × hours × cut) would be wrong
  on curves that flatten at high levels. This needs a small extension to `simulate.run` (a
  change that applies to a share of a place's population). The curves are built on outdoor
  levels with indoor time already baked in, so the cut is relative to that normal mix.
- **Cost** scales with a stated driver (per person covered, per household, per acre, per stack,
  per city), so the same measure costs more in a bigger city. **All costs are brought to 2025
  rupees** with India's GDP deflator (World Bank) *(Claude's call)*; the tool's no-inflation rule
  was fine for one file but would make a 2009-priced scrubber look ~2× cheap against a 2025
  purifier. Whose rupees count: see "Decided after review".
- **`p_success`** as today. Exposure measures get lower odds by default than cuts to outdoor air,
  because no trial shows purifiers or masks cut deaths (they show lower indoor PM2.5 and blood
  pressure) *(Claude's call)*.
- **`who_reaches`**: free text, shown in the output, e.g. "households that can run a purifier".
- **First ~25 measures**, drawn from `bets/README.md` and `lit/prior-rankings.md`. Indicative:
  stubble payments with part upfront; Happy Seeder subsidy; buying Punjab out of rice; FGD
  scrubbers; a Surat-style emissions market; old-vehicle retirement; electric buses; road
  paving and mechanical sweeping; construction-dust enforcement; waste collection with a
  burning ban; zig-zag brick kilns; diesel-generator replacement; industrial fuel switch;
  LPG refill subsidy; home purifiers; school purifiers; N95 distribution in winter; smog towers
  (long shot); winter cloud seeding (long shot, near-zero odds per `bets/`). The builder picks
  the final set by what has a citable cut and cost.

### 4. The arithmetic

For city *c*, month *m*, measure *i*:

ΔPM(c, m) = level(c) × shape(c, m) × Σ over causes k of share(c, k, m) × cut(i, k, m)

Annual Δ = day-weighted mean of the twelve. That annual change is handed to `simulate.run` as a
normal intervention, which already gives deaths and life-years on every curve with uncertainty,
odds, the cessation lag and cost. Life-years per rupee = life-years ÷ cost, expected (× odds)
and if it works.

**Time and discounting** *(Claude's call)*. Every measure is scored on the same footing: all
life-years it causes count, including those that arrive after it ends (under the EPA 20-year
lag, a one-winter mask handout delivers most of its benefit in later years; today's tool drops
them, which would understate short measures several times). The horizon is the measure's
duration plus 20 years. Costs and life-years are both discounted at 3% a year, the usual
cost-effectiveness convention (WHO-CHOICE, DCP3); 0% is a switch. Capital and running costs
are both just costs in the year they fall.

- **One sensitivity**, not the default: apply the curves month by month instead of to the annual
  mean. On curves that flatten at high levels, winter cuts in Delhi look worse. A test of
  whether the ranking flips, not a second answer.
- **Short-term (daily) deaths are not added**: they are mostly part of what the annual-mean
  curves already count.

### 5. Output

- `airhealth rank` (all India, the headline) or `airhealth rank Delhi`: a table per curve, measures in order, life-years per crore
  rupees with ranges, odds, who it reaches, regional or city, and flags (placeholder,
  borrowed profile, annual share used for a seasonal cause, [S]/[R] values). A "curves disagree"
  column marks measures whose rank moves by more than a set amount between curves.
- CSV of the same, with every input's source per row.
- A dashboard tab: pick a city and curve; each row opens to the trail: cause share (which study),
  cut (citation), cost (citation), odds (reason).

### 6. Benchmarks and checks

- Into `benchmarks/cases.toml`, same rules (expected ratio, narrow band, reasons written first):
  stubble payments, ~$3,600-5,400 per life (Jack, Jayachandran, Kala, Pande 2025); FGD scrubbers,
  ~$131k-400k per life (Cropper et al., DCP3); the World Bank GAINS ~$7,600 per life; TERI 2021's
  ₹ per µg/m³ for Delhi; CREA's `creahia` on one shared case. Each read at source before use.
- Checks: `causes.csv` reproduces the APnA CSV exactly; monthly profiles reproduce the CPCB
  annual means already in `data/exposure_cpcb.csv`; the `monthly_pct` fix moves the
  November-only Delhi example by the expected factor.

## Decided after review (2026-11-12)

1. **An all-India table is the headline, plus one table per city** *(Akash)*. Within a city most
   curves agree on the order; across places they disagree (curves that flatten at high levels
   favour cleaner cities), so curve flips are defined on the all-India table.
2. **The funder's rupees** *(Akash)*: what a government or philanthropist would have to spend.
   Society's net cost is a second column where a source gives it. Measures that save money
   overall (TERI puts zig-zag kilns and LPG below zero) are listed separately as "pays for
   itself", not ranked by a ratio.

## Order (for the plan)

1. Cities and monthly profiles; the `monthly_pct` fix.
2. Causes dataset (APnA, McDuffie, the big-city studies); the stubble share.
3. Library format (kind, scope, targets, exposure, cost drivers); the first ~25 files.
4. `rank` command and CSV; benchmarks.
5. Dashboard tab.
6. Second pass: clean cooking, which needs household-exposure data and GBD's household curve
   (GHDx 594794, also needed to reproduce GBD's own burden).

## Left to the builder

File layout inside `airhealth/`; how cost drivers are named; the rank-flip threshold; how
regional benefits are split across cities in the city tables; the exact first 25; whether
generated rank CSVs are committed or written on demand.
