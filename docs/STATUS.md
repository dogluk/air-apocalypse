# Where this stands

Last updated 2026-11-11. Read this first when picking the project up.

## In plain words (rewritten at the end of every session)

**What we are building.** A calculator: "if PM2.5 in place X goes from A to B, how many deaths
a year are avoided and how many years of life are gained?" It answers on several published
risk curves side by side, never one, because they disagree by several times. Now being
extended to rank measures by expected life-years per rupee across ~50 Indian cities, long
shots included. Akash's role: direction and taste; Claude makes the technical calls and
writes them down. Audience for the first ranking: researchers who can check it (CREA, Sarath
Guttikunda) and smart friends.

**Where it is.** India, every state and **50 cities** (APnA's 49 airsheds plus Delhi), from the
command line and a local dashboard. Eight curves, five exposure maps, eight benchmarks within
band. Every place now has a **month-by-month PM2.5 pattern** from CPCB monitors (Delhi:
November 2.4× its annual mean, July 0.3×); places without their own monitors borrow from their
state's cities, then all the state's monitors, then India, and say so. A percent cut in
chosen months is now weighted by how dirty those months are (it used to treat every month
as average, understating a Delhi winter cut ~2.4×).

**Done 2026-11-12 (committed locally, nothing pushed).**
1. Ranking design agreed: `docs/specs/2026-11-12-intervention-ranking-design.md` (Akash:
   thin and wide; exposure measures in; all-India table as the headline plus one per city;
   the funder's rupees).
2. Plan A of four built and reviewed: `docs/plans/2026-11-12-cities-and-months.md` (50 cities,
   monthly tables, `airhealth/months.py`, the monthly_pct fix). 267 tests pass.
3. X searched (credits back): thin; leads in `lit/open-work-and-people.md`.

**Next session: plan B, causes by city.** Write and run the plan for spec part 2: parse APnA
into `data/causes.csv` (spec schema), add McDuffie 2021's 17 cities and the big-city NCAP/TERI
studies from `lit/city-sources.md`, a `--use causes=` switch, and a monthly stubble share for
IGP cities (APnA has none; it sits inside "outside"). Carry-overs: confirm APnA's base years
from its papers before using them (the Zenodo record does not state them); fix the README line
saying all fifty cities have a CPCB station (seven have none); `census_name` keeps the
workbook's footnote markers (strip before joining); Asansol's two satellite maps use different
district sets; Jharkhand and 10 other states still use India's monthly pattern (their monitors
miss months). Then plan C (library and engine) and plan D (ranking, benchmarks, dashboard tab).

**Waiting on Akash.** (1) When to push. X search done 2026-11-12: thin,
see `lit/open-work-and-people.md`.

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
../.venv/bin/python -m pytest -q                       # 241 tests (18 skip without IHME files)
```

## Git

Local commits on `main` only. **Nothing from the health work has been pushed**, and it is not
to be pushed until Akash says so. IHME files live in `health/data_local/` (git-ignored) and
are never committed.

## Waiting on Akash

1. **IHME:** Part A and Part B are downloaded and in use. Next sign-in, two small extras: the
   GBD 2023 risk-curve information sheet and an "All causes" deaths query (see Next builds).
2. **Death-count default.** Deferred on purpose. SRS-scaled stays the default; see the
   source-switches note below.
3. **When to push.**

## Next builds, in order

Done 2026-11-11 (evening, not yet committed when written): design stage 3, the IHME tier.
A fifth map, `gbd2023` (IHME's state values, read from `data_local/` at run time), and three
curves, `gbd2023`, `gbd2019`, `gemm_5cod`, on IHME's deaths by cause, state and age
(`health/airhealth/ihme.py`, `ihme_curves.py`; `tests/test_ihme.py`; two new benchmarks,
both within band). The two-scales question is settled (the 2025-dated files are ln RR), the
TMREL is GBD's 2.4-5.9 midpoint. See the status section of `health/IHME_DOWNLOADS.md`.

1. **Reproduce GBD's own India burden** (969,726 ambient-PM deaths in 2023; this tool gives
   1.61 million on the same curve, map and year). Needs GBD 2023's household air pollution
   file (GHDx record 594794, 13.9 MB, no login) and GBD's proportional ambient/household
   split. Then a benchmark for `gbd2023`, and one for `gbd2019` against Pandey et al. 2021.
2. **A GBD all-cause death source** (`--deaths gbd`): one more Results-tool query, "All
   causes" deaths by state and age. Also the GBD 2023 information sheet for the risk curves
   (login), to confirm the log scale in IHME's own words.
3. **The intervention ranking** (design in progress, see "Next session" above).
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
