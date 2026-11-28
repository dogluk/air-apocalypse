import pytest

from airhealth import paths


@pytest.fixture
def no_ihme(monkeypatch, tmp_path):
    """An empty data_local/, so the IHME curves and map are unavailable whatever is on this
    machine: tests of the open tier use it."""
    monkeypatch.setattr(paths, "LOCAL", tmp_path)
