"""report.rank_table / rank_csv_rows on hand-made rankings (nothing is scored)."""
from airhealth import rank, report
from airhealth.rank import Row, Table

C1, C2 = "c1", "c2"


def _row(mid, e, flags=(), scope="city", status="scored", gap="", reach="Bengaluru"):
    return Row(measure=mid, name=mid, kind="air", scope=scope, status=status, reason="",
               who_reaches="all", reach=reach, p_success=0.5, p_success_basis="",
               flags=tuple(flags), life_years={"median": 10.0, "p5": 5.0, "p95": 20.0},
               mean_life_years=10.0, expected_life_years=5.0, mean_cost_inr=1e7,
               cost_share_only_on_success=0.0, society_net_inr=None, ly_per_crore_if_works=e * 2,
               expected_ly_per_crore=e, rank=None, rank_if_works=None, study="apna_2015",
               trail={"evidence": [{"source": "S", "locator": "L", "url": "U", "key": "O"}],
                      "share_basis": {"1": "apna/annual", "2": "apna/annual"}},
               curve_gap=gap, comparable="partial_cost" not in flags)


def _ranking(rows_by_curve):
    tables = {c: Table(c, c.upper(), tuple(rank.rank_rows(rows))) for c, rows in rows_by_curve.items()}
    return rank.Ranking("Bengaluru", tables, rank.spread(tables),
                        {"map": "acag_total", "study": "apna_2015", "deaths": None, "discount": 0.03,
                         "n": 10, "seed": 0})


def test_partial_cost_shows_PC_beside_the_ratio_and_the_comparable_order():
    r = _ranking({C1: [_row("pc", 9.0, ("partial_cost",)), _row("a", 5.0), _row("b", 3.0)]})
    text = report.rank_table(r)
    line = next(x for x in text.splitlines() if x.split()[:2] == ["1", "pc"])
    assert "9.00 PC" in line
    assert "comparable" in text


def test_curve_gap_shows_a_dash_and_a_reason():
    r = _ranking({C1: [_row("a", 5.0), _row("kids", 1.0, gap="this curve does not cover the ages")],
                  C2: [_row("a", 5.0), _row("kids", 1.0)]})
    text = report.rank_table(r)
    assert "kids on c1: this curve does not cover the ages" in text
    grid = text.split("Curve c1")[0]
    assert report.DASH in grid


def test_regional_rows_sit_in_their_own_group_in_a_city_table():
    r = _ranking({C1: [_row("a", 5.0), _row("reg", 9.0, scope="region", reach="Bengaluru (region)")]})
    text = report.rank_table(r)
    assert "most of their benefit falls outside this city" in text
    assert text.index("Curve c1") < text.index("Regional measures")


def test_csv_rows_carry_sources_and_collapse_the_share_basis():
    r = _ranking({C1: [_row("a", 5.0)], C2: [_row("a", 5.0)]})
    rows = report.rank_csv_rows(r)
    assert len(rows) == 2 and list(rows[0]) == list(report.CSV_COLUMNS)
    assert rows[0]["evidence"] == "S | L | U | O"
    assert rows[0]["share_basis"] == "apna/annual: months 1-2"


def _stubble(mid="pes", scope="region"):
    from dataclasses import replace
    r = _row(mid, 2.0, ("receptor_fallback", "regional"), scope=scope, reach="region: 735 districts")
    return replace(r, trail={**r.trail, "region": {"receptor": "receptor_stubble.csv"}})


def test_stubble_gap_is_stated_at_the_top_when_a_row_stands_on_the_stubble_table():
    from airhealth import score
    r = _ranking({C1: [_row("a", 5.0), _stubble()]})
    text = report.rank_table(r)
    assert report.STUBBLE_NOTE in "\n".join(text.splitlines()[:3])
    assert "not scaled" in report.STUBBLE_NOTE and "undervalued" in report.STUBBLE_NOTE
    # the "about 14 times" is the receptor table's own fallback sentence, read at source
    assert "about 14 times smaller than Lan et al. 2022" in score.receptor_basis(
        "receptor_stubble.csv", key="fallback")
    assert "about 14 times smaller than Lan et al. 2022" in report.STUBBLE_NOTE
    # JSON rows (the dashboard's) give the same answer
    rows = rank.to_json(r)["tables"][C1]["rows"]
    assert report.stubble_note(rows) == report.STUBBLE_NOTE


def test_no_stubble_note_without_a_stubble_row():
    r = _ranking({C1: [_row("a", 5.0), _row("b", 3.0, ("receptor_fallback",))]})
    assert report.STUBBLE_NOTE not in report.rank_table(r)
    assert report.stubble_note([]) == ""


def test_regional_group_heading_says_the_cost_is_the_whole_reach():
    r = _ranking({C1: [_row("a", 5.0), _row("reg", 9.0, scope="region", reach="Bengaluru (region)")]})
    text = report.rank_table(r)
    head = text[text.index("Regional measures"):]
    assert "cost column is the whole reach's" in head.splitlines()[0]


def test_measures_listed_apart_on_any_curve_are_listed():
    # a measure not ranked on the second curve only must still be listed with its reason
    from dataclasses import replace
    late = replace(_row("late", 4.0), status="not_scored", reason="it was not run on the curve c2")
    r = _ranking({C1: [_row("a", 5.0), _row("late", 4.0)], C2: [_row("a", 5.0), late]})
    text = report.rank_table(r)
    assert "late (not_scored): it was not run on the curve c2" in text
