"""GFS extended MOS (MEX) archive from IEM for the 13 CME US stations, runs 2022-09-01..2026-10-01.
Pre-registered benchmark (ii) source (CME-KALSHI-WEATHER-FACTS.md 7b). Free; User-Agent research-bot; no email.
One CSV per station-year in data/raw/cme-weather/mos/. Polite: 4 s between requests, retries on 429.
Run: python3 .planning/research/cme-first-look/fetch_mos.py [ICAO ...]   (default: pre-registered 3 first, then the rest)"""
import sys, time, urllib.request, urllib.error
from common import RAW, CITIES, UA
D = RAW / "mos"; D.mkdir(exist_ok=True)
order = ["KORD", "KLGA", "KCVG"] + [c[4] for c in CITIES if c[4] not in ("KORD", "KLGA", "KCVG")]
stations = sys.argv[1:] or order
SPANS = [("2022-09-01", "2023-09-01"), ("2023-09-01", "2024-09-01"), ("2024-09-01", "2025-09-01"), ("2025-09-01", "2026-10-02")]
for st in stations:
    for a, b in SPANS:
        p = D / f"MEX-{st}-{a[:4]}.csv"
        if p.exists() and p.stat().st_size > 10000: continue
        url = f"https://mesonet.agron.iastate.edu/cgi-bin/request/mos.py?station={st}&model=MEX&sts={a}T00:00Z&ets={b}T00:00Z&format=csv"
        for attempt in range(6):
            try:
                body = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300).read()
                p.write_bytes(body); print(st, a, len(body), flush=True); break
            except urllib.error.HTTPError as e:
                print(st, a, "HTTP", e.code, "retry", attempt, flush=True); time.sleep(30 * (attempt + 1))
            except Exception as e:
                print(st, a, "ERR", type(e).__name__, flush=True); time.sleep(30)
        time.sleep(4)
