"""Station registry for EVAL-02 / EVAL-03 (Phase 3).

Truth sets, index networks and outer rings are exactly the Q5 tables of
.planning/phases/03-geography-residual-bakeoff/03-RESEARCH.md (frozen in reports/eval-03/PREREG.md).
Coordinates are IEM network-table values (data/cache/eval03/networks/*.json, pulled 2026-09-30).
County names use NCEI's state-prefixed form ("NJ: Essex County"), the key of the nClimGrid county CSVs.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

MARKETS = ("NYC", "EWR", "TTN", "MDW", "MIA")
TRAIN = ("2024-01-01", "2024-12-31")
TEST = ("2025-01-01", "2026-08-31")
FULL = ("2024-01-01", "2026-08-31")


@dataclass(frozen=True)
class Station:
    code: str
    name: str
    lat: float
    lon: float
    network: str          # IEM network
    cli: bool             # NWS CLI issued (IEM json/cli.py)
    awos: bool            # AWOS: truth only, never an index input
    ghcn: str | None      # GHCN-D id for the ASOS record (USW...), None if no current record
    county: str           # NCEI county name


# code, name, lat, lon, network, cli, awos, ghcn, county
_ROWS = [
    ("NYC", "Central Park", 40.779, -73.96925, "NY_ASOS", True, False, "USW00094728", "NY: New York County"),
    ("LGA", "LaGuardia", 40.77945, -73.88028, "NY_ASOS", True, False, "USW00014732", "NY: Queens County"),
    ("JRB", "Manhattan Wall St heliport", 40.7012, -74.009, "NY_ASOS", False, False, None, "NY: New York County"),
    ("TEB", "Teterboro", 40.85899, -74.05616, "NJ_ASOS", False, False, "USW00094741", "NJ: Bergen County"),
    ("EWR", "Newark", 40.68272, -74.16932, "NJ_ASOS", True, False, "USW00014734", "NJ: Essex County"),
    ("JFK", "JFK", 40.63861, -73.76222, "NY_ASOS", True, False, "USW00094789", "NY: Queens County"),
    ("CDW", "Caldwell", 40.87639, -74.28306, "NJ_ASOS", False, False, "USW00054743", "NJ: Essex County"),
    ("MMU", "Morristown", 40.79935, -74.41487, "NJ_ASOS", False, False, None, "NJ: Morris County"),
    ("HPN", "White Plains", 41.06694, -73.7075, "NY_ASOS", False, False, "USW00094745", "NY: Westchester County"),
    ("FRG", "Farmingdale", 40.72878, -73.41341, "NY_ASOS", False, False, "USW00054787", "NY: Suffolk County"),
    ("ISP", "Islip", 40.79389, -73.10167, "NY_ASOS", True, False, "USW00004781", "NY: Suffolk County"),
    ("SMQ", "Somerville", 40.62389, -74.66944, "NJ_ASOS", False, False, "USW00054785", "NJ: Somerset County"),
    ("BLM", "Belmar", 40.18, -74.13, "NJ_ASOS", False, False, None, "NJ: Monmouth County"),
    ("TTN", "Trenton", 40.27682, -74.81588, "NJ_ASOS", True, False, "USW00014792", "NJ: Mercer County"),
    ("DYL", "Doylestown", 40.33305, -75.12234, "PA_ASOS", False, False, "USW00054786", "PA: Bucks County"),
    ("PNE", "Philadelphia NE", 40.0789, -75.01335, "PA_ASOS", False, False, "USW00094732", "PA: Philadelphia County"),
    ("WRI", "McGuire AFB", 40.01558, -74.59171, "NJ_ASOS", False, False, "USW00014706", "NJ: Burlington County"),
    ("VAY", "South Jersey Regional", 39.94289, -74.84572, "NJ_ASOS", False, False, "USW00093780", "NJ: Burlington County"),
    ("LOM", "Wings Field", 40.13756, -75.26514, "PA_ASOS", False, True, None, "PA: Montgomery County"),
    ("CKZ", "Pennridge", 40.3891944, -75.2904722, "PA_ASOS", False, True, None, "PA: Bucks County"),
    ("MDW", "Midway", 41.78597, -87.75242, "IL_ASOS", True, False, "USW00014819", "IL: Cook County"),
    ("ORD", "O'Hare", 41.9602, -87.9316, "IL_ASOS", True, False, "USW00094846", "IL: Cook County"),
    ("IGQ", "Lansing", 41.53492, -87.52953, "IL_ASOS", False, True, None, "IL: Cook County"),
    ("GYY", "Gary", 41.61628, -87.41278, "IN_ASOS", False, False, None, "IN: Lake County"),
    ("LOT", "Romeoville", 41.60811, -88.09619, "IL_ASOS", True, False, None, "IL: Will County"),
    ("06C", "Schaumburg", 41.9912708, -88.105, "IL_ASOS", False, True, None, "IL: Cook County"),
    ("PWK", "Palwaukee", 42.12083, -87.90472, "IL_ASOS", True, False, "USW00004838", "IL: Cook County"),
    ("DPA", "DuPage", 41.90778, -88.24861, "IL_ASOS", True, False, "USW00094892", "IL: DuPage County"),
    ("JOT", "Joliet", 41.51769, -88.17561, "IL_ASOS", False, True, "USW00014834", "IL: Will County"),
    ("UGN", "Waukegan", 42.42545326, -87.86330075, "IL_ASOS", True, False, "USW00014880", "IL: Lake County"),
    ("MIA", "Miami", 25.78805, -80.31693, "FL_ASOS", True, False, "USW00012839", "FL: Miami-Dade County"),
    ("OPF", "Opa-locka", 25.91017, -80.28283, "FL_ASOS", False, False, "USW00012882", "FL: Miami-Dade County"),
    ("TMB", "Kendall-Tamiami", 25.64227, -80.43467, "FL_ASOS", False, False, "USW00012888", "FL: Miami-Dade County"),
    ("HWO", "North Perry", 25.99955, -80.24119, "FL_ASOS", False, False, "USW00092809", "FL: Broward County"),
    ("HST", "Homestead ARB", 25.48844, -80.38367, "FL_ASOS", False, False, "USW00012826", "FL: Miami-Dade County"),
    ("FLL", "Fort Lauderdale", 26.07871176, -80.16223087, "FL_ASOS", True, False, "USW00012849", "FL: Broward County"),
    ("FXE", "Fort Lauderdale Exec", 26.2, -80.17, "FL_ASOS", False, False, "USW00012885", "FL: Broward County"),
    ("DJT", "West Palm Beach", 26.6847, -80.0994, "FL_ASOS", False, False, "USW00012844", "FL: Palm Beach County"),
]
STATIONS: dict[str, Station] = {r[0]: Station(*r) for r in _ROWS}

# Q5: truth points (<= 50 km), per market and variable
TRUTH = {
    "temperature": {
        "NYC": ["LGA", "JRB", "TEB", "EWR", "JFK", "CDW", "MMU", "HPN", "FRG"],
        "EWR": ["JRB", "NYC", "TEB", "CDW", "MMU", "LGA", "JFK", "SMQ"],
        "TTN": ["DYL", "PNE", "WRI", "VAY", "SMQ", "LOM", "CKZ"],
        "MDW": ["ORD", "IGQ", "GYY", "LOT", "06C", "PWK", "DPA", "JOT"],
        "MIA": ["OPF", "HWO", "HST", "FLL", "FXE"],
    },
    "rain": {
        "NYC": ["LGA", "JRB", "TEB", "EWR", "JFK", "CDW", "HPN", "FRG"],
        "EWR": ["JRB", "NYC", "TEB", "CDW", "LGA", "JFK", "SMQ"],
        "TTN": ["VAY", "SMQ"],
        "MDW": ["ORD", "LOT", "PWK", "DPA"],
        "MIA": ["OPF", "TMB", "HWO", "FLL", "FXE"],
    },
}
# Q5: index networks (non-AWOS truth stations); S is added to the metro mean, b removed (LOO)
NETWORK = {
    "temperature": {
        "NYC": ["LGA", "JRB", "TEB", "EWR", "JFK", "CDW", "MMU", "HPN", "FRG"],
        "EWR": ["JRB", "NYC", "TEB", "CDW", "MMU", "LGA", "JFK", "SMQ"],
        "TTN": ["DYL", "PNE", "WRI", "VAY", "SMQ"],
        "MDW": ["ORD", "GYY", "LOT", "PWK", "DPA"],
        "MIA": ["OPF", "HWO", "HST", "FLL", "FXE"],
    },
    "rain": {
        "NYC": ["LGA", "JRB", "TEB", "EWR", "JFK", "CDW", "HPN", "FRG"],
        "EWR": ["JRB", "NYC", "TEB", "CDW", "LGA", "JFK", "SMQ"],
        "TTN": ["VAY", "SMQ"],
        "MDW": ["ORD", "LOT", "PWK", "DPA"],
        "MIA": ["OPF", "TMB", "HWO", "FLL", "FXE"],
    },
}
# Q5: outer rings (50-110 km), reported, never in pass tests
OUTER = {
    "temperature": {"NYC": ["ISP"], "EWR": ["BLM", "TTN"], "TTN": ["BLM", "MMU", "EWR", "CDW"],
                    "MDW": ["UGN"], "MIA": ["DJT"]},
    "rain": {"NYC": ["ISP"], "EWR": ["TTN"], "TTN": ["EWR", "CDW"], "MDW": ["UGN"], "MIA": ["DJT"]},
}
# Candidate pool for the network-radius sensitivity (30 / 70 km): every non-AWOS station in the
# registry with data, filtered by distance to S at run time.
ALL_CODES = list(STATIONS)


def haversine_km(a: str | tuple, b: str | tuple) -> float:
    la1, lo1 = (STATIONS[a].lat, STATIONS[a].lon) if isinstance(a, str) else a
    la2, lo2 = (STATIONS[b].lat, STATIONS[b].lon) if isinstance(b, str) else b
    p1, p2 = math.radians(la1), math.radians(la2)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lo2 - lo1) / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(h))


def pairs(variable: str, outer: bool = False) -> list[tuple[str, str]]:
    """(market, point) pairs of the truth set (or the outer ring)."""
    src = OUTER if outer else TRUTH
    return [(m, b) for m in MARKETS for b in src[variable][m]]


def needed_codes() -> list[str]:
    s = set(MARKETS)
    for d in (TRUTH, NETWORK, OUTER):
        for v in d.values():
            for lst in v.values():
                s.update(lst)
    return sorted(s)
