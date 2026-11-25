# Health model core (stages 1–2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Python library, `airhealth`, that turns a change in annual-mean PM2.5 for Indian states, districts and cities into deaths averted, life expectancy and life-years, across several risk curves, from a short intervention file with uncertainty.

**Architecture:** Pure-function core (life table, curves, impact) over plain pandas tables loaded from small committed CSVs, each with a provenance record. A thin intervention/Monte Carlo layer and a terminal interface sit on top. IHME-dependent curves are registered but unavailable until files appear in a git-ignored folder.

**Tech Stack:** Python 3.12+, numpy, pandas, scipy, matplotlib, pytest. `tomllib` for TOML. No web framework.

**Spec:** `docs/specs/2026-11-10-health-model-design.md` — read it first. This plan covers spec build stages 1 and 2 only. Stages 3–6 (IHME curves, run to 2050, valuation presets, Surat) get their own plans.

## Global Constraints

- **Provenance rule (spec):** every number in a data file or curve definition is read at its source. Nothing from memory, and nothing from the research summaries without re-reading. A value that cannot be found at source is left out and listed in `health/data/MISSING.md`.
- Never commit IHME data. `health/data_local/` is git-ignored.
- Do not copy code from `creahia`, `healthiar` or InMAP (GPL). Read for method only.
- Commit locally on `main`. **Never push.**
- Units: concentrations in µg/m³ annual mean. A change is signed: negative means cleaner air.
- Age bands everywhere: starts `(0, 1, 5, 10, …, 80, 85)`, the last open-ended — 19 bands. If the SRS tables use a different top band, change this constant once in `ages.py` and say so in the README.
- Adult curves apply from age 25.
- Output never shows a result without naming its curve and exposure map.
- Charts use the repo fonts (`fonts/`) and the visual style of `diwali/charts/`.
- Committed data stays under about 30 MB; rasters are processed by script and only derived tables kept.

## Review Focus

1. **Place names differ across sources** (Odisha/Orissa, NCT of Delhi, Telangana, J&K and Ladakh, merged UTs). Expect: one canonical name table; a join that drops or double-counts a place fails loudly naming it. → Task 3.
2. **A cut that would take a place below the curve's floor, or below zero.** Expect: concentration clamps at the floor, benefit stops there, no negative concentrations. → Tasks 4, 5.
3. **An intervention that makes air worse** (positive change). Expect: negative life-years reported as such, no error, no absolute value. → Task 5.
4. **A state or UT with no SRS life table.** Expect: falls back to the all-India table, and every output lists which places used the fallback. → Tasks 2, 5.
5. **Malformed intervention file** (monthly profile not 12 long; both absolute and percentage change; probability outside 0–1; 5th percentile above 95th). Expect: one clear message naming the field, no traceback. → Task 7.

Also: asking for an IHME-tier curve without the files prints which files are missing and where the download list is. → Task 4.

## File map

```
health/
  pyproject.toml            package metadata, dependencies, `airhealth` console script
  README.md                 what it is, how to run, known limitations
  IHME_DOWNLOADS.md         exact files Akash downloads by hand (Task 1)
  airhealth/
    ages.py                 AGE_STARTS, ADULT_FROM
    paths.py                DATA, LOCAL, CHARTS, FONTS
    provenance.py           sources.toml loader and checker
    lifetable.py            abridged life table arithmetic
    places.py               canonical names, Place, resolve()
    baseline.py             population and death rates by state and age
    exposure.py             exposure maps → district table
    curves.py               curve classes and registry
    impact.py               steady-state impact for a place
    lag.py                  cessation-lag profiles
    intervention.py         TOML → Intervention; distributions
    simulate.py             Monte Carlo over an intervention; spread breakdown
    report.py               text tables and JSON
    charts.py               the four charts
    cli.py                  terminal commands
  data/                     committed CSVs + sources.toml + MISSING.md
  data_local/               git-ignored; IHME files
  scripts/                  one script per derived table
  interventions/            example .toml files
  benchmarks/               reproduction cases and their write-up
  tests/
```

---

### Task 1: Scaffold, provenance, and the IHME download list

**Files:** Create `health/pyproject.toml`, `health/airhealth/{__init__,ages,paths,provenance}.py`, `health/data/sources.toml`, `health/data/MISSING.md`, `health/IHME_DOWNLOADS.md`, `health/tests/test_provenance.py`. Modify `.gitignore` (add `health/data_local/`).

**Interfaces — Produces:**
- `ages.AGE_STARTS: tuple[int, ...]`, `ages.ADULT_FROM = 25`
- `paths.DATA`, `paths.LOCAL`, `paths.CHARTS`, `paths.FONTS` (`Path`)
- `provenance.load_sources() -> dict[str, dict]` keyed by data filename
- `provenance.check() -> list[str]` — problems found; empty means clean
- Each `sources.toml` entry has: `source`, `url`, `locator` (table/page), `retrieved` (date), `licence`, `method` (`"downloaded"` | `"transcribed"` | `"derived"`), and for derived tables `script`.

- [ ] **Step 1: Failing tests** in `test_provenance.py`:
  - `test_every_data_file_has_a_source`: every `*.csv` under `DATA` is a key in `load_sources()`; `check() == []`.
  - `test_entry_missing_field_is_reported`: a temp `sources.toml` lacking `licence` makes `check()` return a message containing the filename and `"licence"`.
  - `test_local_folder_is_ignored`: `git check-ignore health/data_local/x.csv` exits 0.
- [ ] **Step 2:** Run `cd health && pytest -q` — expect failures (package missing).
- [ ] **Step 3:** Create the package, `pip install -e .[dev]` into the repo's `.venv`, implement.
- [ ] **Step 4:** `pytest -q` passes.
- [ ] **Step 5: Write `IHME_DOWNLOADS.md`.** Open the GHDx records for the GBD 2019 and GBD 2023 particulate-matter risk curves and the GBD Results tool. Write, for each file needed by spec stage 3: the page URL, the exact selections (measure, metric, causes, ages, sex, locations = India + all states, years), and the filename to save it under in `health/data_local/`. Needed: PM2.5 relative-risk curves (2019, 2023); deaths and death rates by cause (IHD, stroke, COPD, lung cancer, lower respiratory infection, type 2 diabetes, and the all-NCD aggregate) by 5-year age band, both sexes, Indian states, 2015, 2019 and latest; population by age for the same. If a selection cannot be confirmed without a login, say so in the file.
- [ ] **Step 6:** Commit: `health: scaffold, provenance check, IHME download list`.

### Task 2: Life-table arithmetic and the SRS baseline

**Files:** Create `airhealth/lifetable.py`, `airhealth/baseline.py`, `scripts/build_baseline.py`, `data/lifetables_srs.csv`, `data/population_age_state.csv`, `data/cause_share_ncd_lri.csv`, `tests/test_lifetable.py`, `tests/test_baseline.py`.

**Interfaces — Produces:**
- `lifetable.life_table(mx: np.ndarray) -> LifeTable` — dataclass of arrays `mx, qx, lx, Lx, ex` over `AGE_STARTS`; radix 1.0; open band closed with `L = l / m`.
- `lifetable.e0(mx) -> float`
- `lifetable.scale_adult(mx, factor: float | np.ndarray, from_age=ADULT_FROM) -> np.ndarray`
- `lifetable.solve_adult_factor(mx, delta_e0: float, from_age=ADULT_FROM) -> float` — the uniform multiplier on adult rates that changes `e0` by `delta_e0`.
- `baseline.load(state: str, year: int | None = None) -> Baseline` — dataclass: `state, year, population (19,), mx (19,), share_ncd_lri (19,), fallback: bool`. Unknown state with no table → all-India rates with `fallback=True` and that state's own population. Unknown name entirely → `KeyError` naming it.
- `baseline.states() -> list[str]`

**Data to obtain (provenance rule applies):** SRS Abridged Life Tables, latest edition, India and every state it covers (`m_x` or `q_x` by age band, persons, plus published `e0`); population by age band and state (official 2011–2036 projections, year matching the life tables); share of deaths that are non-communicable or lower-respiratory by age band (SRS / Registrar General cause-of-death report; all-India if states are not given). Transcribe by script where the PDF allows; spot-check ten cells per table by eye and record that in `sources.toml`.

- [ ] **Step 1: Failing tests.**
  ```python
  def test_constant_hazard_gives_reciprocal_life_expectancy():
      mx = np.full(19, 0.02)
      assert e0(mx) == pytest.approx(50.0, rel=0.02)
  def test_scaling_adults_leaves_children_alone():
      mx = np.full(19, 0.01); out = scale_adult(mx, 0.9)
      assert (out[:6] == mx[:6]).all() and np.allclose(out[6:], 0.009)
  def test_solver_inverts_scaling():
      mx = np.linspace(0.001, 0.15, 19)
      f = solve_adult_factor(mx, e0(scale_adult(mx, 0.85)) - e0(mx))
      assert f == pytest.approx(0.85, abs=1e-4)
  def test_lower_rates_raise_life_expectancy(): ...
  ```
  In `test_baseline.py`:
  - `test_computed_e0_matches_srs_published`: for every state in the table, `abs(e0(load(s).mx) - published_e0[s]) < 0.5`.
  - `test_state_without_table_falls_back`: a UT absent from SRS returns `fallback is True` and non-zero population.
  - `test_unknown_name_raises_naming_it`.
  - `test_india_population_total`: sum over states within 1% of the source's all-India figure.
- [ ] **Step 2:** Run; expect failures.
- [ ] **Step 3:** Implement `lifetable.py` (standard abridged method; `a_x` = half the interval except infancy, where use the source's own convention if given).
- [ ] **Step 4:** Build the three data tables and `baseline.py`; add `sources.toml` entries.
- [ ] **Step 5:** `pytest -q` passes, including Task 1's provenance check.
- [ ] **Step 6:** Commit: `health: life tables and SRS baseline`.

### Task 3: Places and exposure maps

**Files:** Create `airhealth/places.py`, `airhealth/exposure.py`, `scripts/build_exposure_{aqli,acag,gbd2019,cpcb}.py`, `data/places.csv`, `data/exposure_*.csv`, `data/cities.csv`, `tests/test_places.py`, `tests/test_exposure.py`.

**Interfaces — Produces:**
- `places.Place` — frozen dataclass `kind: Literal["country","state","district","city"], name: str, state: str | None`.
- `places.resolve(text: str) -> Place` — accepts aliases, case-insensitive; `KeyError` listing near matches otherwise.
- `places.canonical_state(name: str) -> str`
- `exposure.MAPS: tuple[str, ...] = ("aqli", "acag_total", "gbd2019", "cpcb")`
- `exposure.cells(place: Place, map_name: str, year: int | None = None) -> pd.DataFrame` with columns `state, unit, pm25, population` — one row per district for a state or the country, one row for a district or city. `gbd2019` has one row per state. `cpcb` exists only for the cities in `diwali/config.py`; asking it for a state raises `ValueError` saying so.
- `exposure.mean(place, map_name, year=None) -> float` — population-weighted.

**Data:** AQLI state and district files (CC BY, from `aqli-epic/aqli-update`); ACAG V6.GL.02.04 at 0.1° averaged to districts with WorldPop weights (script downloads rasters to a temp folder, keeps only the table); GBD 2019 state population-weighted PM2.5 as printed in Pandey et al. 2021 (Lancet Planetary Health); CPCB annual means per city from `diwali/data/raw/*.parquet`, full calendar years only, with the count of stations and share of hours present. City populations from the 2011 census urban agglomeration figures or a newer official source.

- [ ] **Step 1: Failing tests.**
  - `test_aliases_resolve`: `resolve("Orissa") == resolve("Odisha")`; `resolve("NCT of Delhi").name == "Delhi"`; `resolve("delhi")` works.
  - `test_unknown_place_suggests`: `resolve("Dilli")` raises `KeyError` whose message contains `"Delhi"`.
  - `test_no_population_lost_in_join`: for each of `aqli`, `acag_total`: population summed over `cells(India)` is within 0.5% of the source file's total, and every state in `baseline.states()` has at least one row.
  - `test_delhi_aqli_matches_published`: `mean(resolve("Delhi"), "aqli", 2023)` equals AQLI's published Delhi figure for 2023 (read it from AQLI; the research summary says 88.4) within 0.5.
  - `test_cpcb_refuses_states`.
  - `test_acag_exceeds_aqli_where_dusty`: Rajasthan's `acag_total` mean is higher than its `aqli` mean (AQLI removes dust).
- [ ] **Step 2:** Run; expect failures.
- [ ] **Step 3:** Build `places.csv` (canonical name, kind, parent state, aliases) from the union of names in the sources; implement `places.py`.
- [ ] **Step 4:** Write the four build scripts, produce the tables, implement `exposure.py`, add provenance entries.
- [ ] **Step 5:** `pytest -q` passes.
- [ ] **Step 6:** Commit: `health: places and four exposure maps`.

### Task 4: Risk curves

**Files:** Create `airhealth/curves.py`, `data/curves_loglinear.csv`, `data/curves_gemm_ncd_lri.csv`, `tests/test_curves.py`.

**Interfaces — Produces:**
- `curves.Curve` (base class) with attributes `name: str`, `label: str`, `kind: Literal["relative_risk","life_expectancy"]`, `floor: float`, `death_scope: Literal["all","ncd_lri"]`, `source: str`; methods:
  - `rr(c: float | np.ndarray, age: int) -> np.ndarray` — relative risk at concentration `c` versus the floor, for the band starting at `age`; 1.0 at or below the floor and for ages under `ADULT_FROM`.
  - `ratio(c_from, c_to, age) -> np.ndarray` — `rr(c_to)/rr(c_from)`, both clamped to `max(c, floor)` and to ≥ 0.
  - `sample(rng: np.random.Generator) -> Curve` — a copy with parameters drawn from their published uncertainty.
  - `with_floor(floor: float) -> Curve`
- `curves.LogLinear(name, pct_per_10, se_pct_per_10, floor, ...)` — `rr = exp(beta * (c - floor))`, `beta = ln(1 + pct/100) / 10`.
- `curves.GEMM(params: pd.DataFrame)` — the published GEMM form, `rr = exp(theta * ln(1 + z/alpha) / (1 + exp(-(z - mu)/nu)))`, `z = max(0, c - 2.4)`, age-specific parameters, `death_scope="ncd_lri"`.
- `curves.AQLILinear` — `kind="life_expectancy"`; `delta_e0(c_from, c_to) -> float` = years per µg/m³ × the clamped fall in concentration.
- `curves.get(name: str) -> Curve`; `curves.available() -> list[Curve]`; `curves.catalogue() -> pd.DataFrame` (name, label, available, needs, source).
- `curves.Unavailable(Exception)` — raised by `get()` for a registered IHME-tier curve (`gbd2019`, `gbd2023`, `gemm_5cod`) whose files are absent; message lists the missing filenames and points to `health/IHME_DOWNLOADS.md`.

**Parameters to obtain at source:** Jaganathan et al. 2024 (Lancet Planetary Health) slope and interval; Brown et al. 2022 (Million Death Study) non-accidental slope and interval; Vodonos et al. 2018 pooled slope; GEMM NCD+LRI age-specific `theta, se_theta, alpha, mu, nu` from the Burnett et al. 2018 PNAS supplement; AQLI's coefficient and reference level from its methodology page. Check whether Burnett et al. 2022 "Fusion" publishes usable all-cause parameters; add it if so, otherwise record it in `MISSING.md`.

- [ ] **Step 1: Failing tests.**
  ```python
  def test_delhi_100_to_80_on_indian_slope():
      c = get("loglinear_jaganathan")
      assert 0.14 < 1 - c.ratio(100, 80, 40) < 0.16
  def test_no_benefit_below_floor():
      c = get("loglinear_jaganathan").with_floor(40)
      assert c.ratio(35, 20, 40) == 1.0
      assert c.ratio(50, 20, 40) == c.ratio(50, 40, 40)
  def test_children_unaffected():
      assert get("gemm_ncd_lri").ratio(100, 50, 5) == 1.0
  def test_worse_air_raises_risk():
      assert get("gemm_ncd_lri").ratio(60, 90, 50) > 1.0
  def test_gemm_flattens_relative_to_loglinear():
      g, l = get("gemm_ncd_lri"), get("loglinear_jaganathan")
      assert (1 - g.ratio(100, 80, 50)) < (1 - l.ratio(100, 80, 50))
  def test_aqli_delhi():
      assert get("aqli").delta_e0(88.4, 5) == pytest.approx(-8.2, abs=0.1) or \
             get("aqli").delta_e0(88.4, 5) == pytest.approx(8.2, abs=0.1)
  def test_ihme_curve_without_files_explains():
      with pytest.raises(Unavailable, match="IHME_DOWNLOADS.md"): get("gbd2019")
  def test_sampling_is_reproducible_and_varies(): ...
  ```
  Fix the sign convention for `delta_e0` (positive = years gained) and tighten `test_aqli_delhi` to that one sign. Add `test_gemm_matches_published_point`: pick two relative-risk values that the PNAS paper or its supplement prints for a stated concentration and age, and assert the implementation reproduces them within 1%.
- [ ] **Step 2:** Run; expect failures.
- [ ] **Step 3:** Fetch and record parameters; implement.
- [ ] **Step 4:** `pytest -q` passes.
- [ ] **Step 5:** Commit: `health: log-linear, GEMM and AQLI curves`.

### Task 5: Steady-state impact

**Files:** Create `airhealth/impact.py`, `tests/test_impact.py`.

**Interfaces — Consumes:** `baseline.load`, `exposure.cells`, `Curve`, `lifetable.*`, `Place`.

**Produces:**
- `impact.Change` — dataclass with exactly one of `delta: float` (µg/m³, signed), `pct: float` (signed, percent of each unit's level), `to: float` (target; units already below it are unchanged). `Change.apply(pm25: np.ndarray) -> np.ndarray`, never below 0.
- `impact.Impact` — dataclass: `place, curve, map_name, pm25_before, pm25_after` (population-weighted), `population`, `deaths_baseline`, `deaths_averted` (per year, steady state; negative if air worsens), `e0_before`, `e0_after`, `yll_averted` (deaths averted by age × remaining life expectancy at that age from the same state table), `derived: bool` (True for AQLI deaths), `fallback_states: list[str]`.
- `impact.steady_state(place: Place, curve: Curve, map_name: str, change: Change, year: int | None = None) -> Impact`
- `impact.burden(place, curve, map_name, counterfactual: float | None = None) -> Impact` — `Change(to=counterfactual or curve.floor)`.

**Method:** per exposure unit, per age band: deaths in scope = population share × `mx` × (`share_ncd_lri` if `death_scope == "ncd_lri"` else 1); averted = in-scope deaths × (1 − ratio). Sum units to the place. Life expectancy: rebuild the state life table with each band's rate multiplied by the population-weighted mean of `1 − scope_share × (1 − ratio)`; for the country, population-weight state results. For `AQLILinear`: `e0_after = e0_before + delta_e0` per unit, then `solve_adult_factor` for the implied deaths, `derived=True`.

- [ ] **Step 1: Failing tests** (use small synthetic baselines and exposure tables via fixtures, plus a few on real data):
  - `test_no_change_no_effect`: `Change(delta=0)` → `deaths_averted == 0`, `e0_after == e0_before`.
  - `test_cleaner_air_averts_deaths_and_adds_years`.
  - `test_worse_air_gives_negative_numbers`: `Change(delta=+10)` → `deaths_averted < 0`, `e0_after < e0_before`.
  - `test_cut_is_clamped_at_floor`: in a place at 20 µg/m³ with a floor of 15, `Change(delta=-30)` equals `Change(delta=-5)`.
  - `test_target_leaves_clean_units_alone`: `Change(to=40)` on two units at 30 and 60 changes only the second.
  - `test_state_is_sum_of_its_districts`.
  - `test_nonlinearity_matters`: with GEMM, a state computed over districts differs from the same state computed at its mean concentration.
  - `test_ncd_scope_averts_fewer_than_all_scope` for the same ratio.
  - `test_aqli_impact_is_marked_derived_and_consistent`: `e0_after - e0_before` equals the curve's `delta_e0`; `derived is True`.
  - `test_fallback_states_listed`.
  - `test_delhi_100_to_80_orders_curves` (real data, city Delhi with `Change(to=80)` from a forced 100 via a fixture): fraction of deaths averted is largest for `loglinear_jaganathan`, then `gemm_ncd_lri`.
- [ ] **Step 2:** Run; expect failures.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** `pytest -q` passes.
- [ ] **Step 5:** Commit: `health: steady-state impact`.

### Task 6: Terminal commands, the curve chart, and the reproduction benchmarks

**Files:** Create `airhealth/report.py`, `airhealth/charts.py`, `airhealth/cli.py`, `benchmarks/cases.toml`, `benchmarks/run.py`, `benchmarks/README.md`, `tests/test_cli.py`, `tests/test_benchmarks.py`.

**Interfaces — Produces:**
- Console script `airhealth` with subcommands:
  - `list curves|maps|places` — each row with its source.
  - `compare PLACE --from C1 --to C2 [--map M] [--curves a,b]` — one row per available curve: % of deaths averted, deaths averted per year, years of life expectancy, life-years. `--from` overrides the map's level for the place (so "Delhi from 100" works whatever the map says); without it the map's level is used.
  - `burden PLACE [--map M] [--counterfactual C]`.
  - Global `--json` writes the same content as JSON to stdout.
- `report.table(impacts: list[Impact]) -> str`; `report.to_json(...) -> dict`. Every table ends with one line naming the map, the year, any fallback states, and any curves unavailable with the reason.
- `charts.curves_chart(curves: list[Curve], marks: dict[str, float], path: Path, age: int = 60) -> Path` — relative risk against concentration, 0–150 µg/m³, one line per curve, places marked on the x-axis, and a shaded band above 84 µg/m³ labelled "no long-term study has observed this range" (confirm the 84 figure in Burnett 2018 before using it).
- `benchmarks/run.py` → prints, for each case in `cases.toml`: published value, our value, ratio, and writes `benchmarks/README.md`.

**Benchmark cases (open tier).** Read each published figure and its inputs at source before entering it:
- Jaganathan 2024: deaths per year attributable above 5 µg/m³ (research summary: about 1.5M) — `burden(India, loglinear_jaganathan, counterfactual=5)`, on the map closest to theirs.
- AQLI, Delhi and all-India life-expectancy loss versus 5 µg/m³ — `aqli` curve on the `aqli` map.
- Burnett 2018 India 2015, GEMM NCD+LRI (research summary: 2.219M at 74.0 µg/m³). Our exposure and mortality years differ; state the differences.

- [ ] **Step 1: Failing tests.**
  - `test_compare_delhi_lists_every_available_curve` (invoke the CLI in-process; output contains each `curves.available()` label and the map name).
  - `test_json_flag_emits_valid_json_with_curve_and_map_on_every_row`.
  - `test_unknown_place_exits_nonzero_with_suggestion` (no traceback text in stderr).
  - `test_unavailable_curve_is_named_in_footer`.
  - `test_curve_chart_is_written` (file exists, non-trivial size).
  - `test_benchmarks_within_tolerance`: each case's ratio within the tolerance recorded for it in `cases.toml`. Start at ±15%; where a case cannot meet it for a reason that is understood (different year, different exposure surface), widen that case's tolerance and write the reason in `cases.toml` — do not tune inputs to hit a number.
- [ ] **Step 2:** Run; expect failures.
- [ ] **Step 3:** Implement report, CLI, chart, benchmarks.
- [ ] **Step 4:** `pytest -q` passes. Run `airhealth compare Delhi --from 100 --to 80` and `python benchmarks/run.py`; save the chart to `health/charts/curves_delhi.png`.
- [ ] **Step 5:** Commit: `health: terminal commands, curve chart, open-tier benchmarks`.

### Task 7: Intervention files

**Files:** Create `airhealth/lag.py`, `airhealth/intervention.py`, `interventions/{_template,delhi_100_to_80,november_only_delhi,punjab_haryana_10pct}.toml`, `tests/test_intervention.py`, `tests/test_lag.py`.

**Interfaces — Produces:**
- `intervention.Dist` — a fixed number, or `{dist = "normal"|"lognormal"|"uniform"|"triangular", p5 = …, p95 = …}` (triangular also takes `mode`). `Dist.sample(rng, n) -> np.ndarray`; `Dist.median -> float`.
- `intervention.Intervention` — dataclass: `name, places: list[Place], change_kind: Literal["delta","pct","to"], change: Dist`, `monthly: list[Dist] | None`, `start_year: int`, `ramp_years: int = 0`, `duration_years: int`, `p_success: float`, `cost_once: Dist`, `cost_annual: Dist`, `cost_currency: "INR"|"USD"`, `cost_year: int`, `cost_share_only_on_success: float = 0.0`, `lag: str = "epa20"`, `notes: str`.
- `intervention.load(path: Path) -> Intervention` — raises `intervention.Invalid` with a message naming the field.
- `intervention.annual_from_monthly(monthly: Sequence[float]) -> float` — day-weighted mean of twelve monthly changes.
- `lag.profile(name: str, years: int) -> np.ndarray` — cumulative share of the full risk change realised by the end of each year after exposure falls; `"immediate"` is all ones; `"epa20"` is the US EPA distributed-lag structure (read the shares from EPA's regulatory-impact documentation; record the source).

**TOML shape** (template file documents every field):
```toml
name = "November-only cut in Delhi"
places = ["Delhi"]
start_year = 2027
duration_years = 10
p_success = 0.5

[change]            # exactly one of: delta, pct, to, monthly_delta, monthly_pct
monthly_delta = [0,0,0,0,0,0,0,0,0,0,-40,0]

[cost]
annual = { dist = "lognormal", p5 = 5e7, p95 = 5e8 }
currency = "INR"
year = 2026
```

- [ ] **Step 1: Failing tests.**
  ```python
  def test_november_only_is_small_on_the_annual_mean():
      assert annual_from_monthly([0]*10 + [-40, 0]) == pytest.approx(-40 * 30 / 365, rel=1e-6)
  def test_two_change_fields_rejected():       # delta and pct together → Invalid, message has "change"
  def test_monthly_must_have_twelve():          # 11 values → Invalid, message has "monthly"
  def test_probability_bounds():                # 1.2 → Invalid, message has "p_success"
  def test_percentiles_ordered():               # p5 > p95 → Invalid naming the field
  def test_unknown_place_rejected_with_suggestion()
  def test_template_and_examples_load()
  def test_lognormal_recovers_its_percentiles(): # sample 200k; 5th and 95th within 2%
  def test_lag_profiles(): immediate all ones; epa20 non-decreasing, ends at 1.0, first year < 0.5
  ```
- [ ] **Step 2:** Run; expect failures.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** `pytest -q` passes.
- [ ] **Step 5:** Commit: `health: intervention files and lag profiles`.

### Task 8: Running an intervention with uncertainty

**Files:** Create `airhealth/simulate.py`; extend `cli.py` (`run`), `report.py`, `charts.py`; create `tests/test_simulate.py`; write `health/README.md`; modify root `README.md`, `bets/README.md`, `lit/gaps.md`.

**Interfaces — Consumes:** everything above.

**Produces:**
- `simulate.Run` — dataclass: `intervention`, `map_name`, `per_curve: dict[str, CurveRun]`, `seed`, `n`.
- `simulate.CurveRun` — arrays of length `n`, all **conditional on success**: `life_years`, `deaths_postponed`, `e0_change_years` (population-weighted, at full effect), `cost_usd`; plus `summary() -> dict` (median, p5, p95 of each; `expected_life_years = p_success × mean`; `cost_per_life_year_if_works`; `expected_cost_per_expected_life_year`), and `spread: dict[str, float]` — share of variance in `life_years` from `"pm25_change"` and `"curve_parameters"` (each measured by sampling that group alone with the other at its median).
- `simulate.run(iv: Intervention, map_name: str = "aqli", curves: list[str] | None = None, n: int = 5000, seed: int = 0) -> Run`
- `simulate.across_curve_spread(run: Run) -> float` — ratio of the largest to the smallest median `life_years` across curves.
- CLI: `airhealth run FILE [--map M] [--curves …] [--n N] [--seed S] [--charts DIR]`.
- `charts.results_chart(run, path)` — one bar per curve with its 5–95% range; `charts.spread_chart(run, path)`.

**Accounting in this plan** (the cohort run to 2050 replaces it in a later plan; say so in the README): for each year of the intervention, deaths postponed = steady-state deaths averted × ramp share × lag share; life-years = those deaths by age × remaining life expectancy at that age. Expected cost = one-off + annual × years, with `cost_share_only_on_success` of it multiplied by `p_success`. Convert rupees to dollars with one documented exchange rate per `cost_year` (source it; put the table in `data/`).

- [ ] **Step 1: Failing tests.**
  - `test_same_seed_same_answer`; `test_different_seed_differs`.
  - `test_fixed_inputs_have_no_pm25_spread`: an intervention with a fixed change has `spread["pm25_change"] == 0` and `spread["curve_parameters"] > 0`.
  - `test_expected_is_probability_times_conditional`: `p_success = 0.25` → `expected_life_years == pytest.approx(0.25 * mean(life_years))`.
  - `test_cost_per_life_year_two_ways`: with cost spent regardless, expected cost per expected life-year = if-works figure ÷ `p_success`; with `cost_share_only_on_success = 1.0` the two are equal.
  - `test_november_only_buys_about_a_twelfth`: `november_only_delhi.toml` gives life-years within 25% of one-twelfth of a year-round −40 µg/m³ cut on the log-linear curve, and the report prints the annual-mean change.
  - `test_harmful_intervention_reports_negative_life_years`.
  - `test_ramp_and_lag_reduce_early_years`: 10-year run with `epa20` lag gives fewer life-years than with `immediate`.
  - `test_run_command_prints_every_curve_and_both_cost_figures` (CLI in-process).
  - `test_across_curve_spread_exceeds_within_curve_for_delhi`: for `delhi_100_to_80.toml`, `across_curve_spread(run) > 1.5`.
- [ ] **Step 2:** Run; expect failures.
- [ ] **Step 3:** Implement `simulate.py`, the `run` command and the two charts.
- [ ] **Step 4:** `pytest -q` passes. Run all three example interventions with `--charts health/charts/`.
- [ ] **Step 5: Documentation.** `health/README.md`: what it is; install; the four commands with real output pasted from this build; the curves chart; the spec's "Known limitations" list; what is not built yet (IHME curves, run to 2050, valuation, Surat). Root `README.md`: add the `health/` row to the tracks table; correct the equation to `concentration ≈ emissions ÷ (mixing height × wind speed)` with one sentence on what it omits (exposure, particles formed in the air from gases, imported air, removal). Same equation fix in `bets/README.md`. `lit/gaps.md`: replace the "Burden-of-disease estimates" bullet with one saying another estimate adds nothing, but a tool exposing why estimates differ does — link `health/`.
- [ ] **Step 6:** Commit: `health: run interventions with uncertainty; docs`.

---

## Done when

`cd health && pytest -q` is green; `airhealth compare Delhi --from 100 --to 80` prints a row per open-tier curve; `airhealth run interventions/november_only_delhi.toml` prints conditional and expected results with both cost figures; `python benchmarks/run.py` writes a table of published-versus-ours with reasons for every gap; `health/data/MISSING.md` lists anything that could not be sourced; nothing under `health/data_local/` is tracked; nothing has been pushed.
