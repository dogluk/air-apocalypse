"""Every data file must have a sources.toml entry with full provenance."""
import tomllib
from pathlib import Path

from . import paths

REQUIRED = ("source", "url", "locator", "retrieved", "licence", "method")
METHODS = ("downloaded", "transcribed", "derived")


def load_sources(path: Path | None = None) -> dict[str, dict]:
    path = path or paths.DATA / "sources.toml"
    with open(path, "rb") as f:
        return tomllib.load(f)


def check(data_dir: Path | None = None, sources_path: Path | None = None) -> list[str]:
    """Return problems found; an empty list means clean."""
    data_dir = data_dir or paths.DATA
    sources = load_sources(sources_path or data_dir / "sources.toml")
    problems = []
    for f in sorted(data_dir.rglob("*.csv")):
        name = f.relative_to(data_dir).as_posix()
        if name not in sources:
            problems.append(f"{name}: no entry in sources.toml")
    for name, entry in sources.items():
        for field in REQUIRED:
            if not entry.get(field):
                problems.append(f"{name}: missing {field}")
        method = entry.get("method")
        if method and method not in METHODS:
            problems.append(f"{name}: method must be one of {METHODS}, got {method!r}")
        if method == "derived" and not entry.get("script"):
            problems.append(f"{name}: derived table needs script")
    return problems
