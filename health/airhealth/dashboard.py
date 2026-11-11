"""A local page for looking at what airhealth computes.

  airhealth dashboard [--port 8765] [--no-open]

Serves one HTML page on 127.0.0.1 and answers its questions by calling the same functions as
the command line, so every number on the page is one the CLI would print. Nothing is cached
to disk and nothing leaves the machine. Standard library only.
"""
import json
import webbrowser
from functools import cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import numpy as np

from . import baseline, curves, exposure, paths, places, report
from .impact import Change, steady_state
from .inputs import DEMOGRAPHIC, REGISTRY, Sources

PAGE = Path(__file__).with_name("dashboard.html")
SHAPES = paths.DATA / "districts.geojson"     # scripts/build_district_shapes.py
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



def _default_map(place: places.Place) -> str:
    if place.kind == "city":
        try:
            exposure.cells(place, "cpcb")
            return "cpcb"
        except (KeyError, ValueError):
            pass
    return "aqli"


@cache
def _districts() -> list[dict]:
    """Properties of every drawn district: state, unit (ACAG's name), aqli_unit."""
    return [f["properties"] for f in json.loads(SHAPES.read_text())["features"]
            if f["properties"]["layer"] == "district"]


def _key(state: str, unit: str) -> str:
    return f"{state}|{unit}"


def district_values(map_name: str, year: int) -> dict[str, float]:
    """PM2.5 for each drawn district on the map: its own value (ACAG), its AQLI district's
    (AQLI, older boundaries; absent when none matches), its state's (GBD 2019), or its
    city's (CPCB, the city's districts only)."""
    t = exposure._table(map_name)
    t = t[t.year == year]
    if map_name == "gbd2019":
        by_state = dict(zip(t.state, t.pm25))
        return {_key(d["state"], d["unit"]): float(by_state[d["state"]])
                for d in _districts() if d["state"] in by_state}
    if map_name == "cpcb":
        out = {}
        for city, pm25 in zip(t.city, t.pm25):
            c = exposure._cities().loc[city]
            out.update({_key(c.state, u): float(pm25) for u in c.acag_units.split(";")})
        return out
    by_unit = {(s, u): float(v) for s, u, v in zip(t.state, t.unit, t.pm25)}
    col = "aqli_unit" if map_name == "aqli" else "unit"
    return {_key(d["state"], d["unit"]): by_unit[d["state"], d[col]]
            for d in _districts() if (d["state"], d[col]) in by_unit}


def selected_districts(place: places.Place) -> list[str]:
    """The drawn districts that make up the place; empty for India (nothing singled out)."""
    if place.kind == "state":
        return [_key(d["state"], d["unit"]) for d in _districts() if d["state"] == place.name]
    if place.kind == "city":
        c = exposure._cities().loc[place.name]
        return [_key(c.state, u) for u in c.acag_units.split(";")]
    return []


def _years(map_name: str) -> list[int]:
    """The map's years that results can run for (the population projections start in 2011)."""
    usable = baseline.projection_years()
    return [int(y) for y in sorted(exposure._table(map_name).year.unique()) if y in usable]


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
        maps=[dict(name=m, short=MAP_SHORT[m], label=exposure.LABELS[m], years=_years(m))
              for m in exposure.MAPS],
        curves=[dict(name=c.name, short=SHORT.get(c.name, c.name), label=c.label, floor=c.floor,
                     min_age=c.min_age, kind=c.kind, source=c.source) for c in run],
        unavailable=[dict(name=n, short=SHORT.get(n, n), label=cat.label[n], why=why)
                     for n, why in unavailable.items()],
        shapes=dict(conc=[float(v) for v in conc], age=SHAPE_AGE, rr=shapes),
        exposure=rows, max_cohort=curves.MAX_COHORT_PM25,
        inputs=[dict(name=i.name, label=i.label, default=i.default, switch=i.switch,
                     pending=i.pending, demographic=i in DEMOGRAPHIC,
                     sources=[dict(name=x.name, label=x.label, body=x.body) for x in i.sources])
                for i in REGISTRY.values()],
        deaths_bases=list(baseline.DEATHS_BASES),
    )


def result(q: dict) -> dict:
    """What `airhealth compare` and `airhealth burden` would print for these settings."""
    place = places.resolve(q["place"], kind=q.get("kind") or None)
    map_name = q.get("map") or _default_map(place)
    deaths = Sources(**{i.name: q.get(i.name) or i.default for i in DEMOGRAPHIC})
    year = int(q["year"]) if q.get("year") not in (None, "") else None
    run, unavailable = curves.select()
    level = float(exposure.mean(place, map_name, year))
    start = float(q["from"]) if q.get("from") not in (None, "") else None
    to = float(q["to"])
    if to < 0 or (start is not None and start < 0):
        raise ValueError("a concentration cannot be below 0 µg/m³")
    origin = level if start is None else start
    notes = ([f"Starting level is the map's, {level:.1f} µg/m³"] if start is None else
             [f"Starting level set to {start:g} µg/m³; the map supplies population only"])
    change = Change(delta=to - origin)
    cmp_ = [steady_state(place, c, map_name, change, year=year, pm25_override=start,
                         deaths=deaths) for c in run]
    bur = [steady_state(place, c, map_name, Change(to=c.floor), year=year, deaths=deaths)
           for c in run]
    label = report.place_label(cmp_[0])
    return dict(
        map=map_name, year=cmp_[0].year, map_level=level, origin=origin, to=to,
        districts=district_values(map_name, cmp_[0].year), selected=selected_districts(place),
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
            elif url.path == "/api/shapes":
                self._send(200, SHAPES.read_bytes(), "application/geo+json")
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
