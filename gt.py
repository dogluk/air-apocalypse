"""Minimal Google Trends client over the website's internal JSON endpoints."""
import json, time, random, requests
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
_s = None
def session():
    global _s
    if _s is None:
        _s = requests.Session()
        _s.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
        _s.get("https://trends.google.com/trends/explore")
    return _s
def _get(url, params, tries=6):
    for i in range(tries):
        r = session().get(url, params=params)
        if r.status_code == 200:
            return json.loads(r.text.split("\n", 1)[1])
        wait = 20 * (i + 1) + random.random() * 10
        print(f"  {r.status_code} on {url.rsplit('/',1)[-1]}, sleeping {wait:.0f}s", flush=True)
        time.sleep(wait)
    raise RuntimeError(f"failed {url}")
def autocomplete(term):
    return _get(f"https://trends.google.com/trends/api/autocomplete/{requests.utils.quote(term)}", {"hl": "en-US", "tz": "-330"})["default"]["topics"]
def timeseries(items, time_="today 5-y", cat=0):
    """items: list of (keyword_or_mid, geo). Returns (dates, [series...]) jointly normalised."""
    req = {"comparisonItem": [{"keyword": k, "geo": g, "time": time_} for k, g in items], "category": cat, "property": ""}
    ex = _get("https://trends.google.com/trends/api/explore", {"hl": "en-US", "tz": "-330", "req": json.dumps(req)})
    w = next(x for x in ex["widgets"] if x["id"] == "TIMESERIES")
    time.sleep(1.5 + random.random())
    d = _get("https://trends.google.com/trends/api/widgetdata/multiline", {"hl": "en-US", "tz": "-330", "req": json.dumps(w["request"]), "token": w["token"]})
    tl = d["default"]["timelineData"]
    dates = [int(t["time"]) for t in tl]
    series = [[t["value"][i] if t["hasData"][i] else None for t in tl] for i in range(len(items))]
    time.sleep(2 + random.random() * 2)
    return dates, series
