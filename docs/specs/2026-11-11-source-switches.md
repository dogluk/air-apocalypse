# A switch for every input: design note

Status: **direction set by Akash on 2026-11-11, design not yet agreed.** The proposal below
is Claude's and has not been reviewed.

## What was asked

"We probably need the ability to take each variable we depend on and have a knob/switch for
using different sources." The trigger was the death count: the government survey (SRS) and
the UN disagree by about a tenth, and Akash does not want to pick one now. The same is true
of most inputs, so the answer is a general one: the tool should not hard-code a winner
anywhere a credible source disagrees with another.

## Where things stand

| Input | Sources today | Switchable? | Candidates not wired |
|---|---|---|---|
| Risk curve | Jaganathan, Brown, Vodonos, GEMM, AQLI | yes, `--curves` | GBD 2019, GBD 2023, GEMM five causes |
| Exposure map | AQLI, ACAG total, GBD 2019 (states), CPCB (cities) | yes, `--map` | GBD 2023 (file is downloaded) |
| Death count | SRS-scaled; population × life-table rates | yes, `--deaths` | UN WPP 2024; GBD; per-year SRS rates |
| Counterfactual | each curve's floor; one number | yes, `--counterfactual` | |
| Death rates by age | SRS abridged life tables 2020-24 | no | UN WPP, GBD |
| Population by age | Government projections 2011-2036 | no | UN WPP, GBD, Census 2011 (cities) |
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
