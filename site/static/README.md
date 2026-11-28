# site/static: what is hand-kept here

`index.html`, `assets/` and `favicon.ico` are a **rendered snapshot** of
`dogluk@99deec1` (branch `airhealth-launch`) `air-apocalypse.markdown`, built with that repo's
Jekyll setup (`bundle exec jekyll build` in a copy, never in the worktree) and rewritten by
`site/port_landing.py`. `start.txt` is a verbatim copy of that repo's `air-apocalypse/start.txt`.
`/open-work/` is not here: `site/build.sh` renders it from `docs/open-work.md` on every build.

## The source of truth is still the dogl.uk repo

The landing's prose, figures and numbers are generated there (`_data/air.json`,
`_includes/air/fig-*.html` from `scripts/air-figures.py`) and the page text is
`air-apocalypse.markdown`. Editing `index.html` here is lost the next time the page is re-ported.
To refresh: build that repo's page, run `python3 site/port_landing.py <_site dir> site/static`,
review the diff, update the commit id above.

## What a port (so this repo owns the page) would need

1. A renderer for `air-apocalypse.markdown`: Liquid (`python-liquid`) plus kramdown-style Markdown
   (`markdown-it-py` or `mistune`), or a one-time static rewrite of the rendered HTML into a template.
   Liquid features used: `assign`, `include`, `if/else`, `size`/`|` filters, `site.data.air`, `page.*`
   front matter (`run_line`, `agent_line`, `grants_url`).
2. `_data/air.json` and the nine fragments `_includes/air/fig-*.html`, plus `scripts/air-figures.py`
   that writes them (it reads this repo's `health/out`); move the script here and run it from `build.sh`.
3. The hand-written `_includes/air/style.html` and `script.html` (copy-buttons), inlined in the page.
4. Theme: the page uses the dogl.uk CSS variables from `assets/css/dogluk.css` and `assets/main.css`
   (kept as copies here) and the Young Serif / Instrument Sans fonts; these would need to be cut
   down to what the page uses or kept as a vendored stylesheet.
5. The og:image card (`assets/img/air-apocalypse-ladder.png`) is a render made in the dogl.uk repo
   (`posts_assets/projects/air-apocalypse-ladder.png`); the script or tool that draws it must move too.
   `assets/img/diwali-week.png` comes from `diwali/` analysis output.
6. Page chrome (header, footer, head tags) is the minimal set written by `port_landing.py`.

Loaded from third parties: Google Fonts (a Kannada glyph subset, for the spine word only).
The favicon and apple-touch icons are the author's dog from dogl.uk.
