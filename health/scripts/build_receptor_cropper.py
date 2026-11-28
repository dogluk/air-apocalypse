"""Build data/receptor_power_cropper2021.csv: coal power plants' PM2.5 by district, from Cropper et al. 2021.

    python scripts/build_receptor_cropper.py

No download: it reads data/cropper2021_state_power_pm25.csv, Table S2 of the paper's SI Appendix
transcribed by hand (see its data/sources.toml entry), and data/exposure_acag_total.csv for the
list of districts in each state.

Cropper et al. 2021 (PNAS 118: e2017936118) ran CAMx for 2018 with and without India's coal-fired
power plants (all plants operating in 2018, no flue-gas desulfurisation assumed) and report the
population-weighted PM2.5 the plants add, by STATE (SI Appendix, Table S2, "in 2018" column). The
paper's gridded results (openICPSR 130404) could not be opened (data/MISSING.md), so each district
takes its state's value: delta_pm25_full = - the state's figure. Districts of states the table does
not list (Andaman & Nicobar, Chandigarh, Dadra & Nagar Haveli, Daman & Diu, Ladakh, Lakshadweep,
Puducherry) get no row, so a measure using this table does not reach them. Ladakh was part of
Jammu & Kashmir in 2018, but J&K's population-weighted value is set by the Kashmir valley and
Jammu, so it is not carried over.

This is the power-plant-only alternative to receptor_energy_coal.csv (McDuffie's coal energy
sector, which also holds fuel production and transformation, but varies within a state). The two
are kept side by side and never averaged.
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from airhealth import measures, paths  # noqa: E402

COLUMNS = ["district", "state", "delta_pm25_full"]


def build() -> pd.DataFrame:
    table = pd.read_csv(paths.DATA / "cropper2021_state_power_pm25.csv")
    units = pd.read_csv(paths.DATA / "exposure_acag_total.csv")
    known = set(units.state)
    unknown = set(table.state) - known
    assert not unknown, f"states not in exposure_acag_total.csv: {sorted(unknown)}"
    out = units.merge(table, on="state")[["unit", "state", "pm25_power_2018"]]
    out = out.rename(columns={"unit": "district"})
    out["delta_pm25_full"] = -out.pop("pm25_power_2018")
    for row in out.itertuples():
        measures.district(row.district, row.state)
    return out[COLUMNS].sort_values(["state", "district"]).reset_index(drop=True)


def main() -> None:
    out = build()
    path = paths.DATA / "receptor_power_cropper2021.csv"
    out.to_csv(path, index=False)
    units = pd.read_csv(paths.DATA / "exposure_acag_total.csv")
    m = out.merge(units, left_on=["state", "district"], right_on=["state", "unit"])
    pw = (m.delta_pm25_full * m.population).sum() / m.population.sum()
    print(f"wrote {path.name}: {len(out)} districts of {len(units)}; population-weighted change over "
          f"them {pw:.2f} µg/m³; largest {out.delta_pm25_full.min():.2f}")


if __name__ == "__main__":
    main()
