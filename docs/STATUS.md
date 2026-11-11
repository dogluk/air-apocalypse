# Where this stands

Last updated 2026-11-11. Read this first when picking the project up.

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
../.venv/bin/python -m pytest -q                       # 185 tests
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

1. **Pre-2020 warning (known defect).** Runs for years before 2020 print death counts about
   15% low with nothing on screen saying so (`health/airhealth/report.py`, `deaths_note`).
   The scaling factor is measured on 2020-24 and applied to every year. Fix: per-year SRS
   rates (listed in `health/data/MISSING.md`), or at least a printed warning. Until then use
   the default year for death counts.
2. **A switch for every input.** Design note, not yet agreed:
   [`specs/2026-11-11-source-switches.md`](specs/2026-11-11-source-switches.md).
3. **IHME curves** (design stage 3): loaders for GBD 2019 and GBD 2023 curves and GEMM five
   causes. Needs the Part B queries. Read the status section of `IHME_DOWNLOADS.md` first:
   the 2023 files are on two different scales.
4. **GBD 2023 exposure as a fifth map.** The file is downloaded. Needs IHME's state ids.
5. Cohort run to 2050 (stage 4), valuation presets (stage 5), the Surat 25× case (stage 6).
6. Air-response layer (emissions to concentration), the dome effect, a public web page.

## Other open work

- **The evidence review** (`lit/evidence.md`: interventions observed to work, and the three
  things most worth doing) was asked for at the start and set aside for the health model.
  Not written.
- **G1** in `lit/gaps.md`: did firecracker bans work? The data is already in `diwali/`.
- **G7** has a first answer: GBD 2023's India exposure is 54, not 91. See the note there.

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
`health/airhealth/dashboard.py`.
