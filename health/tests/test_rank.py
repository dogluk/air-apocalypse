"""rank.py: ordering one place's scored measures per curve, and their spread across curves."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from airhealth import rank, score
from airhealth.rank import Row, Table

FIXTURES = Path(__file__).parent / "fixtures" / "library"
CURVE = "gemm_ncd_lri"


def _row(mid, e, w=None, status="scored", flags=()):
    """A Row with only the ranking fields set."""
    return Row(measure=mid, name=mid, kind="air", scope="city", status=status, reason="",
               who_reaches="", reach="", p_success=0.5, p_success_basis="", flags=tuple(flags),
               life_years=None, mean_life_years=None, expected_life_years=None,
               mean_cost_inr=None, cost_share_only_on_success=0.0, society_net_inr=None,
               ly_per_crore_if_works=e if w is None else w, expected_ly_per_crore=e,
               rank=None, rank_if_works=None, study=None, trail={},
               comparable="partial_cost" not in flags)


def test_rank_by_expected_per_crore():
    rows = rank.rank_rows([_row("a", 1.0), _row("b", 5.0), _row("c", 3.0)])
    assert [(r.measure, r.rank) for r in rows] == [("b", 1), ("c", 2), ("a", 3)]


def test_ties_break_by_id():
    assert [r.measure for r in rank.rank_rows([_row("z", 2.0), _row("a", 2.0)])] == ["a", "z"]


def test_unranked_statuses_are_listed_apart():
    rows = rank.rank_rows([_row("x", None, status="not_scored"), _row("a", 1.0),
                           _row("p", None, status="pays_for_itself"),
                           _row("n", None, status="no_cost")])
    assert [r.measure for r in rows] == ["a", "n", "p", "x"]
    assert [r.rank for r in rows] == [1, None, None, None]


def test_rank_if_works_is_its_own_order():
    rows = rank.rank_rows([_row("a", e=2.0, w=10.0), _row("b", e=3.0, w=4.0)])
    assert {r.measure: (r.rank, r.rank_if_works) for r in rows} == {"a": (2, 1), "b": (1, 2)}


def test_partial_cost_is_marked_beside_the_ratio():
    row = rank.rank_rows([_row("a", 1.0, flags=("partial_cost",))])[0]
    assert "partial_cost" in row.flags and row.rank == 1 and row.comparable is False


def test_partial_cost_can_be_set_aside():
    rows = rank.rank_rows([_row("pc", 9.0, flags=("partial_cost",)), _row("a", 5.0),
                           _row("b", 3.0)])
    got = {r.measure: (r.rank, r.rank_comparable) for r in rows}
    assert got == {"pc": (1, None), "a": (2, 1), "b": (3, 2)}


def test_spread_marks_curve_disagreement():
    t = {"c1": Table("c1", "", tuple(rank.rank_rows([_row(m, v) for m, v in zip("abcd", (4, 3, 2, 1))]))),
         "c2": Table("c2", "", tuple(rank.rank_rows([_row(m, v) for m, v in zip("abcd", (1, 2, 3, 4))])))}
    s = rank.spread(t)
    assert s["a"]["ranks"] == {"c1": 1, "c2": 4} and s["a"]["disagree"] is True
    assert s["b"]["disagree"] is False                     # 2 -> 3
    assert (s["a"]["best"], s["a"]["worst"]) == (1, 4)


def test_spread_skips_curves_where_unranked():
    t = {"c1": Table("c1", "", tuple(rank.rank_rows([_row("a", 1.0), _row("b", 2.0)]))),
         "c2": Table("c2", "", tuple(rank.rank_rows([_row("a", None, status="not_scored"),
                                                     _row("b", 2.0)])))}
    s = rank.spread(t)["a"]
    assert s["ranks"] == {"c1": 2, "c2": None} and s["unranked_on"] == ["c2"]
    assert (s["best"], s["worst"], s["disagree"]) == (2, 2, False)


def test_table_from_scores_uses_score_numbers():
    sc = score.city("Bengaluru", folder=FIXTURES, n=100, curves=[CURVE])
    t = rank.table(sc, CURVE)
    by = {r.measure: r for r in t.rows}
    s = next(x for x in sc if x.status == "scored" and x.scope == "city")
    summary = s.per_curve[CURVE]
    assert by[s.measure].expected_ly_per_crore == summary["expected_life_years_per_crore"]
    assert by[s.measure].mean_cost_inr == summary["cost_inr"]["mean"]
    assert by[s.measure].rank is not None
    ranked = [r.rank for r in t.rows if r.rank is not None]
    assert ranked == list(range(1, len(ranked) + 1))


def _fake(mid, status="scored", reason="", scope="region", curves=(CURVE,), ratio=None,
          flags=("regional",), net=None, trail=None, run=None, ly=100.0):
    per_curve = {c: {"life_years": {"median": ly, "p5": ly / 2, "p95": ly * 2, "mean": ly},
                     "expected_life_years": ly * 0.4, "cost_inr": {"mean": 5e7},
                     "life_years_per_crore_if_works": None if ratio is None else ratio * 2,
                     "expected_life_years_per_crore": ratio}
                 for c in curves}
    return score.Score(
        measure=mid, name=mid, kind="air", scope=scope, place="Bengaluru", study=None,
        status=status, reason=reason, who_reaches="", p_success=0.4, p_success_basis="",
        flags=tuple(score.Flag(f, f) for f in flags), pm25_change=None, per_curve=per_curve,
        trail=trail or {"region": {"districts": 412}}, run=run, society_net_inr=net)


def test_regional_row_in_a_city_table(monkeypatch):
    city_part = _fake("reg", ratio=None, ly=10.0)
    reach = _fake("reg", ratio=7.0, ly=1000.0)
    other = _fake("air", scope="city", ratio=3.0, flags=())
    t = rank.table([city_part, other], CURVE, regional={"reg": reach})
    row = next(r for r in t.rows if r.measure == "reg")
    assert row.expected_ly_per_crore == 7.0 and row.rank == 1 and "regional" in row.flags
    assert row.life_years["median"] == 10.0                    # the city's own part
    assert row.mean_cost_inr == 5e7 and "412 districts" in row.reach
    assert "whole reach" in row.reason

    outside = _fake("reg", status="not_scored",
                    reason="outside the source-receptor study's area: no row for X")
    row = rank.table([outside], CURVE, regional={}).rows[0]
    assert row.rank is None and row.reason.startswith("outside the source-receptor study's area")

    # city() computes the whole reach with score.region when not given
    calls = []
    monkeypatch.setattr(score, "city", lambda *a, **k: [city_part, other])
    monkeypatch.setattr(score, "region", lambda m, **k: calls.append((m, k)) or reach)
    r = rank.city("Bengaluru", n=10, curves=[CURVE], folder=FIXTURES)
    assert calls and calls[0][0] == "reg" and calls[0][1]["n"] == 10
    assert r.tables[CURVE].rows[0].measure == "reg"


def test_regional_without_its_reach_is_not_ranked():
    row = rank.table([_fake("reg")], CURVE).rows[0]
    assert row.rank is None and row.status == "not_scored" and "whole reach" in row.reason


def test_curve_that_misses_the_age_group_does_not_rank():
    def cr(min_age, label):
        return SimpleNamespace(curve=SimpleNamespace(min_age=min_age, label=label),
                               cost_share_only_on_success=0.0)
    run = SimpleNamespace(per_curve={"adult": cr(25, "from 25"), "all": cr(0, "all ages")})
    kids = _fake("kids", scope="city", ratio=0.0, ly=0.0, flags=("age_group",),
                 curves=("adult", "all"), trail={"exposure": {"ages": [5, 19]}}, run=run)
    other = _fake("air", scope="city", ratio=3.0, flags=(), curves=("adult", "all"))
    r = rank.from_scores([kids, other], "Bengaluru", {})
    adult = {x.measure: x for x in r.tables["adult"].rows}
    assert adult["kids"].rank is None and rank.CURVE_GAP in adult["kids"].curve_gap
    assert adult["kids"].expected_ly_per_crore is None and adult["air"].rank == 1
    assert r.spread["kids"]["unranked_on"] == ["adult"]
    assert {x.measure: x for x in r.tables["all"].rows}["kids"].rank is not None


def test_society_net_is_carried():
    sc = score.city("Bengaluru", ["pays"], folder=FIXTURES, n=50, curves=[CURVE])
    s = sc[0]
    assert s.status == "pays_for_itself" and s.society_net_inr < 0
    row = rank.table(sc, CURVE).rows[0]
    assert row.society_net_inr == s.society_net_inr and row.rank is None


def test_monthly_curves_not_yet():
    with pytest.raises(NotImplementedError):
        rank.city("Bengaluru", folder=FIXTURES, monthly_curves=True)


def test_to_json_is_json_safe():
    out = rank.to_json(rank.city("Bengaluru", folder=FIXTURES, n=100, curves=[CURVE]))
    json.dumps(out, allow_nan=False)
    assert out["assumptions"][-2:] == list(rank.RANK_ASSUMPTIONS)
    row = out["tables"][CURVE]["rows"][0]
    assert {"measure", "flags", "rank", "rank_comparable", "comparable", "curve_gap"} <= set(row)
    assert all(isinstance(f, str) for f in row["flags"])
    assert out["parts"] == {} and out["context"]["map"] == "acag_total"
