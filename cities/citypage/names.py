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
    "apna_2018": "APnA 2018 (emissions model)",
    "arai_teri_delhi2018_dispersion": "ARAI-TERI Delhi 2018 (emissions model)",
    "arai_teri_delhi2018_receptor": "ARAI-TERI Delhi 2018 (receptor study)",
    "arai_teri_delhi2018_region": "ARAI-TERI Delhi 2018 (emissions model, by region)",
    "biswal2025_2022": "Biswal 2025, 2022 run (emissions model)",
    "biswal2025_2023": "Biswal 2025, 2023 run (emissions model)",
    "biswal2025_2024": "Biswal 2025, 2024 run (emissions model)",
    "govardhan2024_dss": "Govardhan 2024 (emissions model, by region)",
    "kulkarni2020": "Kulkarni 2020 (emissions model)",
    "mcduffie2021": "McDuffie 2021 (global emissions model)",
    "neeri_iitb_mumbai2023_pmf": "NEERI Mumbai 2023 (receptor study)",
    "neeri_iitb_pune2024_pmf": "NEERI Pune 2024 (receptor study)",
    "teri_kolkata2025_cmaq": "TERI Kolkata 2025 (emissions model)",
    "teri_kolkata2025_cmaq_region": "TERI Kolkata 2025 (emissions model, by region)",
    "teri_kolkata2025_cmb": "TERI Kolkata 2025 (receptor study)",
    "iitk_hyderabad2023_pmf": "IIT Kanpur Hyderabad 2023 (receptor study)",
    "teri_surat2021_cmaq": "TERI Surat 2021 (emissions model)",
    "teri_surat2021_cmaq_region": "TERI Surat 2021 (emissions model, by region)",
    "teri_surat2021_cmb": "TERI Surat 2021 (receptor study)",
    "teri_lucknow2022_cmaq": "TERI Lucknow 2022 (emissions model)",
    "teri_lucknow2022_region": "TERI Lucknow 2022 (emissions model, by region)",
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
