"""Shared constants for the Diwali AQI analysis."""
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent
RAW = ROOT / "data" / "raw"
FIRES = ROOT / "data" / "fires"
DATA = ROOT / "data"
CHARTS = ROOT / "charts"
FONTS = ROOT.parent / "fonts"   # shared across the repo's analysis tracks

# Lakshmi Puja night (the main firework night in North India), per Drik Panchang, New Delhi.
# In Karnataka the festival runs Naraka Chaturdashi (D-1) -> Lakshmi Puja (D) -> Bali Padyami (D+1 or D+2),
# so analyses use a window around D rather than a single night.
DIWALI = {
    2016: date(2016, 10, 30),
    2017: date(2017, 10, 19),
    2018: date(2018, 11, 7),
    2019: date(2019, 10, 27),
    2020: date(2020, 11, 14),
    2021: date(2021, 11, 4),
    2022: date(2022, 10, 24),
    2023: date(2023, 11, 12),
    2024: date(2024, 10, 31),
    2025: date(2025, 10, 20),
}

# Other firework nights that fall inside the +/-8..21-day baseline. Flagged so they don't inflate "normal".
DUSSEHRA = {  # Vijayadashami, ~D-19
    2016: date(2016, 10, 11), 2017: date(2017, 9, 30), 2018: date(2018, 10, 19), 2019: date(2019, 10, 8),
    2020: date(2020, 10, 25), 2021: date(2021, 10, 15), 2022: date(2022, 10, 5), 2023: date(2023, 10, 24),
    2024: date(2024, 10, 12), 2025: date(2025, 10, 2),
}
GURPURAB = {  # Guru Nanak Jayanti / Kartik Purnima, D+15
    2016: date(2016, 11, 14), 2017: date(2017, 11, 4), 2018: date(2018, 11, 23), 2019: date(2019, 11, 12),
    2020: date(2020, 11, 30), 2021: date(2021, 11, 19), 2022: date(2022, 11, 8), 2023: date(2023, 11, 27),
    2024: date(2024, 11, 15), 2025: date(2025, 11, 5),
}

# Ten largest metros (+ Lucknow as a spare if Surat's single monitor is too thin).
# `ph`: include Punjab-Haryana stubble fires as a covariate (cities plausibly downwind in Oct-Nov).
CITIES = {
    "Delhi": {"lat": 28.61, "lon": 77.21, "cpcb_city": ["Delhi"], "ph": True},
    "Mumbai": {"lat": 19.08, "lon": 72.88, "cpcb_city": ["Mumbai"], "ph": False},
    "Kolkata": {"lat": 22.57, "lon": 88.36, "cpcb_city": ["Kolkata"], "ph": False},
    "Bengaluru": {"lat": 12.97, "lon": 77.59, "cpcb_city": ["Bengaluru"], "ph": False},
    "Chennai": {"lat": 13.08, "lon": 80.27, "cpcb_city": ["Chennai"], "ph": False},
    "Hyderabad": {"lat": 17.39, "lon": 78.49, "cpcb_city": ["Hyderabad"], "ph": False},
    "Ahmedabad": {"lat": 23.02, "lon": 72.57, "cpcb_city": ["Ahmedabad"], "ph": False},
    "Pune": {"lat": 18.52, "lon": 73.86, "cpcb_city": ["Pune"], "ph": False},
    "Surat": {"lat": 21.17, "lon": 72.83, "cpcb_city": ["Surat"], "ph": False},
    "Jaipur": {"lat": 26.91, "lon": 75.79, "cpcb_city": ["Jaipur"], "ph": True},
    "Lucknow": {"lat": 26.85, "lon": 80.95, "cpcb_city": ["Lucknow"], "ph": True},
}

# Season window pulled for every year (covers the earliest and latest possible Diwali +/- 4 weeks)
SEASON = ("09-15", "12-20")

# Stubble-burning source region (Punjab + Haryana bounding box, approx.)
PUNJAB_HARYANA_BBOX = dict(lat_min=27.6, lat_max=32.6, lon_min=73.8, lon_max=77.6)
# Local/regional biomass burning: fires within this radius of each city centre
LOCAL_FIRE_KM = 300
