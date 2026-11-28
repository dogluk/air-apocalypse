"""scripts/open_work.py: the registry of open work (health/open_work.toml) is checked, then written
as docs/open-work.md and docs/open-work.json, ordered by how much each item could move the
ranking. Nothing here runs the model: the tests read a small fixture sensitivity file."""
import json
import re
import shutil
import sys

import pytest

from airhealth import paths

sys.path.insert(0, str(paths.HEALTH / "scripts"))
import open_work as ow  # noqa: E402

REPO = paths.REPO
LIB = REPO / "health" / "interventions" / "library"


# ---- a tiny repository the validation tests can break one thing at a time ---------------------

@pytest.fixture
def repo(tmp_path):
    (tmp_path / "health/data").mkdir(parents=True)
    (tmp_path / "health/interventions/library").mkdir(parents=True)
    (tmp_path / "health/data/causes.csv").write_text("city,study\nX,study_a\nY,study_b\n")
    (tmp_path / "health/data/receptor_r.csv").write_text("district,state,delta_pm25_full\n")
    (tmp_path / "health/data/exposure_m.csv").write_text("x\n")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/note.md").write_text("x")
    for m, extra in (("m_air", ""), ("m_other", "")):
        (tmp_path / f"health/interventions/library/{m}.toml").write_text("name = 'x'\n" + extra)
    (tmp_path / "health/interventions/library/m_reg.toml").write_text(
        "name = 'x'\n[region]\nreceptor = 'receptor_r.csv'\n")
    return tmp_path


def item(id="OW-001", **kw):
    base = dict(id=id, title="T", kind="desk lookup", size="one sitting", weakness="S",
                question="What?", read_at="somewhere", lands_in=["docs/note.md"],
                lands_field="a field", check="a test", affects=["measure:m_air"],
                origin=["test"])
    base.update(kw)
    return base


def test_valid_registry_has_no_problems(repo):
    items = [item("OW-001"), item("OW-002", affects=["study:study_a"]),
             item("OW-003", affects=["table:receptor_r.csv"], lands_in=["docs"])]
    assert ow.validate(items, repo) == []


def test_duplicate_id_is_refused(repo):
    problems = ow.validate([item("OW-001"), item("OW-001")], repo)
    assert any("duplicate id OW-001" in p for p in problems)


def test_unknown_measure_study_and_table_are_refused(repo):
    for bad in ("measure:nope", "study:nope", "table:nope.csv", "thing:m_air", "m_air"):
        problems = ow.validate([item(affects=[bad])], repo)
        assert problems, bad
        assert any(bad in p for p in problems), bad


def test_missing_landing_file_is_refused(repo):
    problems = ow.validate([item(lands_in=["health/data/not_there.csv"])], repo)
    assert any("not_there.csv" in p and "does not exist" in p for p in problems)


def test_bad_fields_are_refused(repo):
    assert ow.validate([item(id="OW-1")], repo)
    assert ow.validate([item(kind="chat")], repo)
    assert ow.validate([item(size="a week")], repo)
    assert ow.validate([item(weakness="vibes")], repo)
    assert ow.validate([item(question="")], repo)
    assert ow.validate([item(lands_in=[])], repo)
    bare = item()
    del bare["check"]
    assert any("check" in p for p in ow.validate([bare], repo))


def test_a_weak_measure_no_item_names_is_reported(repo):
    (repo / "health/interventions/library/m_air.toml").write_text(
        "name = 'x'\nplaceholders = ['cost.annual']\n")
    (repo / "health/interventions/library/m_other.toml").write_text(
        "name = 'x'\n[cost]\npartial = 'leaves things out'\n")
    items = [item(affects=["measure:m_air"])]
    out = ow.uncovered(items, repo)
    assert [m for m, _ in out] == ["m_other"]


# ---- ordering ---------------------------------------------------------------------------------

def sens(rows, **top):
    return {"place": "Testville", "top": 5, "generated": "2026-11-27", "research": rows, **top}


def row(unit, nr=None, raw=0):
    r = {"unit": unit, "curves_top_changed": raw}
    if nr is not None:
        r["noise_robust"] = nr
    return r


def sorted_ids(items, s, repo):
    return [e["id"] for e in ow.order(items, s, repo)]


def test_order_by_noise_robust_count_then_weakness_then_size(repo):
    items = [
        item("OW-001", affects=["measure:m_air"], weakness="judgement"),
        item("OW-002", affects=["measure:m_other"], weakness="S"),
        item("OW-003", affects=["measure:m_other"], weakness="placeholder", size="bigger"),
        item("OW-004", affects=["measure:m_other"], weakness="placeholder"),
        item("OW-005", affects=["measure:m_air", "measure:m_other"], weakness="none"),
    ]
    s = sens([row("effect:m_air", nr=3, raw=8), row("cost:m_air", nr=1),
              row("effect:m_other", nr=3), row("cost:m_other", nr=0)], )
    # OW-001 (3), OW-005 (max 3 over both), OW-002/3/4 (3 via effect:m_other)
    got = sorted_ids(items, s, repo)
    # all five have 3; ties by weakness (placeholder first, then S, judgement, none), then size
    assert got == ["OW-004", "OW-003", "OW-002", "OW-001", "OW-005"]


def test_noise_robust_count_is_preferred_to_the_raw_count(repo):
    items = [item("OW-001", affects=["measure:m_air"]), item("OW-002", affects=["measure:m_other"])]
    s = sens([row("effect:m_air", nr=0, raw=8), row("effect:m_other", nr=2, raw=2)])
    assert sorted_ids(items, s, repo) == ["OW-002", "OW-001"]
    e = {x["id"]: x for x in ow.order(items, s, repo)}
    assert e["OW-001"]["priority"]["count"] == 0
    assert e["OW-001"]["priority"]["count_kind"] == "noise-robust"


def test_raw_count_is_the_fallback_when_the_file_has_no_noise_robust_key(repo):
    items = [item("OW-001", affects=["measure:m_air"]), item("OW-002", affects=["measure:m_other"])]
    s = sens([row("effect:m_air", raw=1), row("effect:m_other", raw=4)])
    assert sorted_ids(items, s, repo) == ["OW-002", "OW-001"]
    p = ow.order(items, s, repo)[0]["priority"]
    assert p["count"] == 4 and p["count_kind"] == "raw"


def test_table_and_study_affects_map_to_their_research_units(repo):
    items = [
        item("OW-001", affects=["table:receptor_r.csv"]),     # measures reading it: m_reg
        item("OW-002", affects=["study:study_a"]),            # the study unit
        item("OW-003", affects=["table:exposure_m.csv"]),     # the map unit
        item("OW-004", affects=["measure:m_air"]),
    ]
    s = sens([row("cost:m_reg", nr=2), row("study", nr=3), row("map", nr=1),
              row("effect:m_air", nr=0)])
    got = {e["id"]: e["priority"]["count"] for e in ow.order(items, s, repo)}
    assert got == {"OW-001": 2, "OW-002": 3, "OW-003": 1, "OW-004": 0}
    assert sorted_ids(items, s, repo)[:3] == ["OW-002", "OW-001", "OW-003"]


def test_an_item_outside_the_run_has_no_count_and_says_so(repo):
    items = [item("OW-001", affects=[]), item("OW-002", affects=["measure:m_air"])]
    s = sens([row("effect:m_air", nr=1)])
    got = {e["id"]: e["priority"] for e in ow.order(items, s, repo)}
    assert got["OW-001"]["count"] == 0 and "no research unit" in got["OW-001"]["basis"]
    assert got["OW-002"]["count"] == 1


def test_without_a_sensitivity_file_order_is_by_weakness_then_size_and_says_so(repo):
    items = [
        item("OW-001", weakness="none"),
        item("OW-002", weakness="judgement", size="bigger"),
        item("OW-003", weakness="judgement"),
        item("OW-004", weakness="R"),
        item("OW-005", weakness="placeholder"),
        item("OW-006", weakness="S"),
        item("OW-007", weakness="partial_cost"),
    ]
    out = ow.order(items, None, repo)
    assert [e["id"] for e in out] == ["OW-005", "OW-004", "OW-006", "OW-003", "OW-002",
                                      "OW-007", "OW-001"]
    assert all("no sensitivity file" in e["priority"]["basis"] for e in out)
    md = ow.render_md(out, None, repo)
    assert "No sensitivity file was used" in md


# ---- the outputs ------------------------------------------------------------------------------

def test_outputs_carry_the_rules_verbatim_and_match_the_registry(repo, tmp_path):
    items = [item("OW-001"), item("OW-002", affects=["study:study_a"], title="Second one")]
    s = sens([row("effect:m_air", nr=2), row("study", nr=1)])
    out = ow.order(items, s, repo)
    md = ow.render_md(out, ow.describe(s, "x.json"), repo)
    js = json.loads(ow.render_json(out, ow.describe(s, "x.json"), repo))
    assert ow.RULES in md
    assert js["rules"] == ow.RULES
    assert [e["id"] for e in js["items"]] == re.findall(r"^### (OW-\d{3})", md, re.M)
    for e in js["items"]:
        assert f"### {e['id']}: {e['title']}" in md
        for field in ("question", "read_at", "lands_field", "check"):
            assert e[field] in md
    assert "2026-11-27" in md and js["sensitivity"]["generated"] == "2026-11-27"
    assert "Testville" in md


def test_ids_are_stable_across_regenerations(repo, tmp_path):
    items = [item("OW-001"), item("OW-002", affects=["study:study_a"])]
    s1 = sens([row("effect:m_air", nr=0), row("study", nr=5)])
    s2 = sens([row("effect:m_air", nr=5), row("study", nr=0)])
    a = ow.order(items, s1, repo)
    b = ow.order(items, s2, repo)
    assert [e["id"] for e in a] != [e["id"] for e in b]            # the order moved
    assert {e["id"]: e["title"] for e in a} == {e["id"]: e["title"] for e in b}
    again = ow.order(items, s1, repo)
    assert ow.render_json(a, ow.describe(s1, "x"), repo) == ow.render_json(again, ow.describe(s1, "x"), repo)


def test_done_items_leave_the_list_but_keep_their_ids(repo):
    items = [item("OW-001", status="done", closed_by="abc123"), item("OW-002")]
    out = ow.order(items, None, repo)
    assert [e["id"] for e in out] == ["OW-002"]
    js = json.loads(ow.render_json(out, None, repo, closed=ow.closed_ids(items)))
    assert js["closed"] == ["OW-001"]


def test_main_writes_both_files_and_refuses_a_bad_registry(repo, tmp_path):
    reg = tmp_path / "reg.toml"
    reg.write_text('[[item]]\nid = "OW-001"\ntitle = "T"\nkind = "desk lookup"\nsize = "one sitting"\n'
                   'weakness = "S"\nquestion = "What?"\nread_at = "x"\nlands_in = ["docs/note.md"]\n'
                   'lands_field = "f"\ncheck = "c"\naffects = ["measure:m_air"]\norigin = ["t"]\n')
    sf = tmp_path / "sens.json"
    sf.write_text(json.dumps(sens([row("effect:m_air", nr=2)])))
    out = tmp_path / "out"
    rc = ow.main(["--registry", str(reg), "--repo", str(repo), "--sensitivity", str(sf),
                  "--out-dir", str(out)])
    assert rc == 0
    assert (out / "open-work.md").exists() and (out / "open-work.json").exists()
    reg.write_text(reg.read_text() + reg.read_text())          # duplicate id
    assert ow.main(["--registry", str(reg), "--repo", str(repo), "--sensitivity", str(sf),
                    "--out-dir", str(tmp_path / "out2")]) == 1
    assert not (tmp_path / "out2").exists()


def test_a_missing_sensitivity_path_falls_back_and_says_so(repo, tmp_path):
    reg = tmp_path / "reg.toml"
    reg.write_text('[[item]]\nid = "OW-001"\ntitle = "T"\nkind = "desk lookup"\nsize = "one sitting"\n'
                   'weakness = "S"\nquestion = "What?"\nread_at = "x"\nlands_in = ["docs/note.md"]\n'
                   'lands_field = "f"\ncheck = "c"\naffects = []\norigin = ["t"]\n')
    out = tmp_path / "out"
    assert ow.main(["--registry", str(reg), "--repo", str(repo),
                    "--sensitivity", str(tmp_path / "nope.json"), "--out-dir", str(out)]) == 0
    assert "No sensitivity file was used" in (out / "open-work.md").read_text()


# ---- the real registry and the real documents -------------------------------------------------

def real_items():
    return ow.load(ow.REGISTRY)


def test_real_registry_is_valid():
    assert ow.validate(real_items(), REPO) == []


def test_real_ids_are_contiguous_so_none_was_deleted_or_reused():
    ids = [i["id"] for i in real_items()]
    assert ids == [f"OW-{n:03d}" for n in range(1, len(ids) + 1)]


def test_every_flagged_weak_input_in_the_library_is_in_some_item():
    assert ow.uncovered(real_items(), REPO) == []


def test_every_missing_md_entry_item_is_linked_from_missing_md():
    missing = (REPO / "health/data/MISSING.md").read_text()
    for it in real_items():
        if any(o.startswith("MISSING.md") for o in it["origin"]):
            assert it["id"] in missing, it["id"]


def test_every_gap_g1_to_g7_and_agents_open_work_is_seeded():
    origins = " ".join(o for it in real_items() for o in it["origin"])
    for g in range(1, 8):
        assert f"lit/gaps.md: G{g}" in origins
    for n in range(1, 6):
        assert f"AGENTS.md open work {n}" in origins


def test_rules_block_is_in_agents_md_and_in_the_generated_docs():
    assert ow.RULES in (REPO / "AGENTS.md").read_text()
    md = REPO / "docs" / "open-work.md"
    js = REPO / "docs" / "open-work.json"
    if not md.exists():
        pytest.skip("docs/open-work.md not generated")
    assert ow.RULES in md.read_text()
    assert json.loads(js.read_text())["rules"] == ow.RULES


def test_generated_docs_match_the_registry():
    md, js = REPO / "docs" / "open-work.md", REPO / "docs" / "open-work.json"
    if not md.exists():
        pytest.skip("docs/open-work.md not generated")
    data = json.loads(js.read_text())
    open_ids = {i["id"] for i in real_items() if i.get("status", "open") != "done"}
    assert {e["id"] for e in data["items"]} == open_ids
    assert set(re.findall(r"^### (OW-\d{3})", md.read_text(), re.M)) == open_ids
    by_id = {i["id"]: i for i in real_items()}
    for e in data["items"]:
        for field in ("title", "kind", "size", "question", "read_at", "lands_in", "lands_field",
                      "check", "affects"):
            assert e[field] == by_id[e["id"]][field]


def test_readme_and_agents_link_the_list():
    assert "docs/open-work.md" in (REPO / "AGENTS.md").read_text()
    assert "docs/open-work.md" in (REPO / "README.md").read_text()
