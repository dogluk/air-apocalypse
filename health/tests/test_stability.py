"""stability.py: is a city's top of the table the same on every curve, map and study?"""
import json
from pathlib import Path

from airhealth import rank, stability
from airhealth.rank import Row

FIXTURES = Path(__file__).parent / "fixtures" / "library"
CURVE = "gemm_ncd_lri"


def _row(mid, r, rc=None, comparable=True):
    return Row(measure=mid, name=mid, kind="air", scope="city", status="scored", reason="",
               who_reaches="", reach="", p_success=0.5, p_success_basis="", flags=(),
               life_years=None, mean_life_years=None, expected_life_years=None,
               mean_cost_inr=None, cost_share_only_on_success=0.0, society_net_inr=None,
               ly_per_crore_if_works=None, expected_ly_per_crore=None, rank=r, rank_if_works=r,
               study=None, trail={}, comparable=comparable, rank_comparable=rc)


def _ranking(tables: dict) -> rank.Ranking:
    t = {c: rank.Table(c, c, tuple(rows)) for c, rows in tables.items()}
    return rank.Ranking("X", t, rank.spread(t), {})


def test_top_check_same_and_different():
    same = _ranking({"c1": [_row("a", 1, 1), _row("b", 2, 2), _row("c", 3, 3), _row("d", 4, 4)],
                     "c2": [_row("a", 1, 1), _row("b", 2, 2), _row("c", 3, 3), _row("d", 4, 4)]})
    got = stability.top_check(same, 3)
    assert got["same_top"] and got["same_members"]
    assert got["top"] == {"c1": ["a", "b", "c"], "c2": ["a", "b", "c"]}
    swapped = _ranking({"c1": [_row("a", 1, 1), _row("b", 2, 2), _row("c", 3, 3), _row("d", 4, 4)],
                        "c2": [_row("b", 1, 1), _row("a", 2, 2), _row("c", 3, 3), _row("d", 4, 4)]})
    got = stability.top_check(swapped, 3)
    assert not got["same_top"] and got["same_members"]      # same three, another order
    other = _ranking({"c1": [_row("a", 1, 1), _row("b", 2, 2), _row("c", 3, 3), _row("d", 4, 4)],
                      "c2": [_row("a", 1, 1), _row("b", 2, 2), _row("d", 3, 3), _row("c", 4, 4)]})
    assert not stability.top_check(other, 3)["same_members"]


def test_top_check_comparable_skips_partial_costs():
    r = _ranking({"c1": [_row("p", 1, None, False), _row("a", 2, 1), _row("b", 3, 2)],
                  "c2": [_row("a", 1, 1), _row("p", 2, None, False), _row("b", 3, 2)]})
    got = stability.top_check(r, 2, comparable=True)
    assert got["top"] == {"c1": ["a", "b"], "c2": ["a", "b"]} and got["same_top"]
    assert not stability.top_check(r, 2)["same_top"]


def test_moves_are_worst_minus_best_never_an_average():
    r = _ranking({"c1": [_row("a", 1, 1), _row("b", 2, 2)],
                  "c2": [_row("b", 1, 1), _row("a", 2, 2)],
                  "c3": [_row("a", 1, 1), _row("b", 2, 2)]})
    mv = stability.moves(r)
    assert mv["a"] == {"best": 1, "worst": 2, "move": 1, "comparable_best": 1,
                       "comparable_worst": 2, "comparable_move": 1}


def test_report_runs_on_fixtures_and_writes(tmp_path):
    rep = stability.report("Bengaluru", maps=("acag_total", "cpcb"), n=20, curves=[CURVE],
                           folder=FIXTURES, top=3)
    combos = {(c["map"], c["study"]) for c in rep["combos"]}
    assert ("acag_total", "apna_2015") in combos and ("cpcb", "apna_2015") in combos
    assert ("acag_total", "cstep_bengaluru2022_cmb") in combos
    for c in rep["combos"]:
        assert {"same_top", "same_members", "top"} <= set(c["all"])
        assert {"same_top", "same_members", "top"} <= set(c["comparable"])
    assert rep["burden"]["map"] == "cpcb" and rep["burden"]["deaths"]
    lo, hi = rep["burden"]["lowest"], rep["burden"]["highest"]
    assert lo["deaths"] <= hi["deaths"]
    assert "mean" not in json.dumps(rep["burden"])
    text = stability.text(rep)
    assert "Top 3" in text and "cpcb" in text
    paths = stability.write(rep, tmp_path)
    assert {p.name for p in paths} == {"stability_bengaluru.json", "stability_bengaluru.txt"}
