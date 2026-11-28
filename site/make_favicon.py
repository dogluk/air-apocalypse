"""Draw the airhealth icon: two currents of air and the fine particles they carry, in the site's own colours.

Writes site/static/favicon.svg, favicon.ico (16, 32, 48), assets/favicon-16x16.png,
assets/favicon-32x32.png, assets/apple-touch-icon.png (180) and assets/icon-512.png.
The SVG and the PNGs share one geometry (below), so they cannot drift apart.

    .venv/bin/python site/make_favicon.py
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

STATIC = Path(__file__).resolve().parent / "static"

# Colours from site/src/airhealth.css (dark theme): night, mist, and the sunset accent.
NIGHT = "#111F38"
MIST = "#A9C8EE"
SUNSET = "#F08A4B"

# Geometry in a 64 x 64 box.
SIZE = 64
RADIUS = 14            # corner radius of the tile
STROKE = 5.2           # width of each current
CURRENTS = (           # (y centre, amplitude, phase): two gentle waves across the tile
    (25.0, 3.6, 0.0),
    (40.0, 3.6, math.pi),
)
X0, X1 = 12.0, 52.0    # where each current starts and ends
PARTICLES = ((39.0, 12.5, 3.1), (47.5, 9.5, 2.1), (51.0, 16.0, 1.6))   # (x, y, radius): fine particles riding the air


def wave(y0: float, amp: float, phase: float, n: int = 48) -> list[tuple[float, float]]:
    """Points along one current: a single sine period from X0 to X1."""
    return [(X0 + (X1 - X0) * i / n, y0 + amp * math.sin(2 * math.pi * i / n + phase)) for i in range(n + 1)]


def svg() -> str:
    paths = []
    for y0, amp, phase in CURRENTS:
        pts = wave(y0, amp, phase)
        d = "M" + " L".join(f"{x:.2f} {y:.2f}" for x, y in pts)
        paths.append(f'<path d="{d}" fill="none" stroke="{MIST}" stroke-width="{STROKE}" '
                     f'stroke-linecap="round" stroke-linejoin="round"/>')
    dots = "".join(f'<circle cx="{px}" cy="{py}" r="{pr}" fill="{SUNSET}"/>' for px, py, pr in PARTICLES)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SIZE} {SIZE}">'
            f'<rect width="{SIZE}" height="{SIZE}" rx="{RADIUS}" fill="{NIGHT}"/>'
            + "".join(paths)
            + dots + "</svg>\n")


def raster(px_size: int) -> Image.Image:
    """The same drawing as svg(), rendered at 8x and scaled down for smooth edges."""
    ss = 8
    k = px_size * ss / SIZE
    img = Image.new("RGBA", (px_size * ss, px_size * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, px_size * ss - 1, px_size * ss - 1], radius=RADIUS * k, fill=NIGHT)
    w = max(1, round(STROKE * k))
    for y0, amp, phase in CURRENTS:
        pts = [(x * k, y * k) for x, y in wave(y0, amp, phase)]
        d.line(pts, fill=MIST, width=w, joint="curve")
        for x, y in (pts[0], pts[-1]):                      # round caps
            d.ellipse([x - w / 2, y - w / 2, x + w / 2, y + w / 2], fill=MIST)
    for px, py, pr in PARTICLES:
        d.ellipse([(px - pr) * k, (py - pr) * k, (px + pr) * k, (py + pr) * k], fill=SUNSET)
    return img.resize((px_size, px_size), Image.LANCZOS)


def main() -> None:
    (STATIC / "assets").mkdir(parents=True, exist_ok=True)
    (STATIC / "favicon.svg").write_text(svg())
    raster(16).save(STATIC / "assets" / "favicon-16x16.png")
    raster(32).save(STATIC / "assets" / "favicon-32x32.png")
    raster(180).save(STATIC / "assets" / "apple-touch-icon.png")
    raster(512).save(STATIC / "assets" / "icon-512.png")
    big = raster(256)
    big.save(STATIC / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    print("wrote", ", ".join(p.name for p in sorted(STATIC.rglob("*")) if "favicon" in p.name or "icon" in p.name))


if __name__ == "__main__":
    main()
