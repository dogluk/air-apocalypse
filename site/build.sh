#!/bin/bash
# Assemble the airhealth.dev site into site/dist/ from what the repo already holds.
#   /                 site/src/index.html in site/src/layout.html, filled from site/data/air.json (site/render.py)
#   /start.txt        site/src/start.txt
#   /assets/          site/static/assets/ (fonts, images, film) and site/src/airhealth.css
#   /open-work/       rendered from docs/open-work.md by site/open_work_page.py
#   /cities/...       cities/index.html and cities/<slug>/index.html (generated pages)
#   /data/...         health/out/site/ (health/scripts/export_site_data.py), when present
# Nothing here needs the model to have been run: site/data/air.json and site/src/fig/ are committed
# (site/figures.py regenerates them).
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
D="$ROOT/site/dist"
rm -rf "$D"; mkdir -p "$D/cities" "$D/assets"
cp -R "$ROOT/site/static/." "$D/"
cp "$ROOT/site/src/airhealth.css" "$D/assets/airhealth.css"
cp "$ROOT/site/src/start.txt" "$D/start.txt"
python3 "$ROOT/site/render.py" "$D"
cp "$ROOT/cities/index.html" "$D/cities/index.html"
for p in "$ROOT"/cities/*/index.html; do
  slug=$(basename "$(dirname "$p")")
  mkdir -p "$D/cities/$slug"; cp "$p" "$D/cities/$slug/index.html"
done
if [ -d "$ROOT/health/out/site" ]; then mkdir -p "$D/data"; cp -R "$ROOT/health/out/site/." "$D/data/"; fi
python3 "$ROOT/site/open_work_page.py" "$ROOT" "$D"   # /open-work/ from docs/open-work.md, every build
echo "built $D: $(find "$D" -type f | wc -l | tr -d ' ') files"
