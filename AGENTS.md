# For models (and people) picking this up

This repo tries to make India's air pollution look like a problem that can be worked on:
what is in the air, what it does to people, and which measures are worth their cost. The
part most worth building on is [`health/`](health/), a Python library and command line
called `airhealth`.

Read this file first. It is short, and it holds the rules that are easy to break.

## Your first three moves

**1. Get it running (about a minute).**

```
python3 -m venv .venv
.venv/bin/pip install -e "health[dev]"
cd health
../.venv/bin/python -m pytest -q
../.venv/bin/airhealth compare Delhi --from 100 --to 80
../.venv/bin/airhealth causes Kanpur
../.venv/bin/airhealth list curves
```

Python 3.11 or newer. Every test should pass. Some tests skip: they need files from IHME
(the Global Burden of Disease group) that cannot be shared here, and three of the eight
risk curves are unavailable without them. Everything else works from a fresh clone. Add
`--json` to any command for the same content as JSON.

**2. Read what the two commands just told you.** `compare` gives eight answers to one
question and they differ several-fold. `causes` gives several studies of one city and they
disagree too. That disagreement is the main finding so far, and the tool exists to show it.
Then read [`health/README.md`](health/README.md) for the terms and
[`docs/STATUS.md`](docs/STATUS.md) for where the work stopped.

**3. Pick one task from "Open work" below and finish it**, with a test, and with every new
number traceable to the page it came from.

## The rules

1. **No number enters code or data unless you read it at its source.** Not from memory, not
   from a press report, not from another model's summary, not from this file. Open the
   paper, report or dataset, and record where in it the number sits (table, figure, page).
   Every data file has an entry in [`health/data/sources.toml`](health/data/sources.toml)
   with its source, link, locator, date retrieved, licence and method. Numbers that live in
   code are listed by `airhealth.provenance.constants()`. The tests check both.
2. **If you cannot reach the source, say so in
   [`health/data/MISSING.md`](health/data/MISSING.md)**: what you wanted, what you tried and
   what would settle it. A lead is worth writing down. A guess is not.
3. **Never pick a winner.** Risk curves, exposure maps and source studies are shown side by
   side, because the published ones disagree and nobody knows which is right for air as
   dirty as India's. Do not average them and do not make one the quiet default. The choice
   between death-count sources has been left open on purpose.
4. **"Not reported" is not zero.** A study that does not list a cause has said nothing
   about it. Use `airhealth.causes.shares()`, which returns NaN for those.
5. **Do not tune anything to close a gap with a published number.** Each benchmark states
   the ratio it expects from known differences in inputs, and passes only near that ratio.
   An unexplained gap is written down as unexplained.
6. **Do not commit IHME files, report PDFs or anything else you have no right to share.**
   IHME files go in `health/data_local/`, which git ignores. Tabulate figures with a
   citation; leave the documents where they are.
7. **Write the test first, and write in plain words.** Define a term the first time it
   appears. A reader who is not an air pollution specialist should be able to follow.

## What is solid and what is not

Solid: the code is tested, every input names its source, and the benchmarks reproduce
published shares and life-expectancy figures within a few percent.

Not solid, and you should say so when you use a result:

- **Global Burden of Disease's own India count is not reproduced.** GBD 2023 reports
  969,726 deaths from outdoor PM2.5 in India in 2023. On GBD's own curve, map and year this
  tool gives 1.61 million. The likely main reason: GBD splits one risk between outdoor air
  and cooking smoke, and this tool scores outdoor air alone. That has not been shown with
  numbers. See [`health/IHME_DOWNLOADS.md`](health/IHME_DOWNLOADS.md).
- **No specialist has reviewed the method yet.** The modelling calls are written down so
  that one can: see "Known limitations" in `health/README.md` and the list of unreviewed
  calls at the end of [`docs/STATUS.md`](docs/STATUS.md).
- **Every curve is stretched past its evidence.** No study has followed people who breathe
  air like Delhi's for years.
- **The ranking of measures by cost does not exist yet.** Design:
  [`docs/specs/2026-11-12-intervention-ranking-design.md`](docs/specs/2026-11-12-intervention-ranking-design.md).

## Open work, roughly smallest first

Each of these is one sitting. Say in your write-up what you read and what you could not
check.

1. **Close one gap in `health/data/MISSING.md`.** Three good ones:
   - Nagar and Sharma 2022 (Urban Climate 41: 101084): read the paper's own stubble shares
     for Delhi and Kanpur. Kanpur has no stubble row at all.
   - The Lok Sabha written answer of 10 March 2025, with stubble shares for Delhi for
     2020-24. Only press reports of it have been found.
   - Fig. 3 of Biswal et al. 2025 (doi 10.1039/d5ea00052a), a map. The publisher blocks
     scripted downloads, so this needs a real browser: say which of Ludhiana, Amritsar and
     Chandigarh fall inside which of the paper's regions.
2. **Write one intervention file** from
   [`health/interventions/_template.toml`](health/interventions/_template.toml) for a real
   measure, with its size and cost read at source, and run it with `airhealth run`.
3. **Did firecracker bans work?** Gap G1 in [`lit/gaps.md`](lit/gaps.md). The outcome is
   already computed (`diwali/data/trend_cityyear.csv`: a Diwali effect for each city and
   year, adjusted for the onset of winter, stubble smoke and rain). Bans came in at different times in
   different states. What is missing is a table of which state had which ban in which year,
   read from the court orders and state notifications, and then a
   difference-in-differences.
4. **Reproduce GBD's India count.** Download GBD 2023's household air pollution estimates
   (GHDx record 594794; no login needed for that file), apply GBD's split between outdoor
   air and cooking smoke, and see how much of the gap above it explains.
5. **The measure library and ranking** (the large one). "Next, in order" in `docs/STATUS.md`.
   Talk to the maintainer before starting.

Other gaps nobody has worked on are in `lit/gaps.md` (G2 to G7).

## Where things are

```
health/     airhealth: the package, its data (with sources), tests, benchmarks
diwali/     finished study: ten cities, ten years of hourly PM2.5 around Diwali
lit/        reading list, who is doing what, gaps nobody has filled
bets/       interventions sorted by what the physics allows
docs/       STATUS.md and design notes (specs/)
```

## Sending work back

Work on a branch and open a pull request against
[`dogluk/air-apocalypse`](https://github.com/dogluk/air-apocalypse). In the description,
list each new number with its source and locator, and anything you assumed or could not
verify. A small change that is fully sourced is more useful than a large one that is not.
