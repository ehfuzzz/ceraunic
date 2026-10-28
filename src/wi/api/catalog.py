"""The demo world's static catalogue: location sites, settlement stations, residual pairs, roles, the
world file and the genesis parameters (SPEC sections 3, 7.1, 15). Plain data; no engine state.

Location sites are the ten stations with daily data in the snapshot. A business maps to its nearest
site; its settlement station is the metro's Kalshi station (EWR and TTN route to Central Park: SPEC 7.1,
thin ladders are not hedged directly). A business AT a settlement station has no residual.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

from wi.engine.state import DEFAULT_PARAMS
from wi.engine.units import DAY_S, UNIT, date_to_day

ENGINE_VERSION = "0.9.0"

# anvil public dev accounts (mnemonic "test test ... junk"); worthless on any real chain
ANVIL = [
    "0xf39fd6e51aad88f6f4ce6ab8827279cfffb92266", "0x70997970c51812dc3a010c7d01b50e0d17dc79c8",
    "0x3c44cdddb6a900fa2b585dd299e03d12fa4293bc", "0x90f79bf6eb2c4f870365e785982e1f101e93b906",
    "0x15d34aaf54267db7d7c367839aaf71a00a2c6a65", "0x9965507d1a55bcc2695c58ba16fb37d819b0a4dc",
    "0x976ea74026e726554db657fa54763abd0c3a0aa9", "0x14dc79964da2c08b23698b3d3cc7ca32193d9955",
    "0x23618e81e3f5cdf7f54c3d65f7fbc0abf5b21e8f", "0xa0ee7a142d267c1f36714e4a8f75612f20a79720",
]
OWNER, HOUSE, REPORTER, KEEPER = ANVIL[0], ANVIL[1], ANVIL[2], ANVIL[3]
DEMO_USERS = ANVIL[4:10]
SEED_LP = OWNER  # the senior seed comes from the owner (Configure.s.sol seeds from the deployer too)

# site code -> (station id, name, lat, lon, metro, settlement site, data source)
SITES: dict[str, tuple] = {
    "NYC": ("KNYC", "Central Park", 40.7794, -73.9692, "NYC", "NYC", "NWS CLI"),
    "LGA": ("KLGA", "LaGuardia", 40.7769, -73.8740, "NYC", "NYC", "IEM ASOS daily (CLI stand-in)"),
    "JFK": ("KJFK", "JFK Airport", 40.6398, -73.7789, "NYC", "NYC", "IEM ASOS daily (CLI stand-in)"),
    "EWR": ("KEWR", "Newark Liberty", 40.6895, -74.1745, "NYC", "NYC", "NWS CLI"),
    "TTN": ("KTTN", "Trenton-Mercer", 40.2767, -74.8160, "NYC", "NYC", "NWS CLI"),
    "MDW": ("KMDW", "Chicago Midway", 41.7868, -87.7522, "CHI", "MDW", "NWS CLI"),
    "ORD": ("KORD", "Chicago O'Hare", 41.9786, -87.9048, "CHI", "MDW", "IEM ASOS daily (CLI stand-in)"),
    "MIA": ("KMIA", "Miami Intl", 25.7959, -80.2870, "MIA", "MIA", "NWS CLI"),
    "FLL": ("KFLL", "Fort Lauderdale", 26.0726, -80.1527, "MIA", "MIA", "IEM ASOS daily (CLI stand-in)"),
    "OPF": ("KOPF", "Miami-Opa Locka", 25.9070, -80.2784, "MIA", "MIA", "IEM ASOS daily (CLI stand-in)"),
}
SITE_BY_STATION = {v[0]: k for k, v in SITES.items()}
MAX_SITE_KM = 60.0

# settlement stations shown by /config (the 09-01 list; EWR/TTN are Kalshi stations with thin ladders)
STATIONS = [
    ("KNYC", "NYC", "Central Park", 40.7794, -73.9692, "KXHIGHNY", "NWS CLI"),
    ("KEWR", "EWR", "Newark Liberty", 40.6895, -74.1745, "KXHIGHTEWR", "NWS CLI"),
    ("KTTN", "TTN", "Trenton-Mercer", 40.2767, -74.8160, "KXHIGHTTTN", "NWS CLI"),
    ("KMDW", "CHI", "Chicago Midway", 41.7868, -87.7522, "KXHIGHCHI", "NWS CLI"),
    ("KMIA", "MIA", "Miami Intl", 25.7959, -80.2870, "KXHIGHMIA", "NWS CLI"),
]
HEDGE_SERIES = {"NYC": "KXHIGHNY", "MDW": "KXHIGHCHI", "MIA": "KXHIGHMIA"}
PAIR_SITES = ("LGA", "JFK", "EWR", "TTN", "ORD", "FLL", "OPF")

# Rain cover (13-RAIN): one daily "> 0 in" Kalshi binary per metro, settled on that station's NWS CLI precip
# (KXRAIN rules: CLINYC, CLIORD, CLIMIA). The cover settles on the same station (station-leg-only product: no rain
# residual is listed, the business's local difference is RFQ-only). metro -> rain station site; site -> series key.
RAIN_SITE = {"NYC": "NYC", "CHI": "ORD", "MIA": "MIA"}
RAIN_SERIES = {"NYC": "KXRAIN-NYC", "ORD": "KXRAIN-CHI", "MIA": "KXRAIN-MIA"}


def cli_index(site: str) -> str:
    return f"CLI:{site}:TMAX:v1"


def rain_index(site: str) -> str:
    """Wet-day indicator on the station's NWS CLI daily precipitation (scale 1: 1 = precip >= 0.01 in, 0 = dry;
    a trace is 0, as on Kalshi). Rain cover = market [0, 1] on it, business long (SPEC 2 DIGITAL_ABOVE)."""
    return f"CLI:{site}:WET:v1"


def pair_index(site: str) -> str:
    return f"PAIR:{site}-{SITES[site][5]}:TMAX:v1"


def contract_id(site: str) -> str:
    """Residual contract id for a location site (one auction per contract per day)."""
    return f"RES-{site}-{SITES[site][5]}"


CONTRACTS = {contract_id(s): s for s in PAIR_SITES}
INDEX_NAMES = [cli_index(s) for s in SITES] + [pair_index(s) for s in PAIR_SITES] + \
    [rain_index(s) for s in RAIN_SERIES]

# ---------------------------------------------------------------- calendar
FIRST_DAY = date_to_day("2026-07-16")  # first climate day with a sellable ladder in the world
LAST_DAY = date_to_day("2026-09-28")  # last climate day in the snapshot window
GENESIS_TS = (FIRST_DAY - 1) * DAY_S + 14 * 3600  # 2026-07-15 14:00Z: ladder for day 1 opens
REST_S = 20 * 3600  # the world clock rests at 20:00Z (tomorrow's ladder is open, sales are open)
START_TS = (FIRST_DAY - 1) * DAY_S + REST_S  # 2026-07-15 20:00Z
END_TS = (LAST_DAY + 2) * DAY_S + REST_S  # 2026-09-30 20:00Z: the last day has finalised

# ---------------------------------------------------------------- genesis money (base units)
HOUSE_FLOAT = 200_000 * UNIT  # house wallet (plays Kalshi's side on chain, SPEC 8.6)
JUNIOR_SEED = 200_000 * UNIT
SENIOR_SEED = 300_000 * UNIT
WI = 10**18
WI_SUPPLY = 1_000_000_000 * WI
WI_DEMO_USER = 1_000_000 * WI
WI_OWNER_STAKE = 1_000_000 * WI
PARAM_OVERRIDES = {"unstakeCooldown": 12 * DAY_S}  # seat ruling 2026-09-30 15:00Z (return window + 2 d)
MAX_FAUCET_E6 = 10_000 * UNIT


def params() -> dict[str, int]:
    return {**DEFAULT_PARAMS, **PARAM_OVERRIDES}


def world_file(policy_domain: tuple[int, str] | None = None, oracle_domain: tuple[int, str] | None = None) -> dict:
    """The engine world file. Sim uses the SPEC 15 sentinels; anvil passes the deployed contracts."""
    pd = policy_domain or (31337, "0x00000000000000000000000000000000000000a2")
    od = oracle_domain or (31337, "0x00000000000000000000000000000000000000a1")
    bal = {OWNER: WI_SUPPLY - WI_DEMO_USER * len(DEMO_USERS)}
    bal.update({u: WI_DEMO_USER for u in DEMO_USERS})
    return {
        "name": "demo-5-cities",
        "roles": {"owner": OWNER, "house": HOUSE, "quoter": HOUSE, "reporters": [REPORTER], "keeper": KEEPER,
                  "juniorDepositors": [HOUSE, OWNER], "rfqMakers": [HOUSE]},
        "hedgeableSeries": dict(HEDGE_SERIES),
        "rainSeries": dict(RAIN_SERIES),
        "residualIndexFor": {cli_index(s): pair_index(s) for s in PAIR_SITES},
        "wiSupply": WI_SUPPLY,
        "wiBalances": bal,
        "policyDomain": {"chainId": pd[0], "verifyingContract": pd[1].lower()},
        "oracleDomain": {"chainId": od[0], "verifyingContract": od[1].lower()},
    }


# ---------------------------------------------------------------- geography
def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def nearest_site(lat: float, lon: float) -> tuple[str, float]:
    s = min(SITES, key=lambda k: haversine_km(lat, lon, SITES[k][2], SITES[k][3]))
    return s, haversine_km(lat, lon, SITES[s][2], SITES[s][3])


def spec_hash() -> str:
    here = Path(__file__).resolve()
    for p in (here.parents[3] / "docs" / "SPEC.md", here.parent / "SPEC.sha256"):
        if p.exists():
            raw = p.read_bytes()
            return raw.decode().strip() if p.suffix == ".sha256" else hashlib.sha256(raw).hexdigest()
    return "unknown"
