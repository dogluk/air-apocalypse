"""Bundle the open data, the measure library and the fonts into the wheel.

The files stay where they are in git (health/data, health/interventions, ../fonts). At build
time they are copied into airhealth/_bundle/ inside the wheel, so
`uvx --from git+...#subdirectory=health airhealth ...` works with no clone.
airhealth/paths.py finds them there. health/data_local (IHME files) is never bundled.

The bundle folder is emptied before every copy, so a file deleted or renamed in git cannot ride
along in the next wheel built in the same tree, and every file copied is checked: nothing under
a data_local folder and nothing named like an IHME download goes in (see `leaked`).

Fonts live one level above health/ in git. A wheel built from the checkout reads them there; an
sdist copies them into the tarball (sdist.make_release_tree below, as `_fonts`) so a wheel built
from it finds them too. A bundle source that is missing stops the build with an error, never a
wheel without fonts.
"""
import re
import shutil
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py
from setuptools.command.sdist import sdist

HERE = Path(__file__).resolve().parent
FONTS_IN_GIT = HERE.parent / "fonts"
FONTS_IN_SDIST = HERE / "_fonts"
SKIP = shutil.ignore_patterns("*.pyc", "__pycache__", ".DS_Store")   # not data_local: that is refused
# IHME downloads are named IHME_GBD_... or IHME-GBD_... (health/IHME_DOWNLOADS.md); they live
# under health/data_local/ihme_raw.
IHME_NAME = re.compile(r"^ihme[_-]", re.IGNORECASE)
IHME_FOLDERS = ("data_local", "ihme_raw")


def sources() -> list[tuple[Path, str]]:
    """(source folder, name inside the bundle)."""
    fonts = FONTS_IN_GIT if FONTS_IN_GIT.is_dir() else FONTS_IN_SDIST
    return [(HERE / "data", "data"), (HERE / "interventions", "interventions"), (fonts, "fonts")]


def leaked(root: Path) -> list[Path]:
    """Files under root that must never be bundled: under a data_local (or ihme_raw) folder, or
    named like an IHME download."""
    return [p for p in Path(root).rglob("*")
            if p.is_file() and (any(part.lower() in IHME_FOLDERS for part in p.relative_to(root).parts)
                                or IHME_NAME.match(p.name))]


def bundle(target: Path, entries: list[tuple[Path, str]]) -> None:
    """Empty `target`, copy each source folder into it, and refuse if anything leaked. A missing
    source is an error."""
    missing = [str(src) for src, _ in entries if not Path(src).is_dir()]
    if missing:
        raise SystemExit("airhealth: cannot bundle, folder missing: " + ", ".join(missing)
                         + ". Build from a checkout (the fonts are ../fonts) or from an sdist "
                         "made from one.")
    target = Path(target)
    shutil.rmtree(target, ignore_errors=True)
    for source, name in entries:
        shutil.copytree(source, target / name, ignore=SKIP)
    bad = leaked(target)
    if bad:
        shutil.rmtree(target, ignore_errors=True)
        raise SystemExit(f"airhealth: IHME files must never be bundled: {[str(p) for p in bad]}")


class BuildPy(build_py):
    def run(self):
        super().run()
        bundle(Path(self.build_lib) / "airhealth" / "_bundle", sources())


class Sdist(sdist):
    def make_release_tree(self, base_dir, files):
        super().make_release_tree(base_dir, files)
        if not FONTS_IN_GIT.is_dir():
            raise SystemExit(f"airhealth: no fonts folder at {FONTS_IN_GIT}; an sdist is built "
                             "from a checkout")
        shutil.copytree(FONTS_IN_GIT, Path(base_dir) / "_fonts", ignore=SKIP)


setup(cmdclass={"build_py": BuildPy, "sdist": Sdist})
