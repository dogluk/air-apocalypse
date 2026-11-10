# Bets

Which interventions survive contact with arithmetic. Working notes, not conclusions.

## The sorting principle

```
concentration  ≈  emissions / (mixing height × ventilation)
```

Every proposal attacks one of those three terms — or else gives up on the air and protects
the lungs directly. Sorting by which term a bet touches, and whether the physics permits
it, kills most of them in one step.

## Two numbers that decide most of it

**Delhi's smog weighs about 150 tonnes.** A 50 × 50 km airshed under a 300 m winter mixed
layer is 7.5 × 10¹¹ m³; at 200 µg/m³ that's ~150 t of PM2.5. The entire visible apocalypse
over 30 million people is a few hundred tonnes of dust. This is why scrubbing *feels*
tractable.

**It refills in about a day.** Delhi's primary PM2.5 emissions run order-100 t/day, more
across the NCR airshed — a residence time of roughly 1–2 days. A perfect, free,
instantaneous 100% scrub buys **one clean day**. Weekly scrubbing changes an annual average
by almost nothing.

That single ratio kills the entire "remove it from the air" family: smog towers, outdoor
filtration, mist cannons, and most of what gets announced each November.

## Why winter cloud seeding can't work in Delhi

Three independent reasons. Only the third is an engineering problem.

**1. The water isn't there.** At 15% RH and 20 °C, the air holds ~2.6 g/m³ of vapour.
Condense *every molecule* in a 1 km column over the city and you get **2.6 mm**. Real
precipitation efficiency is 10–30%, so under 1 mm — drizzle. And drizzle has a
[*negative* removal effect](https://www.researchgate.net/publication/325581755_Observation_of_the_wet_scavenge_effect_of_rainfall_on_PM25_in_Shanghai)
on PM2.5. This is an inventory limit, not a technology limit.

Independently confirmed from the other direction: IITM's Ghude estimates that moving
"very poor" to "moderate" would need [rain almost every other day](https://india.mongabay.com/2025/11/cloud-seeding-not-a-proven-solution-for-air-pollution/).

**2. Seeding is a trigger, not an energy source.** A thunderstorm dropping 1 cm over
20 × 20 km releases ~10¹⁶ J of latent heat — about 2 megatons TNT. Seeding gets that free
by releasing stored CAPE. Spectacular leverage. But **Delhi's winter CAPE is ≈ 0.** It's a
lever with nothing on the other end. The Soviets built
[200–500 MW jet-engine meteotrons](https://doi.org/10.3390/atmos14010086) to force it; in
dry conditions the power was [insufficient to overcome surface inversions](https://esd.copernicus.org/articles/15/109/2024/).

**3. Brute-forcing the inversion means out-muscling the sun.** Heating Delhi's 200 m
nocturnal layer by 2 K takes ~1.2 × 10¹⁵ J — **~30 GW sustained over a morning**, roughly
3–4× Delhi's entire peak electrical demand, as pure waste heat. The sun already delivers
**>1 TW** at noon and still fails on the worst days.

*Empirical confirmation:* Delhi's Oct 2025 trial, two sorties, eight flares, ₹3.21 crore,
**zero precipitation** — moisture 15–20% against the ~50% needed. IIT Kanpur's next attempt
is planned for *summer*, which concedes the point.

## The dome effect — the one real leverage point

Why the sun loses. Absorbing aerosol (black carbon) converts sunlight to heat *aloft* while
dimming the surface by [40–80 W/m²](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2018jd029758).
Warm layer on top, cold ground beneath: stability increased from both ends simultaneously.
Turbulence collapses, the boundary layer doesn't grow, pollution concentrates, absorption
strengthens. A closed positive feedback — the only place in this system where a small input
is amplified.

**The asymmetry that matters:** black carbon is ~5–10% of the mass but does most of the
absorption. Scattering aerosol dims the surface but doesn't heat aloft — it has one arm;
soot has both.

So cutting BC is **two-for-one with a multiplier**: disproportionately toxic mass removed,
*and* a weakened lid that deepens the mixing layer and dilutes the 90% you didn't touch.

The [400,000 vs 80,000 lives estimate](https://www.science.org/doi/10.1126/sciadv.abo4093)
for BC-targeted planning is built on **toxicity alone**. If the dilution multiplier is real,
that figure is an underestimate. Nobody has priced it. See [`../lit/gaps.md`](../lit/gaps.md) G3.

## The menu

| Bet | Status | Read |
|---|---|---|
| **Airshed-wide emissions markets** | ✅ RCT'd | Surat: 20–30% cuts, ~11% cheaper compliance, **benefits ≥ 25× costs**. The only intervention here with a randomised trial. Scale version: CEMS on every stack in the IGP, one market. |
| **Target black carbon, not PM2.5 mass** | 🟡 Strong modelling | ~5× the health return. **India has no BC target at all.** Biggest unclaimed policy lever. |
| **Buy Punjab out of rice** | 🟡 Costed | ~₹35,000/ha for 5 years, largely self-funding from subsidy savings. Attacks the root. |
| **Household fuel transition** | ✅ Proven elsewhere | 90% of China's 2005–15 exposure reduction came from this. Boring, enormous. |
| **Decouple exposure from concentration** | 🟢 Trivially sound | Cheap filtration where people actually are. Fights 20 m³/day per person, not 7.5 × 10¹¹ m³. The only family where physics is on your side. |
| **Dome-effect feedback targeting** | 🔵 Unexplored | Real option value. Simulation-first, not aircraft. |
| **Outdoor electrostatic / ionisation** | 🔴 Prototype | Same refill arithmetic kills it, plus ozone byproduct. |
| **Cloud seeding, winter** | ❌ Closed | Above. |

## Where a company could exist

The cap must be government — only the state can create scarcity and enforce it. Market
design is a public good, and EPIC/J-PAL already do it. **The binding constraint is
measurement**, and that's the part a company can own.

India already mandates CEMS on 17 categories of polluting industry. The data is widely
acknowledged to be junk. **A market on corrupt data is worse than no market** — it
launders pollution into compliance.

The trap in the obvious business: sell monitoring to polluters and *your customer wants
your product to lie.* The shape that works is **independent measurement sold to whoever
needs to trust the number** — regulator, exchange, lender, insurer. The analogue is
Kayrros/Carbon Mapper for methane. It does not exist for Indian particulates.

Prior art to check before assuming open field: Sudarshan already runs a
[sparse low-cost sensor network line of work](https://arxiv.org/pdf/2410.04309) in Delhi.
