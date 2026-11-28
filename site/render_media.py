#!/usr/bin/env python3
"""Render the share card (PNG) and the launch film (MP4) from site/src/card.html and site/src/film.html.

Those two pages are written by site/figures.py from the same numbers as the landing page, so a new
model run changes the card and the film too. This script is the second step: it needs Playwright
(`pip install playwright`, `playwright install chromium`) and ffmpeg on the PATH.

    python site/render_media.py card            # -> site/static/assets/img/air-apocalypse-ladder.png (1600x900)
    python site/render_media.py film            # -> site/static/assets/media/air-apocalypse-film.mp4 (1280x720, 30 fps)
    python site/render_media.py all --out /tmp/media    # write somewhere else, leave the committed files alone
    python site/render_media.py card --chrome /path/to/chrome   # use an installed browser

The film page draws itself at any time t from `window.render(t)` (opened as film.html#frame, which
stops its own clock). One screenshot per frame at t = n / 30, clamped to its length, then ffmpeg.
Both pages load /assets/airhealth.css and /assets/fonts/, so they are served from a temporary
folder laid out like the built site; nothing is fetched from the network.
"""
import argparse
import functools
import http.server
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC, STATIC = HERE / "src", HERE / "static"
FPS = 30


def serve(root: Path):
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    handler = functools.partial(Quiet, directory=str(root))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=["card", "film", "all"])
    ap.add_argument("--out", type=Path, help="write the files here instead of over the committed ones")
    ap.add_argument("--chrome", help="path to a Chrome/Chromium binary (default: Playwright's own)")
    a = ap.parse_args()
    from playwright.sync_api import sync_playwright

    png = (a.out or STATIC / "assets/img") / "air-apocalypse-ladder.png"
    mp4 = (a.out or STATIC / "assets/media") / "air-apocalypse-film.mp4"
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "site"
        (root / "assets").mkdir(parents=True)
        shutil.copy(SRC / "airhealth.css", root / "assets/airhealth.css")
        shutil.copytree(STATIC / "assets/fonts", root / "assets/fonts")
        for page in ("card.html", "film.html"):
            shutil.copy(SRC / page, root / page)
        httpd, base = serve(root)
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=a.chrome) if a.chrome else p.chromium.launch()
            if a.what in ("card", "all"):
                page = browser.new_page(viewport={"width": 1600, "height": 900})
                page.goto(f"{base}/card.html")
                page.evaluate("document.fonts.ready")
                png.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(png))
                print("wrote", png)
            if a.what in ("film", "all"):
                page = browser.new_page(viewport={"width": 1280, "height": 720})
                page.goto(f"{base}/film.html#frame")
                page.evaluate("document.fonts.ready")
                dur = float(re.search(r"var DUR = ([0-9.]+)", (SRC / "film.html").read_text()).group(1))
                frames = Path(tmp) / "frames"
                frames.mkdir()
                n = int(round(dur * FPS)) + 1
                for i in range(n):
                    page.evaluate("t => window.render(t)", min(i / FPS, dur))
                    page.screenshot(path=str(frames / f"{i:05d}.png"))
                mp4.parent.mkdir(parents=True, exist_ok=True)
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i",
                                str(frames / "%05d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "26",
                                "-movflags", "+faststart", str(mp4)], check=True)
                print("wrote", mp4, f"({n} frames)")
            browser.close()
        httpd.shutdown()


if __name__ == "__main__":
    sys.exit(main())
