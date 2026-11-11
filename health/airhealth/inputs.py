"""Every input a result depends on, the sources each can take, and the choice in use.

Sources is the choice for the three demographic inputs baseline.load reads (population by
age, death rates by age, the death count). The other inputs already have their own switches
(the exposure map, the curves, the counterfactual, the timing of benefit in an intervention
file) or one source only; REGISTRY lists them all so `airhealth list inputs`, the footer and
the dashboard describe the same thing. Defaults are called "default", not "best".

A source names its body (the organisation behind the numbers) so a run that mixes bodies can
say so: "india" for the Indian government's own figures, "un" for the United Nations'.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields, replace

INDIA, UN = "Indian government", "United Nations"


@dataclass(frozen=True)
class Source:
    name: str
    label: str
    body: str | None        # None: not a body's figure (e.g. leaving the counts unscaled)


@dataclass(frozen=True)
class Input:
    name: str
    label: str
    default: str
    sources: tuple[Source, ...]
    switch: str              # how to change it today
    pending: str = ""        # credible sources not yet wired

    def source(self, name: str) -> Source:
        for s in self.sources:
            if s.name == name:
                return s
        raise ValueError(f"{self.name}: unknown source {name!r}; choose from "
                         f"{', '.join(s.name for s in self.sources)}")


UNWPP = "UN World Population Prospects 2024, India level"

DEMOGRAPHIC = (
    Input("population", "Population by age", "projection", (
        Source("projection", "Government projections 2011-2036 (Technical Group, 2019), by state", INDIA),
        Source("unwpp", f"{UNWPP}; states keep their projected shares, band by band", UN)),
        switch="--use population=…", pending="Census 2011 for cities after 2011; GBD"),
    Input("death_rates", "Death rates by age", "srs", (
        Source("srs", "SRS life tables 2020-24, by state; 2011-19 moved by each year's SRS rates by age", INDIA),
        Source("unwpp", f"{UNWPP}; states keep their SRS pattern relative to India, band by band", UN)),
        switch="--use death_rates=…", pending="GBD"),
    Input("deaths", "Death count", "srs", (
        Source("srs", "scaled at ages 45+ to each state's SRS crude death rate", INDIA),
        Source("model", "population × death rates, not scaled", None),
        Source("unwpp", "scaled band by band to the UN's deaths by age for India", UN)),
        switch="--use deaths=… (or --deaths)",
        pending="GBD all-cause deaths (needs an 'All causes' query; the IHME curves already use GBD's deaths by cause)"),
)

OTHER = (
    Input("map", "Exposure (PM2.5) map", "aqli", (), switch="--map (gbd2023 needs IHME files)"),
    Input("curves", "Risk curve", "all that can run", (),
          switch="--curves (gbd2019, gbd2023, gemm_5cod need IHME files)"),
    Input("counterfactual", "Counterfactual level", "each curve's floor", (),
          switch="--counterfactual"),
    Input("cause_share", "Share of deaths that are NCD + LRI", "SRS cause of death 2021-23, all-India",
          (), switch="none", pending="GBD by state"),
    Input("timing", "Timing of benefit (intervention files)", "immediate, or EPA 20-year lag", (),
          switch="in the intervention file"),
    Input("fx", "Exchange rate (intervention costs)", "World Bank annual", (), switch="none"),
)

REGISTRY = {i.name: i for i in (*DEMOGRAPHIC, *OTHER)}


@dataclass(frozen=True)
class Sources:
    """The source chosen for each demographic input."""
    population: str = "projection"
    death_rates: str = "srs"
    deaths: str = "srs"

    def __post_init__(self):
        for f in fields(self):
            REGISTRY[f.name].source(getattr(self, f.name))     # raises on an unknown name

    @classmethod
    def of(cls, value: "Sources | str | None") -> "Sources":
        """A Sources from itself, None (the defaults) or a deaths basis ("srs", "model")."""
        if value is None:
            return cls()
        if isinstance(value, Sources):
            return value
        return cls(deaths=value)

    def items(self) -> list[tuple[Input, Source]]:
        return [(REGISTRY[f.name], REGISTRY[f.name].source(getattr(self, f.name)))
                for f in fields(self)]

    @property
    def is_default(self) -> bool:
        return self == Sources()

    @property
    def bodies(self) -> list[str]:
        return list(dict.fromkeys(s.body for _, s in self.items() if s.body))

    @property
    def text(self) -> str:
        return "Sources: " + "; ".join(f"{i.label.lower()}, {s.name}"
                                       + ("" if s.name != i.default else " (default)")
                                       for i, s in self.items())


@dataclass
class Choice:
    """--use flags parsed: each demographic input with one or more sources."""
    chosen: dict[str, list[str]] = field(default_factory=dict)

    @classmethod
    def parse(cls, flags: list[str] | None, deaths: str | None = None) -> "Choice":
        out: dict[str, list[str]] = {}
        if deaths:
            out["deaths"] = [deaths]
        for flag in flags or []:
            if "=" not in flag:
                raise ValueError(f"--use takes input=source, got {flag!r}")
            name, value = flag.split("=", 1)
            name = name.strip()
            if name not in {i.name for i in DEMOGRAPHIC}:
                raise ValueError(f"--use: {name!r} is not a switchable input; choose from "
                                 f"{', '.join(i.name for i in DEMOGRAPHIC)}")
            values = [v.strip() for v in value.split(",") if v.strip()]
            for v in values:
                REGISTRY[name].source(v)
            out[name] = values
        return cls(out)

    def combinations(self, base: Sources | None = None) -> list[Sources]:
        """Every combination of the sources asked for; `base` (default: the defaults) for the
        rest."""
        combos = [{}]
        for name, values in self.chosen.items():
            combos = [{**c, name: v} for c in combos for v in values]
        return [replace(base or Sources(), **c) for c in combos]
