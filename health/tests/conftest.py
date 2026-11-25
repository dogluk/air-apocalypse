import pytest

from airhealth import paths


@pytest.fixture
def no_ihme(monkeypatch, tmp_path):
    """An empty data_local/, so the IHME curves and map are unavailable whatever is on this
    machine: tests of the open tier use it."""
    monkeypatch.setattr(paths, "LOCAL", tmp_path)


@pytest.fixture
def ihme_files():
    """Skip unless the IHME files are in data_local/ (they are never committed)."""
    from airhealth import ihme, ihme_curves
    needed = {*ihme_curves.files("gbd2023"), *ihme_curves.files("gbd2019"), ihme.EXPOSURE_2023}
    if ihme.missing(needed):
        pytest.skip("IHME files not in health/data_local/ (see IHME_DOWNLOADS.md)")


@pytest.fixture(autouse=True)
def fresh_month_shapes():
    """months.shape caches its profiles; a test that swaps the tables must not leak them."""
    from airhealth import months
    months.clear_cache()
    yield
    months.clear_cache()
