import numpy as np
import pytest

from airhealth import intervention, paths, prices, simulate

INTERVENTIONS = paths.HEALTH / "interventions"


def test_deflator_is_the_world_banks():
    d = prices.deflator()
    assert d[2025] == pytest.approx(107.097208955348, rel=1e-9)
    assert d[2024] == pytest.approx(106.064599179458, rel=1e-9)
    assert min(d) <= 2000 and max(d) == 2025


def test_2025_rupees_are_unchanged():
    assert prices.to_base_inr(1e7, "INR", 2025) == 1e7


def test_older_rupees_are_inflated():
    d = prices.deflator()
    assert prices.to_base_inr(100.0, "INR", 2010) == pytest.approx(100 * d[2025] / d[2010])


def test_dollars_use_their_own_years_rate_then_the_deflator():
    fx = intervention._inr_per_usd()
    d = prices.deflator()
    assert prices.to_base_inr(1.0, "USD", 2009) == pytest.approx(fx[2009] * d[2025] / d[2009])


def test_arrays_stay_arrays():
    out = prices.to_base_inr(np.array([1.0, 2.0]), "INR", 2020)
    assert isinstance(out, np.ndarray) and out[1] == pytest.approx(2 * out[0])


def test_usd_per_base_inr_is_one_over_the_2025_rate():
    assert prices.usd_per_base_inr() == pytest.approx(1 / intervention._inr_per_usd()[2025])


@pytest.mark.parametrize("currency", ["INR", "USD"])
def test_year_outside_the_tables_is_invalid(tmp_path, currency):
    text = ((INTERVENTIONS / "november_only_delhi.toml").read_text()
            .replace("year = 2025", "year = 1990").replace('currency = "INR"', f'currency = "{currency}"'))
    (tmp_path / "x.toml").write_text(text)
    with pytest.raises(intervention.Invalid, match=r"^cost\.year"):
        intervention.load(tmp_path / "x.toml")


def test_existing_files_cost_the_same():       # every shipped file is priced in 2025
    run = simulate.run(intervention.load(INTERVENTIONS / "delhi_100_to_80.toml"),
                       curves=["gemm_ncd_lri"], n=200)
    r = run.per_curve["gemm_ncd_lri"]
    assert np.allclose(r.cost_usd, r.cost_inr * prices.usd_per_base_inr())
