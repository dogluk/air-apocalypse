#!/bin/bash
# Assemble the airhealth.dev site into site/dist/ from what the repo already holds.
#   /                 site/static/ (landing page, start.txt, figures), when present
#   /open-work/       rendered from docs/open-work.md by site/open_work_page.py
#   /cities/...       cities/index.html and cities/<slug>/index.html (generated pages)
#   /data/...         health/out/site/ (health/scripts/export_site_data.py), when present
# Without site/static/index.html, / redirects to /cities/.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
D="$ROOT/site/dist"
rm -rf "$D"; mkdir -p "$D/cities"
if [ -d "$ROOT/site/static" ]; then cp -R "$ROOT/site/static/." "$D/"; fi
cp "$ROOT/cities/index.html" "$D/cities/index.html"
for p in "$ROOT"/cities/*/index.html; do
  slug=$(basename "$(dirname "$p")")
  mkdir -p "$D/cities/$slug"; cp "$p" "$D/cities/$slug/index.html"
done
if [ -d "$ROOT/health/out/site" ]; then mkdir -p "$D/data"; cp -R "$ROOT/health/out/site/." "$D/data/"; fi
python3 "$ROOT/site/open_work_page.py" "$ROOT" "$D"   # /open-work/ from docs/open-work.md, every build
if [ ! -f "$D/index.html" ]; then printf '/ /cities/ 302\n' >> "$D/_redirects"; fi
echo "built $D: $(find "$D" -type f | wc -l | tr -d ' ') files"
