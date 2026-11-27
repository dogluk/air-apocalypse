"""Where the files are.

Two layouts, one answer:
  * a repository checkout (or `pip install -e`): data/ and interventions/ sit in health/, the
    fonts in the repository's fonts/, and output goes to health/out and health/charts;
  * an installed wheel: setup.py copied data/, interventions/ and fonts/ into the package
    (airhealth/_bundle/), found here with importlib.resources. Output goes under the folder
    you run the command from, never into site-packages.
IHME files are never bundled. Put them in a data_local/ folder and point AIRHEALTH_LOCAL at it
(or work from a checkout, where health/data_local/ is used).
"""
import os
from importlib import resources
from pathlib import Path

_bundle = Path(str(resources.files("airhealth").joinpath("_bundle")))
BUNDLED = (_bundle / "data").is_dir()     # True for an installed wheel

if BUNDLED:
    HEALTH = _bundle
    REPO = _bundle
    FONTS = _bundle / "fonts"
    _OUT = Path.cwd() / "airhealth_out"
else:
    HEALTH = Path(__file__).resolve().parents[1]
    REPO = HEALTH.parent
    FONTS = REPO / "fonts"
    _OUT = HEALTH

DATA = HEALTH / "data"          # committed, open tier
LOCAL = Path(os.environ["AIRHEALTH_LOCAL"]) if os.environ.get("AIRHEALTH_LOCAL") else HEALTH / "data_local"
OUT = _OUT / "out"              # `rank --write`, stability runs
CHARTS = _OUT / "charts"
