import copy
import re
import tomllib
from pathlib import Path

import pytest

from airhealth import intervention, measures
from airhealth.intervention import Dist

FIXTURES = Path(__file__).parent / "fixtures" / "library"


def _value(v) -> str:
    """A TOML value, written inline (tables as inline tables)."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, str):
        return '"' + v.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'
    if isinstance(v, list):
        return "[" + ", ".join(_value(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{" + ", ".join(f"{k} = {_value(x)}" for k, x in v.items()) + "}"
    raise TypeError(v)


def base(name: str) -> dict:
    with open(FIXTURES / f"{name}.toml", "rb") as f:
        return tomllib.load(f)


def write(tmp_path, table: dict, stem: str = "m") -> Path:
    path = tmp_path / f"{stem}.toml"
    path.write_text("".join(f"{k} = {_value(v)}\n" for k, v in table.items()))
    return path


def edited(name: str, edit: dict) -> dict:
    """A fixture's table with top-level keys replaced (None removes the key). Field checks run
    before the evidence rule, so a bad field is named even if placeholders no longer match."""
    t = copy.deepcopy(base(name))
    for k, v in edit.items():
        if v is None:
            t.pop(k, None)
        else:
            t[k] = v
    return t


def test_template_loads_with_everything_a_placeholder():
    m = measures.load(measures.LIBRARY / "_template.toml")
    assert m.id == "_template"
    assert m.numbers() and set(m.placeholders) == set(m.numbers())


def test_each_fixture_kind_loads():
    air = measures.load(FIXTURES / "air_city.toml")
    assert (air.id, air.kind, air.scope) == ("air_city", "air", "city")
    assert air.cities == ("Delhi", "Mumbai") and air.min_share_pct == 5
    assert [t.cause for t in air.targets] == ["dust", "waste_burning"]
    assert air.targets[0].months == tuple(range(1, 13))
    assert air.targets[1].months == (1, 11, 12)
    assert air.targets[1].cut == Dist.fixed(0.5)
    assert air.exposure is None and air.region is None
    assert air.cost.driver == "city" and air.cost.once == Dist.fixed(0) and air.cost.year == 2023
    assert air.lag == "epa20" and air.ramp_years == 2 and not air.long_shot
    assert air.numbers() == ["targets.dust.cut", "targets.waste_burning.cut", "cost.annual"]

    exp = measures.load(FIXTURES / "exposure_city.toml")
    assert (exp.kind, exp.scope, exp.cities, exp.targets) == ("exposure", "city", None, ())
    assert exp.exposure.hours == Dist.fixed(0.4) and exp.exposure.months == (1, 11, 12)
    assert exp.cost.driver == "household" and exp.cost.currency == "USD"
    assert exp.lag == "immediate"

    reg = measures.load(FIXTURES / "air_region.toml")
    assert (reg.kind, reg.scope, reg.cities) == ("air", "region", ())
    assert reg.region.receptor == "receptor_fixture.csv" and reg.region.cut.kind == "triangular"
    assert reg.cost.unit == "acre" and reg.cost.units.kind == "normal"
    assert reg.cost.society_net_annual == Dist.fixed(-500) and reg.cost.society_net_once is None
    assert reg.long_shot
    assert set(reg.numbers()) == {"region.cut", "cost.annual", "cost.units",
                                  "cost.society_net_annual"}

    free = measures.load(FIXTURES / "no_cost.toml")
    assert free.cost is None and free.numbers() == ["targets.dust.cut"]


def test_library_skips_underscored_files(tmp_path):
    for name in ("air_city", "no_cost"):
        write(tmp_path, base(name), name)
    write(tmp_path, base("air_city"), "_draft")
    assert sorted(measures.library(tmp_path)) == ["air_city", "no_cost"]


def test_check_library_names_the_file(tmp_path):
    write(tmp_path, base("air_city"), "good")
    write(tmp_path, edited("air_city", {"kind": "water"}), "bad")
    problems = measures.check_library(tmp_path)
    assert len(problems) == 1 and problems[0].startswith("bad.toml: kind:")


COST = {"driver": "city", "annual": 1, "currency": "INR", "year": 2025}


@pytest.mark.parametrize("name, edit, field", [
    ("air_city", {"kind": "water"}, "kind"),
    ("air_city", {"scope": "state"}, "scope"),
    ("air_city", {"scope": "city", "targets": [{"cause": "outside", "cut": 0.5}]},
     "targets.outside"),
    ("air_city", {"targets": [{"cause": "secondary_unassigned", "cut": 0.5}]},
     "targets.secondary_unassigned"),
    ("air_city", {"targets": [{"cause": "dust", "cut": 1.5}]}, "targets.dust.cut"),
    ("air_city", {"targets": [{"cause": "dust", "cut": 0.5, "months": [0, 1]}]},
     "targets.dust.months"),
    ("air_city", {"targets": [{"cause": "dust", "cut": 0.1}, {"cause": "dust", "cut": 0.2}]},
     "targets.dust"),
    ("air_city", {"targets": []}, "targets"),
    ("exposure_city", {"exposure": {"covered": 0.5, "hours": 0.5}}, "exposure.cut"),
    ("exposure_city", {"exposure": {"covered": 0.5, "hours": -0.1, "cut": 0.5}},
     "exposure.hours"),
    ("air_city", {"kind": "exposure", "min_share_pct": None,
                  "targets": [{"cause": "dust", "cut": 0.5}],
                  "exposure": {"covered": 0.5, "hours": 0.5, "cut": 0.5}}, "targets"),
    ("exposure_city", {"scope": "region"}, "scope"),
    ("exposure_city", {"min_share_pct": 5}, "min_share_pct"),
    ("air_region", {"cities": "all"}, "cities"),
    ("air_region", {"region": {"receptor": "stubble.csv", "cut": 0.5}}, "region.receptor"),
    ("air_city", {"cities": ["Atlantis"]}, "cities"),
    ("air_city", {"cities": None}, "cities"),
    ("air_city", {"cost": {**COST, "driver": "acre"}}, "cost.driver"),
    ("air_city", {"cost": {"driver": "unit", "once": 1, "currency": "INR", "year": 2025}},
     "cost.units"),
    ("air_city", {"cost": {**COST, "units": 5}}, "cost.units"),
    ("air_city", {"cost": {**COST, "annual": -1}}, "cost.annual"),
    ("air_city", {"cost": {**COST, "year": 1990}}, "cost.year"),
    ("air_city", {"cost": {**COST, "currency": "EUR"}}, "cost.currency"),
    ("air_city", {"cost": {**COST, "rupees": 1}}, "cost.rupees"),
    ("air_city", {"cost": {**COST, "partial": " "}}, "cost.partial"),
    ("air_city", {"p_success": 1.2}, "p_success"),
    ("air_city", {"p_success_basis": ""}, "p_success_basis"),
    ("air_city", {"p_success_basis": None}, "p_success_basis"),
    ("air_city", {"who_reaches": " "}, "who_reaches"),
    ("air_city", {"ramp_years": 11}, "ramp_years"),
    ("air_city", {"lag": "slow"}, "lag"),
    ("air_city", {"long_shot": "yes"}, "long_shot"),
    ("air_city", {"colour": "red"}, "colour"),
])
def test_bad_field_is_named(tmp_path, name, edit, field):
    with pytest.raises(measures.Invalid, match=f"^{re.escape(field)}"):
        measures.load(write(tmp_path, edited(name, edit)))


def test_invalid_is_the_intervention_one():
    assert measures.Invalid is intervention.Invalid


def test_number_without_evidence_or_placeholder_is_refused(tmp_path):
    t = edited("air_city", {"placeholders": ["targets.dust.cut", "cost.annual"]})
    with pytest.raises(measures.Invalid, match=r"^targets\.waste_burning\.cut: no \[\[evidence\]\]"):
        measures.load(write(tmp_path, t))


def test_cost_partial_is_read_and_optional(tmp_path):
    t = edited("air_city", {"cost": {**COST, "partial": "It leaves out what builders spend."}})
    t["placeholders"] = ["targets.dust.cut", "targets.waste_burning.cut", "cost.annual"]
    assert measures.load(write(tmp_path, t)).cost.partial == "It leaves out what builders spend."
    t["cost"] = dict(COST)
    assert measures.load(write(tmp_path, t, "n")).cost.partial == ""


FULL_EVIDENCE = {"fields": ["cost.full.low", "cost.full.high"], "source": "A report",
                 "url": "https://example.org/r", "locator": "Table 2, p. 4", "key": "O",
                 "retrieved": "2026-11-27"}
FULL = {"low": 2000000, "high": 100000000, "dist": "lognormal", "currency": "INR",
        "year": 2022, "adds": "What builders spend on barriers and water.",
        "evidence": [FULL_EVIDENCE]}


def _with_full(full: dict) -> dict:
    t = edited("air_city", {"cost": {**COST, "partial": "It leaves out builders.", "full": full}})
    t["placeholders"] = ["targets.dust.cut", "targets.waste_burning.cut", "cost.annual"]
    return t


def test_cost_full_is_read_and_optional(tmp_path):
    m = measures.load(write(tmp_path, _with_full(FULL)))
    f = m.cost.full
    assert (f.low, f.high, f.currency, f.year, f.key) == (2000000, 100000000, "INR", 2022, "O")
    assert f.annual == Dist("lognormal", 2000000, 100000000)
    assert f.evidence[0].locator == "Table 2, p. 4"
    assert "cost.full.low" not in m.numbers()        # the default scoring never reads it
    assert measures.load(FIXTURES / "air_city.toml").cost.full is None


def test_cost_full_key_is_its_weakest_evidence(tmp_path):
    low = {**FULL_EVIDENCE, "fields": ["cost.full.low"]}
    high = {**FULL_EVIDENCE, "fields": ["cost.full.high"], "key": "S"}
    m = measures.load(write(tmp_path, _with_full({**FULL, "evidence": [low, high]})))
    assert m.cost.full.key == "S"


@pytest.mark.parametrize("full, field", [
    ({**FULL, "low": 5e8}, "cost.full.low"),                                   # above high
    ({**FULL, "low": -1}, "cost.full.low"),
    ({**FULL, "dist": "normal"}, "cost.full.dist"),
    ({**FULL, "currency": "EUR"}, "cost.full.currency"),
    ({**FULL, "year": 1990}, "cost.full.year"),
    ({**FULL, "adds": " "}, "cost.full.adds"),
    ({**FULL, "evidence": []}, "cost.full.evidence"),
    ({**FULL, "evidence": [{**FULL_EVIDENCE, "fields": ["cost.full.low"]}]}, "cost.full.high"),
    ({**FULL, "evidence": [{**FULL_EVIDENCE, "fields": ["cost.annual"]}]},
     "cost.full.evidence[1].fields"),
    ({**FULL, "evidence": [{**FULL_EVIDENCE, "key": "X"}]}, "cost.full.evidence[1].key"),
    ({**FULL, "cheap": 1}, "cost.full.cheap"),
])
def test_bad_cost_full_is_named(tmp_path, full, field):
    with pytest.raises(measures.Invalid, match=f"^{re.escape(field)}"):
        measures.load(write(tmp_path, _with_full(full)))


def test_cost_full_needs_a_partial_cost(tmp_path):
    t = _with_full(FULL)
    del t["cost"]["partial"]
    with pytest.raises(measures.Invalid, match=r"^cost\.full: only for a partial cost"):
        measures.load(write(tmp_path, t))


def test_library_full_costs_are_sourced():
    lib = measures.library()
    for mid in ("construction_dust_controls", "waste_collection_burning_ban"):
        f = lib[mid].cost.full
        assert f is not None and f.low < f.high and f.evidence
        assert all(e.locator and e.url for e in f.evidence)
        assert lib[mid].cost.partial                     # the default stays the partial cost
    # the waste figures are newspaper reports of officials: never better than S
    assert lib["waste_collection_burning_ban"].cost.full.key == "S"


def test_absent_or_zero_once_needs_nothing(tmp_path):
    t = edited("air_city", {"cost": {**COST, "once": 0}})
    t["placeholders"] = ["targets.dust.cut", "targets.waste_burning.cut", "cost.annual"]
    assert "cost.once" not in measures.load(write(tmp_path, t)).numbers()


EVIDENCE = {"fields": ["targets.dust.cut"], "source": "Test source (no real study)",
            "url": "https://example.org/test", "locator": "Table 1", "key": "O",
            "retrieved": "2026-11-28"}


def test_evidence_backs_a_number(tmp_path):
    t = edited("air_city", {"placeholders": ["targets.waste_burning.cut", "cost.annual"],
                            "evidence": [EVIDENCE]})
    m = measures.load(write(tmp_path, t))
    assert m.evidence[0].fields == ("targets.dust.cut",) and m.evidence[0].derivation == ""


def test_number_both_evidenced_and_placeholder_is_refused(tmp_path):
    t = edited("air_city", {"evidence": [EVIDENCE]})
    with pytest.raises(measures.Invalid, match=r"^targets\.dust\.cut: both in placeholders"):
        measures.load(write(tmp_path, t))


def test_number_in_two_evidence_entries_is_refused(tmp_path):
    t = edited("air_city", {"placeholders": ["targets.waste_burning.cut", "cost.annual"],
                            "evidence": [EVIDENCE, {**EVIDENCE, "locator": "Table 2"}]})
    with pytest.raises(measures.Invalid, match=r"^targets\.dust\.cut: backed by two"):
        measures.load(write(tmp_path, t))


def test_evidence_for_a_number_not_in_the_file_is_refused(tmp_path):
    t = edited("air_city", {"evidence": [{**EVIDENCE, "fields": ["targets.transport.cut"]}]})
    with pytest.raises(measures.Invalid, match=r"^evidence\[1\]\.fields"):
        measures.load(write(tmp_path, t))


def test_placeholder_not_in_the_file_is_refused(tmp_path):
    t = edited("no_cost", {"placeholders": ["targets.dust.cut", "cost.once"]})
    with pytest.raises(measures.Invalid, match=r"^placeholders: 'cost\.once'"):
        measures.load(write(tmp_path, t))


@pytest.mark.parametrize("key", ["X", "o", ""])
def test_evidence_key_must_be_O_S_or_R(tmp_path, key):
    t = edited("air_city", {"placeholders": ["targets.waste_burning.cut", "cost.annual"],
                            "evidence": [{**EVIDENCE, "key": key}]})
    with pytest.raises(measures.Invalid, match=r"^evidence\[1\]\.key"):
        measures.load(write(tmp_path, t))


@pytest.mark.parametrize("key, value", [("url", "example.org"), ("retrieved", "28 Nov 2026"),
                                        ("locator", ""), ("source", None)])
def test_evidence_needs_its_locator_link_and_date(tmp_path, key, value):
    e = {**EVIDENCE, key: value}
    if value is None:
        e.pop(key)
    t = edited("air_city", {"placeholders": ["targets.waste_burning.cut", "cost.annual"],
                            "evidence": [e]})
    with pytest.raises(measures.Invalid, match=rf"^evidence\[1\]\.{key}"):
        measures.load(write(tmp_path, t))


def test_judgement_odds_are_valid(tmp_path):
    """p_success is outside the evidence rule: a judgement with a reason is enough, and
    exposure measures are not forced below any number (a guideline, not a check)."""
    t = edited("exposure_city", {"p_success": 0.9,
                                 "p_success_basis": "judgement: masks were handed out reliably"})
    assert measures.load(write(tmp_path, t)).p_success == 0.9


def test_library_is_clean():
    assert measures.check_library() == []


@pytest.mark.parametrize("csv, message", [
    (None, "no file"),
    ("district,state,delta\nMumbai,Maharashtra,-1\n", "exactly the columns"),
    ("district,state,delta_pm25_full\nMumbai,Maharashtra,1.5\n", "at or below 0"),
    ("district,state,delta_pm25_full\nMumbai,Maharashtra,x\n", "at or below 0"),
    ("district,state,delta_pm25_full\nAtlantis,Maharashtra,-1\n", "unknown place"),
    ("district,state,delta_pm25_full\nMumbai,Maharashtra,-1\nMumbai,Maharashtra,-2\n", "twice"),
])
def test_receptor_file_must_exist_and_be_well_formed(tmp_path, csv, message):
    (tmp_path / "m.toml").write_text((FIXTURES / "air_region.toml").read_text())
    if csv is not None:
        (tmp_path / "receptor_fixture.csv").write_text(csv)
    with pytest.raises(measures.Invalid, match=f"^region.receptor: .*{message}"):
        measures.load(tmp_path / "m.toml")


def test_receptor_files_in_data_are_well_formed():
    from airhealth import paths
    found = sorted(paths.DATA.glob("receptor_*.csv"))
    for p in found:
        t = measures.receptor(p.name)
        assert (t.delta_pm25_full <= 0).all() and len(t) > 600, p.name


@pytest.mark.parametrize("ages, ok", [([5, 19], True), ([6, 19], False), ([5, 18], False),
                                      ([20, 10], False), ([60, 200], True), ([0, 0], True),
                                      ([5], False), ("5-19", False)])
def test_exposure_ages_validation(tmp_path, ages, ok):
    t = base("exposure_city")
    t["exposure"] = {**t["exposure"], "ages": ages}
    t["cost"] = {**t["cost"], "driver": "person"}
    path = write(tmp_path, t)
    if ok:
        assert measures.load(path).exposure.ages == tuple(ages)
    else:
        with pytest.raises(intervention.Invalid, match=r"^exposure\.ages"):
            measures.load(path)


def test_exposure_without_ages_is_everyone(tmp_path):
    assert measures.load(write(tmp_path, base("exposure_city"))).exposure.ages is None


def test_household_driver_with_ages_is_invalid(tmp_path):
    t = base("exposure_city")
    t["exposure"] = {**t["exposure"], "ages": [5, 19]}
    assert t["cost"]["driver"] == "household"
    with pytest.raises(intervention.Invalid, match=r"^exposure\.ages: households"):
        measures.load(write(tmp_path, t))
