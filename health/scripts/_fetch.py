"""Download helper for the build scripts: files go to a folder outside the repo."""
import hashlib
import sys
import tempfile
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def workdir(argv: list[str], name: str) -> Path:
    """The download folder: argv[1] if given (to reuse downloads), else a new temp dir."""
    d = Path(argv[1]) if len(argv) > 1 else Path(tempfile.mkdtemp(prefix=f"airhealth-{name}-"))
    d = d.resolve()
    if d.is_relative_to(REPO):
        sys.exit(f"download folder {d} is inside the repo; use one outside it")
    d.mkdir(parents=True, exist_ok=True)
    return d


def fetch(url: str, folder: Path, filename: str | None = None) -> Path:
    """Download url into folder unless already there; print its sha256."""
    path = folder / (filename or url.rsplit("/", 1)[-1].replace("%20", "_"))
    if not path.exists():
        req = urllib.request.Request(url, headers={"User-Agent": "airhealth-build"})
        with urllib.request.urlopen(req, timeout=600) as r, open(path, "wb") as f:
            while chunk := r.read(1 << 20):
                f.write(chunk)
    print(f"{sha256(path)}  {path.name}")
    return path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()
