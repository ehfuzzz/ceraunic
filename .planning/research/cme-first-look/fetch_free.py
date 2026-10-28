"""Re-download the free inputs used by dd.py/bench.py/implied.py/basis.py into data/raw/cme-weather/:
GHCN-Daily (LGA, ORD, CVG), IEM NWS CLI 2026 JSON, IEM ASOS hourly at CVG for Q4 2023-25, and the
last 5 CME settlement days for NY/CHI/CVG HDD (CME blocks curl, so via the r.jina.ai reader). ~35 MB total."""
import urllib.request, datetime as dt
from common import RAW, OUT, UA
def get(url, path):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180) as r: open(path, "wb").write(r.read())
    print(path.name, path.stat().st_size)
for g in ["USW00014732", "USW00094846", "USW00093814"]:
    get(f"https://www.ncei.noaa.gov/data/global-historical-climatology-network-daily/access/{g}.csv", RAW / f"{g}.csv")
for s in ["KLGA", "KORD", "KCVG"]:
    get(f"https://mesonet.agron.iastate.edu/json/cli.py?station={s}&year=2026", RAW / f"cli-{s}-2026.json")
for y in (2023, 2024, 2025):
    get(f"https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station=CVG&data=tmpf&year1={y}&month1=10&day1=1&year2={y+1}&month2=1&day2=1"
        "&tz=America%2FNew_York&format=onlycomma&latlon=no&missing=M&trace=T&report_type=3", RAW / f"asos-cvg-q4-{y}.csv")
(OUT / "cme-settles").mkdir(exist_ok=True)
for pid in (1151, 1186, 1145):  # NY, CHI, CVG HDD monthly futures
    for back in range(0, 9):
        d = dt.date.today() - dt.timedelta(days=back)
        if d.weekday() > 4: continue
        u = (f"https://r.jina.ai/https://www.cmegroup.com/CmeWS/mvc/Settlements/Futures/Settlements/{pid}/FUT"
             f"?strategy=DEFAULT&tradeDate={d:%m/%d/%Y}&pageSize=50")
        get(u, OUT / "cme-settles" / f"{pid}-{d:%m-%d-%Y}.json")
