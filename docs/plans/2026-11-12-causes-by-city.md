# Causes by city (ranking stage, plan B) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One table, `health/data/causes.csv`, holding what causes PM2.5 in each of the 50 cities according to every study we can read at source, side by side, plus a module to read it and an `airhealth causes CITY` command to show it.

**Architecture:** A build script assembles `causes.csv` from three inputs: APnA's CSV (already committed), McDuffie et al. 2021's Supplementary Data 1 (downloaded, derived), and a hand-transcribed file `data/causes_transcribed.csv`, where every row carries its own URL and locator (page, table or figure). `airhealth/causes.py` reads and validates the table. Nothing in this plan changes any result the tool already gives.

**Tech Stack:** Python 3.13 (`.venv` at repo root), pandas, openpyxl, `pdftotext` (poppler, at /opt/homebrew/bin) for reading PDFs, pytest.

**Spec:** `docs/specs/2026-11-12-intervention-ranking-design.md`, part 2 ("Causes by city"). Research notes the tasks start from: `lit/city-sources.md` (which study exists for which city, with URLs; its numbers are leads, not sources).

## Global Constraints

- **Provenance:** no number enters the data unless read at its source by the task that writes it. `lit/city-sources.md` gives URLs and leads; its numbers must be re-read in the PDF or file. A value that cannot be read at source is left out and listed in `health/data/MISSING.md`.
- Every row has `evidence_key`: `O` (read at source), `S` (search snippet or press only) or `R` (memory). Only `O` rows are written in this plan; `S` values may be recorded only for stubble where no `O` value exists, flagged.
- Licences: APnA CC BY 4.0; McDuffie supplementary data CC BY 4.0 (open-access article); NCAP/state reports: tabulate facts with citation, never commit the PDFs. Downloads go to a scratch directory, not the repo.
- Shares are of **PM2.5 concentration** unless `metric = emission_share`. Emission shares are kept but must never be summed with concentration shares.
- Commit locally on `main`. **Never push.** Never commit IHME data.
- Tests from `health/`: `../.venv/bin/python -m pytest -q` (267 pass today). Benchmarks unchanged.

### The schema (`causes.csv`, one row per city × study × season × size fraction × source)

`city, study, institution, year_sampled, season, months, size_fraction, method, metric, boundary, covers, source_raw, source_harmonised, share_pct, n_sites, n_days, url, locator, evidence_key`

- `city`: a `cities.csv` name. `study`: short id, e.g. `apna2019`, `mcduffie2021`, `teri_kolkata2025_cmb`.
- `season`: `annual`, `winter`, `summer`, `post-monsoon`, `monsoon`, or the study's own label; `months`: the months it covers as `10,11` (1-12; `1-12` for annual).
- `size_fraction`: `PM2.5` (PM10 rows are not written in this plan). `method`: `CAMx`, `CMAQ`, `GEOS-Chem`, `WRF-Chem`, `CMB`, `PMF`, `AERMOD`, `GAINS`. `metric`: `concentration_share` | `emission_share`.
- `boundary`: `airshed_box`, `municipal`, `district`, `site`, `grid_cell`, `region`. `covers`: `all` (the study's shares for this group are its whole split) or `partial` (e.g. a stubble-only estimate).
- `source_harmonised`, one of: `transport, residential, industry, dust, waste_burning, dg_sets, brick_kilns, agri_burning, natural, secondary_unassigned, biomass_unassigned, outside, other`. Use `secondary_unassigned` for receptor-model "secondary" and `biomass_unassigned` for receptor "biomass" that does not say whose (homes, fields or both). *(Claude's call: the spec's list plus `biomass_unassigned` and `other`; the spec's `outside_share_pct` column becomes `outside` rows, so every share is in one column.)*

## Review Focus

1. **Shares that don't add up** (rounding, a missing category, a study that reports PM10 and PM2.5 in one pie). Expect: groups with `covers = all` sum to 100 ± 2; anything else fails the build naming the group. → Task 1 `test_complete_groups_sum_to_100`.
2. **Emission shares mixed with concentration shares.** Expect: they never share a group; `causes.for_city` returns `metric` so a caller can't miss it. → Task 1 `test_metrics_never_mix`.
3. **A city spelt differently in a source** (APnA "Kolkata-Howarh", McDuffie "Ahmadabad"). Expect: every `city` value is in `cities.csv`; a source row for a place that is not one of the 50 is dropped and counted in the build's printout. → Task 1 `test_every_city_is_known`.
4. **A study's season mapped to the wrong months** ("winter" is Dec-Feb in one report, Nov-Feb in another). Expect: `months` follows the report's own sampling dates; the locator cites where they are stated. → Tasks 3-4 (each transcribed row's `months` is checked against its locator by the task's own review step).
5. **Stubble counted twice** (APnA's "outside" already contains it). Expect: stubble rows are `covers = partial`, `source_harmonised = agri_burning`, and the README says they overlap `outside` in APnA. → Task 4 `test_stubble_rows_are_partial`.

---

### Task 1: The table, the module, and APnA

**Files:**
- Create: `health/scripts/build_causes.py`, `health/airhealth/causes.py`, `health/data/causes.csv` (generated), `health/data/causes_transcribed.csv` (header only in this task)
- Modify: `health/data/sources.toml` (entries for `causes.csv` and `causes_transcribed.csv`)
- Test: `health/tests/test_causes.py`

**Interfaces:**
- Produces:

```python
HARMONISED: tuple[str, ...]          # the 13 names above, in that order
COLUMNS: tuple[str, ...]             # the schema above, in that order
def table() -> pd.DataFrame          # all rows, validated (cached)
def for_city(city: str, study: str | None = None) -> pd.DataFrame
def studies(city: str) -> list[str]  # study ids with rows for the city, APnA first
```

  `build_causes.py` writes `causes.csv` from APnA + `causes_transcribed.csv` (+ McDuffie from Task 2), sorted by city, study, season, source_harmonised; it validates with the same checks `table()` runs and prints rows dropped for unknown places.

- **APnA mapping:** A transport, B residential, C industry, D dust, E waste_burning, F dg_sets, G brick_kilns, H natural (sea salt), I outside. `season = annual`, `months = 1-12`, `method = CAMx`, `boundary = airshed_box`, `covers = all`, `study = apna` + base year. City: via `cities.csv`'s `apna_airshed` column. A blank H is omitted (not 0).
- **APnA base years:** the CSV's `study_uear` is the publication batch (2017, 2019), not the model year. Read the base year from the APnA papers (UrbanEmissions' 20-city paper and its 2019 batch documentation, linked from the Zenodo record and urbanemissions.info/india-apna) and write it in `year_sampled`; if the papers don't state it per batch, write the batch year, set `locator` to say so, and add a MISSING.md line. Study ids: `apna_<base year>`.

- [ ] **Step 1: Write the failing tests**

```python
def test_apna_rows_match_the_published_file():
    t = causes.table()
    a = t[t.study.str.startswith("apna")]
    assert a.city.nunique() == 49
    chennai = a[a.city == "Chennai"].set_index("source_harmonised").share_pct
    assert chennai["outside"] == 13.3 and chennai["transport"] == 24.5
    assert "natural" not in a[a.city == "Delhi"].source_harmonised.values      # Delhi has no APnA row at all
    assert a[a.city == "Mumbai"].set_index("source_harmonised").share_pct["natural"] == 12.1

def test_complete_groups_sum_to_100():
    t = causes.table()
    g = t[t.covers == "all"].groupby(["city", "study", "season", "size_fraction", "metric"]).share_pct.sum()
    assert ((g - 100).abs() <= 2).all(), g[(g - 100).abs() > 2]

def test_metrics_never_mix():
    t = causes.table()
    assert (t.groupby(["city", "study", "season"]).metric.nunique() == 1).all()

def test_every_city_is_known():
    known = set(pd.read_csv(paths.DATA / "cities.csv").city)
    assert set(causes.table().city) <= known
    assert set(causes.table().source_harmonised) <= set(causes.HARMONISED)

def test_for_city_and_studies():
    assert causes.studies("Chennai")[0].startswith("apna")
    assert set(causes.for_city("Chennai").columns) == set(causes.COLUMNS)
    with pytest.raises(KeyError):
        causes.for_city("Atlantis")
```

- [ ] **Step 2: Run them; expect FAIL** (no module).
- [ ] **Step 3: Implement** the module, the build script and the APnA rows; read the base years at source.
- [ ] **Step 4: Run the full suite; expect PASS.**
- [ ] **Step 5: Commit** `git commit -m "causes: table, module and APnA rows"`

### Task 2: McDuffie et al. 2021

**Files:**
- Modify: `health/scripts/build_causes.py` (download and map Supplementary Data 1), `health/data/causes.csv` (regenerated), `health/data/sources.toml`
- Test: `health/tests/test_causes.py`

**Interfaces:**
- Consumes: Task 1's schema and build.
- Source: McDuffie et al. 2021, *Nature Communications* 12:3594, Supplementary Data 1. Candidate URLs (check which file holds the city table): `https://static-content.springer.com/esm/art%3A10.1038%2Fs41467-021-23853-y/MediaObjects/41467_2021_23853_MOESM4_ESM.xlsx` (and `MOESM5`, `MOESM6`). Record the sha256 in sources.toml.
- Rows only for the cities in `cities.csv` (expected overlap: Jaipur, Ahmedabad, Kanpur, Kolkata, Mumbai, Pune, Hyderabad; confirm). `study = mcduffie2021`, `year_sampled = 2017`, `method = GEOS-Chem`, `boundary = grid_cell` (or what the paper says its city value is), `covers = all`. The sector-to-harmonised map is written as a dict in the build script with a one-line reason for each non-obvious entry (e.g. agricultural non-combustion → `secondary_unassigned`? or `other`; decide from the paper's sector definitions and say why).

- [ ] **Step 1: Write the failing test**

```python
def test_mcduffie_rows():
    m = causes.table().query("study == 'mcduffie2021'")
    assert {"Kanpur", "Mumbai", "Kolkata"} <= set(m.city)
    kanpur = m[m.city == "Kanpur"].groupby("source_harmonised").share_pct.sum()
    assert kanpur["residential"] == pytest.approx(RESIDENTIAL_KANPUR, abs=0.05)
```

  `RESIDENTIAL_KANPUR` is the sum of McDuffie's residential sectors for Kanpur as read in the file by this task (lit/ says residential biofuel alone is 24.5; that is a lead, not the value).
- [ ] **Step 2: Run; expect FAIL.**
- [ ] **Step 3: Implement** the download, the sector map and the rows.
- [ ] **Step 4: Run the full suite; expect PASS.**
- [ ] **Step 5: Commit** `git commit -m "causes: McDuffie 2021 city rows"`

### Task 3: City studies, north and east

**Files:**
- Modify: `health/data/causes_transcribed.csv`, `health/data/causes.csv` (regenerated), `health/data/MISSING.md`
- Test: `health/tests/test_causes.py`

**Studies** (URLs in `lit/city-sources.md` §1; read each PDF with `pdftotext -layout` in a scratch directory): **Delhi** (ARAI-TERI 2018, the study CPCB still uses; and the DSS seasonal means in Govardhan et al. 2024, *GMD* 17:2617), **Kolkata** (TERI for WBPCB 2025, CMB and CMAQ as two studies), **Lucknow** (TERI for UPPCB 2022, CMAQ), **Kanpur** (IIT Kanpur for UPPCB, winter and summer PMF), **Patna** (TERI for BSPCB 2021, winter and summer), **Agra** (IIT Kanpur summary).

- Each row: `locator` names the page and table or figure. A value read off a pie chart's printed label is `O`; a value estimated from a bar's length is not written.
- Seasons: `months` from the report's stated sampling dates.

- [ ] **Step 1: Write the failing test** — one pinned value per study, read at source by this task, e.g.

```python
@pytest.mark.parametrize("city, study, season, cause, share", [
    # one row per study, filled in from the PDFs in this task (city, study id, season, harmonised cause, share)
])
def test_transcribed_values(city, study, season, cause, share):
    t = causes.for_city(city, study)
    got = t[(t.season == season) & (t.source_harmonised == cause)].share_pct.sum()
    assert got == pytest.approx(share, abs=0.05)
```

  and `test_complete_groups_sum_to_100` must still pass with the new rows.
- [ ] **Step 2: Run; expect FAIL** (the rows aren't there yet).
- [ ] **Step 3: Transcribe** the studies into `causes_transcribed.csv`; rebuild `causes.csv`; list anything that couldn't be read in MISSING.md.
- [ ] **Step 4: Self-check:** for each study, re-open the PDF at the locator and compare three random rows. Note the check in the report. Run the full suite; expect PASS.
- [ ] **Step 5: Commit** `git commit -m "causes: Delhi, Kolkata, Lucknow, Kanpur, Patna, Agra studies"`

### Task 4: City studies, west and south; stubble

**Files:**
- Modify: `health/data/causes_transcribed.csv`, `health/data/causes.csv` (regenerated), `health/data/MISSING.md`, `health/README.md`
- Test: `health/tests/test_causes.py`

**City studies** (same rules as Task 3): **Mumbai** (NEERI + IIT Bombay for MPCB 2023, PMF), **Pune** (NEERI + IIT Bombay 2024, PMF), **Bengaluru** (CSTEP for KSPCB 2022, CMB, three seasons), **Hyderabad** (IIT Kanpur for TSPCB, winter and summer PMF), **Surat** (TERI 2021, CMB and CMAQ as two studies), **Ahmedabad** (GEMI: PM *emissions*, so `metric = emission_share`), **Chennai** (IIT Madras interim report, if it has PM2.5 shares).

**Stubble (`agri_burning`, `covers = partial`):** for each IGP city among the 50, every published estimate of crop-residue burning's share of PM2.5 for October-November that can be read at source. Known candidates (read each; keep the season and years each reports):
- Delhi: Kulkarni et al. 2020, *ES&T* (~20% Oct-Nov); Govardhan et al. 2024, *GMD* (post-monsoon 2021); Biswal et al. 2025, *Env. Sci.: Atmospheres* (Delhi-NCR 2022, 2023, 2024, 16 Oct-30 Nov); Nagar and Sharma 2022 (Delhi and Kanpur, Oct-Nov 2013-14); the DSS season means for 2020-24 given in a Lok Sabha written answer (10 March 2025), if the answer itself can be read (otherwise `S`, flagged).
- Kanpur: Nagar and Sharma 2022.
- Lucknow: TERI 2022 (agri burning, post-monsoon), if Task 3 hasn't already written it.
- Punjab and Haryana cities (Ludhiana, Amritsar, Chandigarh): Biswal et al. 2025 regional means, `boundary = region`, `locator` naming the region (North Punjab, Central Haryana); a region value goes to a city only if the city lies in that region by the paper's own map.

- [ ] **Step 1: Write the failing tests** — `test_transcribed_values` gains one row per new study, and:

```python
def test_stubble_rows_are_partial():
    s = causes.table().query("source_harmonised == 'agri_burning' and covers == 'partial'")
    assert "Delhi" in set(s.city)
    assert set(s.months.unique()) <= {"10,11", "10,11,12", "11", "10"}   # whatever the studies state; no annual
```

- [ ] **Step 2: Run; expect FAIL.**
- [ ] **Step 3: Transcribe**; rebuild; README: one paragraph under a new heading "What causes the PM2.5" saying what `causes.csv` holds, that APnA's `outside` already contains stubble smoke, and that studies disagree by multiples (point to `lit/city-sources.md` §3).
- [ ] **Step 4: Self-check** as in Task 3; run the full suite; expect PASS.
- [ ] **Step 5: Commit** `git commit -m "causes: Mumbai, Pune, Bengaluru, Hyderabad, Surat, Ahmedabad, Chennai; stubble shares"`

### Task 5: `airhealth causes`, the registry, and the README

**Files:**
- Modify: `health/airhealth/cli.py`, `health/airhealth/inputs.py` (`OTHER`), `health/airhealth/report.py` (a table function), `health/README.md`
- Test: `health/tests/test_cli.py`, `health/tests/test_inputs.py`

**Interfaces:**
- Consumes: `causes.for_city`, `causes.studies`.
- Produces: `airhealth causes CITY [--study ID] [--season SEASON]`: one column per study (and season), one row per harmonised cause, shares in %, `—` where a study doesn't report a cause; a footer naming each study's method, year, boundary and URL, flagging `emission_share` columns and `partial` columns. `airhealth causes` with no city lists cities and how many studies each has.
- `inputs.OTHER` gains `Input("causes", "Causes of PM2.5 by city", "apna", (), switch="airhealth causes CITY to see them; chosen per run in the ranking (plan D)", pending="the ~45 other NCAP reports on PRANA")`. *(Ruling: the `--use causes=` switch is wired in plan D, where a run first uses causes; here the registry only describes the input.)*
- README: the `causes` command, and fix the carried-over line saying all fifty cities have a CPCB station (seven have none).

- [ ] **Step 1: Write the failing tests**

```python
def test_causes_command_shows_every_study(capsys):
    cli.main(["causes", "Kolkata"])
    out = capsys.readouterr().out
    for study in causes.studies("Kolkata"):
        assert study in out
    assert "outside" in out and "transport" in out

def test_causes_lists_cities(capsys):
    cli.main(["causes"])
    assert "Delhi" in capsys.readouterr().out

def test_registry_has_causes():
    assert inputs.REGISTRY["causes"].default == "apna"
```

- [ ] **Step 2: Run; expect FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the full suite and benchmarks; expect PASS, benchmarks unchanged.** Paste `airhealth causes Delhi` and `airhealth causes Kanpur` output into the report.
- [ ] **Step 5: Commit** `git commit -m "airhealth causes: every study side by side"`
