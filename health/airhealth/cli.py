"""airhealth: health effects of air pollution in India, from the terminal.

  airhealth list curves|maps|places|inputs
  airhealth compare PLACE --to C2 [--from C1] [--map M] [--curves a,b] [--use input=source]
  airhealth burden PLACE [--map M] [--counterfactual C] [--curves a,b] [--use input=source]
  airhealth chart PLACE [PLACE ...] [--map M] [--age A] [--out FILE]
  airhealth run FILE [--map M] [--curves a,b] [--n N] [--seed S] [--charts DIR] [--use ...]
  airhealth dashboard [--port 8765] [--no-open]     a local page over the same functions

--use input=source picks a source for population, death_rates or deaths (airhealth list
inputs); repeat it for several inputs, or give several sources (--use deaths=srs,unwpp) to get
a result for each and the range across them. --deaths X is shorthand for --use deaths=X. The
last line of every result names the source of each input.
--json (anywhere) prints the same content as JSON; --debug shows the traceback of an error. A city's map defaults to cpcb when the city
has ground-monitor data, everything else to aqli; the map used is named on the last line. An
intervention file's map defaults to cpcb when every place in it is such a city, else aqli.
"""
import argparse
import json
import sys

import numpy as np

from pathlib import Path

from . import baseline, curves, exposure, intervention, paths, places, provenance, report, simulate
from .impact import Change, steady_state
from .inputs import DEMOGRAPHIC, REGISTRY, Choice
from .places import KINDS

PLACES_SOURCE = "places.csv"


def _place(args) -> places.Place:
    return places.resolve(args.place, kind=args.kind)


def _default_map(place: places.Place) -> str:
    if place.kind == "city":
        try:
            exposure.cells(place, "cpcb")
            return "cpcb"
        except (KeyError, ValueError):
            pass
    return "aqli"


def _curves(spec: str | None):
    names = [n.strip() for n in spec.split(",") if n.strip()] if spec else None
    run, unavailable = curves.select(names)
    if not run:
        raise ValueError("no curve can run: " + "; ".join(f"{n}: {why}" for n, why in unavailable.items()))
    return run, unavailable


def _choice(args) -> Choice:
    return Choice.parse(getattr(args, "use", None), getattr(args, "deaths", None))


SPREAD = (("deaths_averted", "deaths/yr", "{:,.0f}"), ("life_years_averted", "life-years/yr", "{:,.0f}"))


def _across(results) -> dict:
    """Per curve, the lowest and highest of each count across the source combinations."""
    out = {}
    for name in [i.curve.name for i in results[0][0]]:
        rows = [next(i for i in impacts if i.curve.name == name) for impacts, _ in results]
        out[name] = {k: [min(getattr(r, a) for r in rows), max(getattr(r, a) for r in rows)]
                     for k, a in (("deaths_averted", "deaths_averted"),
                                  ("life_years_averted", "yll_averted"))}
    return out


def _emit_all(args, results, unavailable, notes):
    """One result as before; several (one per source combination) each in turn, then the
    range across them."""
    if len(results) == 1:
        impacts, heading = results[0]
        return _emit(args, impacts, unavailable, heading, notes)
    across = _across(results)
    if args.json:
        print(json.dumps(dict(results=[report.to_json(i, unavailable, h, notes) for i, h in results],
                              across_sources=across), indent=2, default=float, ensure_ascii=False))
        return
    for impacts, heading in results:
        print(report.table(impacts, unavailable, heading, notes) + "\n")
    for name, spans in across.items():
        print(f"Across sources, {name}: " + "; ".join(
            f"{fmt.format(spans[k][0])} to {fmt.format(spans[k][1])} {unit}"
            for k, unit, fmt in SPREAD))


def _emit(args, impacts, unavailable, heading, notes):
    if args.json:
        print(json.dumps(report.to_json(impacts, unavailable, heading, notes), indent=2,
                         default=float, ensure_ascii=False))
    else:
        print(report.table(impacts, unavailable, heading, notes))


def cmd_compare(args) -> None:
    place = _place(args)
    map_name = args.map or _default_map(place)
    run, unavailable = _curves(args.curves)
    for flag, value in (("--to", args.to), ("--from", args.from_)):
        if value is not None and value < 0:
            raise ValueError(f"{flag}: a concentration cannot be below 0 µg/m³, got {value:g}")
    notes = []
    if args.from_ is None:
        level = exposure.mean(place, map_name, args.year)
        start = None
        notes.append(f"Starting level is the map's, {level:.1f} µg/m³; every unit is moved by "
                     f"{args.to - level:+.1f} µg/m³")
    else:
        level = start = args.from_
        notes.append(f"Starting level set to {start:g} µg/m³ by --from; the map supplies population only")
    change = Change(delta=args.to - level)
    results = []
    for src in _choice(args).combinations():
        impacts = [steady_state(place, c, map_name, change, year=args.year, pm25_override=start,
                                deaths=src) for c in run]
        heading = f"{report.place_label(impacts[0])}: PM2.5 {level:.4g} → {args.to:g} µg/m³"
        results.append((impacts, heading))
    _emit_all(args, results, unavailable, notes)


def cmd_burden(args) -> None:
    place = _place(args)
    map_name = args.map or _default_map(place)
    run, unavailable = _curves(args.curves)
    against = ("each curve's own floor" if args.counterfactual is None
               else f"{args.counterfactual:g} µg/m³")
    results = []
    for src in _choice(args).combinations():
        impacts = [steady_state(place, c, map_name,
                                Change(to=c.floor if args.counterfactual is None
                                       else args.counterfactual),
                                year=args.year, deaths=src) for c in run]
        heading = f"{report.place_label(impacts[0])}: deaths attributable to PM2.5 above {against}"
        results.append((impacts, heading))
    _emit_all(args, results, unavailable, [])


def cmd_chart(args) -> None:
    marks, maps = {}, []
    for text in args.place:
        place = places.resolve(text, kind=args.kind)
        m = args.map or _default_map(place)
        cells = exposure.cells(place, m, args.year)
        marks[place.name] = float(np.average(cells.pm25, weights=cells.population))
        maps.append(f"{place.name} on {m} {cells.attrs['year']}")
    run, _ = _curves(args.curves)
    out = args.out or paths.CHARTS / f"curves_{places.norm(args.place[0]).replace(' ', '_')}.png"
    note = "Places marked at their population-weighted level: " + "; ".join(maps) + "."
    from . import charts  # matplotlib only when a chart is drawn
    path = charts.curves_chart(run, marks, out, age=args.age, note=note)
    if args.json:
        print(json.dumps(dict(path=str(path), marks=marks, maps=maps, age=args.age), indent=2))
    else:
        print(path)


def _intervention_file(text: str) -> Path:
    path = Path(text)
    if not path.exists() and (paths.HEALTH / path).exists():
        path = paths.HEALTH / path          # interventions/x.toml from anywhere
    if not path.exists():
        raise ValueError(f"no intervention file {text!r}")
    return path


def cmd_run(args) -> None:
    path = _intervention_file(args.file)
    iv = intervention.load(path)
    if args.map:
        map_name = args.map
    else:
        defaults = {_default_map(p) for p in iv.places}
        map_name = "cpcb" if defaults == {"cpcb"} else "aqli"
    names = [n.strip() for n in args.curves.split(",") if n.strip()] if args.curves else None
    combos = _choice(args).combinations(base=iv.sources)
    runs = [simulate.run(iv, map_name=map_name, curves=names, n=args.n, seed=args.seed,
                         deaths=src) for src in combos]
    if len(runs) > 1:
        return _emit_runs(args, runs)
    result = runs[0]
    written = []
    if args.charts:
        from . import charts  # matplotlib only when a chart is drawn
        folder = Path(args.charts)
        written = [charts.results_chart(result, folder / f"run_{path.stem}.png"),
                   charts.spread_chart(result, folder / f"spread_{path.stem}.png")]
    if args.json:
        out = report.run_json(result)
        out["charts"] = [str(w) for w in written]
        print(json.dumps(out, indent=2, default=float, ensure_ascii=False))
    else:
        if written:
            print("Charts: " + ", ".join(str(w) for w in written) + "\n")
        print(report.run_table(result))


def _emit_runs(args, runs) -> None:
    """Several runs of one intervention, one per source combination, and the range of the
    median life-years across them."""
    across = {}
    for name in runs[0].per_curve:
        meds = [float(np.median(r.per_curve[name].life_years)) for r in runs]
        across[name] = dict(life_years_median=[min(meds), max(meds)])
    if args.json:
        print(json.dumps(dict(results=[report.run_json(r) for r in runs], across_sources=across),
                         indent=2, default=float, ensure_ascii=False))
        return
    for r in runs:
        print(report.run_table(r) + "\n")
    for name, spans in across.items():
        lo, hi = spans["life_years_median"]
        print(f"Across sources, {name}: median life-years {lo:,.0f} to {hi:,.0f}")


def _list_rows(what: str) -> list[dict]:
    sources = provenance.load_sources()
    if what == "curves":
        run, unavailable = curves.select()
        rows = [dict(name=c.name, available="yes", label=c.label, source=c.source) for c in run]
        cat = curves.catalogue().set_index("name")
        rows += [dict(name=n, available=f"no: {why}", label=cat.label[n], source=cat.source[n])
                 for n, why in unavailable.items()]
        return rows
    if what == "inputs":
        return [dict(name=i.name, label=i.label, default=i.default, switch=i.switch,
                     sources=[dict(name=s.name, label=s.label, body=s.body) for s in i.sources],
                     pending=i.pending) for i in REGISTRY.values()]
    if what == "maps":
        rows = []
        for m in exposure.MAPS:
            s = sources[f"exposure_{m}.csv"]
            years = sorted(exposure._table(m).year.unique())
            span = f"{years[0]}-{years[-1]}" if len(years) > 1 else str(years[0])
            usable = [y for y in years if y in baseline.projection_years()]
            if usable != years:     # results need a population, and the projections start in 2011
                span += (f"; results {usable[0]}-{usable[-1]} (the population projections "
                         f"start in {usable[0]}); earlier years for charts only")
            rows.append(dict(name=m, years=span, label=exposure.LABELS[m],
                             source=f"{s['source']} {s['url']}"))
        return rows
    s = sources[PLACES_SOURCE]
    t = places._table()
    return [dict(kind=r.kind, name=r.name, state=r.state or "", source=f"places.csv: {s['url']}")
            for r in t.itertuples()]


def cmd_list(args) -> None:
    rows = _list_rows(args.what)
    if args.kind and args.what == "places":
        rows = [r for r in rows if r["kind"] == args.kind]
    if args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return
    if args.what == "inputs":
        for r in rows:
            print(f"{r['name']}: {r['label']}  [switch: {r['switch']}]")
            for s in r["sources"]:
                mark = " (default)" if s["name"] == r["default"] else ""
                print(f"  {s['name']}{mark}: {s['label']}" + (f"  [{s['body']}]" if s["body"] else ""))
            if not r["sources"]:
                print(f"  now: {r['default']}")
            if r["pending"]:
                print(f"  not yet wired: {r['pending']}")
        print("\nMixing bodies (e.g. UN population with SRS death rates) is allowed; the result "
              "says when it happens.")
        return
    if args.what == "places":
        src = rows[0]["source"] if rows else ""
        for r in rows:
            print(f"{r['kind']:<9} {r['name']}" + (f", {r['state']}" if r["kind"] in ("city", "district") else ""))
        print(f"\n{len(rows)} places. Source: {src}")
        return
    for r in rows:
        extra = r.get("available") or r.get("years")
        print(f"{r['name']}  [{extra}]\n  {r['label']}\n  Source: {r['source']}\n")


def cmd_dashboard(args) -> None:
    from . import dashboard  # http.server only when asked for
    dashboard.serve(port=args.port, open_browser=not args.no_open)


def _parser() -> argparse.ArgumentParser:
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                        help="print the same content as JSON")
    shared.add_argument("--debug", action="store_true", default=argparse.SUPPRESS,
                        help="on an error, show the full traceback instead of one line")
    p = argparse.ArgumentParser(prog="airhealth", parents=[shared],
                                description="Health effects of air pollution in India.")
    sub = p.add_subparsers(dest="command", required=True)

    def deaths_flag(s):
        s.add_argument("--use", action="append", metavar="INPUT=SOURCE[,SOURCE]",
                       help="source for an input: " + "; ".join(
                           f"{i.name}={'|'.join(x.name for x in i.sources)}" for i in DEMOGRAPHIC)
                       + " (airhealth list inputs). Repeatable; several sources give a result each")
        s.add_argument("--deaths", choices=baseline.DEATHS_BASES, default=None,
                       help="shorthand for --use deaths=…")

    def placed(name, help_):
        s = sub.add_parser(name, parents=[shared], help=help_)
        s.add_argument("place", help="India, a state, a district or a city (add ', State' if ambiguous)")
        s.add_argument("--kind", choices=KINDS, help="force the kind of place, e.g. --kind city for Delhi city")
        s.add_argument("--map", choices=exposure.MAPS, help="exposure map (default: cpcb for a city "
                       "that has it, otherwise aqli)")
        s.add_argument("--year", type=int, help="map year (default: the map's latest)")
        s.add_argument("--curves", help="comma-separated curve names (default: every curve)")
        deaths_flag(s)
        return s

    c = placed("compare", "deaths and life expectancy for a move from one concentration to another")
    c.add_argument("--from", dest="from_", type=float, metavar="C1",
                   help="starting level, µg/m³ (default: the map's level for the place)")
    c.add_argument("--to", type=float, required=True, metavar="C2", help="new level, µg/m³")
    c.set_defaults(func=cmd_compare)

    b = placed("burden", "deaths attributable to PM2.5 above a counterfactual")
    b.add_argument("--counterfactual", type=float, metavar="C",
                   help="µg/m³ (default: each curve's own floor)")
    b.set_defaults(func=cmd_burden)

    ch = sub.add_parser("chart", parents=[shared], help="draw the curves with places marked")
    ch.add_argument("place", nargs="+")
    ch.add_argument("--kind", choices=KINDS)
    ch.add_argument("--map", choices=exposure.MAPS)
    ch.add_argument("--year", type=int)
    ch.add_argument("--curves")
    ch.add_argument("--age", type=int, default=60)
    ch.add_argument("--out", help="PNG path (default: health/charts/curves_<place>.png)")
    ch.set_defaults(func=cmd_chart)

    r = sub.add_parser("run", parents=[shared], help="run an intervention file, with uncertainty")
    r.add_argument("file", help="intervention TOML file (see interventions/_template.toml)")
    r.add_argument("--map", choices=exposure.MAPS, help="exposure map (default: cpcb if every "
                   "place is a city that has it, otherwise aqli)")
    r.add_argument("--curves", help="comma-separated curve names (default: every curve)")
    r.add_argument("--n", type=int, default=5000, help="Monte Carlo draws (default 5000)")
    r.add_argument("--seed", type=int, default=0, help="random seed (default 0)")
    r.add_argument("--charts", metavar="DIR", help="also draw the results and spread charts here")
    deaths_flag(r)
    r.set_defaults(func=cmd_run)

    d = sub.add_parser("dashboard", parents=[shared], help="open a local page to explore results")
    d.add_argument("--port", type=int, default=8765)
    d.add_argument("--no-open", action="store_true", help="do not open a browser tab")
    d.set_defaults(func=cmd_dashboard)

    ls = sub.add_parser("list", parents=[shared], help="curves, maps or places, each with its source")
    ls.add_argument("what", choices=("curves", "maps", "places", "inputs"))
    ls.add_argument("--kind", choices=KINDS, help="places only: one kind")
    ls.set_defaults(func=cmd_list)
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    args.json = getattr(args, "json", False)
    try:
        args.func(args)
    except (KeyError, ValueError, curves.Unavailable, NotImplementedError) as e:
        if getattr(args, "debug", False):
            raise
        msg = e.args[0] if e.args else str(e)
        print(f"airhealth: {msg}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
