"""Bundle the open data, the measure library and the fonts into the wheel.

The files stay where they are in git (health/data, health/interventions, ../fonts). At build
time they are copied into airhealth/_bundle/ inside the wheel, so
`uvx --from git+...#subdirectory=health airhealth ...` works with no clone.
airhealth/paths.py finds them there. health/data_local (IHME files) is never copied.
"""
import shutil
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py

HERE = Path(__file__).resolve().parent
# (source folder, name inside the bundle)
BUNDLE = [(HERE / "data", "data"), (HERE / "interventions", "interventions"), (HERE.parent / "fonts", "fonts")]
SKIP = shutil.ignore_patterns("data_local", "*.pyc", "__pycache__", ".DS_Store")


class BuildPy(build_py):
    def run(self):
        super().run()
        target = Path(self.build_lib) / "airhealth" / "_bundle"
        for source, name in BUNDLE:
            if source.is_dir():
                shutil.copytree(source, target / name, ignore=SKIP, dirs_exist_ok=True)
        leaked = [p for p in target.rglob("*") if "data_local" in p.parts]
        assert not leaked, f"IHME folder must never be bundled: {leaked}"


setup(cmdclass={"build_py": BuildPy})
