import hashlib

import pandas as pd

from airhealth import paths


def test_apna_file_is_the_published_one():
    raw = (paths.DATA / "apna_source_apportionment.csv").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == "c3222ffb4c41f1c31d8a6da55c0ea800af3e7fdd7088f8059c17a86717381dcf"
    t = pd.read_csv(paths.DATA / "apna_source_apportionment.csv")
    assert len(t) == 49 and t.City.is_unique
    assert t.set_index("City").loc["Chennai", "I"] == "13.30%"      # outside share, lowest
    assert t.set_index("City").loc["Amritsar-Tarn Taran", "I"] == "52.70%"
