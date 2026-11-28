import pandas as pd

from airhealth import paths


def test_targets_table():
    t = pd.read_csv(paths.DATA / "targets.csv").set_index("target")
    assert t.loc["india_naaqs_annual", "pm25_annual"] == 40     # as read at source
    assert t.loc["who_aqg_2021_annual", "pm25_annual"] == 5
    assert t.locator.str.len().min() > 10
