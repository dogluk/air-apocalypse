import subprocess

from airhealth import paths, provenance


def test_every_data_file_has_a_source():
    sources = provenance.load_sources()
    for f in paths.DATA.glob("**/*.csv"):
        assert f.relative_to(paths.DATA).as_posix() in sources
    assert provenance.check() == []


def test_entry_missing_field_is_reported(tmp_path):
    (tmp_path / "x.csv").write_text("a\n1\n")
    (tmp_path / "sources.toml").write_text(
        '["x.csv"]\nsource = "s"\nurl = "u"\nlocator = "l"\n'
        'retrieved = "2026-11-10"\nmethod = "downloaded"\n'
    )
    problems = provenance.check(tmp_path)
    assert any("x.csv" in p and "licence" in p for p in problems)


def test_local_folder_is_ignored():
    r = subprocess.run(
        ["git", "check-ignore", "health/data_local/x.csv"],
        cwd=paths.REPO, capture_output=True,
    )
    assert r.returncode == 0
