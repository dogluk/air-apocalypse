"""The installed wheel must run with no clone: data, measure library and fonts ride inside it.

The build-and-install test is slow (it builds the wheel, makes a venv and downloads the
dependencies): it runs with AIRHEALTH_SLOW_WHEEL=1.
"""
import os
import shutil
import subprocess
import sys
import venv
import zipfile
from pathlib import Path

import pytest

from airhealth import paths

HEALTH = Path(__file__).resolve().parents[1]
SLOW = os.environ.get("AIRHEALTH_SLOW_WHEEL") == "1"


def test_checkout_layout_unchanged():
    if paths.BUNDLED:
        pytest.skip("running from an installed wheel")
    assert paths.DATA == HEALTH / "data" and (paths.DATA / "sources.toml").exists()
    assert paths.FONTS == HEALTH.parent / "fonts"
    assert paths.OUT == HEALTH / "out" and paths.CHARTS == HEALTH / "charts"


def test_local_folder_can_be_pointed_elsewhere(monkeypatch, tmp_path):
    import importlib
    monkeypatch.setenv("AIRHEALTH_LOCAL", str(tmp_path))
    try:
        importlib.reload(paths)
        assert paths.LOCAL == tmp_path
    finally:
        monkeypatch.delenv("AIRHEALTH_LOCAL")
        importlib.reload(paths)


def test_wheel_contents_and_commands(tmp_path_factory):
    if not SLOW:
        pytest.skip("slow: set AIRHEALTH_SLOW_WHEEL=1 (builds a wheel, creates a venv, downloads dependencies)")
    out = tmp_path_factory.mktemp("wheel")
    # The wheel is built from health/ with fonts one level up, as in git.
    work = out / "health"
    work.mkdir()
    shutil.copytree(HEALTH, work / "h", ignore=shutil.ignore_patterns(
        "build", "*.egg-info", "__pycache__", "out", "charts", ".pytest_cache"))
    shutil.copytree(HEALTH.parent / "fonts", work / "fonts")
    r = subprocess.run([sys.executable, "-m", "pip", "wheel", "--no-deps",
                        "-w", str(out / "dist"), str(work / "h")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-2000:]
    wheel = next((out / "dist").glob("airhealth-*.whl"))
    names = zipfile.ZipFile(wheel).namelist()
    assert not [n for n in names if "data_local" in n], "IHME folder must never be in the wheel"
    for needed in ("airhealth/_bundle/data/sources.toml", "airhealth/_bundle/data/curves_gemm_5cod.csv",
                   "airhealth/_bundle/interventions/library/_template.toml",
                   "airhealth/_bundle/fonts/youngserif.ttf", "airhealth/dashboard.html"):
        assert needed in names, needed

    env_dir = out / "venv"
    venv.create(env_dir, with_pip=True)
    py = env_dir / "bin" / "python"
    r = subprocess.run([str(py), "-m", "pip", "install", "-q", str(wheel)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-2000:]
    cli = env_dir / "bin" / "airhealth"
    clean_env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "AIRHEALTH_LOCAL")}
    cwd = out / "elsewhere"
    cwd.mkdir()

    def run(*args):
        return subprocess.run([str(cli), *args], capture_output=True, text=True, cwd=cwd, env=clean_env)

    for args, text in ((("burden", "Bengaluru"), "Bengaluru"), (("causes", "Bengaluru"), "Bengaluru"),
                       (("score", "Bengaluru", "--n", "200"), "Bengaluru"),
                       (("measures",), "electric_buses")):
        r = run(*args)
        assert r.returncode == 0, (args, r.stderr[-1500:])
        assert text in r.stdout, (args, r.stdout[:500])
    # the three IHME curves are reported unavailable, not broken
    r = run("list", "curves")
    assert r.returncode == 0 and r.stdout.count("[yes]") == 5 and r.stdout.count("[no:") == 3, r.stdout[-800:]
