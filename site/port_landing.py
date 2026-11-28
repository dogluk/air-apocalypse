#!/usr/bin/env python3
"""One-off port: turn the rendered dogl.uk /air-apocalypse/ page into site/static/ for airhealth.dev.

Usage: port_landing.py <rendered dogl.uk _site dir> <site/static dir>
Rewrites the head (canonical, og, twitter, JSON-LD), replaces the dogl.uk header/footer with a
minimal one, points assets at /assets/, links open work at /open-work/, copies the assets the
page loads. Not run by build.sh: site/static/ is the committed snapshot (see site/static/README.md).
"""
import re, shutil, sys
from pathlib import Path

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
s = (src / "air-apocalypse/index.html").read_text()
H = "https://airhealth.dev"
OG = "/assets/img/air-apocalypse-ladder.png"

s = s.replace("https://dogl.uk/air-apocalypse/", H + "/")
s = s.replace("https://dogl.uk/posts_assets/projects/air-apocalypse-ladder.png", H + OG)
# generic head: drop the personal-site keywords, Person JSON-LD, feed, Font Awesome
s = re.sub(r'\s*<!-- Primary Meta Tags -->\s*<meta name="keywords"[^>]*>', "", s)
s = re.sub(r'<!-- JSON-LD Person Schema -->\s*<script type="application/ld\+json">.*?</script>', "", s, flags=re.S)
s = re.sub(r'<link type="application/atom\+xml"[^>]*>', "", s)
s = re.sub(r'<link rel="stylesheet" href="https://cdnjs[^>]*>', "", s)
s = s.replace('<meta name="theme-color"', '<meta name="theme-color"', 1)
s = re.sub(r'(<meta property="og:title" content=")air apocalypse(")', r'\1air apocalypse: an open model of India’s air\2', s)
s = s.replace("<title>air apocalypse | Akash Kulgod</title>", "<title>air apocalypse | airhealth</title>")
s = re.sub(r'\?v=\d+', "", s)
s = s.replace('"/posts_assets/projects/diwali-week.png"', '"/assets/img/diwali-week.png"')
s = s.replace('<a href="/about/">find me</a>', '<a href="https://dogl.uk/about/">find me</a>')
s = s.replace('href="https://github.com/dogluk/air-apocalypse/blob/main/docs/open-work.md"', 'href="/open-work/"')

header_nav = ('<div class="trigger"><a class="page-link" href="/cities/">cities</a>'
              '<a class="page-link" href="/open-work/">open work</a>'
              '<a class="page-link" href="/start.txt">for agents</a>'
              '<a class="page-link" href="https://github.com/dogluk/air-apocalypse">code</a>'
              '<a class="page-link" href="https://dogl.uk" rel="author">Akash Kulgod</a></div>')
# header: brand + nav links
s = re.sub(r'<a class="site-brand".*?</a><nav', '<a class="site-brand" href="/" aria-label="airhealth, home"><span class="site-title">airhealth</span></a><nav', s, count=1, flags=re.S)
s = re.sub(r'<div class="trigger">.*?</div>\s*(?=<button class="theme-toggle")', header_nav + "\n        ", s, count=1, flags=re.S)
# footer
footer = ('<footer class="site-footer"><div class="wrapper">'
          '<nav class="footer-nav" aria-label="Site"><a href="/cities/">cities</a><a href="/open-work/">open work</a>'
          '<a href="/start.txt">for agents</a><a href="https://github.com/dogluk/air-apocalypse">code</a></nav>'
          '<p>An open model by <a href="https://dogl.uk" rel="author">Akash Kulgod</a>. Code MIT, derived data ODbL, figures and writing CC BY 4.0.</p>'
          '<p class="footer-credit">Type: <a href="https://github.com/noirblancrouge/YoungSerif">Young Serif</a> and '
          '<a href="https://github.com/Instrument/instrument-sans">Instrument Sans</a>.</p>'
          '</div></footer>')
s = re.sub(r'<footer class="site-footer h-card">.*?</footer>', footer, s, count=1, flags=re.S)

prov = ("<!-- Rendered snapshot of dogluk@99deec1 air-apocalypse.markdown (Jekyll build), ported by site/port_landing.py.\n"
        "     The source of truth for this page still lives in the dogl.uk repo; see site/static/README.md. -->\n")
s = s.replace("<!DOCTYPE html>\n", "<!DOCTYPE html>\n" + prov, 1)

(dst / "assets/css").mkdir(parents=True, exist_ok=True)
(dst / "assets/fonts").mkdir(parents=True, exist_ok=True)
(dst / "assets/img").mkdir(parents=True, exist_ok=True)
(dst / "index.html").write_text(s)
shutil.copy(src / "air-apocalypse/start.txt", dst / "start.txt")
for f in ["assets/main.css", "assets/css/dogluk.css", "assets/favicon-32x32.png", "assets/favicon-16x16.png",
          "assets/apple-touch-icon.png", "assets/fonts/youngserif.woff2", "assets/fonts/instrumentsans-normal.woff2",
          "assets/fonts/instrumentsans-italic.woff2", "assets/fonts/OFL-YoungSerif.txt", "assets/fonts/OFL-InstrumentSans.txt", "favicon.ico"]:
    if (src / f).exists():
        shutil.copy(src / f, dst / f)
shutil.copy(src / "posts_assets/projects/air-apocalypse-ladder.png", dst / "assets/img/air-apocalypse-ladder.png")
shutil.copy(src / "posts_assets/projects/diwali-week.png", dst / "assets/img/diwali-week.png")
