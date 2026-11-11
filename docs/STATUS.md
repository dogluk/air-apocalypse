# Where this stands

Last updated 2026-11-11. Read this first when picking the project up.

## In plain words (rewritten at the end of every session)

**What we are building.** A calculator: "if PM2.5 in place X goes from A to B, how many deaths
a year are avoided and how many years of life are gained?" It answers on five published risk
curves side by side, never one, because they disagree by several times. Later it prices
interventions (cost per life-year) and becomes a public page on dogl.uk. Akash's role:
direction and taste, and bringing in researchers to check and push it; Claude makes the
technical calls and writes them down so an expert can check them quickly.

**Where it is.** Works for India, every state and ten cities, from the command line and a
local dashboard (`airhealth dashboard`): place, map, year, a source for each input, a district
map. Checks itself against three published studies and lands where it should.

**Done 2026-11-11 (all committed locally, nothing pushed).**
1. Years before 2020 use that year's own SRS death figures (was up to a sixth off).
2. Dashboard: a year selector and a district map of PM2.5.
3. A switch for every input: population, death rates and the death count can each come from
   the Indian government or the UN (World Population Prospects 2024); the result names its
   sources and says when it mixes them; giving several sources prints the range. Finding:
   across sources India's numbers move about 15%; across risk curves, about 8 times. The
   curve is the choice that matters.

**Next session.** The IHME (GBD) risk curves, once the Part B data is downloaded. Akash
signs in to IHME in a browser window Claude drives (Playwright); Claude runs the queries
in `health/IHME_DOWNLOADS.md` Part B and writes the loader. Without that, next is either
the evidence review (`lit/evidence.md`, which interventions are observed to work) or a
one-page "methods for reviewers" note to send to researchers.

**Waiting on Akash.** (1) Fifteen minutes to sign in to IHME in the browser Claude opens.
(2) When to push.

## What exists

- `diwali/`: finished 10-city, 10-year PM2.5 analysis.
- `lit/`: `landscape.md` (who is doing what in Indian air quality), `gaps.md` (G1-G7).
- `bets/`: interventions sorted by the physics.
- `health/`: `airhealth`, a Python library and command line that scores a PM2.5 change in an
  Indian place on five risk curves. Start with [`health/README.md`](../health/README.md).
  Design: [`specs/2026-11-10-health-model-design.md`](specs/2026-11-10-health-model-design.md).
  Plan that was built (stages 1-2): [`plans/2026-11-10-health-model-core.md`](plans/2026-11-10-health-model-core.md).

## How to look at it

```
cd health
../.venv/bin/airhealth dashboard                       # local page, http://127.0.0.1:8765/
../.venv/bin/airhealth compare Delhi --from 100 --to 80
../.venv/bin/airhealth burden India
../.venv/bin/airhealth run interventions/november_only_delhi.toml
../.venv/bin/python -m pytest -q                       # 215 tests
```

## Git

Local commits on `main` only. **Nothing from the health work has been pushed**, and it is not
to be pushed until Akash says so. IHME files live in `health/data_local/` (git-ignored) and
are never committed.

## Waiting on Akash

1. **IHME queries (Part B of [`health/IHME_DOWNLOADS.md`](../health/IHME_DOWNLOADS.md)).**
   Deaths by cause, age and state, and population, from the GBD Results tool. The risk-curve
   files (Part A) are already in `health/data_local/ihme_raw/`.
2. **Death-count default.** Deferred on purpose. SRS-scaled stays the default; see the
   source-switches note below.
3. **When to push.**

## Next builds, in order

1. **IHME curves** (design stage 3): loaders for GBD 2019 and GBD 2023 curves and GEMM five
   causes. Needs the Part B queries (Claude drives the browser; Akash signs in). Read the
   status section of `IHME_DOWNLOADS.md` first: the 2023 files are on two different scales.
   GBD deaths then become a third source for `deaths` (`airhealth/inputs.py`).
2. **GBD 2023 exposure as a fifth map.** The file is downloaded. Needs IHME's state ids.
3. **A methods note for reviewers**: one page per input and curve, what was chosen and why,
   what would change the answer most. For Akash to send to researchers.
4. Cohort run to 2050 (stage 4), valuation presets (stage 5), the Surat 25× case (stage 6).
5. Air-response layer (emissions to concentration), the dome effect, a public web page.

## Other open work

- **The evidence review** (`lit/evidence.md`: interventions observed to work, and the three
  things most worth doing) was asked for at the start and set aside for the health model.
  Not written.
- **G1** in `lit/gaps.md`: did firecracker bans work? The data is already in `diwali/`.
- **G7** has a first answer: GBD 2023's India exposure is 54, not 91. See the note there.

## Done 2026-11-11

Years before 2020 now use that year's own SRS figures: the nine Statistical Reports 2011-19
are transcribed (crude death rates, rates by age, age shares; `health/data/sources.toml`),
death rates by age are moved band by band to each year's, and counts are scaled to each
year's crude death rate (`health/data/death_reconciliation_by_year.csv`). Before, a 2014 run
had 5.7 deaths per 1,000 against the SRS's 6.7; now it matches. Two benchmarks' expected
ratios moved with it (Jaganathan deaths 1.185 → 1.392, Burnett at 74 µg/m³ 0.754 → 0.816);
both write-ups had predicted the direction. Years after 2024 still carry a footer warning.

## Small known issues in `health/`

Ages 25-29 borrow the 15-29 cause-of-death share. Fifteen small states and territories use
the all-India life table. City populations are Census 2011. Cooking smoke is excluded. Our
ACAG India mean (49.8) is above ACAG's own summary (47.1), unexplained. Full list:
"Known limitations" in `health/README.md`.

## Calls Claude made during the build that Akash has not reviewed

Positive AQLI numbers mean years gained. Each curve applies from its own starting age
(Jaganathan all ages, Brown 15, GEMM and Vodonos 25; Vodonos's source says all-age). Map
populations are scaled to the year asked for. Death counts are reconciled to each state's
SRS crude death rate. The dashboard's table of inputs is hand-written in
`health/airhealth/dashboard.py`. For 2011-19: each year's rates by age average it and a
year either side; states with no SRS rates by age that year borrow India's change; the
early-year scaling is at 45 and over, like 2020-24's.
