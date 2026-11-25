# Cities and months (ranking stage, plan A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `airhealth` knows APnA's ~50 city airsheds and each place's month-by-month PM2.5 shape, and `monthly_pct` cuts use that shape instead of treating every month as average.

**Architecture:** The CPCB build script grows from 11 cities to 50 (APnA's 49 airsheds plus Delhi) and also writes monthly means. A new module, `airhealth/months.py`, turns those into a twelve-value shape for any place (city, district, state, India) with a stated fallback. The intervention layer samples one quantile per draw and turns it into an annual change per place, so `monthly_pct` can weight months by each place's own shape while every other change kind gives exactly today's numbers.

**Tech Stack:** Python 3.13 (`.venv` at repo root), numpy, pandas, duckdb + openpyxl (`build` extra), pytest.

**Spec:** `docs/specs/2026-11-12-intervention-ranking-design.md`, part 1 ("Cities and their months"). Read it first. This plan is the first of four for that spec (see "Later plans" at the end).

## Global Constraints

- **Provenance:** no number enters code or data unless read at its source. Every new data file gets an entry in `health/data/sources.toml` (source, url, locator, retrieved, licence, method, script, notes), like the existing ones.
- APnA CSV: Zenodo record 6919069, file `APnA_50airsheds_PM25_Source_Apportionment_CAMxOutputs.csv`, CC BY 4.0, sha256 `c3222ffb4c41f1c31d8a6da55c0ea800af3e7fdd7088f8059c17a86717381dcf`, 49 airsheds (Varanasi is missing). Attribute UrbanEmissions in sources.toml.
- CPCB-derived tables are ODbL 1.0, like `exposure_cpcb.csv`.
- City populations stay Census 2011 (table A-04 (I), already the source of `cities.csv`). Existing 11 cities' rows keep their current values.
- Never commit IHME data (`health/data_local/`). Commit locally on `main`. **Never push.**
- Run tests from `health/`: `../.venv/bin/python -m pytest -q`. Today: 241 pass with the IHME files, 18 skip without them. Benchmarks must still pass unchanged.
- A shape is twelve numbers, January first, normalised so its day-weighted mean is 1: `np.dot(MONTH_DAYS, shape) / 365 == 1`.
- Default shape window: CPCB years **2023-2025**.

## Review Focus

1. **A city with no monitor, or with months missing (monsoon outages).** Expect a fallback that is named on the result ("Gaya: shape borrowed from Patna"), never a silent flat shape. → Task 4 tests `test_city_without_monitor_borrows`, `test_missing_month_falls_back`.
2. **A multi-place `monthly_pct` file** (`["Punjab", "Haryana"]`). Expect each place cut by its own shape, results added as today. → Task 5 `test_monthly_pct_two_places`.
3. **New city names that collide with districts** (Aurangabad is a district in Bihar and Maharashtra; Patna, Raipur, Hyderabad are districts too). Expect the bare name to resolve to the city (city outranks district, as now), the district to remain reachable as "Aurangabad, Bihar". → Task 2 `test_new_city_names_resolve`.
4. **Existing results move when they shouldn't.** Every change kind except `monthly_pct` must give bit-identical draws to today. → Task 5 `test_draws_unchanged_for_other_kinds`.
5. **`from_level` with `monthly_pct`.** The shape is relative, so it still applies; the annual pct is the same with or without `from_level`. → Task 5 `test_monthly_pct_with_from_level`.

---

### Task 1: The APnA file, committed with its provenance

**Files:**
- Create: `health/data/apna_source_apportionment.csv` (the Zenodo CSV byte for byte)
- Modify: `health/data/sources.toml` (new entry `["apna_source_apportionment.csv"]`)
- Test: `health/tests/test_apna.py`

**Interfaces:**
- Produces: `data/apna_source_apportionment.csv` with columns `Airshed, City, A..I, study_uear` exactly as published (the typo `study_uear` is theirs; keep it). Plan B parses the shares; this task only commits the file.

- [ ] **Step 1: Write the failing test**

```python
def test_apna_file_is_the_published_one():
    raw = (paths.DATA / "apna_source_apportionment.csv").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == "c3222ffb4c41f1c31d8a6da55c0ea800af3e7fdd7088f8059c17a86717381dcf"
    t = pd.read_csv(paths.DATA / "apna_source_apportionment.csv")
    assert len(t) == 49 and t.City.is_unique
    assert t.set_index("City").loc["Chennai", "I"] == "13.30%"      # outside share, lowest
    assert t.set_index("City").loc["Amritsar-Tarn Taran", "I"] == "52.70%"
```

- [ ] **Step 2: Run it; expect FAIL (file missing).** `../.venv/bin/python -m pytest tests/test_apna.py -q`
- [ ] **Step 3:** Download with `scripts/_fetch.py`'s `fetch` (or curl) from `https://zenodo.org/api/records/6919069/files/APnA_50airsheds_PM25_Source_Apportionment_CAMxOutputs.csv/content`; write the sources.toml entry. Locator: the categories A transport, B residential, C industry, D dust, E waste burning, F diesel generators, G brick kilns, H sea salt, I outside the airshed; base year 2015 (rows with `study_uear` 2017) or 2018 (2019); the source is the record page, not `lit/`.
- [ ] **Step 4: Run it; expect PASS.** Also run `tests/test_provenance.py` (it checks every data file has an entry).
- [ ] **Step 5: Commit** `git commit -m "data: APnA 49-airshed source apportionment (CC BY 4.0)"`

### Task 2: Fifty cities

**Files:**
- Modify: `health/scripts/build_exposure_cpcb.py` (the `CITIES` table; city CPCB names move from `diwali/config.py` into this table; population sums several Census entries)
- Modify (regenerated): `health/data/cities.csv`, `health/data/exposure_cpcb.csv`, `health/data/places.csv` (via `scripts/build_places.py`)
- Modify: `health/data/sources.toml` (`cities.csv`, `exposure_cpcb.csv` entries: new locator listing every Census entry used, new columns)
- Test: `health/tests/test_places.py`, `health/tests/test_exposure.py`

**Interfaces:**
- Produces: `cities.csv` columns `city, state, population, census_name, aqli_units, acag_units, apna_airshed, cpcb_cities`. `census_name` and `cpcb_cities` are `;`-separated when an airshed spans several towns. `apna_airshed` is the APnA `City` string, or empty for Delhi. `cpcb_cities` is empty when CPCB has no station for the city.
- City set: every APnA airshed (49) plus Delhi = 50 rows. The 11 existing cities keep their names; an APnA airshed that is one of them maps to it (`Ahmedabad` ↔ `Ahmedabad-Gandhi-Nagar`, `Kolkata` ↔ `Kolkata-Howarh`, `Pune` ↔ `Pune-Pimpri-Chinchwad`, and Hyderabad, Mumbai, Surat, Jaipur, Lucknow, Bengaluru, Chennai by name). New cities take a short name: the first town in the APnA name, or the usual name for a pair (`Hubli-Dharwad`, `Raipur-Durg-Bhilai`). A city's Census population is the sum of the Class I entries for the towns its APnA name lists *(Claude's call; say so in sources.toml notes)*.

- [ ] **Step 1: Write the failing tests**

```python
def test_fifty_cities_cover_every_apna_airshed():
    c = pd.read_csv(paths.DATA / "cities.csv")
    a = pd.read_csv(paths.DATA / "apna_source_apportionment.csv")
    assert len(c) == 50 and c.city.is_unique
    assert sorted(c.apna_airshed.dropna()) == sorted(a.City)
    assert c.set_index("city").apna_airshed.isna()["Delhi"]

def test_existing_city_rows_unchanged():
    c = pd.read_csv(paths.DATA / "cities.csv").set_index("city")
    assert c.loc["Delhi", "population"] == 16349831
    assert c.loc["Jaipur", "population"] == 3046163
    assert c.loc["Mumbai", "aqli_units"] == "Mumbai City;Mumbai Suburban"

def test_new_city_names_resolve():
    assert places.resolve("Kanpur") == Place("city", "Kanpur", "Uttar Pradesh")
    assert places.resolve("Aurangabad").kind == "city"
    assert places.resolve("Aurangabad").state == "Maharashtra"
    assert places.resolve("Aurangabad, Bihar").kind == "district"

def test_every_city_has_a_level_on_both_district_maps():   # in test_exposure.py
    for city in pd.read_csv(paths.DATA / "cities.csv").city:
        for m in ("aqli", "acag_total"):
            assert exposure.mean(places.resolve(city), m) > 0, (city, m)
```

- [ ] **Step 2: Run them; expect FAIL.**
- [ ] **Step 3: Extend `CITIES`** to `{city: (census_names, aqli_units, acag_units, apna_airshed, cpcb_cities)}`. The script already checks units exist in each map; add checks that every Census name is found in A-04 (I) and every CPCB name occurs in the 2024 parquet's `City` column (or the city is listed as having no monitor). Rebuild `cities.csv`, `exposure_cpcb.csv` and `places.csv`. Fix any existing test that hard-codes 11 cities.
- [ ] **Step 4: Run the full suite; expect PASS** (241 + new). Benchmarks unchanged.
- [ ] **Step 5: Commit** `git commit -m "Fifty cities: APnA's 49 airsheds plus Delhi"`

### Task 3: Monthly PM2.5 by city from CPCB

**Files:**
- Modify: `health/scripts/build_exposure_cpcb.py` (also write the monthly table, same QC and hourly city medians)
- Create (generated): `health/data/monthly_cpcb.csv`
- Modify: `health/data/sources.toml` (new entry, ODbL 1.0)
- Test: `health/tests/test_months.py`

**Interfaces:**
- Produces: `monthly_cpcb.csv` columns `city, year, month, pm25, hours_share`, every city with a monitor, years 2016-2025, a month-year kept only when `hours_share >= 0.75` (the annual table's rule, applied per month).

- [ ] **Step 1: Write the failing tests**

```python
def test_monthly_means_rebuild_the_annual_ones():
    m = pd.read_csv(paths.DATA / "monthly_cpcb.csv")
    a = pd.read_csv(paths.DATA / "exposure_cpcb.csv")
    for city, year in [("Delhi", 2024), ("Mumbai", 2024), ("Bengaluru", 2023)]:
        months = m[(m.city == city) & (m.year == year)].sort_values("month")
        assert len(months) == 12
        hours = intervention.MONTH_DAYS * 24 * months.hours_share.to_numpy()
        rebuilt = np.dot(hours, months.pm25) / hours.sum()     # hour-weighted, as the annual is
        annual = a[(a.city == city) & (a.year == year)].pm25.item()
        assert rebuilt == pytest.approx(annual, rel=0.005)

def test_delhi_winter_is_dirtier_than_monsoon():
    m = pd.read_csv(paths.DATA / "monthly_cpcb.csv")
    d = m[(m.city == "Delhi") & m.year.between(2023, 2025)].groupby("month").pm25.mean()
    assert d[11] / d[7] > 4
```

- [ ] **Step 2: Run them; expect FAIL.**
- [ ] **Step 3:** Group the existing hourly city medians by month in the same duckdb query that makes the annual table; write the CSV and the sources.toml entry (notes: which city-months were dropped for coverage).
- [ ] **Step 4: Run them; expect PASS.**
- [ ] **Step 5: Commit** `git commit -m "data: monthly PM2.5 by city from CPCB"`

### Task 4: A shape for every place

**Files:**
- Create: `health/airhealth/months.py`
- Test: `health/tests/test_months.py`

**Interfaces:**
- Consumes: `monthly_cpcb.csv`, `cities.csv`; `places.Place`; `intervention.MONTH_DAYS` (move `MONTH_DAYS` and `MONTHS` into `months.py` and import them back into `intervention.py` and `report.py`, so there is one copy).
- Produces:

```python
@dataclass(frozen=True)
class Shape:
    values: np.ndarray        # twelve, Jan first, day-weighted mean exactly 1
    basis: str                # "Delhi, CPCB 2023-25" / "borrowed from Patna" / "Bihar: 3 monitored cities"
    borrowed: bool            # True whenever it is not the place's own monitors

def shape(place: Place, years: tuple[int, int] = (2023, 2025)) -> Shape: ...
```

- **Rules, in order** *(Claude's call; these refine the spec's "nearest city", since `cities.csv` has no coordinates)*:
  1. A city with a complete own profile: mean of each month over the years in the window that have that month, then normalised. Complete = all twelve months present in at least one year.
  2. A city without one: the largest (by population) city in the same state with a complete profile; `borrowed=True`.
  3. A state, or a district: the population-weighted mean of the normalised shapes of the state's cities with complete profiles; `borrowed=True` (it comes from cities, not the place). No such city: India's.
  4. India: the population-weighted mean over all cities with complete profiles.

- [ ] **Step 1: Write the failing tests**

```python
def test_shape_is_normalised():
    for p in (places.resolve("Delhi"), places.resolve("Chennai"), places.resolve("Bihar"),
              places.resolve("India"), places.resolve("Patna", kind="district")):
        s = months.shape(p).values
        assert len(s) == 12 and np.dot(months.MONTH_DAYS, s) / 365 == pytest.approx(1)

def test_delhi_own_shape():
    c = months.shape(places.resolve("Delhi", kind="city"))
    assert not c.borrowed and c.values[10] > 2 and c.values[6] < 0.5
    s = months.shape(places.resolve("Delhi"))      # the state: one monitored city, rule 3
    assert s.borrowed and np.allclose(s.values, c.values)

def test_city_without_monitor_borrows(monkeypatch):   # use a real unmonitored city if one exists, else drop its rows
    ...
    assert s.borrowed and "borrowed from" in s.basis

def test_missing_month_falls_back(): ...   # a city whose rows lack July in every year → rule 2

def test_state_shape_is_population_weighted(): ...   # two-city state, by hand
```

  (The implementer fills the elided names after Task 2 fixes the city list; each test keeps the assertion shown.)
- [ ] **Step 2: Run them; expect FAIL.**
- [ ] **Step 3: Implement `months.py`.** Cache the table read (`functools.cache`, as `exposure.py` does).
- [ ] **Step 4: Run them; expect PASS.**
- [ ] **Step 5: Commit** `git commit -m "months: a twelve-month shape for every place"`

### Task 5: `monthly_pct` uses each place's shape

**Files:**
- Modify: `health/airhealth/intervention.py` (`MonthlyMean.ppf` takes optional weights; new `Intervention.annual_change`)
- Modify: `health/airhealth/simulate.py` (`run` draws quantiles once; `_steady` asks each place for its values)
- Modify: `health/airhealth/report.py` (replace the "monthly_pct takes every month to be as polluted…" note with one naming each place's shape basis and any borrowing)
- Modify: `health/interventions/_template.toml`, `health/README.md` (the paragraphs that describe the old assumption), module docstring of `intervention.py`
- Test: `health/tests/test_intervention.py`, `health/tests/test_simulate.py`

**Interfaces:**
- Consumes: `months.shape(place) -> Shape` (Task 4).
- Produces:

```python
class MonthlyMean:
    def ppf(self, q, weights: np.ndarray | None = None) -> np.ndarray: ...
    # weights default MONTH_DAYS / 365; monthly_pct passes MONTH_DAYS * shape / 365

class Intervention:
    def annual_change(self, place: Place, q: np.ndarray) -> np.ndarray:
        """The annual change at quantiles q for this place: monthly_pct weights months by the
        place's shape; every other kind ignores the place."""
```

  `simulate.run`: `q = _rng(seed, 0).random(n)` replaces `iv.change.sample(_rng(seed, 0), n)`; median draws use `q = np.full(n, 0.5)`. Because `Dist.sample` and `MonthlyMean.sample` are both `ppf(rng.random(n))`, draws for every other kind are bit-identical to today. `_steady` takes `q` and calls `iv.annual_change(p, q)` per place. `Run` gains `shapes: dict[str, Shape]` (by place name) for monthly_pct runs, empty otherwise, for the report.

- [ ] **Step 1: Write the failing tests**

```python
def test_monthly_pct_weights_by_shape():
    iv = load(INTERVENTIONS / "november_pct_delhi.toml")    # Delhi (the state), -20% in Nov
    s = months.shape(iv.places[0]).values
    q = np.array([0.5])
    assert iv.annual_change(iv.places[0], q) == pytest.approx(-20 * s[10] * 30 / 365)

def test_draws_unchanged_for_other_kinds():
    for f in ("delhi_100_to_80.toml", "november_only_delhi.toml", "punjab_haryana_10pct.toml"):
        iv = load(INTERVENTIONS / f)          # INTERVENTIONS: health/interventions, as test_intervention.py locates it
        old = iv.change.sample(simulate._rng(0, 0), 500)
        new = iv.annual_change(iv.places[0], simulate._rng(0, 0).random(500))
        assert np.array_equal(old, new)

def test_monthly_pct_two_places():   # Punjab + Haryana, -10% in Oct and Nov
    run = simulate.run(iv, curves=["gemm_ncd_lri"], n=200)
    # each place's annual pct equals -10 * (shape[9]*31 + shape[10]*30) / 365 for its own shape
    ...

def test_monthly_pct_with_from_level():
    a = iv.annual_change(p, q); b = replace(iv, from_level=100).annual_change(p, q)
    assert np.array_equal(a, b)

def test_report_names_the_shape():   # test_report or test_cli
    assert "shape" in footer_text and "CPCB 2023-25" in footer_text
```

- [ ] **Step 2: Run them; expect FAIL.**
- [ ] **Step 3: Implement** the interfaces above; update the report note, template comment, README and docstring (one paragraph each: what the shape is, where it comes from, how it falls back). Add `interventions/november_pct_delhi.toml` as the worked example (`monthly_pct`, -20 in November only, `places = ["Delhi"]` (the state, whose shape is Delhi city's); notes say the number is illustrative). Write this file in Step 1 so the test can load it.
- [ ] **Step 4: Run the full suite and the benchmarks; expect PASS, benchmark ratios unchanged.** Run `../.venv/bin/airhealth run interventions/november_pct_delhi.toml` and check the annual change printed is about 2.4× what a flat month would give (the spec's figure; the exact factor is Delhi's November shape value).
- [ ] **Step 5: Commit** `git commit -m "monthly_pct weights months by each place's own shape"`

---

## Later plans (same spec, written when this one is done)

- **B. Causes by city:** parse APnA into `data/causes.csv` (spec schema), add McDuffie 2021 Supplementary Data 1 and the big-city NCAP/TERI/CSTEP studies from `lit/city-sources.md`, the `--use causes=` switch, and a stubble share by month for IGP cities.
- **C. Library and engine:** `kind`, `scope`, `[targets]`, `[exposure]`, cost drivers, the 2025-rupee deflator, horizon and 3% discounting, covered-population runs in `simulate`, regional measures with source-receptor inputs, and the first ~25 measure files.
- **D. Ranking and checks:** `airhealth rank` (all-India headline and per city), CSV, flips, the `acag_total` default for ranking, the month-by-month sensitivity, new benchmark cases, and the dashboard tab.
