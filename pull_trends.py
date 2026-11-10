"""Google Trends search interest for health topics around Diwali (cached, resumable).

Part 1, national daily: India, Sep 15 - Dec 20 of each year 2016-2025 (daily resolution).
Part 2, state weekly:   9 states, 2016-2020 and 2021-2025 (weekly resolution).

One topic per request, so each series gets the full 0-100 scale. Responses cached as JSON under
data/trends/ so a 429 or crash can resume. Run: python pull_trends.py [daily|weekly|all]
"""
import json
import sys
from datetime import datetime, timezone

import gt
from config import DATA, DIWALI, SEASON

TOPICS = {
    # air-related symptoms
    "cough": "/m/01b_21", "sore_throat": "/m/0b76bty", "asthma": "/m/0c78m", "breathless": "/m/01cdt5",
    "eye_irritation": "/m/0dl9sgx", "inhaler": "/m/04tpm9", "headache": "/m/0j5fv",
    # cardiac
    "heart_attack": "/m/0gk4g", "chest_pain": "/m/02np4v",
    # positive control (crackers cause burns), negative controls (unrelated to air), attention
    "burn": "/m/01hwqk", "toothache": "/m/045c85", "back_pain": "/m/0142ky",
    "aqi": "/m/067tjj", "air_pollution": "/m/0dc7h",
}
STATES = {"Delhi": "IN-DL", "Maharashtra": "IN-MH", "Karnataka": "IN-KA", "Tamil Nadu": "IN-TN",
          "Telangana": "IN-TG", "West Bengal": "IN-WB", "Gujarat": "IN-GJ", "Rajasthan": "IN-RJ",
          "Uttar Pradesh": "IN-UP"}
OUT = DATA / "trends"
OUT.mkdir(exist_ok=True)


def fetch(name, mid, geo, window):
    f = OUT / f"{name}__{geo}__{window.replace(' ', '_')}.json"
    if f.exists():
        return
    dates, series = gt.timeseries([(mid, geo)], time_=window)
    f.write_text(json.dumps({"topic": name, "geo": geo, "window": window,
                             "dates": [datetime.fromtimestamp(d, timezone.utc).strftime("%Y-%m-%d") for d in dates],
                             "values": series[0]}))
    print(f"ok {f.name} ({len(dates)} pts)", flush=True)


mode = sys.argv[1] if len(sys.argv) > 1 else "all"
if mode in ("daily", "all"):
    for y in DIWALI:
        for name, mid in TOPICS.items():
            fetch(name, mid, "IN", f"{y}-{SEASON[0]} {y}-{SEASON[1]}")
if mode in ("weekly", "all"):
    for name, mid in TOPICS.items():
        for st, geo in STATES.items():
            for window in ["2016-01-01 2020-12-31", "2021-01-01 2025-12-31"]:
                fetch(name, mid, geo, window)
print("done", mode)
