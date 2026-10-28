"""Shared paths and key loading. Run scripts from anywhere; paths are repo-relative."""
import os, re
from pathlib import Path
REPO = Path(__file__).resolve().parents[3]
RAW = REPO / "data/raw/cme-weather"          # gitignored (data/raw/*)
OUT = Path(__file__).resolve().parent        # .planning/research/cme-first-look
RAW.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "research-bot"}
# 13 CME US cities: (city, HDD root, CDD root, WBAN station, ICAO, GHCN id)
CITIES = [
    ("Atlanta", "H1", "K1", "13874", "KATL", "USW00013874"),
    ("Chicago", "H2", "K2", "94846", "KORD", "USW00094846"),
    ("Cincinnati", "H3", "K3", "93814", "KCVG", "USW00093814"),
    ("New York", "H4", "K4", "14732", "KLGA", "USW00014732"),
    ("Dallas", "H5", "K5", "03927", "KDFW", "USW00003927"),
    ("Philadelphia", "H6", "K6", "13739", "KPHL", "USW00013739"),
    ("Portland", "H7", "K7", "24229", "KPDX", "USW00024229"),
    ("Houston", "HR", "KR", "12960", "KIAH", "USW00012960"),
    ("Sacramento", "HS", "KS", "23232", "KSAC", "USW00023232"),
    ("Minneapolis", "HQ", "KQ", "14922", "KMSP", "USW00014922"),
    ("Boston", "HW", "KW", "14739", "KBOS", "USW00014739"),
    ("Las Vegas", "H0", "K0", "23169", "KLAS", "USW00023169"),
    ("Burbank", "LP", "KP", "23152", "KBUR", "USW00023152"),
]
def databento_key():
    """Read DATABENTO_API_KEY from env or ~/.config/dev/secrets.env. Never printed."""
    k = os.environ.get("DATABENTO_API_KEY")
    if k: return k
    for l in open(os.path.expanduser("~/.config/dev/secrets.env")):
        m = re.match(r'\s*(?:export\s+)?DATABENTO_API_KEY\s*=\s*["\']?([^"\'\s]+)', l)
        if m: return m.group(1)
    raise SystemExit("DATABENTO_API_KEY not found")
