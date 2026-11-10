# What hasn't been analysed

A gap is only worth anything if it sits where three things overlap: a question that
matters, data that can answer it, and nobody having done it. This is an attempt at that
intersection, given what's already in this repo.

**Caveat on novelty.** "Nobody has done this" means *I searched and didn't find it*, which
is weaker than it sounds — Indian AQI literature is large, much of it in journals that
index badly. Check before claiming novelty in public. Each gap below carries a confidence.

---

## G1. Did firecracker bans work? — the missing causal evaluation

**Confidence that this is a real gap: high.**

The literature here is a mess of naive before/after comparisons that contradict each other.
One study finds PM2.5 [down ~50% in 2017, then up ~32% in 2018](https://link.springer.com/article/10.1007/s11356-021-17695-w);
another finds the [2020 IGP ban "had a positive impact"](https://www.sciencedirect.com/science/article/abs/pii/S1352231022002886);
advocacy reports claim bans failed entirely. None of them adjusts for the thing that makes
all of this hard — **Diwali moves around the calendar while the smog season doesn't**.

The `diwali/` track already solved exactly that problem. And bans arrived at **different
times in different states** — Supreme Court orders, outright state bans, "green crackers
only" regimes, varying enforcement. That is staggered policy adoption across units, which
is a difference-in-differences design.

**Why this is nearly free:** `diwali/analyze.py` already produces a confounder-adjusted
Diwali effect per city per year. `data/trend_cityyear.csv` *is the dependent variable*.
The remaining work is coding each state-year's ban regime and running the DiD.

**What would kill it:** enforcement varies more than the legal regime does, so a null
result is ambiguous between "bans don't work" and "bans weren't enforced." Mitigation:
SO₂ is the firework fingerprint (sulphur-based crackers) — if a ban bit, the SO₂ signature
should weaken even where PM2.5 is noisy. That makes it a two-outcome test, which is much
harder to explain away.

**Why it matters:** this is a live Supreme Court question, re-litigated every autumn, with
essentially no credible evidence on either side.

---

## G2. GRAP as a regression discontinuity

**Confidence: medium-high.**

GRAP triggers at sharp AQI thresholds (Stage I at 201, II at 301, III at 401, IV at 450).
That is a running variable with cutoffs — the textbook setup for regression discontinuity.
Days just above a threshold get restrictions; days just below don't; nothing else about
them differs systematically.

Nobody in the published evaluations appears to use it. [Kattuman & Harvey](http://www.isid.ac.in/~acegd/acegd2024/papers/PaulKattuman.pdf)
use structural time-series and find **no significant effect for stages 1, 3 and 4**. An
IITM/CAQM counterfactual claims **60% more severe hours without GRAP**. Those can't both
be right, and an RDD would adjudicate.

**The honest complication:** GRAP triggers partly on *forecast* AQI, not realised AQI, so
the discontinuity is fuzzy, not sharp. That's workable — fuzzy RD is standard — but it
needs the forecast series, which may not be archived publicly. **Check that before
committing.** If forecasts aren't available, this gap closes.

---

## G3. Diwali as a natural experiment on the dome effect

**Confidence that it's novel: medium. Confidence that it's interesting: high.**

Absorbing aerosol warms the air aloft and dims the surface, which suppresses the boundary
layer, which concentrates the aerosol further. Over the IGP the feedback is
[well established](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2018jd029758)
(surface forcing of 40–80 W/m²). What nobody has quantified is **the multiplier**: if you
removed X% of the black carbon, how much would the boundary layer deepen, and how much
would that dilute everything else?

That multiplier is the whole case for targeting black carbon over PM2.5 mass — and the
[Science Advances estimate](https://www.science.org/doi/10.1126/sciadv.abo4093) of 400,000
vs 80,000 lives is built on **toxicity alone**. It doesn't price dilution at all.

Diwali is a sudden, dated, massive injection of absorbing aerosol into a winter atmosphere.
If the dome effect is strong, the day *after* a big Diwali should show an anomalously
shallow boundary layer, after controlling for season and weather. Ten years, ten cities,
and cities that differ in baseline.

**The hard limitation, stated plainly:** ERA5's boundary layer height is a *model* output,
and ERA5 does not represent aerosol–radiation feedback well. Testing a feedback using a
product that doesn't contain it is close to circular. This gap needs a different BLH source
— ceilometer or radiosonde (IMD launches twice daily from Delhi) — or it needs to be
reframed around what ERA5 *can* support. **Resolve this before starting.**

---

## G4. How much does monitor siting bias the numbers?

**Confidence: high that it's under-quantified.**

The CAG's audit found [all 13 Delhi CAAQMS had trees on multiple sides](https://cag.gov.in/uploads/download_audit_report/2021/6-Chapter-2-067ebb3e72ff8b4.30490563.pdf),
with Anand Vihar and Wazirpur beside heavy-vehicle roads, against CPCB's own >20 m rule.
A later DPCC/CPCB committee said most stations complied. Both can't be right.

Nobody seems to have asked the downstream question: **how much does this move the city
number everyone quotes?** This repo computes city series as a cross-station median
specifically to limit one bad monitor's influence — which means the machinery to test
station heterogeneity is already here.

Testable with station coordinates plus OpenStreetMap road geometry: do roadside stations
show systematically different *levels*, and different *responses* to events like Diwali?
A roadside monitor is dominated by local traffic and should show a muted festival signal
relative to a background site. If it doesn't, the siting critique is weaker than claimed.

**Why it matters more than it sounds:** every number in Indian air policy — GRAP triggers,
NCAP targets, the AQLI estimates, this repo — inherits whatever bias is in the network.

---

## G5. Nobody looks at the night

**Confidence: medium-high.**

Almost all air-pollution epidemiology uses 24-hour means. The `diwali/` track found the
daily average rises 1.5× on Diwali while **the midnight hour hits 4×, and ~12× in Chennai**.
If health response is non-linear in concentration — and the evidence suggests it is — then
daily means systematically understate harm from peaky exposure, and understate it *unevenly*
across cities with different diurnal shapes.

There is, as far as I can find, no decade-scale characterisation of the diurnal PM2.5
distribution across Indian cities. `tempo.py` already computes it for the festival window.
Extending it to the full decade is mostly mechanical, and it reframes a measurement
question (what's the mean?) as an exposure question (what does a body actually meet?).

---

## G6. The multi-pollutant fingerprint

**Confidence: medium.**

The Diwali work found something methodologically reusable: on firework nights **SO₂ rises
1.25–2.3× in 9 of 11 cities while NO₂ and CO rise far less than PM2.5.** Crackers are
sulphur-based; traffic isn't. That ratio is a source fingerprint, recovered from routine
regulatory monitoring with no receptor model, no filters, no lab.

CAAQMS reports six pollutants at 15-minute resolution across ~500 stations. In principle
the ratios between them carry source information continuously, everywhere, for a decade.
Source apportionment in India is otherwise done with expensive, sparse, infrequent
campaigns — which is why [estimates disagree so violently](https://www.mdpi.com/2071-1050/15/5/4209).

**What would kill it:** secondary aerosol formation scrambles ratios over hours, so this
likely works for sharp local events and fails for aged regional air. That's a real limit,
but it still leaves fires, festivals and industrial episodes.

---

## Deliberately not on this list

Well covered already; don't spend time here.

- **Source apportionment of Delhi** — [done exhaustively](https://www.mdpi.com/2071-1050/15/5/4209), and the disagreement is about method, not missing analysis.
- **COVID lockdown effects** — one of the most over-studied natural experiments in the field.
- **Burden-of-disease estimates** — AQLI and GBD own this; adding another estimate adds nothing.
- **Does stubble burning affect Delhi** — settled; the argument is now about shares and timing.
- **Whether smog towers work** — settled. They don't, and the [arithmetic is not close](https://www.downtoearth.org.in/pollution/smog-towers-ineffective-at-least-40-000-needed-in-delhi-to-combat-toxic-air-dpcc-tells-ngt-92841).

---

## If you only do one

**G1 (firecracker bans).** The dependent variable is already computed and sitting in
`diwali/data/trend_cityyear.csv`. It answers a question that is re-argued in the Supreme
Court every year on almost no evidence. And it's the natural sequel to work that's already
finished and published — the same data, the same method, one more step.

G4 is the best second, because it's the kind of result that makes everything else in the
field more trustworthy, including ours.
