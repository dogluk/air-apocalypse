# airhealth.dev

The public site, served by Cloudflare Pages (project `airhealth`). Nothing here is hand-copied
from the model: the city pages come from `cities/`, the data files from
`health/scripts/export_site_data.py`.

| Path | From |
| --- | --- |
| `/` | `site/static/index.html` (landing page) |
| `/start.txt` | `site/static/start.txt` (instructions for agents) |
| `/cities/`, `/cities/<slug>/` | `cities/index.html`, `cities/<slug>/index.html` (`python -m citypage.build --all`) |
| `/data/` | `health/out/site/` (`python health/scripts/export_site_data.py`) |

```
bash site/build.sh     # assemble site/dist/
bash site/deploy.sh    # build, then deploy to airhealth.dev (needs a Cloudflare token; see the script)
```

`site/dist/` is generated and git-ignored.
