"""airhealth: health effects of air pollution in India, from the terminal.

  airhealth list curves|maps|places
  airhealth compare PLACE --to C2 [--from C1] [--map M] [--curves a,b] [--deaths srs|model]
  airhealth burden PLACE [--map M] [--counterfactual C] [--curves a,b] [--deaths srs|model]
  airhealth chart PLACE [PLACE ...] [--map M] [--age A] [--out FILE]
  airhealth run FILE [--map M] [--curves a,b] [--n N] [--seed S] [--charts DIR] [--deaths ...]

--deaths srs (the default) scales death counts to the SRS's own crude death rate for each
state, 2020-24; --deaths model leaves them as projected population × life-table death rates.
Life expectancy is the same either way. The last line of every result says which was used.
--json (anywhere) prints the same content as JSON. A city's map defaults to cpcb when the city
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
    run, unavailable = report.select_curves(names)
    if not run:
        raise ValueError("no curve can run: " + "; ".join(f"{n}: {why}" for n, why in unavailable.items()))
    return run, unavailable


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
    impacts = [steady_state(place, c, map_name, change, year=args.year, pm25_override=start,
                            deaths=args.deaths) for c in run]
    heading = f"{report.place_label(impacts[0])}: PM2.5 {level:.4g} → {args.to:g} µg/m³"
    _emit(args, impacts, unavailable, heading, notes)


def cmd_burden(args) -> None:
    place = _place(args)
    map_name = args.map or _default_map(place)
    run, unavailable = _curves(args.curves)
    impacts = [steady_state(place, c, map_name,
                            Change(to=c.floor if args.counterfactual is None else args.counterfactual),
                            year=args.year, deaths=args.deaths) for c in run]
    against = ("each curve's own floor" if args.counterfactual is None
               else f"{args.counterfactual:g} µg/m³")
    heading = f"{report.place_label(impacts[0])}: deaths attributable to PM2.5 above {against}"
    _emit(args, impacts, unavailable, heading, [])


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
    result = simulate.run(iv, map_name=map_name, curves=names, n=args.n, seed=args.seed,
                          deaths=args.deaths)
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


def _list_rows(what: str) -> list[dict]:
    sources = provenance.load_sources()
    if what == "curves":
        run, unavailable = report.select_curves()
        rows = [dict(name=c.name, available="yes", label=c.label, source=c.source) for c in run]
        cat = curves.catalogue().set_index("name")
        rows += [dict(name=n, available=f"no: {why}", label=cat.label[n], source=cat.source[n])
                 for n, why in unavailable.items()]
        return rows
    if what == "maps":
        rows = []
        for m in exposure.MAPS:
            s = sources[f"exposure_{m}.csv"]
            years = sorted(exposure._table(m).year.unique())
            span = f"{years[0]}-{years[-1]}" if len(years) > 1 else str(years[0])
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
    if args.what == "places":
        src = rows[0]["source"] if rows else ""
        for r in rows:
            print(f"{r['kind']:<9} {r['name']}" + (f", {r['state']}" if r["kind"] in ("city", "district") else ""))
        print(f"\n{len(rows)} places. Source: {src}")
        return
    for r in rows:
        extra = r.get("available") or r.get("years")
        print(f"{r['name']}  [{extra}]\n  {r['label']}\n  Source: {r['source']}\n")


def _parser() -> argparse.ArgumentParser:
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                        help="print the same content as JSON")
    p = argparse.ArgumentParser(prog="airhealth", parents=[shared],
                                description="Health effects of air pollution in India.")
    sub = p.add_subparsers(dest="command", required=True)

    def deaths_flag(s):
        s.add_argument("--deaths", choices=baseline.DEATHS_BASES, default="srs",
                       help="death counts scaled to the SRS crude death rate of each state, "
                       "2020-24 (srs, the default), or left as population × life-table rates (model)")

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

    ls = sub.add_parser("list", parents=[shared], help="curves, maps or places, each with its source")
    ls.add_argument("what", choices=("curves", "maps", "places"))
    ls.add_argument("--kind", choices=KINDS, help="places only: one kind")
    ls.set_defaults(func=cmd_list)
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    args.json = getattr(args, "json", False)
    try:
        args.func(args)
    except (KeyError, ValueError, curves.Unavailable, NotImplementedError) as e:
        msg = e.args[0] if e.args else str(e)
        print(f"airhealth: {msg}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
