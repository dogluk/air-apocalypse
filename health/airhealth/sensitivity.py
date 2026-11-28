"""What reorders the ranking: one input moved at a time, and what each move does to the ranks.

The funder's question. With money to spend on research before spending on measures, which
uncertainties are worth settling first? The ones that would change the order. This module moves
each input away from the stated defaults, one at a time, re-ranks, and reports:

  - the spread of each measure's rank on each curve across every setting (best, worst), never an
    average of ranks;
  - the single input that moves each measure most on each curve (its mover);
  - the inputs that change the top of the table (the first TOP measures) on how many curves, and
    which measures enter and leave it: the research list, longest first;
  - break-even odds: the odds that it works at which a measure would pass the one above it, or
    fall below the one below.

Defaults: the ACAG total map, the city's APnA study, SRS deaths, 3% a year, curves applied to the
annual mean, each range's middle (the draws), the measure's own odds, seed 0.

Rank changes are measured among the measures ranked both by default and under the setting, so a
measure that drops out (it cannot be scored under that setting; e.g. regional measures under
month-by-month curves, which apply to percent changes only) is counted as dropping out, and does
not shift the others' ranks. A move is "within noise" when it is no larger than the move the seed
settings (other random seeds, nothing else changed) give the same measure on the same curve (the
largest of them). The research list counts each unit twice: raw (a curve counts when the top
changes by more than the seed moves those measures) and noise-robust (a curve counts only when one
measure both is outside the seed's flips and moves further than the seeds move it: two measures
the draws cannot tell apart, swapped, are noise however far the setting moves them). The seed's
flips are those of the first few other seeds we ran (SEEDS, default 3: seed + 1, + 2, + 3), not of
every seed there could be; "never swapped by the seeds we ran" is all the evidence offers. It is
sorted by the noise-robust count.
Delta is the rank under the setting minus the rank by default: + is down the table, - is up.

Everything is shown twice: among all ranked measures, and among the comparable ones only (those
whose cost is whole: flag partial_cost set aside), since several measures rank high on costs
that leave part out.

Speed. Whole-reach scoring of a regional measure (score.region) dominates, and each reach is
scored once per input setting that changes it (map, deaths, discount, seed, and the regional
measure's own effect and cost ranges) and kept in a cache for the rest of the process; settings
that do not touch the reaches (a city's causes study, a city measure's ranges, the odds) reuse the
default reaches. `jobs` > 1 scores the reaches in that many processes.
Timed 2026-11-27 on the maintainer's laptop (10 cores, IHME files present, eight curves, the real
library, n = 300, jobs = 10): Bengaluru 1,224 s (71 settings; 1,196 s of it the 54 whole-reach runs, 40
of them slow, which every setting shares); India (all 50 cities, 108 settings) 1,091 s more, run in
the same process after Bengaluru so that the reaches were cached (alone it would also pay the
~20 minutes of reaches). Most of India's time is the fifty cities rescored under each global
setting, month-by-month curves the slowest.
"""
from __future__ import annotations

import math
import re
import shutil
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

from . import causes, exposure, measures, rank, score, simulate
from .intervention import Dist
from .measures import Measure

INPUTS = ("map", "study", "deaths", "discount", "monthly_curves", "effect", "cost", "odds", "seed")
SEEDS = 3             # how many other seeds make the noise floor (seed + 1 ... seed + SEEDS)
TOP = 5               # size of "the top of the table" (a display choice, stated in output)
LOW, HIGH = 0.05, 0.95
CANNOT = "cannot, even if certain"
GLOBAL = ("map", "deaths", "discount", "monthly_curves", "seed")   # rerun every city and reach

NOTES = (
    "One input at a time, each moved from the stated defaults (ACAG total map, the city's APnA study, "
    "SRS deaths, 3% a year, curves applied to the annual mean, each range's middle, the measure's own "
    "odds). This is a swing, not a value-of-information figure: that would need odds on each input "
    "being right, which nobody has.",
    "Ranks on different curves are shown side by side and never averaged.",
    "A rank change no larger than the largest one the other random seeds we ran give is within "
    "noise; a measure the seeds we ran never swap across the top line may still be swapped by "
    "another seed.",
    "Effect and cost low/high are each measure's own 5th and 95th percentiles, from its file.",
)
NOTE_COMMON = ("A rank change is counted among the measures ranked both by default and under the "
               "setting; a measure that cannot be scored under a setting drops out and is counted "
               "as dropping out, not as falling to last. Delta: + is down the table, - is up.")
NOTE_MONTHLY = ("Under month-by-month curves (monthly_curves) the regional measures are not run: "
                "month by month applies to percent changes, and a regional change is a fixed "
                "amount. They drop out there; that is not a rank change.")
NOTE_ODDS = ("odds:certain ranks every measure as if it were sure to work (the ratio if it "
             "works); nothing is rerun.")

# Labelled what-ifs: run beside the default, never in place of it, and never part of the research
# list. Each reports where the measures it touches land, among all and among comparable ones.
WHATIFS = ("stubble_lan2022", "full_cost")
WHATIF_NOTE = "what-if, not the default"
STUBBLE_RECEPTOR = "receptor_stubble.csv"
WHATIF_LABELS = {
    "stubble_lan2022": ("the crop-burning source-receptor table scaled up to Lan et al. 2022's "
                        "national figure (the factor is the ratio of the two India-wide "
                        "figures in the table's own fallback note, the same for every district, "
                        "and no district's change is taken past its own PM2.5 on the map used)"),
    "full_cost": ("full costs, from each measure's sourced [cost.full] range, in place of the "
                  "partial costs (whole range; and fixed at its low and its high end)"),
}

_DEATHS = {"model": "deaths from population x the model's death rates, not scaled to the SRS",
           "unwpp": "deaths scaled band by band to the UN's (WPP) deaths by age"}


@dataclass(frozen=True)
class Setting:
    id: str           # "map:aqli", "study:Delhi:teri_..." (India) / "study:teri_..." (city),
                      # "deaths:model", "deaths:unwpp", "discount:0", "monthly_curves",
                      # "effect:<measure>:low|high", "cost:<measure>:low|high", "odds:certain", "seed:1"
    input: str        # one of INPUTS; for effect/cost/study the research unit is input + ":" +
                      # measure or city
    label: str        # plain words

    @property
    def unit(self) -> str:
        """The research unit: the input, or input:measure (effect, cost), or study:city (India)."""
        parts = self.id.split(":")
        if self.input in ("effect", "cost") or (self.input == "study" and len(parts) == 3):
            return ":".join(parts[:2])
        return self.input


def _cols(comparable: bool) -> tuple[str, str]:
    return ("rank_comparable", "base_rank_comparable") if comparable else ("rank", "base_rank")


@dataclass(frozen=True)
class Swing:
    place: str
    base: rank.Ranking
    settings: tuple[Setting, ...]
    ranks: pd.DataFrame        # long: measure, curve, setting, rank (NaN = not ranked under it),
                               # base_rank, rank_comparable, base_rank_comparable
    top: int
    skipped: dict | None = None    # setting id -> why it could not be run at all
    whatifs: tuple = ()            # labelled what-ifs (dicts, see whatif_rows); never defaults

    # --- helpers -------------------------------------------------------------------------------
    def _units(self) -> dict[str, str]:
        return {s.id: s.unit for s in self.settings}

    def _inputs(self) -> dict[str, str]:
        return {s.id: s.input for s in self.settings}

    def _curves(self) -> list[str]:
        return list(dict.fromkeys(self.ranks.curve)) if len(self.ranks) else []

    def deltas(self, comparable: bool = False) -> pd.DataFrame:
        """ranks with a `delta` column: the rank under the setting minus the default rank, both
        counted among the measures ranked under both (NaN where either is missing)."""
        r, b = _cols(comparable)
        df = self.ranks.copy()
        if r not in df:
            df[r], df[b] = df["rank"], df["base_rank"]
        df["delta"] = np.nan
        for _, g in df.groupby(["setting", "curve"], sort=False):
            both = g[g[r].notna() & g[b].notna()]
            if len(both):
                df.loc[both.index, "delta"] = (both[r].rank(method="first")
                                               - both[b].rank(method="first"))
        return df

    def _seed(self, d: pd.DataFrame) -> dict:
        """(measure, curve) -> |delta| under the seed setting(s) (largest if several)."""
        inputs = self._inputs()
        seed = d[d.setting.map(inputs) == "seed"]
        out = {}
        for (m, c), g in seed.groupby(["measure", "curve"], sort=False):
            v = g.delta.abs().max()
            out[(m, c)] = None if pd.isna(v) else float(v)
        return out

    # --- the four views ------------------------------------------------------------------------
    def stability(self, comparable: bool = False) -> pd.DataFrame:
        """measure, curve, base_rank, best, worst (over the default and every setting, each
        setting's rank being the default rank plus its delta),
        settings_moved (settings, not the seed, whose |delta| exceeds the seed's), drops_out
        (settings where it is not ranked while ranked by default), enters (ranked under a
        setting while not by default), seed_delta."""
        cols = ["measure", "curve", "base_rank", "best", "worst", "settings_moved", "drops_out",
                "enters", "seed_delta"]
        if not len(self.ranks):
            return pd.DataFrame(columns=cols)
        r, b = _cols(comparable)
        d = self.deltas(comparable)
        inputs = self._inputs()
        seed = self._seed(d)
        curves = self._curves()
        rows = []
        for (m, c), g in d.groupby(["measure", "curve"], sort=False):
            base = g[b].iloc[0]
            # a setting's rank as moved: default + delta (counted among the measures ranked
            # under both, so others dropping out move nobody); raw when unranked by default
            moved_to = g[r] if pd.isna(base) else base + g.delta
            got = [x for x in [base, *moved_to] if not pd.isna(x)]
            if not got:
                continue
            noise = seed.get((m, c))
            others = g[g.setting.map(inputs) != "seed"]
            moved = int((others.delta.abs() > (noise or 0.0)).sum())
            rows.append(dict(measure=m, curve=c, base_rank=None if pd.isna(base) else int(base),
                             best=int(min(got)), worst=int(max(got)), settings_moved=moved,
                             drops_out=int((g[r].isna() & g[b].notna()).sum()),
                             enters=int((g[r].notna() & g[b].isna()).sum()),
                             seed_delta=noise))
        out = pd.DataFrame(rows, columns=cols)
        if len(out):
            out["_c"] = out.curve.map({c: i for i, c in enumerate(curves)})
            out["_b"] = out.base_rank.fillna(10 ** 6)
            out = out.sort_values(["_c", "_b", "measure"]).drop(columns=["_c", "_b"])
        return out.reset_index(drop=True)

    def movers(self, comparable: bool = False) -> pd.DataFrame:
        """measure, curve, unit, setting, delta (signed), within_noise: for each measure ranked
        by default on a curve, the research unit whose setting moves it most (every tied unit,
        one row each). The seed is never a mover; a setting where it drops out is not a move.
        If nothing moves it, one row with unit and setting None and delta 0."""
        cols = ["measure", "curve", "unit", "setting", "delta", "within_noise"]
        if not len(self.ranks):
            return pd.DataFrame(columns=cols)
        _, b = _cols(comparable)
        d = self.deltas(comparable)
        units, inputs = self._units(), self._inputs()
        seed = self._seed(d)
        rows = []
        for (m, c), g in d.groupby(["measure", "curve"], sort=False):
            if pd.isna(g[b].iloc[0]):
                continue
            noise = seed.get((m, c)) or 0.0
            cand = g[(g.setting.map(inputs) != "seed") & g.delta.notna()]
            biggest = cand.delta.abs().max() if len(cand) else 0.0
            if not len(cand) or biggest == 0:
                rows.append(dict(measure=m, curve=c, unit=None, setting=None, delta=0.0,
                                 within_noise=True))
                continue
            seen = set()
            for x in cand[cand.delta.abs() == biggest].itertuples():
                u = units[x.setting]
                if u in seen:
                    continue
                seen.add(u)
                rows.append(dict(measure=m, curve=c, unit=u, setting=x.setting,
                                 delta=float(x.delta), within_noise=bool(biggest <= noise)))
        return pd.DataFrame(rows, columns=cols)

    def _top_change(self, g: pd.DataFrame, comparable: bool) -> tuple[set, set, pd.DataFrame]:
        """(entered, left, both) for one setting on one curve: the measures that enter and leave
        the top `top`, counted among the measures ranked under both (`both`)."""
        r, b = _cols(comparable)
        both = g[g[r].notna() & g[b].notna()]
        base_top = set(both.sort_values([b, "measure"]).measure[: self.top])
        set_top = set(both.sort_values([r, "measure"]).measure[: self.top])
        return set_top - base_top, base_top - set_top, both

    def noise_sets(self, comparable: bool = False) -> dict[str, list[str]]:
        """curve -> the measures whose place in the top `top` any of the seed settings (the
        other seeds we ran) alone flips (enter or leave): ties the random draws cannot tell apart,
        e.g. two measures whose ratios sit within each other's noise. The union over the seeds,
        so one lucky seed does not clear a measure. Empty lists when there is no seed setting."""
        d = self.deltas(comparable)
        inputs = self._inputs()
        out = {c: set() for c in self._curves()}
        for sid in (s.id for s in self.settings if inputs[s.id] == "seed"):
            for c in out:
                e, lv, _ = self._top_change(d[(d.setting == sid) & (d.curve == c)], comparable)
                out[c] |= e | lv
        return {c: sorted(v) for c, v in out.items()}

    def research(self, comparable: bool = False) -> pd.DataFrame:
        """unit, noise_robust, curves_noise_robust, curves_top_changed, curves, enter, leave,
        max_abs_delta, within_noise, drops_out: for each research unit, the curves on which one
        of its settings changes which measures make the top `top` (among the measures ranked
        under both), the measures that enter and leave, the largest |delta| it gives anyone, the
        curves where the top changed only within seed noise (not counted), and measures in the
        default top that drop out under it.

        Two counts. curves_top_changed (raw): a curve counts when some measure entering or
        leaving moves further than the seed moves it. noise_robust: a curve counts only when
        one measure that enters or leaves is outside the seeds' own flips on that curve
        (noise_sets) and also moves further than the seeds move it. Without a seed setting the
        two are equal, and a noise-robust curve is always a raw one. Sorted by noise_robust,
        then the raw count, then max_abs_delta, descending; the seed is last, as the noise
        floor."""
        cols = ["unit", "noise_robust", "curves_noise_robust", "curves_top_changed", "curves",
                "enter", "leave", "max_abs_delta", "within_noise", "drops_out"]
        if not len(self.ranks):
            return pd.DataFrame(columns=cols)
        r, b = _cols(comparable)
        d = self.deltas(comparable)
        units, inputs = self._units(), self._inputs()
        seed = self._seed(d)
        noise = {c: set(v) for c, v in self.noise_sets(comparable).items()}
        has_seed = any(v == "seed" for v in inputs.values())
        order = list(dict.fromkeys(units[s.id] for s in self.settings))
        rows = []
        for u in order:
            ids = [s.id for s in self.settings if s.unit == u]
            is_seed = all(inputs[i] == "seed" for i in ids)
            changed, quiet, robust, enter, leave, drops = [], [], [], set(), set(), set()
            sub = d[d.setting.isin(ids)]
            big = sub.delta.abs().max() if sub.delta.notna().any() else 0.0
            for c in self._curves():
                hit = noisy = firm = False
                for i in ids:
                    g = sub[(sub.setting == i) & (sub.curve == c)]
                    e, lv, both = self._top_change(g, comparable)
                    drops |= set(g[(g[b] <= self.top) & g[r].isna()].measure)
                    if not (e or lv):
                        continue
                    moved = both[both.measure.isin(e | lv)]
                    beyond = {x.measure for x in moved.itertuples()
                              if abs(x.delta) > (seed.get((x.measure, c)) or 0.0)}
                    real = is_seed or not has_seed or bool(beyond)
                    if real:
                        hit = True
                        enter |= e
                        leave |= lv
                    else:
                        noisy = True
                    if real and not is_seed and (beyond - noise.get(c, set())):
                        firm = True
                if hit:
                    changed.append(c)
                elif noisy:
                    quiet.append(c)
                if firm:
                    robust.append(c)
            rows.append(dict(unit=u, noise_robust=len(robust), curves_noise_robust=robust,
                             curves_top_changed=len(changed), curves=changed,
                             enter=sorted(enter), leave=sorted(leave),
                             max_abs_delta=None if pd.isna(big) else float(big),
                             within_noise=len(quiet), drops_out=sorted(drops), _seed=is_seed))
        out = pd.DataFrame(rows, columns=[*cols, "_seed"])
        out["_d"] = out.max_abs_delta.fillna(-1)
        out = out.sort_values(["_seed", "noise_robust", "curves_top_changed", "_d", "unit"],
                              ascending=[True, False, False, False, True])
        return out.drop(columns=["_seed", "_d"]).reset_index(drop=True)

    def break_even_odds(self, comparable: bool = False) -> pd.DataFrame:
        """measure, curve, rank, p_success, above, odds_to_pass_above, below, odds_to_fall_below,
        pass_above, fall_below: on the default ranking, the odds that it works at which the
        measure's expected life-years per crore would equal the measure just above (or below)
        it. None at the ends; a value above 1 (infinity when no odds would do) cannot happen even
        if it were certain, and its text says so."""
        cols = ["measure", "curve", "rank", "p_success", "above", "odds_to_pass_above", "below",
                "odds_to_fall_below", "pass_above", "fall_below"]
        key = "rank_comparable" if comparable else "rank"
        rows = []
        for c, t in self.base.tables.items():
            ranked = sorted((x for x in t.rows if getattr(x, key) is not None),
                            key=lambda x: getattr(x, key))
            for i, x in enumerate(ranked):
                up = ranked[i - 1] if i > 0 else None
                down = ranked[i + 1] if i + 1 < len(ranked) else None
                pa = None if up is None else break_even(x, up.expected_ly_per_crore)
                fb = None if down is None else break_even(x, down.expected_ly_per_crore)
                rows.append(dict(measure=x.measure, curve=c, rank=getattr(x, key),
                                 p_success=x.p_success, above=up.measure if up else None,
                                 odds_to_pass_above=pa, below=down.measure if down else None,
                                 odds_to_fall_below=fb, pass_above=odds_text(pa),
                                 fall_below=odds_text(fb)))
        return pd.DataFrame(rows, columns=cols)


def break_even(row: rank.Row, target: float | None) -> float | None:
    """The odds p at which row's expected life-years per crore equals `target` (life-years per
    crore). E = p L / (C (1 - s + s p)) per rupee, with L life-years if it works, C the mean cost
    if it works, s the share of cost paid only on success; with k = target x C / 1e7,
    p = k (1 - s) / (L - k s). L is read as the ratio if it works x C / 1e7, so a regional row in a
    city table uses its whole reach's life-years, as its ratio does. inf when L <= k s."""
    c, w = row.mean_cost_inr, row.ly_per_crore_if_works
    if target is None or c is None or w is None or c <= 0:
        return None
    s = row.cost_share_only_on_success
    life = w * c / rank.CRORE
    k = target * c / rank.CRORE
    if life <= k * s:
        return math.inf
    return k * (1 - s) / (life - k * s)


def odds_text(p: float | None) -> str:
    if p is None:
        return ""
    return CANNOT if p > 1 else f"{100 * p:.3g}%"


# --- settings ----------------------------------------------------------------------------------

def pin(m: Measure, group: Literal["effect", "cost"], q: float) -> Measure:
    """The measure with every Dist in the group fixed at its own quantile q (effect: targets'
    cut, exposure covered/hours/cut, region cut; cost: once, annual, units). Other fields are
    untouched."""
    def fix(d):
        return None if d is None else Dist.fixed(float(d.ppf(q)))
    if group == "effect":
        out = replace(m, targets=tuple(replace(t, cut=fix(t.cut)) for t in m.targets))
        if m.exposure is not None:
            e = m.exposure
            out = replace(out, exposure=replace(e, covered=fix(e.covered), hours=fix(e.hours),
                                                cut=fix(e.cut)))
        if m.region is not None:
            out = replace(out, region=replace(m.region, cut=fix(m.region.cut)))
        return out
    if group == "cost":
        if m.cost is None:
            return m
        c = m.cost
        return replace(m, cost=replace(c, once=fix(c.once), annual=fix(c.annual),
                                       units=fix(c.units)))
    raise ValueError(f"group must be effect or cost, not {group!r}")


def _dists(m: Measure, group: str) -> list[Dist]:
    if group == "effect":
        out = [t.cut for t in m.targets]
        if m.exposure is not None:
            out += [m.exposure.covered, m.exposure.hours, m.exposure.cut]
        if m.region is not None:
            out.append(m.region.cut)
        return out
    if m.cost is None:
        return []
    return [d for d in (m.cost.once, m.cost.annual, m.cost.units) if d is not None]


def _is_india(place: str) -> bool:
    return place == rank.INDIA or place.strip().lower() in ("india", "all india")


def _usable_studies(city: str, default: str | None) -> list[str]:
    return [s for s in causes.studies(city)
            if s != default and not isinstance(score._study_shares(city, s), str)]


def settings_for(place: str, inputs: Sequence[str] = INPUTS, folder=measures.LIBRARY, *,
                 map_name: str = "acag_total", deaths=None, discount: float = simulate.DISCOUNT,
                 study: str | None = None, cities: Sequence[str] | None = None,
                 library: dict | None = None, seeds: int = SEEDS) -> list[Setting]:
    """Every setting for the inputs asked for (see the module docstring), each moved from the
    defaults given. seeds: how many other random seeds make the noise floor (seed + 1 to + seeds). A city's study settings are its other studies with a complete split of
    concentration by cause; India's are each such (city, study). Effect and cost settings are
    made only for measures that can apply to the place and have a range in that group."""
    unknown = [i for i in inputs if i not in INPUTS]
    if unknown:
        raise ValueError(f"unknown input {unknown[0]!r}; inputs are {', '.join(INPUTS)}")
    india = _is_india(place)
    lib = measures.library(folder) if library is None else library
    names = (sorted(causes.known_cities()) if cities is None else list(cities)) if india else [place]
    out: list[Setting] = []
    for inp in INPUTS:
        if inp not in inputs:
            continue
        if inp == "map":
            for m in exposure.MAPS:
                if m == map_name or (m == "cpcb" and india) or not exposure.available(m):
                    continue
                out.append(Setting(f"map:{m}", "map",
                                   f"the {m} map ({exposure.LABELS[m]}) instead of {map_name}"))
        elif inp == "study":
            for c in names:
                default = score._default_study(c) if (india or study is None) else study
                for s in _usable_studies(c, default):
                    sid = f"study:{c}:{s}" if india else f"study:{s}"
                    out.append(Setting(sid, "study", f"{c}'s causes of PM2.5 from {s} instead of "
                                                     f"{default or 'no study (none by default)'}"))
        elif inp == "deaths":
            base = deaths if isinstance(deaths, str) else "srs"
            for k, words in _DEATHS.items():
                if k != base:
                    out.append(Setting(f"deaths:{k}", "deaths", f"{words}, instead of {base}"))
        elif inp == "discount":
            if discount != 0:
                out.append(Setting("discount:0", "discount",
                                   f"no discounting instead of {100 * discount:g}% a year"))
        elif inp == "monthly_curves":
            out.append(Setting("monthly_curves", "monthly_curves",
                               "curves applied month by month instead of to the annual mean "
                               "(regional measures are not run under it)"))
        elif inp in ("effect", "cost"):
            for mid, m in lib.items():
                if not india and m.scope == "city" and m.cities is not None and place not in m.cities:
                    continue
                if all(d.kind == "fixed" for d in _dists(m, inp)):
                    continue
                for end, q in (("low", LOW), ("high", HIGH)):
                    out.append(Setting(f"{inp}:{mid}:{end}", inp,
                                       f"{mid}'s {inp} ranges all at their {end} end "
                                       f"({round(100 * q)}th percentile)"))
        elif inp == "odds":
            out.append(Setting("odds:certain", "odds", "every measure as if certain to work"))
        elif inp == "seed":
            for k in range(1, seeds + 1):
                out.append(Setting(f"seed:{k}", "seed", f"another random seed (seed + {k}), "
                                                        "nothing else changed: the noise floor"))
    return out


# --- what-ifs ----------------------------------------------------------------------------------

def stubble_factor() -> tuple[float, float, float]:
    """(factor, table's figure, Lan et al. 2022's figure): read from the "(0.48 against 6.7
    µg/m³)" in receptor_stubble.csv's fallback sentence in data/sources.toml, so the factor is
    computed from the stored values, never typed. ValueError if the sentence has no such pair."""
    sentence = score.receptor_basis(STUBBLE_RECEPTOR, key="fallback")
    got = re.search(r"\(([\d.]+) against ([\d.]+) µg/m³\)", sentence)
    if got is None:
        raise ValueError(f"no '(X against Y µg/m³)' in {STUBBLE_RECEPTOR}'s fallback sentence")
    small, big = float(got[1]), float(got[2])
    return big / small, small, big


def district_pm25(map_name: str) -> dict[tuple[str, str], float]:
    """(state, district) -> annual PM2.5 (µg/m³) on a district map, as the map's own table has
    it. ValueError if the map has no district values."""
    from . import places
    t = exposure.cells(places.resolve("India", kind="country"), map_name)
    return {(r.state, r.unit): float(r.pm25) for r in t.itertuples()}


def scaled_receptors(folder: Path, name: str, factor: float,
                     map_name: str | None = None) -> tuple[Path, dict]:
    """(a new temporary folder, what was capped). The folder holds `name` with every delta times
    `factor`, beside copies of the other receptor files in `folder` (so measure files that read
    them still find them). With map_name, a scaled change is capped at the district's own annual
    PM2.5 on that map: removing a source cannot take out more PM2.5 than there is. The report:
    districts (with a change), capped (how many were cut back), capped_names (up to five, the
    largest scaled change first), no_pm25 (districts the map has no value for; left as scaled,
    not as zero), and map (None when no map was given: nothing capped)."""
    tmp = Path(tempfile.mkdtemp(prefix="airhealth_whatif_"))
    for f in Path(folder).glob("receptor_*.csv"):
        shutil.copy(f, tmp / f.name)
    t = measures.receptor(name, folder)
    scaled = t.delta_pm25_full * factor
    info = dict(map=map_name, districts=int((t.delta_pm25_full != 0).sum()), capped=0,
                capped_names=[], no_pm25=0)
    if map_name is not None:
        have = district_pm25(map_name)
        over = []
        for i, r in t.iterrows():
            p = measures.district(r.district, r.state)
            ambient = have.get((p.state, p.name))
            if ambient is None:
                info["no_pm25"] += int(r.delta_pm25_full != 0)
            elif -scaled[i] > ambient:
                over.append((-scaled[i], r.label))
                scaled[i] = -ambient
        info["capped"] = len(over)
        info["capped_names"] = [lab for _, lab in sorted(over, reverse=True)[:5]]
    t = t[list(measures.RECEPTOR_COLUMNS)].assign(delta_pm25_full=scaled)
    t.to_csv(tmp / name, index=False)
    return tmp, info


def cap_sentence(c: dict) -> str:
    """The cap in words, from scaled_receptors' report."""
    if c["map"] is None:
        return "no map was given, so no district's change was capped"
    out = (f"each district's scaled change is capped at its own PM2.5 on the {c['map']} map "
           f"(a cut cannot remove more than there is): {c['capped']} of {c['districts']} "
           "districts capped")
    if c["capped_names"]:
        out += f" (largest: {', '.join(c['capped_names'])})"
    if c["no_pm25"]:
        out += f"; {c['no_pm25']} districts have no PM2.5 on that map and were not capped"
    return out


def full_cost_library(lib: dict, end: str = "range") -> dict:
    """The library with each measure that has [cost.full] costed by it instead: its annual cost
    becomes the full range (end "range"), or its low or high end fixed ("low", "high"), in the
    range's currency and year; no once cost; and no longer partial (so no partial_cost flag)."""
    out = dict(lib)
    for mid, m in lib.items():
        f = m.cost.full if m.cost is not None else None
        if f is None:
            continue
        annual = {"range": f.annual, "low": Dist.fixed(f.low), "high": Dist.fixed(f.high)}[end]
        out[mid] = replace(m, cost=replace(m.cost, once=Dist.fixed(0.0), annual=annual,
                                           currency=f.currency, year=f.year, partial="",
                                           full=None))
    return out


def whatif_rows(r: rank.Ranking, ids: Sequence[str], variant: str) -> list[dict]:
    """measure, curve, variant, rank, of, rank_comparable, of_comparable, expected_ly_per_crore,
    comparable, status: where each measure in ids sits on each curve of r (of: how many are
    ranked)."""
    out = []
    for c, t in r.tables.items():
        n_all = sum(x.rank is not None for x in t.rows)
        n_comp = sum(x.rank_comparable is not None for x in t.rows)
        for x in t.rows:
            if x.measure in ids:
                out.append(dict(measure=x.measure, curve=c, variant=variant, rank=x.rank, of=n_all,
                                rank_comparable=x.rank_comparable, of_comparable=n_comp,
                                expected_ly_per_crore=x.expected_ly_per_crore,
                                comparable=bool(x.comparable), status=x.status))
    return out


# --- running -----------------------------------------------------------------------------------

_REACHES: dict = {}       # cache: reach key -> Score, or the reason it could not be scored


def _key(mid, s: dict, pinned, folder) -> tuple:
    return (mid, s["map_name"], None if s["curves"] is None else tuple(s["curves"]), s["n"],
            s["seed"], s["discount"], repr(s["deaths"]), s["monthly_curves"], pinned, str(folder))


def _reach_job(args):
    """One whole-reach score (picklable, for a process pool)."""
    mid, s, lib, folder = args
    try:
        return score.region(mid, folder=folder, library=lib, **s)
    except (ValueError, KeyError) as e:
        return f"its whole reach could not be scored: {e}"


def _reaches_many(jobs: list, folder, n_jobs: int, say) -> None:
    """Score every (key, mid, settings, lib) job not already cached, into _REACHES."""
    todo, seen = [], set()
    for key, mid, s, lib in jobs:
        if key in _REACHES or key in seen:
            continue
        seen.add(key)
        todo.append((key, (mid, s, lib, folder)))
    if not todo:
        return
    say(f"scoring {len(todo)} whole reaches of regional measures"
        + (f" in {n_jobs} processes" if n_jobs > 1 and len(todo) > 1 else ""))
    if n_jobs > 1 and len(todo) > 1:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=min(n_jobs, len(todo))) as pool:
            for (key, _), got in zip(todo, pool.map(_reach_job, [a for _, a in todo])):
                _REACHES[key] = got
    else:
        for key, a in todo:
            _REACHES[key] = _reach_job(a)


def _with(s: dict, setting: Setting) -> dict:
    """The settings dict moved by one global setting."""
    out = dict(s)
    head, _, rest = setting.id.partition(":")
    if head == "map":
        out["map_name"] = rest
    elif head == "deaths":
        out["deaths"] = rest
    elif head == "discount":
        out["discount"] = float(rest) / 100
    elif head == "monthly_curves":
        out["monthly_curves"] = True
    elif head == "seed":
        out["seed"] = s["seed"] + int(rest)
    return out


def _odds_ranks(r: rank.Ranking, sid: str) -> list[dict]:
    """Ranks as if every measure were certain to work: the ratio if it works (rank_if_works)."""
    return [dict(measure=x.measure, curve=c, setting=sid, rank=x.rank_if_works,
                 rank_comparable=x.rank_if_works_comparable)
            for c, t in r.tables.items() for x in t.rows]


def _ranks_of(r: rank.Ranking, sid: str) -> list[dict]:
    return [dict(measure=x.measure, curve=c, setting=sid, rank=x.rank,
                 rank_comparable=x.rank_comparable)
            for c, t in r.tables.items() for x in t.rows]


def run(place: str = "India", *, inputs: Sequence[str] = INPUTS, map_name="acag_total",
        curves=None, n: int = 500, seed: int = 0, discount=simulate.DISCOUNT,
        folder=measures.LIBRARY, top: int = TOP, cities: Sequence[str] | None = None,
        progress: Callable[[str], None] | None = None, study: str | None = None, deaths=None,
        jobs: int = 1, whatifs: Sequence[str] = WHATIFS, seeds: int = SEEDS) -> Swing:
    """Rank `place` (India or a city) by default, then once per setting, and gather the ranks.
    Each city is scored once per setting that changes it, each reach once per setting that
    changes it (cached), and every other Score is the default one. progress(text) reports
    what is being run. jobs: processes for the whole-reach runs. whatifs: labelled what-ifs
    (WHATIFS) run beside the default, reported in Swing.whatifs; they never change the default
    ranking or the research list. seeds: how many other seeds (seed + 1 ... seed + seeds) make the
    noise floor; each is a full rerun, so 1 is quicker but a thinner floor."""
    folder = Path(folder)
    say = progress or (lambda text: None)
    india = _is_india(place)
    names = (sorted(causes.known_cities()) if cities is None else list(cities)) if india else [place]
    lib = measures.library(folder)
    base_s = dict(map_name=map_name, curves=curves, n=n, seed=seed, discount=discount,
                  deaths=deaths, monthly_curves=False)
    city_study = None if india else study

    def score_city(c, s, ids=None, library=lib, study_=None, fallback=None, folder_=None):
        used = study_ if study_ is not None else city_study
        try:
            return score.city(c, ids, study=used, folder=folder_ or folder, library=library, **s)
        except (KeyError, ValueError) as e:
            if fallback is None:
                raise
            why = f"could not be scored under this setting: {e.args[0] if e.args else e}"
            return [replace(x, status="not_scored", reason=why, per_curve={}, run=None)
                    for x in fallback if ids is None or x.measure in ids]

    def merge(old, new):
        got = {x.measure: x for x in new}
        return [got.get(x.measure, x) for x in old]

    say("scoring the default" + (f" in {len(names)} cities" if india else f" in {place}"))
    base_scores = {c: score_city(c, base_s) for c in names}
    if india:
        regional = [m for m, x in lib.items() if x.scope == "region"]
    else:
        regional = [x.measure for x in base_scores[place]
                    if x.scope == "region" and x.status == "scored"]
    settings = settings_for(place, inputs, folder, map_name=map_name, deaths=deaths,
                            discount=discount, study=study, cities=names, library=lib,
                            seeds=seeds)

    pinned_libs = {}
    for st in settings:
        if st.input in ("effect", "cost"):
            _, mid, end = st.id.split(":")
            q = LOW if end == "low" else HIGH
            pinned_libs[st.id] = (mid, {**lib, mid: pin(lib[mid], st.input, q)}, (mid, st.input, q))

    jobs_list = [(_key(m, base_s, None, folder), m, base_s, lib) for m in regional]
    for st in settings:
        if st.input in GLOBAL:
            s = _with(base_s, st)
            jobs_list += [(_key(m, s, None, folder), m, s, lib) for m in regional]
        elif st.id in pinned_libs:
            mid, plib, pkey = pinned_libs[st.id]
            if mid in regional:
                jobs_list.append((_key(mid, base_s, pkey, folder), mid, base_s, plib))
    _reaches_many(jobs_list, folder, jobs, say)

    def reaches(s, pinned=None):
        reach, missing = {}, {}
        for m in regional:
            got = _REACHES[_key(m, s, pinned if pinned and pinned[0] == m else None, folder)]
            if isinstance(got, str):
                missing[m] = got
            else:
                reach[m] = got
        return reach, missing

    def ranking(city_scores, reach, missing, ctx):
        if india:
            return rank.india_from_scores(city_scores, reach, ctx, regional_missing=missing)
        return rank.from_scores(city_scores[place], place, ctx, reach, regional_missing=missing)

    every = [x for c in names for x in base_scores[c]]
    context = rank._context(every, city_study, **base_s)
    if india:
        context["study"] = "each city's own APnA study (each row names the studies it used)"
        context["cities"] = names
    base_reach, base_missing = reaches(base_s)
    base = ranking(base_scores, base_reach, base_missing, context)

    def rerun(ids, library=lib, folder_=None, tag=None):
        """The ranking with the measures in ids rescored (cities and reaches) under another
        library or receptor folder, everything else the default."""
        cs = dict(base_scores)
        for c in names:
            todo = [x.measure for x in base_scores[c] if x.measure in ids
                    and x.status != "not_applicable" and not (india and x.scope == "region")]
            if todo:
                cs[c] = merge(base_scores[c], score_city(c, base_s, todo, library=library,
                                                         fallback=base_scores[c],
                                                         folder_=folder_))
        reach, missing = dict(base_reach), dict(base_missing)
        mine = [m for m in regional if m in ids]
        f = Path(folder_ or folder)
        _reaches_many([(_key(m, base_s, tag, f), m, base_s, library) for m in mine], f, jobs, say)
        for m in mine:
            got = _REACHES[_key(m, base_s, tag, f)]
            reach.pop(m, None)
            missing.pop(m, None)
            if isinstance(got, str):
                missing[m] = got
            else:
                reach[m] = got
        return ranking(cs, reach, missing, context)

    whatif_out = []
    for w in whatifs:
        if w not in WHATIFS:
            raise ValueError(f"unknown what-if {w!r}; what-ifs are {', '.join(WHATIFS)}")
        say(f"what-if (not the default): {w}")
        entry = dict(id=f"whatif:{w}", note=WHATIF_NOTE, label=WHATIF_LABELS[w], measures=[],
                     skipped=None, rows=[])
        if w == "stubble_lan2022":
            factor, small, big = stubble_factor()
            entry.update(factor=factor, basis=(
                f"factor {big:g} / {small:g} = {factor:.3g}: Lan et al. 2022's India-wide "
                f"PM2.5 from crop burning ({big:g} µg/m³) over the table's own "
                f"({small:g} µg/m³), both from {STUBBLE_RECEPTOR}'s fallback note in "
                "data/sources.toml"))
            ids = [m for m, x in lib.items()
                   if x.region is not None and x.region.receptor == STUBBLE_RECEPTOR]
            ids = [m for m in ids if any(x.measure == m and x.status != "not_applicable"
                                         for c in names for x in base_scores[c])]
            if not ids:
                entry["skipped"] = f"no measure scored here reads {STUBBLE_RECEPTOR}"
            else:
                tmp, capped = scaled_receptors(folder, STUBBLE_RECEPTOR, factor, map_name)
                try:
                    r = rerun(ids, folder_=tmp)
                finally:
                    shutil.rmtree(tmp, ignore_errors=True)
                entry["capped"] = capped
                entry["basis"] += "; " + cap_sentence(capped)
                entry["measures"] = ids
                entry["rows"] = whatif_rows(base, ids, "default") + whatif_rows(r, ids, "whatif")
        else:
            ids = [m for m, x in lib.items() if x.cost is not None and x.cost.full is not None
                   and any(y.measure == m and y.status != "not_applicable"
                           for c in names for y in base_scores[c])]
            if not ids:
                entry["skipped"] = "no measure scored here has a [cost.full] range"
            else:
                entry["measures"] = ids
                entry["key"] = {m: lib[m].cost.full.key for m in ids}
                entry["full_cost"] = {m: dict(low=lib[m].cost.full.low, high=lib[m].cost.full.high,
                                              dist=lib[m].cost.full.dist,
                                              currency=lib[m].cost.full.currency,
                                              year=lib[m].cost.full.year,
                                              adds=lib[m].cost.full.adds) for m in ids}
                rows = whatif_rows(base, ids, "default")
                for end, variant in (("range", "whatif"), ("low", "whatif_low"),
                                     ("high", "whatif_high")):
                    r = rerun(ids, library=full_cost_library(lib, end), tag=("full_cost", end))
                    rows += whatif_rows(r, ids, variant)
                entry["rows"] = rows
        whatif_out.append(entry)

    rows, skipped = [], {}
    air_city = [m for m, x in lib.items() if x.kind == "air" and x.scope == "city"]
    for i, st in enumerate(settings, 1):
        say(f"setting {i}/{len(settings)}: {st.id}")
        if st.input == "odds":
            rows += _odds_ranks(base, st.id)
            continue
        if st.input in GLOBAL:
            s = _with(base_s, st)
            cs = {c: score_city(c, s, fallback=base_scores[c]) for c in names}
            reach, missing = reaches(s)
        elif st.input == "study":
            parts = st.id.split(":")
            c, sid = (parts[1], parts[2]) if india else (place, parts[1])
            cs = dict(base_scores)
            cs[c] = merge(base_scores[c], score_city(c, base_s, air_city, study_=sid,
                                                     fallback=base_scores[c]))
            reach, missing = base_reach, base_missing
        else:
            mid, plib, pkey = pinned_libs[st.id]
            cs = dict(base_scores)
            if not (india and mid in regional):
                for c in names:
                    old = next(x for x in base_scores[c] if x.measure == mid)
                    if old.status == "not_applicable":
                        continue
                    cs[c] = merge(base_scores[c], score_city(c, base_s, [mid], library=plib,
                                                             fallback=base_scores[c]))
            reach, missing = reaches(base_s, pkey)
        try:
            r = ranking(cs, reach, missing, context)
        except (KeyError, ValueError) as e:
            skipped[st.id] = str(e)
            continue
        rows += _ranks_of(r, st.id)

    df = pd.DataFrame(rows, columns=["measure", "curve", "setting", "rank", "rank_comparable"])
    basemap = {(x["measure"], x["curve"]): x for x in _ranks_of(base, "base")}
    keys = list(zip(df.measure, df.curve))
    df["base_rank"] = [basemap.get(k, {}).get("rank") for k in keys]
    df["base_rank_comparable"] = [basemap.get(k, {}).get("rank_comparable") for k in keys]
    for col in ("rank", "rank_comparable", "base_rank", "base_rank_comparable"):
        df[col] = pd.to_numeric(df[col], errors="coerce").astype(float)
    df = df[["measure", "curve", "setting", "rank", "base_rank", "rank_comparable",
             "base_rank_comparable"]]
    return Swing(place=base.place, base=base, settings=tuple(settings), ranks=df, top=top,
                 skipped=skipped, whatifs=tuple(whatif_out))


def notes(s: Swing) -> list[str]:
    """NOTES, plus the notes this swing needs (month by month, odds)."""
    out = [*NOTES, NOTE_COMMON]
    ids = {x.id for x in s.settings}
    if "monthly_curves" in ids:
        out.append(NOTE_MONTHLY)
    if "odds:certain" in ids:
        out.append(NOTE_ODDS)
    return out


def _records(df: pd.DataFrame) -> list[dict]:
    return [{k: (None if (not isinstance(v, (list, tuple, str)) and v is not None and pd.isna(v))
                 else v) for k, v in r.items()} for r in df.to_dict("records")]


def to_json(s: Swing) -> dict:
    """{"place", "top", "base": rank.to_json(base) without parts, "settings", "ranks",
    "stability", "movers", "research", "break_even_odds", "notes"}, plus the same four views
    among comparable measures ("*_comparable"), "noise_sets[_comparable]", "skipped" and
    "whatifs" (each labelled "what-if, not the default")."""
    base = {k: v for k, v in rank.to_json(s.base).items() if k != "parts"}
    out = {"place": s.place, "top": s.top, "base": base,
           "settings": [{"id": x.id, "input": x.input, "unit": x.unit, "label": x.label}
                        for x in s.settings],
           "ranks": _records(s.deltas())}
    for comparable in (False, True):
        tail = "_comparable" if comparable else ""
        out["stability" + tail] = _records(s.stability(comparable))
        out["movers" + tail] = _records(s.movers(comparable))
        out["research" + tail] = _records(s.research(comparable))
        out["noise_sets" + tail] = s.noise_sets(comparable)
        out["break_even_odds" + tail] = _records(s.break_even_odds(comparable))
    out["skipped"] = dict(s.skipped or {})
    out["whatifs"] = [dict(w) for w in s.whatifs]
    out["notes"] = notes(s)
    return score._clean(out)


CSV_COLUMNS = ("place", "measure", "curve", "setting", "unit", "label", "rank", "base_rank",
               "delta", "rank_comparable", "base_rank_comparable", "delta_comparable")


def csv_rows(s: Swing) -> list[dict]:
    """One row per measure, curve and setting: ranks under it and by default, and the deltas."""
    d, dc = s.deltas(), s.deltas(True)
    by = {x.id: x for x in s.settings}
    out = []
    for a, c in zip(d.itertuples(), dc.delta):
        st = by.get(a.setting)
        out.append({"place": s.place, "measure": a.measure, "curve": a.curve,
                    "setting": a.setting, "unit": st.unit if st else "",
                    "label": st.label if st else "", "rank": a.rank, "base_rank": a.base_rank,
                    "delta": a.delta, "rank_comparable": a.rank_comparable,
                    "base_rank_comparable": a.base_rank_comparable, "delta_comparable": c})
    return [{k: ("" if isinstance(v, float) and math.isnan(v) else v) for k, v in r.items()}
            for r in out]
