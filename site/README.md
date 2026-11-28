# airhealth.dev

The public site, served by Cloudflare Pages (project `airhealth`). The repository owns all of it; nothing
is copied from another site. Nothing is hand-copied from the model either: the city pages come from
`cities/`, the data files from `health/scripts/export_site_data.py`, and the landing page's numbers and
figures from `site/figures.py`.

| Path | From |
| --- | --- |
| `/` | `site/src/index.html` in `site/src/layout.html`, filled from `site/data/air.json` by `site/render.py` |
| `/start.txt` | `site/src/start.txt` (instructions for agents) |
| `/assets/airhealth.css` | `site/src/airhealth.css` (the one stylesheet: tokens, light and dark themes, header, footer, figures) |
| `/assets/` (fonts, images, film) | `site/static/assets/` |
| `/cities/`, `/cities/<slug>/` | `cities/index.html`, `cities/<slug>/index.html` (`python -m citypage.build --all`) |
| `/open-work/` | `docs/open-work.md`, rendered by `site/open_work_page.py` on every build |
| `/data/` | `health/out/site/` (`python health/scripts/export_site_data.py`) |

```
bash site/build.sh     # assemble site/dist/
bash site/deploy.sh    # build, then deploy to airhealth.dev (needs a Cloudflare token; see the script)
.venv/bin/python -m pytest site/tests -q
```

`site/dist/` is generated and git-ignored. A fresh clone builds the whole site with no model run: the
generated pieces below are committed.

## How the landing page is made

- `site/src/index.html` is the page's text. It speaks the small part of Liquid it needs (`{{ a.toll.pm25 }}`,
  `{% if %}`, `{% include fig/toll.html %}`); `site/render.py` (standard library) fills it in. A name that
  is not in the data is an error, so a number cannot silently drop out.
- `site/src/page.json` holds the title, description, the two copy-one-line commands and the grants link.
- `site/src/fig/*.html` are the eight figures (HTML fragments, positioned in percent so they reflow).
- `site/data/air.json` holds every number the prose quotes. **No result is typed in the template.**
  `site/tests/` checks that each number in the prose is in `air.json` and that changing `air.json` changes the page.
- Numbers that are not results (the standards of 40 and 5) and the hand-written notebook sections below
  "Run it" are plain text in the template.

## Changing the numbers

`fig/*.html`, `data/air.json`, `src/card.html` and `src/film.html` are all written by one script from the
model's canonical outputs:

```
PYTHONPATH=health:cities .venv/bin/python site/figures.py --from health/out/launch-19fb04c
```

`--from` holds `rank5000/` (`airhealth rank --write`), `sens2000/sensitivity_bengaluru.json` and
`stab/stability_bengaluru.json` (`health/scripts/stability_report.py`); the default is
`health/out/launch-19fb04c/`. The script also runs this checkout's `airhealth` for the terminal figure, the
toll and the fifty cities. Commit the files it writes. Regenerated from those inputs, the fragments are
byte-identical to the ones the dogl.uk build produced (`meta.model_commit` in `air.json` is this checkout's
head when it was run; `meta.rank_commit` is `--rank-commit`).

## The card and the film

`site/src/card.html` (1600x900 ladder, the og:image) and `site/src/film.html` (1280x720, 35 s) are render
pages written by `figures.py`. To turn them into files:

```
pip install playwright && playwright install chromium     # and ffmpeg on the PATH
python site/render_media.py card     # -> site/static/assets/img/air-apocalypse-ladder.png
python site/render_media.py film     # -> site/static/assets/media/air-apocalypse-film.mp4
python site/render_media.py all --out /tmp/media    # elsewhere, leaving the committed files alone
```

The card render is pixel-identical to the committed PNG. The film is one screenshot per frame at 30 fps
through `window.render(t)` and then `ffmpeg` (libx264, crf 26); re-rendering gives the same 1,057 frames
and the same pictures, at a smaller file than the committed one (different encoder settings).

Provenance of the committed files: `air-apocalypse-ladder.png` and `air-apocalypse-film.mp4` are the
ones from dogl.uk commit `99deec1` (branch `airhealth-launch`), made from the same inputs as `air.json`.
`img/diwali-week.png` is the Diwali analysis figure from the same commit (source: `diwali/` in this repo).

## Type, icons and third parties

Young Serif and Instrument Sans (SIL Open Font License, `assets/fonts/`, licences beside them; the same fonts
as the TTFs in `fonts/`, served as WOFF2). The icons (two currents of air and the fine particles they carry, in the site's colours) are drawn by `site/make_favicon.py`. Google Fonts
serves one Kannada glyph subset (the vertical word in the margin); nothing else is loaded from a third party.
The author link in the header and footer, and "find me" at the foot of the page, point to https://dogl.uk.
