"""Place names: one canonical spelling for India, its states and UTs, districts and cities.

data/places.csv holds every place with its kind, parent state and aliases. Canonical
state names are the ones baseline.states() prints (SRS / population projections);
every source's spelling of a state is an alias of one of them. Matching ignores case,
accents ('Bihār'), punctuation and '&' versus 'and'.

A Place's `state` is None for the country, the state itself for a state, and the
parent state for a district or city.
"""
import difflib
import re
import unicodedata
from dataclasses import dataclass
from functools import cache
from typing import Literal

import pandas as pd

from . import paths

Kind = Literal["country", "state", "district", "city"]
KINDS: tuple[Kind, ...] = ("country", "state", "city", "district")  # resolve() precedence


@dataclass(frozen=True)
class Place:
    kind: Kind
    name: str
    state: str | None

    @property
    def label(self) -> str:
        """Unique per place: 'Delhi (state)', 'Aurangabad, Bihar (district)'."""
        if self.kind in ("country", "state"):
            return f"{self.name} ({self.kind})"
        return f"{self.name}, {self.state} ({self.kind})"


def norm(text: str) -> str:
    """Matching key: no accents, lower case, '&' as 'and', punctuation as spaces."""
    t = unicodedata.normalize("NFKD", text)
    t = "".join(c for c in t if not unicodedata.combining(c)).lower().replace("&", " and ")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", t).split())


@cache
def _table() -> pd.DataFrame:
    t = pd.read_csv(paths.DATA / "places.csv", dtype=str, keep_default_na=False)
    return t.replace({"": None})


@cache
def _index() -> dict[str, list[Place]]:
    """Normalised name or alias -> places, in resolve() precedence order."""
    out: dict[str, list[Place]] = {}
    t = _table()
    for kind in KINDS:
        for row in t[t.kind == kind].itertuples():
            place = Place(kind, row.name, row.state)
            for key in {norm(row.name), *(norm(a) for a in (row.aliases or "").split(";") if a)}:
                out.setdefault(key, []).append(place)
    return out


def canonical_state(name: str) -> str:
    """The canonical name of a state, UT or India, from any spelling a source prints."""
    for p in _index().get(norm(name), []):
        if p.kind in ("country", "state"):
            return p.name
    raise KeyError(f"unknown state {name!r}")


def _suggest(text: str) -> str:
    keys = difflib.get_close_matches(norm(text), _index(), n=5, cutoff=0.5)
    names = list(dict.fromkeys(f"{_label(p)} ({p.kind})" for k in keys for p in _index()[k]))
    return f"; did you mean {' | '.join(names)}?" if names else ""


def _label(p: Place) -> str:
    return f"{p.name}, {p.state}" if p.kind in ("district", "city") else p.name


def resolve(text: str, kind: Kind | None = None) -> Place:
    """The place a name refers to: country, then state, city, district.

    Districts that share a name (Aurangabad in Bihar and Maharashtra) need the state:
    'Aurangabad, Bihar'. `kind` restricts the match, e.g. kind='district' for Pune
    district rather than Pune city.
    """
    name, _, state = text.partition(",")
    found = _index().get(norm(name), [])
    if state.strip():
        st = canonical_state(state)
        found = [p for p in found if p.state == st]
    if kind:
        found = [p for p in found if p.kind == kind]
    if not found:
        raise KeyError(f"unknown place {text!r}{_suggest(name)}")
    best = [p for p in found if p.kind == found[0].kind]
    if len(set(best)) > 1:
        raise KeyError(f"{text!r} is ambiguous: {'; '.join(_label(p) for p in best)}. "
                       "Add the state after a comma.")
    return best[0]

