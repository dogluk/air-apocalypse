# Where this stands

Last updated 2026-11-11. Read this first when picking the project up.

## In plain words (rewritten at the end of every session)

**What we are building.** A calculator: "if PM2.5 in place X goes from A to B, how many deaths
a year are avoided and how many years of life are gained?" It answers on five published risk
curves side by side, never one, because they disagree by several times. Later it prices
interventions (cost per life-year) and becomes a public page on dogl.uk.

**Where it is.** The calculator works for India, every state and ten cities, from the command
line and from a local dashboard (`airhealth dashboard`). It checks itself against three
published studies and lands where it should, with the gaps explained.

**Last session (2026-11-11).** Fixed death counts for years before 2020: they used 2020-24
death rates and came out up to a sixth wrong. Now each year uses the government survey's (SRS)
own figures for that year. Committed locally (`4b67ed2`), not pushed.

**Next session.** "A switch for every input" (next builds, item 1). Today some inputs have
one source hard-wired: death rates by age, population, cause-of-death shares. Where credible
sources disagree, the tool should let you pick, say which one it used, and show how much the
answer moves between them. Concretely: add the UN's population and death estimates (World
Population Prospects) as a second source, put a dropdown for each input on the dashboard,
and print the spread. Three questions in the design note; defaults are proposed there.

**Waiting on Akash.** (1) The IHME downloads, Part B of `health/IHME_DOWNLOADS.md`: about an
hour of form-filling on IHME's site with a free login; unblocks the GBD risk curves.
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
../.venv/bin/python -m pytest -q                       # 193 tests
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

1. **A switch for every input.** Design note, not yet agreed:
   [`specs/2026-11-11-source-switches.md`](specs/2026-11-11-source-switches.md).
2. **IHME curves** (design stage 3): loaders for GBD 2019 and GBD 2023 curves and GEMM five
   causes. Needs the Part B queries. Read the status section of `IHME_DOWNLOADS.md` first:
   the 2023 files are on two different scales.
3. **GBD 2023 exposure as a fifth map.** The file is downloaded. Needs IHME's state ids.
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
