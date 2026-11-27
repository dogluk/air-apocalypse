"""Plain names for what a reader sees: risk curves, source studies and exposure maps.
One table each; code ids (the keys) may appear only in footnotes. Each name's author and year
are read from the curve's own description (airhealth.curves) or the study's rows in
health/data/causes.csv, and a test checks that they still match."""
from __future__ import annotations

CURVES: dict[str, str] = {
    "loglinear_jaganathan": "Jaganathan 2024 (log-linear)",
    "loglinear_brown": "Brown 2022 (log-linear)",
    "loglinear_vodonos": "Vodonos 2018 (log-linear)",
    "gemm_ncd_lri": "GEMM 2018",
    "aqli": "AQLI",
    "gbd2019": "GBD 2019",
    "gbd2023": "GBD 2023",
    "gemm_5cod": "GEMM 2018, five causes",
}
STUDIES: dict[str, str] = {
    "cstep_bengaluru2022_cmb": "CSTEP 2022 (receptor study)",
    "apna_2015": "APnA 2015 (emissions model)",
}
MAPS: dict[str, str] = {
    "cpcb": "CPCB monitors",
    "aqli": "AQLI satellite",
    "acag_total": "ACAG satellite",
    "gbd2019": "GBD 2019 state maps",
    "gbd2023": "GBD 2023 state maps",
}


def curve(cid: str) -> str:
    return CURVES.get(cid, cid)


def study(sid: str) -> str:
    return STUDIES.get(sid, sid)


def exposure_map(mid: str) -> str:
    return MAPS.get(mid, mid)


def every_id() -> list[str]:
    """All code ids that have a plain name (what the no-code-id test looks for). The id
    "aqli" is both a curve and a map, so a test looks for it only inside chart text."""
    return [*CURVES, *STUDIES, *MAPS]
