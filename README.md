# The air apocalypse

India's air kills on the scale that tobacco killed in the twentieth century, and the
response has mostly been theatre: towers that clean a 200-metre radius, aircraft seeding
clouds that aren't there. This repo is an attempt to do the unglamorous part properly —
measure what is actually happening, find the analyses nobody has run, and work out which
ambitious bets survive contact with arithmetic.

Open notebooks, not a finished argument. Everything here is reproducible from free data.

## Tracks

| | What | State |
|---|---|---|
| [`diwali/`](diwali/) | Ten years of hourly PM2.5 across India's ten biggest cities: how much Diwali actually changes the air, and how much of the famous "post-Diwali smog" is Diwali at all | Complete — see its [README](diwali/README.md) |
| [`lit/`](lit/) | What's been published on Indian air quality, and the gap analysis: which questions the data can answer that nobody has asked | In progress |
| [`bets/`](bets/) | Interventions, costed and sorted by whether the physics allows them | In progress |

## What the Diwali track found

Every city has a real Diwali effect — about **4× normal PM2.5 at midnight**, and up to
12× in Chennai — but the "post-Diwali smog" is mostly **not Diwali**. Adjusted for the
onset of winter, stubble smoke and rain, the week after Diwali is statistically
indistinguishable from normal everywhere. What looks like a hangover is the smog season
arriving on schedule.

The health track adds a twist. Around Diwali, Indian searches for **"air quality index"
rise 237%** and "air pollution" 36%, while searches for **cough and sore throat don't
move at all** (−1.8%, −1.3%, both null). Burns rise 75% — the positive control works, so
the method can see a real effect when one is there. Attention spikes; measurable symptoms,
at least as search reveals them, do not.

## The question behind all of it

Concentration ≈ emissions ÷ (mixing height × ventilation).

Every intervention attacks one of those three terms, or else gives up on the air and
protects the lungs directly. Sorting proposals by which term they touch, and whether the
physics permits it, kills most of them quickly. The survivors are mostly about
**measurement** — you cannot regulate or trade what you cannot credibly count.

## Licence

Code MIT; derived data ODbL (inherited from the CPCB compilation); fonts OFL. See `LICENSE`.
By [Akash Kulgod](https://dogl.uk).
