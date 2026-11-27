# Where this stands

Last updated 2026-11-28. New to the repo? Read [`../AGENTS.md`](../AGENTS.md) first.

## In short

**What is being built.** A calculator: "if PM2.5 in place X goes from A to B, how many deaths
a year are avoided and how many years of life are gained?" It answers on several published
risk curves side by side, never one, because they disagree by several times. Next it is
being extended to rank measures by expected life-years per rupee across ~50 Indian cities,
long shots included. The first ranking is meant for researchers who can check it.

**Where it is.** India, every state and **50 cities** (APnA's 49 airsheds plus Delhi), from the
command line and a local dashboard. Eight curves (three need IHME files that cannot be
shared), five exposure maps, eight benchmarks within band. Every place has a
**month-by-month PM2.5 pattern** from CPCB monitors (Delhi: November 2.4× its annual mean,
July 0.3×); places without their own monitors borrow from their state's cities, then all the
state's monitors, then India, and say so. A percent cut in chosen months is weighted by how
dirty those months are.

**Causes by city.** `health/data/causes.csv` holds what causes PM2.5 in each city according to
every study read at source, side by side: APnA for 49 cities, McDuffie 2021 for 9, government
and research studies for 11 (Delhi, Kolkata, Lucknow, Kanpur, Patna, Agra, Mumbai, Pune,
Bengaluru, Hyderabad, Surat), stubble shares for Delhi. Every row says where its pollution
comes from (`origin`: inside the city, from anywhere, or a geographic split).
`airhealth causes Kanpur` shows them side by side. A second pass re-read ~230 rows at source
and found no wrong number.

**Measures and ranking (built 2026-11-28).** A library of 22 measures
(`health/interventions/library/`), each number read at source or flagged; `airhealth score CITY`
scores them on every curve and every source study; `airhealth rank` ranks them per city and for
all India (never averaging curves); `airhealth rank --sensitivity` shows which inputs reorder the
ranking; ranking benchmarks in `health/benchmarks/RANKING.md`; a ranking tab on the dashboard.
Design: [`specs/2026-11-12-intervention-ranking-design.md`](specs/2026-11-12-intervention-ranking-design.md).

**Bengaluru end to end.** [`cities/bengaluru/index.html`](../cities/bengaluru/index.html): the
air (monitors 2016-2025, satellites, gases), its sources, its health toll and the measures,
generated from the repo. Design: [`specs/2026-11-27-bengaluru-page-design.md`](specs/2026-11-27-bengaluru-page-design.md).

## Next, in order

1. **An open source-receptor table.** The stubble and coal tables are stand-ins (the stubble one
   is about 14 times smaller than Lan et al. 2022's national figure), so every regional measure
   is understated. District-level receiving changes from a published model would fix it.
2. **Full costs for the top city measures.** The waste-burning ban and construction-dust controls
   rank on enforcement-only costs (`partial_cost`).
3. **Widen measures to more cities** where a per-city count can be read at source (leads in
   `health/data/MISSING.md`; cheapest: diesel-generator kVA and kiln counts per city).
4. **Reproduce GBD's own India burden** (969,726 outdoor-PM2.5 deaths in 2023; this tool gives
   1.61 million on the same curve, map and year). Needs GBD 2023's household air pollution
   file (GHDx record 594794, no login) and GBD's split between outdoor air and cooking smoke.
   Then a benchmark for `gbd2023`, and one for `gbd2019` against Pandey et al. 2021.
5. **A GBD all-cause death source** (`--deaths gbd`), from one more IHME Results-tool query.
6. Later: a cohort run to 2050, valuation presets, the Surat emissions-trading case, an
   emissions-to-concentration layer, a public web page.

## Gaps a person could close in minutes

From [`health/data/MISSING.md`](../health/data/MISSING.md): open Fig. 3 of Biswal et al. 2025
(the publisher blocks scripted downloads) to place Ludhiana, Amritsar and Chandigarh in its
stubble regions; find the Lok Sabha written answer of 10 March 2025 (stubble shares for Delhi
2020-24, now only in press reports); read Nagar & Sharma 2022's own numbers (Urban Climate
41:101084). Chennai (interim report, no shares) and Ahmedabad (PM, not PM2.5) have no city
study.

## Other open work

- **An evidence review** (`lit/evidence.md`: interventions observed to work, and the three
  things most worth doing). Not written.
- **G1** in `lit/gaps.md`: did firecracker bans work? The data is already in `diwali/`.
- **G7** has a first answer: GBD 2023's India exposure is 54, not 91. See the note there.

## What exists

- `diwali/`: finished 10-city, 10-year PM2.5 analysis.
- `lit/`: `landscape.md` (who is doing what in Indian air quality), `gaps.md` (G1-G7),
  `open-work-and-people.md`, `prior-rankings.md`.
- `bets/`: interventions sorted by the physics.
- `health/`: `airhealth`, the Python library and command line. Start with
  [`health/README.md`](../health/README.md). Design notes in [`specs/`](specs/).

## How to look at it

```
cd health
../.venv/bin/airhealth dashboard                       # local page, http://127.0.0.1:8765/
../.venv/bin/airhealth compare Delhi --from 100 --to 80
../.venv/bin/airhealth burden India
../.venv/bin/airhealth run interventions/november_only_delhi.toml
../.venv/bin/python -m pytest -q                       # all pass; 18 skip without IHME files
```

IHME files live in `health/data_local/` (git-ignored) and are never committed.

## Small known issues in `health/`

Ages 25-29 borrow the 15-29 cause-of-death share. Fifteen small states and territories use
the all-India life table. City populations are Census 2011. Cooking smoke is excluded. Our
ACAG India mean (49.8) is above ACAG's own summary (47.1), unexplained. Full list:
"Known limitations" in `health/README.md`.

## Modelling calls not yet reviewed by a specialist

Positive AQLI numbers mean years gained. Each curve applies from its own starting age
(Jaganathan all ages, Brown 15, GEMM and Vodonos 25; Vodonos's source says all-age). Map
populations are scaled to the year asked for. Death counts are reconciled to each state's
SRS crude death rate. The dashboard's table of inputs is hand-written in
`health/airhealth/dashboard.py`. For 2011-19: each year's rates by age average it and a
year either side; states with no SRS rates by age that year borrow India's change; the
early-year scaling is at 45 and over, like 2020-24's.
