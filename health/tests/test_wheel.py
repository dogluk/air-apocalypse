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
        "build", "dist", "*.egg-info", "__pycache__", "out", "charts", ".pytest_cache", "data_local"))
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


SDIST_CALLS: list = []


def _setup_module(monkeypatch):
    """health/setup.py as a namespace, run against stand-ins for setuptools (the test venv need
    not have it): setup does nothing, and the two command classes are empty bases."""
    import runpy
    import types

    class BuildPy:
        pass

    class Sdist:
        def make_release_tree(self, base_dir, files):
            SDIST_CALLS.append(base_dir)

    mods = {"setuptools": types.ModuleType("setuptools"),
            "setuptools.command": types.ModuleType("setuptools.command"),
            "setuptools.command.build_py": types.ModuleType("setuptools.command.build_py"),
            "setuptools.command.sdist": types.ModuleType("setuptools.command.sdist")}
    mods["setuptools"].setup = lambda **kw: None
    mods["setuptools.command.build_py"].build_py = BuildPy
    mods["setuptools.command.sdist"].sdist = Sdist
    for name, mod in mods.items():
        monkeypatch.setitem(sys.modules, name, mod)
    return runpy.run_path(str(HEALTH / "setup.py"))


def _tree(root, files):
    for rel in files:
        f = root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("x")
    return root


def test_bundle_is_emptied_before_each_copy(monkeypatch, tmp_path):
    ns = _setup_module(monkeypatch)
    src = _tree(tmp_path / "data", ["a.csv", "old.csv"])
    fonts = _tree(tmp_path / "fonts", ["f.ttf"])
    target = tmp_path / "bundle"
    entries = [(src, "data"), (fonts, "fonts")]
    ns["bundle"](target, entries)
    assert (target / "data" / "old.csv").exists()
    (src / "old.csv").unlink()
    ns["bundle"](target, entries)                          # built again in the same tree
    assert (target / "data" / "a.csv").exists() and not (target / "data" / "old.csv").exists()


def test_bundle_refuses_ihme_files_by_path_and_by_name(monkeypatch, tmp_path):
    ns = _setup_module(monkeypatch)
    for rel in ("data_local/x.csv", "sub/data_local/x.csv", "ihme_raw/x.csv",
                "IHME_GBD_2023_AIR_POLLUTION_1990_2023_PM_Y20250930.CSV",
                "deep/ihme-gbd_2023_data-0b7890d0-1.csv"):
        src = _tree(tmp_path / rel.replace("/", "_") / "data", ["ok.csv", rel])
        with pytest.raises(SystemExit, match="IHME"):
            ns["bundle"](tmp_path / "b" / rel.replace("/", "_"), [(src, "data")])
    # caught by name alone
    named = _tree(tmp_path / "n" / "data", ["IHME_x.csv"])
    with pytest.raises(SystemExit, match="IHME"):
        ns["bundle"](tmp_path / "bn", [(named, "data")])
    # an open file with GBD in its name is fine (exposure_gbd2019.csv is from a CC BY appendix)
    ok = _tree(tmp_path / "ok" / "data", ["exposure_gbd2019.csv"])
    ns["bundle"](tmp_path / "bok", [(ok, "data")])
    assert (tmp_path / "bok" / "data" / "exposure_gbd2019.csv").exists()


def test_the_real_data_folder_passes_the_ihme_check(monkeypatch, tmp_path):
    ns = _setup_module(monkeypatch)
    assert ns["leaked"](HEALTH / "data") == [] and ns["leaked"](HEALTH / "interventions") == []


def test_bundle_stops_when_a_source_is_missing(monkeypatch, tmp_path):
    ns = _setup_module(monkeypatch)
    src = _tree(tmp_path / "data", ["a.csv"])
    with pytest.raises(SystemExit, match="folder missing.*fonts"):
        ns["bundle"](tmp_path / "b", [(src, "data"), (tmp_path / "fonts", "fonts")])
    assert not (tmp_path / "b").exists()


def test_sdist_carries_the_fonts(monkeypatch, tmp_path):
    ns = _setup_module(monkeypatch)
    SDIST_CALLS.clear()
    ns["Sdist"]().make_release_tree(str(tmp_path / "tree"), [])
    assert SDIST_CALLS and (tmp_path / "tree" / "_fonts" / "youngserif.ttf").exists()
