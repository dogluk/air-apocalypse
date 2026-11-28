"""The list of open work, checked and written out.

    cd health && PYTHONPATH=. ../.venv/bin/python scripts/open_work.py [--sensitivity PATH]
        [--registry open_work.toml] [--out-dir ../docs]

Reads health/open_work.toml (the registry, edited by hand: the source of truth), checks it, and
writes docs/open-work.md and docs/open-work.json. Never edit those two; edit the registry and run
this again. Standard library only (it does not run the model).

The order is by how much an item could move the ranking. The input is the latest sensitivity
file (default health/out/rank/sensitivity_bengaluru.json, written by
`airhealth rank Bengaluru --sensitivity`, or one given with --sensitivity). Its "research" list
counts, for each research unit (effect:<measure>, cost:<measure>, study, map, ...), the curves on
which moving that input changes the top 5 of the table. An item's count is the largest over the
units its `affects` touch. The noise-robust count (a curve counts only when a measure the other random
seeds we ran never swap in or out of the top enters or leaves it and moves further than the
seeds move it) is used when the file has it, the raw count otherwise. Ties are broken by how weak the evidence is (placeholder, recalled [R],
seen in a summary [S], receptor fallback, judgement, partial cost, none) and then by size (one sitting first), then
by id. With no sensitivity file the order is by weakness and size alone, and the output says so.

What `affects` touches:
  measure:<id>   units effect:<id> and cost:<id>
  study:<id>     unit "study" (a causes study)
  table:<file>   receptor_*.csv: the units of every measure reading that receptor;
                 exposure_*.csv: unit "map"; causes*.csv and cause_share*.csv: unit "study";
                 anything else: no research unit
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import re
import sys
import tomllib
from pathlib import Path

HEALTH = Path(__file__).resolve().parents[1]
REPO = HEALTH.parent
REGISTRY = HEALTH / "open_work.toml"
DEFAULT_SENSITIVITY = HEALTH / "out" / "rank" / "sensitivity_bengaluru.json"
OUT_DIR = REPO / "docs"

RULES = ("No number enters code or data unless you read it at its source, and you record where "
         "(table, figure, page). Never average curves, studies or maps; show them side by side. "
         "A source that does not report something has not reported zero. Never tune an input to "
         "close a gap with a published figure; a labelled what-if run beside an unchanged default, "
         "or a spread shown instead of a point, is not tuning.")

KINDS = ("desk lookup", "data build", "model build", "fieldwork", "review")
SIZES = ("one sitting", "bigger")
WEAKNESS = ("placeholder", "R", "S", "receptor_fallback", "judgement", "partial_cost", "none")   # weakest first
WEAKNESS_WORDS = {"placeholder": "placeholder", "R": "[R] recalled", "S": "[S] seen in a summary",
                  "receptor_fallback": "receptor fallback",
                  "judgement": "judgement", "partial_cost": "partial cost", "none": "none flagged"}
REQUIRED = ("id", "title", "kind", "size", "weakness", "question", "read_at", "lands_in",
            "lands_field", "check", "affects", "origin")
STRINGS = ("title", "question", "read_at", "lands_field", "check")
ID_RE = re.compile(r"^OW-\d{3}$")


# ---- reading ----------------------------------------------------------------------------------

def load(path: Path | str = REGISTRY) -> list[dict]:
    with open(path, "rb") as f:
        return tomllib.load(f).get("item", [])


def _library(repo: Path) -> dict[str, dict]:
    out = {}
    for f in sorted((repo / "health" / "interventions" / "library").glob("*.toml")):
        if not f.name.startswith("_"):
            with open(f, "rb") as h:
                out[f.stem] = tomllib.load(h)
    return out


def _studies(repo: Path) -> set[str]:
    path = repo / "health" / "data" / "causes.csv"
    if not path.exists():
        return set()
    with open(path, newline="", encoding="utf-8") as f:
        return {r["study"] for r in csv.DictReader(f)}


def _sources(repo: Path) -> dict:
    path = repo / "health" / "data" / "sources.toml"
    if not path.exists():
        return {}
    with open(path, "rb") as f:
        return tomllib.load(f)


# ---- checking ---------------------------------------------------------------------------------

def validate(items: list[dict], repo: Path = REPO) -> list[str]:
    """Every problem found, one line each (an empty list means the registry is sound)."""
    problems: list[str] = []
    lib, studies = _library(repo), _studies(repo)
    seen: set[str] = set()
    for n, it in enumerate(items, 1):
        name = it.get("id", f"item #{n}")
        for key in REQUIRED:
            if key not in it:
                problems.append(f"{name}: missing field {key!r}")
        if not ID_RE.match(str(it.get("id", ""))):
            problems.append(f"{name}: id must look like OW-001")
        elif it["id"] in seen:
            problems.append(f"duplicate id {it['id']}")
        seen.add(str(it.get("id")))
        for key, allowed in (("kind", KINDS), ("size", SIZES), ("weakness", WEAKNESS)):
            if key in it and it[key] not in allowed:
                problems.append(f"{name}: {key} {it[key]!r} is not one of {', '.join(allowed)}")
        if it.get("status", "open") not in ("open", "done"):
            problems.append(f"{name}: status must be open or done")
        if it.get("status") == "done" and not it.get("closed_by"):
            problems.append(f"{name}: a done item names the commit that closed it (closed_by)")
        for key in STRINGS:
            if key in it and (not isinstance(it[key], str) or not it[key].strip()):
                problems.append(f"{name}: {key} must be a non-empty string")
        for key in ("lands_in", "origin"):
            v = it.get(key)
            if key in it and (not isinstance(v, list) or not v
                              or not all(isinstance(x, str) and x for x in v)):
                problems.append(f"{name}: {key} must be a non-empty list of strings")
        for path in it.get("lands_in", []) if isinstance(it.get("lands_in"), list) else []:
            if not (repo / path).exists():
                problems.append(f"{name}: landing file {path} does not exist")
        aff = it.get("affects", [])
        if not isinstance(aff, list):
            problems.append(f"{name}: affects must be a list")
            aff = []
        for a in aff:
            kind, _, ident = str(a).partition(":")
            if kind == "measure" and ident in lib:
                continue
            if kind == "study" and ident in studies:
                continue
            if kind == "table" and ident and (repo / "health" / "data" / ident).is_file():
                continue
            problems.append(f"{name}: affects {a!r} names no real measure, study or table")
    return problems


def _weak_reasons(m: dict, sources: dict) -> list[str]:
    why = []
    if m.get("placeholders"):
        why.append("placeholder")
    keys = [e.get("key") for e in m.get("evidence", [])]
    keys += [e.get("key") for e in (m.get("cost", {}).get("full", {}) or {}).get("evidence", [])]
    why += [f"[{k}] evidence" for k in sorted({k for k in keys if k in ("S", "R")})]
    if m.get("cost", {}).get("partial"):
        why.append("partial cost")
    if m.get("evidence_from"):
        why.append("borrowed evidence")
    rec = m.get("region", {}).get("receptor")
    if rec and any(k in sources.get(rec, {}) for k in ("fallback", "caveat")):
        why.append("receptor fallback")
    return why


def uncovered(items: list[dict], repo: Path = REPO) -> list[tuple[str, list[str]]]:
    """Library measures flagged weak (placeholder, [S]/[R] evidence, partial cost, borrowed
    evidence, receptor fallback) that no item's `affects` names."""
    named = {a.partition(":")[2] for it in items for a in it.get("affects", [])
             if a.startswith("measure:")}
    src = _sources(repo)
    return [(m, w) for m, d in _library(repo).items()
            if m not in named and (w := _weak_reasons(d, src))]


def closed_ids(items: list[dict]) -> list[str]:
    return [i["id"] for i in items if i.get("status", "open") == "done"]


# ---- ordering ---------------------------------------------------------------------------------

def units_of(affect: str, repo: Path = REPO) -> list[str]:
    kind, _, ident = affect.partition(":")
    if kind == "measure":
        return [f"effect:{ident}", f"cost:{ident}"]
    if kind == "study":
        return ["study"]
    if kind == "table":
        if ident.startswith("receptor_"):
            return [u for m, d in _library(repo).items()
                    if d.get("region", {}).get("receptor") == ident for u in units_of(f"measure:{m}")]
        if ident.startswith("exposure_"):
            return ["map"]
        if ident.startswith(("causes", "cause_share")):
            return ["study"]
    return []


def _count(row: dict) -> tuple[int, str]:
    if row.get("noise_robust") is not None:
        return int(row["noise_robust"]), "noise-robust"
    raw = row.get("curves_top_changed")
    if raw is None:
        c = row.get("curves", 0)
        raw = len(c) if isinstance(c, list) else int(c or 0)
    return int(raw), "raw"


def load_sensitivity(path: Path | str | None) -> dict | None:
    """The sensitivity JSON, or None if there is no such file. Adds `generated` (the file's own
    key if it has one, else its modification date) and `path`."""
    if path is None or not Path(path).is_file():
        return None
    p = Path(path)
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("generated",
                    datetime.date.fromtimestamp(p.stat().st_mtime).isoformat())
    data["path"] = str(p)
    return data


def describe(sens: dict | None, path: str | None = None) -> dict | None:
    if sens is None:
        return None
    kinds = {_count(r)[1] for r in sens.get("research", [])}
    return {"file": path or sens.get("path", ""), "place": sens.get("place", base_place(sens)),
            "generated": sens.get("generated", ""), "top": sens.get("top", 5),
            "seeds": sum(1 for x in sens.get("settings", []) if x.get("input") == "seed"),
            "count": ("noise-robust" if kinds == {"noise-robust"} else
                      "raw" if kinds <= {"raw"} else "noise-robust where present, else raw")}


def base_place(sens: dict) -> str:
    return (sens.get("base") or {}).get("place", "")


def order(items: list[dict], sens: dict | None, repo: Path = REPO) -> list[dict]:
    """The open items, each with a `priority` dict, most movable first."""
    counts = {r["unit"]: _count(r) for r in (sens or {}).get("research", [])}
    out = []
    for it in items:
        if it.get("status", "open") == "done":
            continue
        e = dict(it)
        w = it["weakness"]
        if sens is None:
            pr = {"count": None, "count_kind": None, "unit": None,
                  "basis": f"no sensitivity file; ordered by evidence weakness ({WEAKNESS_WORDS[w]}) "
                           f"then size ({it['size']})"}
        else:
            units = [u for a in it["affects"] for u in units_of(a, repo)]
            found = [(counts[u][0], u, counts[u][1]) for u in dict.fromkeys(units) if u in counts]
            if found:
                c, u, kind = max(found, key=lambda t: (t[0], t[1]))
                pr = {"count": c, "count_kind": kind, "unit": u,
                      "basis": f"{u}: changes the top {sens.get('top', 5)} on {c} curves ({kind}); "
                               f"then evidence weakness ({WEAKNESS_WORDS[w]}), size ({it['size']})"}
            else:
                why = ("it names no research unit" if not units else
                       "none of its research units is in this run")
                pr = {"count": 0, "count_kind": None, "unit": None,
                      "basis": f"no research unit in the sensitivity file ({why}); counted as 0; "
                               f"then evidence weakness ({WEAKNESS_WORDS[w]}), size ({it['size']})"}
        e["priority"] = pr
        out.append(e)
    out.sort(key=lambda e: (-(e["priority"]["count"] or 0), WEAKNESS.index(e["weakness"]),
                            SIZES.index(e["size"]), e["id"]))
    for n, e in enumerate(out, 1):
        e["priority"]["order"] = n
    return out


# ---- writing ----------------------------------------------------------------------------------

def _header(desc: dict | None) -> list[str]:
    if desc is None:
        return ["No sensitivity file was used, so this order is by evidence weakness "
                "(placeholder, [R], [S], receptor fallback, judgement, partial cost, none) and then size, not by how "
                "much an item could move the ranking. Pass `--sensitivity PATH` (a file written by "
                "`airhealth rank CITY --sensitivity`) to order by that."]
    return [f"Order: by the {desc['count']} count of curves whose top {desc['top']} changes when the "
            f"inputs an item touches are moved (largest over those inputs; a noise-robust curve is "
            f"one where a measure outside the swaps of the other random seeds that run made "
            f"({desc.get('seeds', 0)} other seed{'' if desc.get('seeds') == 1 else 's'} in this "
            f"run) enters or leaves and moves further than those seeds move it), taken from the "
            f"sensitivity run for {desc['place'] or 'one city'} generated {desc['generated']}"
            f" (file: `{desc['file']}`). The run may be stale: re-run it after the library or data "
            f"change, then regenerate this list. Ties go to the weaker evidence, then the smaller "
            f"item. Items that touch nothing in that city's run count as 0."]


def render_md(ordered: list[dict], desc: dict | None, repo: Path = REPO) -> str:
    L = ["# Open work", "",
         "Generated from `health/open_work.toml` by `health/scripts/open_work.py`. Do not edit "
         "this file: edit the registry and regenerate. Claim an item by its id (OW-NNN); an id "
         "never changes and is never reused. The same list is in `docs/open-work.json`.", "",
         "## Rules (quote these in your write-up)", "", f"> {RULES}", "",
         "Say in your write-up what you read and what you could not check. "
         "[AGENTS.md](../AGENTS.md) has the rest of the rules.", "",
         "## How this list is ordered", ""]
    L += _header(desc)
    L += ["", f"{len(ordered)} open items. Kinds: desk lookup, data build, model build, fieldwork, "
          "review. Size: one sitting, or bigger.", "", "## Items", ""]
    for e in ordered:
        p = e["priority"]
        L += [f"### {e['id']}: {e['title']}", "",
              f"- Kind: {e['kind']}",
              f"- Size: {e['size']}",
              f"- Question: {e['question']}",
              f"- Where to read it: {e['read_at']}",
              f"- Lands in: {', '.join(f'`{x}`' for x in e['lands_in'])}: {e['lands_field']}",
              f"- Check: {e['check']}",
              f"- Affects: {', '.join(e['affects']) if e['affects'] else 'no input of the ranking'}",
              f"- Weakest evidence it replaces: {WEAKNESS_WORDS[e['weakness']]}",
              f"- Priority (#{p['order']}): {p['basis']}",
              f"- Origin: {'; '.join(e['origin'])}", ""]
    return "\n".join(L).rstrip() + "\n"


def render_json(ordered: list[dict], desc: dict | None, repo: Path = REPO,
                closed: list[str] | None = None) -> str:
    doc = {"rules": RULES,
           "ordered_by": (f"{desc['count']} count of curves whose top changes (see sensitivity), "
                          "then evidence weakness, then size" if desc else
                          "evidence weakness, then size (no sensitivity file)"),
           "sensitivity": desc,
           "closed": closed or [],
           "items": ordered}
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


# ---- command line -----------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--registry", type=Path, default=REGISTRY)
    ap.add_argument("--repo", type=Path, default=REPO, help="repository root (for landing files)")
    ap.add_argument("--sensitivity", type=Path, default=DEFAULT_SENSITIVITY,
                    help="a sensitivity JSON (default health/out/rank/sensitivity_bengaluru.json)")
    ap.add_argument("--out-dir", type=Path, default=None, help="default <repo>/docs")
    a = ap.parse_args(argv)
    items = load(a.registry)
    problems = validate(items, a.repo)
    if problems:
        print("open_work: registry problems:\n  " + "\n  ".join(problems), file=sys.stderr)
        return 1
    for m, why in uncovered(items, a.repo):
        print(f"open_work: warning: library measure {m} is flagged ({', '.join(why)}) and no item "
              "names it", file=sys.stderr)
    sens = load_sensitivity(a.sensitivity)
    if sens is None:
        print(f"open_work: no sensitivity file at {a.sensitivity}; ordering by weakness and size",
              file=sys.stderr)
    desc = describe(sens, _display(a.sensitivity, a.repo)) if sens else None
    ordered = order(items, sens, a.repo)
    out = a.out_dir or a.repo / "docs"
    out.mkdir(parents=True, exist_ok=True)
    (out / "open-work.md").write_text(render_md(ordered, desc, a.repo), encoding="utf-8")
    (out / "open-work.json").write_text(render_json(ordered, desc, a.repo, closed_ids(items)),
                                        encoding="utf-8")
    print(f"open_work: {len(ordered)} open items -> {out / 'open-work.md'}, open-work.json",
          file=sys.stderr)
    return 0


def _display(path: Path, repo: Path) -> str:
    """The path as written in the output: relative to the repository when inside it."""
    try:
        return str(Path(path).resolve().relative_to(repo.resolve()))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
