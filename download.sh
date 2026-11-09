#!/usr/bin/env bash
# Fetch the raw inputs (~4 GB). Needs the GitHub CLI (gh) and curl. No API keys.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p data/raw data/fires

# CPCB 15-minute station data, compiled by Vonter/india-cpcb-aqi (ODbL)
for y in 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025; do
  gh release download "$y" -R Vonter/india-cpcb-aqi -p "cpcb-air-quality-$y.parquet" -D data/raw --clobber &
done

# NASA FIRMS MODIS fire detections, India, yearly public CSVs
for y in 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025; do
  curl -sf -o "data/fires/modis_${y}_India.csv" \
    "https://firms.modaps.eosdis.nasa.gov/data/country/modis/$y/modis_${y}_India.csv" &
done
wait
ls -la data/raw data/fires
