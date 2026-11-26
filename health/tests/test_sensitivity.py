"""sensitivity.py: which uncertainties reorder the ranking."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from airhealth import measures, rank, score, sensitivity
from airhealth.cli import main
from airhealth.rank import Row
from airhealth.sensitivity import Setting, Swing

FIXTURES = Path(__file__).parent / "fixtures" / "library"
CURVE = "gemm_ncd_lri"
EMPTY = rank.Ranking(place="X", tables={}, spread={}, context={})


def _swing(rows, settings, top=5, base=EMPTY):
    """A Swing from (measure, curve, setting, rank, base_rank) tuples."""
    df = pd.DataFrame(rows, columns=["measure", "curve", "setting", "rank", "base_rank"])
    df = df.astype({"rank": float, "base_rank": float})
    df["rank_comparable"], df["base_rank_comparable"] = df["rank"], df["base_rank"]
    return Swing(place="X", base=base, settings=tuple(settings), ranks=df, top=top)


SEED = Setting("seed:1", "seed", "another seed")
MAP = Setting("map:aqli", "map", "aqli")
STUDY = Setting("study:x", "study", "study x")


def test_pin_fixes_every_dist_in_the_group():
    m = measures.load(FIXTURES / "air_dust.toml")
    lo = sensitivity.pin(m, "effect", 0.05)
    assert lo.targets[0].cut.kind == "fixed"
    assert lo.targets[0].cut.p5 == pytest.approx(float(m.targets[0].cut.ppf(0.05)))
    assert lo.cost == m.cost
    e = measures.load(FIXTURES / "exposure_purifier.toml")
    hi = sensitivity.pin(e, "effect", 0.95)
    assert hi.exposure.covered.p5 == pytest.approx(float(e.exposure.covered.ppf(0.95)))
    assert hi.exposure.covered.kind == "fixed" and hi.cost == e.cost
    r = measures.load(FIXTURES / "air_region.toml")
    c = sensitivity.pin(r, "cost", 0.05)
    assert c.cost.units.kind == "fixed" and c.region == r.region
    assert c.cost.units.p5 == pytest.approx(float(r.cost.units.ppf(0.05)))


def test_settings_for_a_city_name_its_other_studies():
    ids = {s.id for s in sensitivity.settings_for("Bengaluru", ["study"])}
    assert "study:cstep_bengaluru2022_cmb" in ids
    assert "study:apna_2015" not in ids                      # the default is not a setting


def test_settings_for_india_name_city_and_study():
    got = sensitivity.settings_for("India", ["study"], cities=["Bengaluru"])
    assert [(s.id, s.unit) for s in got] == [("study:Bengaluru:cstep_bengaluru2022_cmb",
                                              "study:Bengaluru")]


def test_settings_skip_fixed_ranges_and_other_cities():
    ids = {s.id for s in sensitivity.settings_for("Bengaluru", ["effect", "cost"], FIXTURES)}
    assert "effect:air_dust:low" in ids and "cost:air_region:high" in ids
    assert not any(i.startswith("cost:air_dust") for i in ids)      # its cost is a fixed number
    assert not any(":air_city:" in i for i in ids)                   # written for Delhi, Mumbai


def test_one_setting_reruns_only_what_it_changes(monkeypatch):
    calls, regions = [], []
    real_city, real_region = score.city, score.region

    def spy_city(city, ids=None, **kw):
        calls.append((city, None if ids is None else tuple(ids)))
        return real_city(city, ids, **kw)

    def spy_region(mid, **kw):
        regions.append((mid, kw["n"]))
        return real_region(mid, **kw)
    monkeypatch.setattr(score, "city", spy_city)
    monkeypatch.setattr(score, "region", spy_region)
    sensitivity._REACHES.clear()
    s = sensitivity.run("Bengaluru", inputs=["effect"], folder=FIXTURES, n=20, curves=[CURVE])
    assert calls[0] == ("Bengaluru", None)                           # the default, once
    pins = [x for x in s.settings]
    assert calls[1:] == [("Bengaluru", (x.id.split(":")[1],)) for x in pins]
    # one reach by default, one per pin of the regional measure (low, high), each once
    assert sorted(regions) == [("air_region", 20)] * 3


def test_india_effect_pin_runs_its_measure_in_each_city(monkeypatch):
    calls = []
    real_city = score.city

    def spy_city(city, ids=None, **kw):
        calls.append((city, None if ids is None else tuple(ids)))
        return real_city(city, ids, **kw)
    monkeypatch.setattr(score, "city", spy_city)
    s = sensitivity.run("India", inputs=["effect"], folder=FIXTURES, n=20, curves=[CURVE],
                        cities=["Bengaluru", "Mumbai"])
    assert s.place == rank.INDIA
    dust = [c for c in calls if c[1] == ("air_dust",)]
    assert len(dust) == 4                                             # low and high, two cities
    assert not [c for c in calls if c[1] == ("air_region",)]          # India uses its reach only


def test_ranks_are_never_averaged():
    s = sensitivity.run("Bengaluru", inputs=["map"], folder=FIXTURES, n=50,
                        curves=["gemm_ncd_lri", "aqli"])
    assert set(s.ranks.curve) == {"gemm_ncd_lri", "aqli"}
    assert "mean" not in " ".join(s.stability().columns)
    assert "mean" not in " ".join(s.ranks.columns)


def test_moves_within_seed_noise_are_not_flips():
    rows = [("a", CURVE, "seed:1", 2, 1), ("b", CURVE, "seed:1", 1, 2),
            ("a", CURVE, "map:aqli", 2, 1), ("b", CURVE, "map:aqli", 1, 2)]
    s = _swing(rows, [MAP, SEED])
    st = s.stability().set_index("measure")
    assert st.loc["a", "settings_moved"] == 0 and st.loc["a", "seed_delta"] == 1
    mv = s.movers().set_index("measure")
    assert mv.loc["a", "unit"] == "map" and bool(mv.loc["a", "within_noise"]) is True
    assert "seed" not in set(s.movers().unit)
    res = s.research()
    assert res.unit.iloc[-1] == "seed"                               # the noise floor, last


def test_a_move_larger_than_the_seed_is_a_move():
    rows = [("a", CURVE, "seed:1", 1, 1), ("b", CURVE, "seed:1", 2, 2), ("c", CURVE, "seed:1", 3, 3),
            ("a", CURVE, "map:aqli", 3, 1), ("b", CURVE, "map:aqli", 1, 2),
            ("c", CURVE, "map:aqli", 2, 3)]
    s = _swing(rows, [MAP, SEED])
    st = s.stability().set_index("measure")
    assert st.loc["a", "settings_moved"] == 1 and st.loc["a", "worst"] == 3
    mv = s.movers().set_index("measure")
    assert mv.loc["a", "delta"] == 2 and not mv.loc["a", "within_noise"]


def test_dropping_out_is_not_a_rank():
    rows = [("a", CURVE, "study:x", np.nan, 1), ("b", CURVE, "study:x", 1, 2),
            ("c", CURVE, "study:x", 2, 3),
            ("a", CURVE, "map:aqli", 1, 1), ("b", CURVE, "map:aqli", 3, 2),
            ("c", CURVE, "map:aqli", 2, 3)]
    s = _swing(rows, [STUDY, MAP])
    st = s.stability().set_index("measure")
    assert st.loc["a", "drops_out"] == 1 and st.loc["a", "worst"] == 1
    d = s.deltas().set_index(["measure", "setting"]).delta
    assert d[("b", "study:x")] == 0 and d[("c", "study:x")] == 0    # a's absence moves nobody
    mv = s.movers()
    assert "study" not in set(mv.unit)
    assert mv.set_index("measure").loc["b", "unit"] == "map"


def test_break_even_odds_formula():
    def row(mid, life, cost, p, s=0.0):
        w = life * rank.CRORE / cost
        e = p * life * rank.CRORE / (cost * (1 - s + s * p))
        return Row(measure=mid, name=mid, kind="air", scope="city", status="scored", reason="",
                   who_reaches="", reach="", p_success=p, p_success_basis="", flags=(),
                   life_years=None, mean_life_years=life, expected_life_years=p * life,
                   mean_cost_inr=cost, cost_share_only_on_success=s, society_net_inr=None,
                   ly_per_crore_if_works=w, expected_ly_per_crore=e, rank=None,
                   rank_if_works=None, study=None, trail={})
    rows = rank.rank_rows([row("a", 1000, 1e7, 0.5), row("b", 300, 1e7, 0.5),
                           row("c", 3000, 1e8, 0.1, s=0.5)])
    base = rank.Ranking("X", {CURVE: rank.Table(CURVE, CURVE, tuple(rows))}, {}, {})
    s = _swing([("a", CURVE, "map:aqli", 1, 1)], [MAP], base=base)
    be = s.break_even_odds().set_index("measure")
    # s = 0: p* = E_j * C / L, E in life-years per crore
    e_a = 0.5 * 1000
    assert be.loc["b", "odds_to_pass_above"] == pytest.approx(e_a * 1e7 / rank.CRORE / 300)
    assert be.loc["b", "pass_above"] == sensitivity.CANNOT              # 500/300 > 1
    assert be.loc["a", "odds_to_pass_above"] is None or pd.isna(be.loc["a", "odds_to_pass_above"])
    p = be.loc["a", "odds_to_fall_below"]
    b_row = next(x for x in rows if x.measure == "b")
    assert p * 1000 * rank.CRORE / 1e7 == pytest.approx(b_row.expected_ly_per_crore)
    # with s > 0, E at p* equals the neighbour's E
    c_row = next(x for x in rows if x.measure == "c")
    p = be.loc["c", "odds_to_pass_above"]
    assert 0 < p < 1
    e = p * 3000 * rank.CRORE / (1e8 * (1 - 0.5 + 0.5 * p))
    assert e == pytest.approx(b_row.expected_ly_per_crore)
    assert pd.isna(be.loc["c", "below"]) and c_row.rank == 3


def test_research_counts_curves_where_the_top_changes():
    cost = Setting("cost:a:low", "cost", "a's cost low")
    rows = []
    for c in ("c1", "c2", "c3"):
        for i, m in enumerate("abcdef", 1):
            r = i
            if c != "c3" and m in "ef":
                r = 11 - i                       # e (5) and f (6) swap on c1 and c2
            rows.append((m, c, "cost:a:low", r, i))
    s = _swing(rows, [cost])
    res = s.research().set_index("unit")
    assert res.loc["cost:a", "curves_top_changed"] == 2
    assert res.loc["cost:a", "curves"] == ["c1", "c2"]
    assert res.loc["cost:a", "enter"] == ["f"] and res.loc["cost:a", "leave"] == ["e"]


def test_monthly_curves_drop_regional_measures_and_say_so(tmp_path):
    for f in FIXTURES.iterdir():          # the fixture region pays for itself; give it a plain cost
        text = f.read_text()
        if f.name == "air_region.toml":
            text = text.replace("society_net_annual = -500\n", "").replace(
                ', "cost.society_net_annual"', "")
        (tmp_path / f.name).write_text(text)
    s = sensitivity.run("Bengaluru", inputs=["monthly_curves"], folder=tmp_path, n=20,
                        curves=[CURVE])
    st = s.stability().set_index("measure")
    assert st.loc["air_region", "drops_out"] == 1
    assert sensitivity.NOTE_MONTHLY in sensitivity.notes(s)
    assert "seed" not in set(s.research().unit)


def test_sensitivity_table_lists_the_research_first():
    s = sensitivity.run("Bengaluru", inputs=["odds", "seed"], folder=FIXTURES, n=30,
                        curves=[CURVE])
    from airhealth import report
    text = report.sensitivity_table(s)
    assert text.index("1. What would reorder") < text.index("2. Rank on each curve")
    assert "comparable" in text and "Break-even odds" in text
    for note in sensitivity.NOTES:
        assert note in text


def test_cli_sensitivity_json(capsys):
    main(["rank", "Bengaluru", "--library", str(FIXTURES), "--sensitivity", "--inputs", "map,odds",
          "--n", "50", "--curves", "gemm_ncd_lri", "--json", "--jobs", "1"])
    out = json.loads(capsys.readouterr().out)
    assert {"research", "stability", "movers", "break_even_odds", "notes"} <= set(out)
    assert {"research_comparable", "stability_comparable"} <= set(out)
    assert out["top"] == sensitivity.TOP and "parts" not in out["base"]


def test_cli_sensitivity_write(tmp_path, capsys):
    code = main(["rank", "Bengaluru", "--library", str(FIXTURES), "--sensitivity", "--inputs",
                 "odds", "--n", "20", "--curves", CURVE, "--jobs", "1", "--write", str(tmp_path)])
    assert code == 0
    assert (tmp_path / "sensitivity_bengaluru.json").exists()
    assert (tmp_path / "sensitivity_bengaluru.csv").read_text().startswith("place,measure")


def test_cli_rejects_sensitivity_flags_without_it(capsys):
    assert main(["rank", "Bengaluru", "--library", str(FIXTURES), "--top", "3"]) == 1
