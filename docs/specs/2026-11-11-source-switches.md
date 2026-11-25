# A switch for every input: design note

Status: **agreed 2026-11-11** (Akash: "go ahead", taking Claude's defaults on the three open
questions: mixing allowed with a note; switches before the IHME curves; UN WPP 2024 first).
The build is described under "As built" at the end.

## What was asked

"We probably need the ability to take each variable we depend on and have a knob/switch for
using different sources." The trigger was the death count: the government survey (SRS) and
the UN disagree by about a tenth, and Akash does not want to pick one now. The same is true
of most inputs, so the answer is a general one: the tool should not hard-code a winner
anywhere a credible source disagrees with another.

## Where things stood (before the build; see "As built")

| Input | Sources today | Switchable? | Candidates not wired |
|---|---|---|---|
| Risk curve | Jaganathan, Brown, Vodonos, GEMM, AQLI | yes, `--curves` | GBD 2019, GBD 2023, GEMM five causes |
| Exposure map | AQLI, ACAG total, GBD 2019 (states), CPCB (cities) | yes, `--map` | GBD 2023 (file is downloaded) |
| Death count | SRS-scaled; population × life-table rates; UN WPP 2024 | yes, `--use deaths=` | GBD |
| Counterfactual | each curve's floor; one number | yes, `--counterfactual` | |
| Death rates by age | SRS abridged life tables 2020-24 (2011-19 moved by each year's SRS rates by age); UN WPP 2024 | yes, `--use death_rates=` | GBD |
| Population by age | Government projections 2011-2036; UN WPP 2024 | yes, `--use population=` | GBD, Census 2011 (cities) |
| Share of deaths that are NCD + LRI | SRS cause of death 2021-23, all-India | no | GBD by state |
| Timing of benefit | immediate; EPA 20-year lag | yes, in the intervention file | |
| Exchange rate | World Bank annual | no | |

The same table is shown at the bottom of `airhealth dashboard` (`INPUTS` in
`health/airhealth/dashboard.py`); keep the two in step until the registry below replaces both.

## Proposal (Claude's, unreviewed)

1. **One registry of inputs.** Each input gets a name and a set of named sources, the way
   `curves` and `exposure.MAPS` already work. A source is a loader plus its `sources.toml`
   entry. `airhealth list inputs` prints the table above from the registry.
2. **One way to choose.** A single `--use input=source` flag (repeatable), with the existing
   `--map`, `--curves` and `--deaths` kept as shorthand. Intervention files get a `[sources]`
   table with the same keys.
3. **No silent default.** Every result already names its map and death basis in the footer;
   extend that line to name every input's source. Defaults stay as they are today and are
   called "default", not "best".
4. **Spread across sources as an output.** `run` already reports the spread across curves.
   Add the same for any input given more than one source (`--use deaths=srs,unwpp`), so the
   disagreement is a number on the page and not a choice made out of sight.
5. **Coherence warnings.** Some sources belong together (a life table and a death count from
   the same body; a GBD curve and GBD deaths by cause). Mixing is allowed, and the footer
   says when a combination mixes bodies.

## Open questions for Akash

- Should mixing sources across bodies (SRS life table with UN death count) be allowed
  freely, warned about, or refused?
- Is "spread across sources" worth building before the IHME curves, or after?
- Which second source matters most to add first: UN WPP (deaths, population, life tables in
  one download, openly licensed) is Claude's suggestion.

## Not decided here

Which death count is the default. It stays SRS-scaled until Akash chooses; `--deaths model`
gives the other.

## As built (2026-11-11)

Three demographic inputs get a second source, the UN's World Population Prospects 2024
(`data/unwpp_*.csv`). WPP has India only, no states, so a UN choice keeps each state's own
pattern from the Indian sources and takes India's level, age by age, from the UN:

| Input | `srs`/`projection` (default) | `unwpp` |
|---|---|---|
| `population` | Technical Group projection, by state | each state's projection × (UN India ÷ projection India), band by band, for the year |
| `death_rates` | SRS life tables 2020-24; 2011-19 moved by each year's SRS rates by age | each state's SRS rates × (UN India ÷ SRS India 2020-24), band by band, for the year |
| `deaths` | scaled at 45+ to the SRS crude death rate (`model`: not scaled) | scaled band by band to the UN's deaths by age for India, the same factors in every state |

The SRS scaling is now solved at run time for whatever population and death rates are in use
(the CSVs of factors stay, and a test checks the run-time factor reproduces them for the
defaults).

- `--use input=source` (repeatable; `--use deaths=srs,unwpp` for several). `--deaths` stays as
  shorthand. Intervention files take a `[sources]` table with the same keys.
- Every footer names the source of each input, and says when a run mixes the Indian
  government's and the UN's figures.
- With several sources for an input, `compare`, `burden` and `run` print a result per
  combination and the range across them.
- `airhealth list inputs` prints the registry (`airhealth/inputs.py`); the dashboard reads it
  and has a dropdown per input.
