"""Daily max/min (°F, NWS climate day) 1985-01-01..yesterday for the 13 CME US stations from NOAA RCC-ACIS
(serves the GHCN-Daily/NWS record; sid = GHCN id). Free, small (~0.5 MB/station). Writes data/raw/cme-weather/acis-<ICAO>.json"""
import json, urllib.request, datetime as dt
from common import RAW, CITIES, UA
end = (dt.date.today() - dt.timedelta(days=1)).isoformat()
for city, h, k, wban, icao, ghcn in CITIES:
    p = RAW / f"acis-{icao}.json"
    body = json.dumps({"sid": ghcn, "sdate": "1985-01-01", "edate": end,
                       "elems": [{"name": "maxt"}, {"name": "mint"}], "meta": ["name", "sids"]}).encode()
    req = urllib.request.Request("https://data.rcc-acis.org/StnData", data=body,
                                 headers={**UA, "Content-Type": "application/json"})
    d = json.load(urllib.request.urlopen(req, timeout=120))
    json.dump(d, open(p, "w"))
    print(icao, d["meta"]["name"], len(d["data"]), "days", p.stat().st_size, "bytes")
