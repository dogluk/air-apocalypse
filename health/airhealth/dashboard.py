"""A local page for looking at what airhealth computes.

  airhealth dashboard [--port 8765] [--no-open]

Serves one HTML page on 127.0.0.1 and answers its questions by calling the same functions as
the command line, so every number on the page is one the CLI would print. Nothing is cached
to disk and nothing leaves the machine. Standard library only.
"""
import json
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import numpy as np

from . import baseline, curves, exposure, places, report
from .impact import Change, steady_state

PAGE = Path(__file__).with_name("dashboard.html")
SHAPE_AGE = 60
STATE_MAPS = ("aqli", "acag_total", "gbd2019")

SHORT = {
    "loglinear_jaganathan": "Jaganathan 2024",
    "loglinear_vodonos": "Vodonos 2018",
    "aqli": "AQLI",
    "gemm_ncd_lri": "GEMM (Burnett 2018)",
    "loglinear_brown": "Brown 2022",
    "gbd2019": "GBD 2019",
    "gbd2023": "GBD 2023",
    "gemm_5cod": "GEMM five causes",
}
MAP_SHORT = {"aqli": "AQLI (dust removed)", "acag_total": "ACAG total", "gbd2019": "GBD 2019",
             "cpcb": "CPCB monitors"}

# Every input the result depends on, and how many sources can be switched between today.
# Kept here, next to the page that shows it, until the inputs get a registry of their own
# (docs/specs/2026-11-11-source-switches.md).
INPUTS = [
    dict(input="Risk curve", now="5 open curves", switch="--curves",
         pending="GBD 2019, GBD 2023, GEMM five causes (IHME files)"),
    dict(input="Exposure map", now="AQLI, ACAG total, GBD 2019 (states), CPCB (11 cities)",
         switch="--map", pending="GBD 2023 exposure (IHME file is downloaded)"),
    dict(input="Death count", now="SRS-scaled, or population × life-table rates",
         switch="--deaths", pending="UN WPP 2024; GBD deaths; per-year SRS rates"),
    dict(input="Counterfactual level", now="each curve's floor, or one number",
         switch="--counterfactual", pending=""),
    dict(input="Death rates by age (life table)", now="SRS abridged life tables 2020-24",
         switch="none", pending="UN WPP, GBD life tables"),
    dict(input="Population by age", now="Government projections 2011-2036",
         switch="none", pending="UN WPP, GBD population, Census 2011 for cities"),
    dict(input="Share of deaths from NCD + LRI", now="SRS cause of death 2021-23, all-India",
         switch="none", pending="GBD cause-specific deaths by state"),
    dict(input="Timing of benefit (intervention files)", now="immediate, or EPA 20-year lag",
         switch="lag = in the file", pending=""),
    dict(input="Exchange rate (intervention files)", now="World Bank annual rates",
         switch="none", pending=""),
]


def _default_map(place: places.Place) -> str:
    if place.kind == "city":
        try:
            exposure.cells(place, "cpcb")
            return "cpcb"
        except (KeyError, ValueError):
            pass
    return "aqli"


def meta() -> dict:
    run, unavailable = curves.select()
    conc = np.arange(0, 251, 2.5)
    shapes = {}
    for c in run:
        if c.kind == "relative_risk":
            shapes[c.name] = [round(float(v), 4) for v in np.atleast_1d(c.rr(conc, SHAPE_AGE))]
    t = places._table()
    plist = [dict(name=r.name, kind=r.kind, state=r.state or "") for r in t.itertuples()
             if r.kind in ("country", "state", "city")]
    rows = []
    for p in plist:
        if p["kind"] == "city":
            continue
        place = places.resolve(p["name"], kind=p["kind"])
        row = dict(place=p["name"], kind=p["kind"])
        for m in STATE_MAPS:
            try:
                row[m] = round(float(exposure.mean(place, m)), 1)
            except (KeyError, ValueError):
                row[m] = None
        rows.append(row)
    cat = curves.catalogue().set_index("name")
    return dict(
        places=plist,
        maps=[dict(name=m, short=MAP_SHORT[m], label=exposure.LABELS[m]) for m in exposure.MAPS],
        curves=[dict(name=c.name, short=SHORT.get(c.name, c.name), label=c.label, floor=c.floor,
                     min_age=c.min_age, kind=c.kind, source=c.source) for c in run],
        unavailable=[dict(name=n, short=SHORT.get(n, n), label=cat.label[n], why=why)
                     for n, why in unavailable.items()],
        shapes=dict(conc=[float(v) for v in conc], age=SHAPE_AGE, rr=shapes),
        exposure=rows, max_cohort=curves.MAX_COHORT_PM25, inputs=INPUTS,
        deaths_bases=list(baseline.DEATHS_BASES),
    )


def result(q: dict) -> dict:
    """What `airhealth compare` and `airhealth burden` would print for these settings."""
    place = places.resolve(q["place"], kind=q.get("kind") or None)
    map_name = q.get("map") or _default_map(place)
    deaths = q.get("deaths") or "srs"
    run, unavailable = curves.select()
    level = float(exposure.mean(place, map_name))
    start = float(q["from"]) if q.get("from") not in (None, "") else None
    to = float(q["to"])
    if to < 0 or (start is not None and start < 0):
        raise ValueError("a concentration cannot be below 0 µg/m³")
    origin = level if start is None else start
    notes = ([f"Starting level is the map's, {level:.1f} µg/m³"] if start is None else
             [f"Starting level set to {start:g} µg/m³; the map supplies population only"])
    change = Change(delta=to - origin)
    cmp_ = [steady_state(place, c, map_name, change, pm25_override=start, deaths=deaths)
            for c in run]
    bur = [steady_state(place, c, map_name, Change(to=c.floor), deaths=deaths) for c in run]
    label = report.place_label(cmp_[0])
    return dict(
        map=map_name, map_level=level, origin=origin, to=to,
        compare=report.to_json(cmp_, unavailable, f"{label}: PM2.5 {origin:.4g} → {to:g} µg/m³", notes),
        burden=report.to_json(bur, unavailable,
                              f"{label}: deaths attributable to PM2.5 above each curve's own floor", []),
    )


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # quiet
        pass

    def _send(self, code: int, body: bytes, kind: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj) -> None:
        self._send(code, json.dumps(obj, default=float, ensure_ascii=False).encode(),
                   "application/json; charset=utf-8")

    def do_GET(self):
        url = urlparse(self.path)
        try:
            if url.path in ("/", "/index.html"):
                self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
            elif url.path == "/api/meta":
                self._json(200, meta())
            elif url.path == "/api/result":
                self._json(200, result({k: v[0] for k, v in parse_qs(url.query).items()}))
            else:
                self._json(404, dict(error="not found"))
        except (KeyError, ValueError, curves.Unavailable, NotImplementedError) as e:
            self._json(400, dict(error=str(e.args[0] if e.args else e)))


def serve(port: int = 8765, open_browser: bool = True) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"airhealth dashboard at {url}  (Ctrl-C to stop)")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
