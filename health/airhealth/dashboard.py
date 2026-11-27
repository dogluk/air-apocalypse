"""A local page for looking at what airhealth computes.

  airhealth dashboard [--port 8765] [--no-open]

Serves one HTML page on 127.0.0.1 and answers its questions by calling the same functions as
the command line, so every number on the page is one the CLI would print. Nothing is cached
to disk and nothing leaves the machine. Standard library only.
"""
import json
import time
import webbrowser
from functools import cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import numpy as np

from . import baseline, causes, curves, exposure, paths, places, rank, report, score, simulate
from .impact import Change, steady_state
from .inputs import DEMOGRAPHIC, REGISTRY, Sources

PAGE = Path(__file__).with_name("dashboard.html")
SHAPES = paths.DATA / "districts.geojson"     # scripts/build_district_shapes.py
SHAPE_AGE = 60
OUT = paths.OUT / "rank"      # written by `airhealth rank --write`
DASH_N = 500          # draws for a city computed on demand (stated on the page)
STATE_MAPS = ("aqli", "acag_total", "gbd2019", "gbd2023")   # compared in the exposure table

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
             "gbd2023": "GBD 2023", "cpcb": "CPCB monitors"}



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
    if map_name in exposure.STATE_MAPS:
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
            except (KeyError, ValueError, curves.Unavailable):
                row[m] = None
        rows.append(row)
    cat = curves.catalogue().set_index("name")
    return dict(
        places=plist,
        maps=[dict(name=m, short=MAP_SHORT[m], label=exposure.LABELS[m], years=_years(m))
              for m in exposure.MAPS if exposure.available(m)],
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
        rank_cities=sorted(causes.known_cities()), rank_dash_n=DASH_N,
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


def _slug(name: str) -> str:
    return name.lower().replace(" ", "_")            # the file names `airhealth rank --write` makes


def _rank_place(q: dict) -> tuple[bool, str]:
    """(is India, the canonical city name or "India")."""
    raw = (q.get("place") or "").strip()
    if not raw:
        raise ValueError("choose a place: India or one of the fifty cities")
    if raw.lower() in ("india", "all india"):
        return True, "India"
    try:
        name = places.resolve(raw, kind="city").name
    except KeyError:
        raise ValueError(f"unknown city {raw!r}") from None
    if name not in causes.known_cities():
        raise ValueError(f"{name} is not one of the fifty cities the ranking covers")
    return False, name


def _stamp(path: Path) -> str:
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(path.stat().st_mtime))


def rank_legend() -> dict:
    return dict(flags=[dict(flag=f, code=c, text=report.FLAG_LEGEND.get(c, c))
                       for f, c in report.FLAG_CODES.items()],
                evidence=report.EVIDENCE_LEGEND)


def _city_now(name: str, curves_: list[str] | None, n: int) -> dict:
    """A city ranked now, from its own measures only. A regional measure's ratio needs its whole
    reach scored (about two minutes each), which a page load must not start: those rows show
    as not scored, with the way to get them."""
    scores = score.city(name, curves=curves_, n=n, seed=0, discount=simulate.DISCOUNT)
    wanted = {s.measure for s in scores if s.scope == "region" and s.status == "scored"}
    why = ("its whole reach is not scored on this page (about two minutes per measure); "
           f"`airhealth rank --write` writes it, or run `airhealth rank {name}`")
    context = rank._context(scores, None, map_name="acag_total", curves=curves_, n=n, seed=0,
                            discount=simulate.DISCOUNT, deaths=None)
    return rank.to_json(rank.from_scores(scores, name, context,
                                         regional_missing={m: why for m in wanted}))


def rank_result(q: dict, out: Path = OUT) -> dict:
    """The ranking of the measure library for India or a city, as `airhealth rank --json` prints
    it, plus where it came from. India, and any city asked for at its defaults, are read from
    the files `airhealth rank --write` leaves in `out`; a city asked for with its own draws or
    curves (or with no file) is computed now, on its own measures: regional measures are left
    unscored, not run."""
    india, name = _rank_place(q)
    slug = "india" if india else _slug(name)
    path = Path(out) / f"rank_{slug}.json"
    custom = bool(q.get("n") or q.get("curves"))
    if india or (path.exists() and not custom):
        if not path.exists():
            raise ValueError("run `airhealth rank --write` first; it takes several minutes")
        res = json.loads(path.read_text())
        res["source"] = f"file {path.name}, written {_stamp(path)}"
    else:
        names = [c.strip() for c in (q.get("curves") or "").split(",") if c.strip()] or None
        n = int(q.get("n") or DASH_N)
        if n < 10:
            raise ValueError("n must be at least 10 draws")
        res = _city_now(name, names, n)
        res["source"] = f"computed now, {n} draws"
    res["dash_n"] = DASH_N
    note = report.stubble_note(x for t in res.get("tables", {}).values() for x in t.get("rows", ()))
    res["notes"] = [note] if note else []
    res["legend"] = rank_legend()
    res["sensitivity_file"] = (Path(out) / f"sensitivity_{slug}.json").exists()
    return res


def sensitivity_result(q: dict, out: Path = OUT) -> dict:
    """What reorders the ranking, from the file `airhealth rank PLACE --sensitivity --write` left."""
    india, name = _rank_place(q)
    path = Path(out) / f"sensitivity_{'india' if india else _slug(name)}.json"
    if not path.exists():
        raise ValueError(f"no sensitivity file for {name}; run `airhealth rank "
                         f"{'' if india else name + ' '}--sensitivity --write` first")
    res = json.loads(path.read_text())
    res["source"] = f"file {path.name}, written {_stamp(path)}"
    return res


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
            elif url.path == "/api/rank":
                self._json(200, rank_result({k: v[0] for k, v in parse_qs(url.query).items()}))
            elif url.path == "/api/sensitivity":
                self._json(200, sensitivity_result({k: v[0] for k, v in parse_qs(url.query).items()}))
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
