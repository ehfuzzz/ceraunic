"""EVAL-07 (Phase 6): build reports/EVALUATION.md, reports/figures/*.png and an HTML/PDF export
from the phase results files. Nothing here computes a new statistic; it only reads, formats and plots.

Run:   make report          (= uv run python scripts/build_report.py)
In:    reports/eval-01/results.json            (Phase 2, EVAL-01)
       reports/eval-03/results.json            (Phase 3, EVAL-02/03; optional until it lands)
       reports/eval-04-05/{results,handoff}.json (Phase 4, EVAL-04/05)
       reports/eval-06/results.json            (Phase 5, EVAL-06)
       prior/hl-mm-ins/reports/ins2/results.json (baseline)
Out:   reports/EVALUATION.md, reports/EVALUATION.pdf (pandoc) or reports/EVALUATION.html, reports/figures/*.png

How numbers are traced
- Prose templates never contain a result number. They contain placeholders {{src:path|fmt}}. `src` is one of
  the results files (e01, e03, e45, e45h, e45j, rain, e06, ins2), a quoted constant table (ins1 = the ins1 README table,
  man = data/manifests/DATA.md, pre = a pre-registered threshold quoted from a PREREG/RESEARCH file) or
  calc (a derived value; its formula and input keys are listed). Every placeholder that renders goes into the
  key map (Appendix B). A missing key raises, except for Phase 3 keys, which render as "n/a" and are listed.
- Tables are built from results.json by code; each table caption names the source path it reads.
- After rendering, a lint pass looks for digits in the prose templates outside placeholders and prints them.
  Allowed without a key: identifiers (T1, M3, G2, EVAL-01, Phase 5, section numbers), horizons (24 h),
  calendar years used as labels, the digits 0 and 1 in formulas, and file names.

Phase 3 contract (what this script reads from reports/eval-03/results.json when it exists; the full list is
printed by `--contract` and written to .planning/phases/06-evaluation-report/06-EVAL03-CONTRACT.md):
  meta.prereg_frozen_utc, meta.written_utc
  eval02.<variable>.pooled_median_he0, .pooled_median_he0_ci, .by_market.<MKT>.median_he0, .n_pairs
  eval02.points = [{market, point, variable, dist_km, he0}, ...]
  bakeoff.<variable>.<DESIGN>.{pooled_median_he, pooled_median_dhe, dhe_ci, share_pairs_dhe_pos,
      markets_dhe_pos, pooled_median_eta, sd_r_median, L_median, settleable, verdict}
  verdicts.winner.<variable>, verdicts.pc1_vs_equal.{he_diff, ci, adopted}
  deviations = [{utc, what}, ...]
  <variable> in {temperature, rain}; <MKT> in {NYC, EWR, TTN, MDW, MIA};
  <DESIGN> in {D0, G1-P, G1-N, G1-P*, G1-N*, C1-N, R-A, R-P, R-N, R-A-PC, R-N-PC, P-A, P-A-IDW}
"""
from __future__ import annotations

import base64
import hashlib
import html
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
REP = ROOT / "reports"
FIG = REP / "figures"
OUT_MD = REP / "EVALUATION.md"
CONTRACT_MD = ROOT / ".planning" / "phases" / "06-evaluation-report" / "06-EVAL03-CONTRACT.md"

FILES = {
    "e01": REP / "eval-01" / "results.json",
    "e03": REP / "eval-03" / "results.json",
    "e45": REP / "eval-04-05" / "results.json",
    "e45h": REP / "eval-04-05" / "handoff.json",
    "e45j": REP / "eval-04-05" / "junior_returns.json",
    "rain": REP / "eval-04-05" / "rain_book.json",
    "trace": REP / "eval-01" / "trace_kxrain_2026.json",
    "sens": REP / "eval-01" / "sensitivity_trace_dry.json",
    "e06": REP / "eval-06" / "results.json",
    "ins2": ROOT / "prior" / "hl-mm-ins" / "reports" / "ins2" / "results.json",
}
OPTIONAL = {"e03"}

# ---------------------------------------------------------------------------------------------------------
# Quoted constants that do not live in a results.json. Each carries its source file.
# ---------------------------------------------------------------------------------------------------------
INS1_SRC = "prior/hl-mm-ins/reports/ins1/README.md (Results table and geography line; 68/34 city-days from 2026-07-24)"
INS1 = {  # ins1 README, per $1/degF unit, 24 h asks, fees excluded
    "n_citydays": 272,
    "NYC.premium": 1.73, "NYC.payout": 1.43, "NYC.overpay": 0.17, "NYC.he": 0.94,
    "CHI.premium": 3.14, "CHI.payout": 2.93, "CHI.overpay": 0.07, "CHI.he": 0.94,
    "MIA.premium": 4.79, "MIA.payout": 4.79, "MIA.overpay": 0.00, "MIA.he": 0.86,
    "EWR.overpay": 2.41, "TTN.overpay": 2.66, "EWR.he": 0.96, "TTN.he": 0.90,
    "he_lo": 0.86, "he_hi": 0.94, "overpay_hi": 0.17,
    "geo.LGA": 0.21, "geo.JFK": 0.13, "geo.TTN_via_EWR": 0.46, "geo.EWR_via_TTN": -0.06,
    "geo.ORD_via_MDW": 0.64, "geo.FLL": 0.08, "geo.OPF": 0.46,
    "depth_units_lo": 5, "depth_units_hi": 20,
    "mismatch_days": 5,
    "V1.worst_over_mean_lo": 9, "V1.worst_over_mean_hi": 19,
}
MAN_SRC = "data/manifests/DATA.md"
MAN = {  # DATA.md (plan 01-06 consolidation)
    "D1.markets": (34495, "D1 rows"), "D1.candle_rows": (1113358, "D1 rows"),
    "D1.series": (61, "D1 coverage"), "D3.stations": (26, "D3 rows"), "D4.cli_rows": (6832, "D4 rows"),
}
PRE = {  # pre-registered thresholds, quoted
    "e01.T1.he_min": (0.85, "reports/eval-01/PREREG.md §7 T1"),
    "e01.T1.overround_max": (0.20, "reports/eval-01/PREREG.md §7 T1"),
    "e01.T1b.expect": (0.5, "reports/eval-01/PREREG.md §7 T1b"),
    "e01.T2.overround_fail": (1.00, "reports/eval-01/PREREG.md §7 T2"),
    "e01.T3.gain_min": (0.02, "reports/eval-01/PREREG.md §7 T3"),
    "e01.T4.no_offer_max": (0.10, "reports/eval-01/PREREG.md §7 T4"),
    "e45.M1.nr_min": (0.25, "reports/eval-04-05/PREREG.md M1"),
    "e45.M1.stations": (3, "reports/eval-04-05/PREREG.md M1"),
    "e45.M2.null_max": (0.10, "reports/eval-04-05/PREREG.md M2"),
    "e45.M3.cpc_max": (0.35, "reports/eval-04-05/PREREG.md M3"),
    "e45.M4.share_max": (0.02, "reports/eval-04-05/PREREG.md M4"),
    "e45.ensemble_draws": (1000, "reports/eval-04-05/PREREG.md Fixed choices (Priors)"),
    "e45.participation": (0.02, "reports/eval-04-05/PREREG.md Fixed choices"),
    "rain.history_months": (32, "reports/eval-04-05/rain_book.md Caveats (two-leg history 2024-01..2026-08)"),
    "rain.measurable_min_in": (0.01, "SPEC §3 and .planning/phases/07-*/07-CONTEXT.md seat ruling 2026-09-30T19:12Z (rain cover pays on CLI precip of 0.01 in or more)"),
    "rain.depth_share": (0.10, "reports/eval-04-05/PREREG-rain.md (depth proxy = 10 % of pre-cutoff volume)"),
    "e45.hedge_cap_units": (5, "reports/eval-04-05/PREREG.md Fixed choices (Kalshi paper hedge)"),
    "e06.T2.he_min": (0.20, "reports/eval-06/PREREG.md §8 T2"),
    "e06.T3.cost_max": (0.25, "reports/eval-06/PREREG.md §8 T3"),
    "e06.T4.gain_min": (0.02, "reports/eval-06/PREREG.md §8 T4"),
    "e06.P1.he_max": (0.02, "reports/eval-06/PREREG.md §8 P1"),
    "e03.P1.dhe_min": (0.10, ".planning/phases/03-geography-residual-bakeoff/03-RESEARCH.md Pre-registration Draft"),
    "e03.P2.share_min": (0.70, "03-RESEARCH.md Pre-registration Draft, P2"),
    "e03.P2.markets_min": (4, "03-RESEARCH.md Pre-registration Draft, P2"),
    "e03.P3.eta_min": (0.5, "03-RESEARCH.md Pre-registration Draft, P3"),
    "e03.P4.days_max": (7, "03-RESEARCH.md Pre-registration Draft, P4"),
    "e03.ig.he_min": (0.70, "03-RESEARCH.md Pre-registration Draft, insurance-grade flag"),
    "e03.pc1.margin": (0.03, "03-RESEARCH.md Pre-registration Draft, Winner and ties"),
    "e03.test_days": (608, "03-RESEARCH.md Pre-registration Draft, Sample"),
    "e03.block_days": (14, "03-RESEARCH.md Pre-registration Draft, Inference"),
    "e03.rain_markets_min": (3, "03-RESEARCH.md Pre-registration Draft, rain P2"),
}

MACROS = {
    "@LIQ24": "e01:temperature.pooled[rule=A,h=24,pool=liquid NY+CHI+MIA]",
    "@LIQ12": "e01:temperature.pooled[rule=A,h=12,pool=liquid NY+CHI+MIA]",
    "@LIQ2": "e01:temperature.pooled[rule=A,h=2,pool=liquid NY+CHI+MIA]",
    "@L25_24": "e01:temperature.pooled[rule=A,h=24,pool=liquid 2025+ (post-hoc)]",
    "@L25_2": "e01:temperature.pooled[rule=A,h=2,pool=liquid 2025+ (post-hoc)]",
    "@THIN24": "e01:temperature.pooled[rule=A,h=24,pool=thin EWR+TTN]",
    "@B24": "e01:temperature.pooled[rule=B,h=24,pool=liquid NY+CHI+MIA]",
    "@B25": "e01:temperature.pooled[rule=B,h=24,pool=liquid 2025+ (post-hoc)]",
    "@RAIN24": "e01:rain_daily.horizons.24",
    "@CAP": "e45h:capital_per_usd_cover_H30",
    "@DEP": "e45:capital.deploy_detrended",
    "@MO": "e45:markouts",
}

# ---------------------------------------------------------------------------------------------------------
# Loading and key resolution
# ---------------------------------------------------------------------------------------------------------
DATA: dict[str, object] = {}
MISSING_E03: list[str] = []


def rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def load():
    for k, p in FILES.items():
        if p.exists():
            DATA[k] = json.loads(p.read_text())
        elif k in OPTIONAL:
            DATA[k] = None
        else:
            raise SystemExit(f"build_report: required input missing: {rel(p)}")


def _split(path: str) -> list[str]:
    segs, cur, depth = [], "", 0
    for ch in path:
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
        if ch == "." and depth == 0:
            segs.append(cur)
            cur = ""
        else:
            cur += ch
    segs.append(cur)
    return [s for s in segs if s != ""]


def _select(obj, sel: str):
    if re.fullmatch(r"-?\d+", sel):
        return obj[int(sel)]
    conds = dict(c.split("=", 1) for c in sel.split(","))
    hits = [x for x in obj if isinstance(x, dict) and all(str(x.get(k)) == v for k, v in conds.items())]
    if len(hits) != 1:
        raise KeyError(f"selector [{sel}] matched {len(hits)} items")
    return hits[0]


def resolve(src: str, path: str):
    if src == "ins1":
        return INS1[path]
    if src == "man":
        return MAN[path][0]
    if src == "pre":
        return PRE[path][0]
    if src == "calc":
        return CALC[path][0]()
    obj = DATA[src]
    if obj is None:
        raise KeyError(f"{src} not available")
    segs = _split(path)
    i = 0
    while i < len(segs):
        seg = segs[i]
        m = re.fullmatch(r"([^\[]*)((?:\[[^\]]*\])*)", seg)
        name, sels = m.group(1), re.findall(r"\[([^\]]*)\]", m.group(2))
        if name:
            if not isinstance(obj, dict):
                raise KeyError(f"{src}:{path}: not a dict at '{name}'")
            # dotted keys (e.g. 'central_p0.5'): take the longest run of plain segments that is a key
            found = False
            if not sels:
                for j in range(len(segs), i, -1):
                    cand = ".".join(segs[i:j])
                    if all("[" not in s for s in segs[i:j]) and cand in obj:
                        obj, i, found = obj[cand], j, True
                        break
            if not found:
                if name not in obj:
                    raise KeyError(f"{src}:{path}: missing '{name}'")
                obj, i = obj[name], i + 1
        else:
            i += 1
        for s in sels:
            obj = _select(obj, s)
    return obj


def source_label(src: str, path: str) -> str:
    if src == "ins1":
        return f"ins1 README: {path}"
    if src == "man":
        return f"{MAN_SRC} {MAN[path][1]}"
    if src == "pre":
        return f"threshold, {PRE[path][1]}"
    if src == "calc":
        return f"derived: {CALC[path][1]}"
    return f"{rel(FILES[src])} :: {path}"


# ---------------------------------------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------------------------------------
MINUS = "−"


def _num(x: float, d: int) -> str:
    s = f"{x:,.{d}f}"
    if s.startswith("-"):
        s = MINUS + s[1:]
    if s in (f"{MINUS}0", f"{MINUS}0." + "0" * d):
        s = s[1:]
    return s


def fmt(v, f: str) -> str:
    if f == "winner":
        return "none survived" if v in (None, "", "none") else str(v)
    if v is None:
        return "n/a"
    if f == "str":
        return str(v)
    if f == "bool":
        return "yes" if v else "no"
    if f == "winner":
        return "none survived" if v in (None, "", "none") else str(v)
    if f == "pf":
        return "PASS" if v is True else ("FAIL" if v is False else str(v))
    if f.startswith("ci"):  # ci2, ci3, cipct1
        lo, hi = (v["lo"], v["hi"]) if isinstance(v, dict) else (v[0], v[1])
        inner = f[2:]
        if inner.isdigit():
            inner = "f" + inner
        return f"[{fmt(lo, inner)}, {fmt(hi, inner)}]"
    if f.startswith("f"):
        return _num(float(v), int(f[1:]))
    if f.startswith("pct"):
        return _num(100 * float(v), int(f[3:])) + " %"
    if f == "int":
        return _num(float(v), 0)
    if f == "usd0":
        return ("$" + _num(float(v), 0)).replace("$" + MINUS, MINUS + "$")
    if f == "usdk":
        return ("$" + _num(float(v) / 1000, 0) + "k").replace("$" + MINUS, MINUS + "$")
    if f == "mult":
        return _num(float(v), 0) + "×"
    raise ValueError(f"unknown format {f}")


# ---------------------------------------------------------------------------------------------------------
# Derived values (formula text + inputs shown in the key map)
# ---------------------------------------------------------------------------------------------------------
def R(ref: str):
    src, path = ref.split(":", 1)
    return resolve(src, path)


def _m(ref: str) -> str:
    for k, v in MACROS.items():
        ref = ref.replace(k, v)
    return ref


_RAIN_ST = ["NYC", "EWR", "TTN", "MDW", "MIA"]
CALC = {
    "gap_2025": (lambda: R(_m("@L25_24.he_cover.est")) - R(_m("@L25_24.he_ladder.est")),
                 "HE_cover − HE_ladder, e01 liquid 2025+ pool, rule A, 24 h"),
    "gap_pooled": (lambda: R(_m("@LIQ24.he_cover.est")) - R(_m("@LIQ24.he_ladder.est")),
                   "HE_cover − HE_ladder, e01 liquid pool 2022-2026, rule A, 24 h"),
    "mo_worst_over_mean": (lambda: abs(R("e45:markouts.pooled.hedged.worst_day_over_mean")),
                           "|e45 markouts.pooled.hedged.worst_day_over_mean|"),
    "e06_gap_G1": (lambda: R("e06:verdicts.T2.G1.heat_rain_median") - R("e06:verdicts.T3.G1.ladder_median"),
                   "e06 T2 G1 heat_rain_median − T3 G1 ladder_median"),
    "e06_bar_ratio_G1": (lambda: R("e06:verdicts.T2.G1.heat_rain_median") / PRE["e06.T2.he_min"][0],
                         "e06 T2 G1 heat_rain_median / T2 bar"),
    "mismatch_pct_ins1": (lambda: INS1["mismatch_days"] / INS1["n_citydays"], "ins1 5 / 272"),
    "nyc_share_of_markout": (lambda: R("e45:markouts.NYC/residual.hedged.mean") / R("e45:markouts.pooled.hedged.mean"),
                             "e45 markouts NYC/residual hedged mean / pooled hedged mean"),
    "mo_station_per_day": (lambda: sum(R(f"e45:markouts.{s}/station.hedged.total") for s in ["NYC", "EWR", "TTN", "MDW", "MIA"])
                           / R("e45:markouts.pooled.hedged.n_days"),
                           "Σ e45 markouts.<station>/station.hedged.total over five stations / markouts.pooled.hedged.n_days"),
    "mo_resid_per_day": (lambda: sum(R(f"e45:markouts.{s}/residual.hedged.total") for s in ["NYC", "EWR", "TTN", "MDW", "MIA"])
                         / R("e45:markouts.pooled.hedged.n_days"),
                         "Σ e45 markouts.<station>/residual.hedged.total over five stations / markouts.pooled.hedged.n_days"),
    "junior_share_pct": (lambda: R("e45h:junior_share"), "e45h junior_share"),
    "overround_ins1_nyc_payout_basis": (lambda: INS1["NYC.premium"] / INS1["NYC.payout"] - 1,
                                        "ins1 NYC premium / payout − 1"),
    "e45_nyc_leftover_share": (lambda: R("e45:netting.leftover_units_per_day.NYC.mean_units") / R("e45:netting.leftover_units_per_day.NYC.mean_gross_units"),
                               "e45 NYC leftover units / gross units"),
    "season_worst_loss": (lambda: -min(R("e45j:model.weather_pnl_hist").values()),
                          "−min over seasons of e45j model.weather_pnl_hist (worst modelled season weather loss)"),
    "season_book_fraction": (lambda: R("e45j:model.C30_check") / -min(R("e45j:model.weather_pnl_hist").values()),
                             "e45j model.C30_check / worst modelled season weather loss (season write cap per unit of the simulated book)"),
    "cpc_season": (lambda: R("e45:verdicts.M3.CPC") * -min(R("e45j:model.weather_pnl_hist").values()) / R("e45j:model.C30_check"),
                   "e45 verdicts.M3.CPC × worst modelled season weather loss / e45j model.C30_check"),
    "rain_leftover_total": (lambda: sum(R(f"rain:netting.leftover.{t}.leftover_units_per_day") for t in _RAIN_ST),
                            "Σ rain netting.leftover.<ST>.leftover_units_per_day over NYC, EWR, TTN, MDW, MIA ($1 of payout per unit)"),
    "rain_depth_total": (lambda: sum(R(f"rain:depth.by_city.{t}.depth_proxy") for t in _RAIN_ST),
                         "Σ rain depth.by_city.<ST>.depth_proxy over the five cities (contracts a day)"),
    "rain_need_total": (lambda: sum(R(f"rain:depth.by_city.{t}.mean_net_short_contracts") for t in _RAIN_ST),
                        "Σ rain depth.by_city.<ST>.mean_net_short_contracts over the five cities (contracts a day)"),
    "rain_thin_x": (lambda: sum(R(f"rain:depth.by_city.{t}.mean_net_short_contracts") for t in _RAIN_ST)
                    / sum(R(f"rain:depth.by_city.{t}.depth_proxy") for t in _RAIN_ST),
                    "Σ mean_net_short_contracts / Σ depth_proxy, rain depth.by_city, five cities"),
    "e45_worst30_over_c30": (lambda: R("e45:verdicts.M5.worst_realized_30day_loss") / R("e45:verdicts.M5.C30_backtest_model"),
                             "e45 M5 worst realised 30-day loss / backtest C_30"),
}

# ---------------------------------------------------------------------------------------------------------
# Rendering prose templates
# ---------------------------------------------------------------------------------------------------------
KEYMAP: list[tuple[str, str, str, str]] = []  # (section, rendered, ref, source label)
LINT: list[tuple[str, str]] = []
_SECTION = ["front"]
PH = re.compile(r"\{\{(.+?)\}\}")
FMTS = re.compile(r"^(f\d|pct\d|ci\w*|int|usd0|usdk|str|bool|pf|mult|winner)$")


def _render_ph(body: str) -> str:
    if re.match(r"^(table|fig|block):", body):
        return "{{" + body + "}}"  # directives are expanded after the prose pass
    ref, f = body, "str"
    if "|" in body:
        a, b = body.rsplit("|", 1)
        if FMTS.match(b):
            ref, f = a, b
    ref = _m(ref)
    src, path = ref.split(":", 1)
    if src == "e03":
        try:
            v = resolve(src, path)
        except (KeyError, TypeError, IndexError) as e:
            MISSING_E03.append(path)
            return f"n/a (key missing: e03:{path}; {type(e).__name__})" if DATA.get("e03") is not None else "n/a"
    else:
        v = resolve(src, path)  # raises on a missing key: no silent defaults
    out = fmt(v, f)
    KEYMAP.append((_SECTION[0], out, ref, source_label(src, path)))
    return out


ALLOW = [
    r"\bv0\.\d\b", r"\b(?:5-)?95 %", r"\bmd5s?\b", r"\bS3\b", r"\b\d+ km\b", r"0\.07 × C × P × \(1 − P\)", r"\b2 °F steps\b", r"\b7-day\b", r"\b3c\b", r"2β − 1", r"\b\d+ bps\b", r"\b\d\d:\d\dZ\b", r"EVAL-01\.\.07", r"\bD\d+-D\d+\b",
    r"\b(?:T[1-5]b?|M[1-5]|P[1-4]|G[1-6](?:-[PN]\*?)?|A[0-4]|D[0-9]+|C1-N|R-[APN](?:-PC)?|P-A(?:-IDW)?|Q[1-5][ab]?|V[0-9]|H[1-9][0-9]?)\b",
    r"\bEVAL-0[1-7]\b", r"\b(?:PROT|PORT|PITCH)-0\d\b", r"\bins[12]\b", r"\bPhase \d+\b", r"\bPhases \d+(?:[-–, ]+\d+)*\b",
    r"§\s?\d+", r"\bDeviation \d+\b", r"\bdeviation \d+\b", r"\b(?:24|12|2|30) h(?:ours)?\b", r"\b20\d\d-\d\d(?:-\d\d)?\b", r"\b(?:19|20)\d\d(?:s|\+)?",
    r"\beval-\d\d(?:-\d\d)?\b", r"\b0[1-9]-[A-Z]+\b", r"\b\d\d-[a-z-]+\b", r"\bC_30\b", r"\bN_30\b", r"\bES(?:99|95)\b",
    r"\bVaR99\b", r"\bh = (?:1|5|30)\b", r"\bn\*", r"\bn = \d+\b", r"\$1\b", r"\b[01]\b", r"\bT\+\d\b", r"\bD\+\d\b",
    r"\bK = 75\b", r"\bKXHIGH\w*", r"\bKXRAIN\w*", r"\b1/°F\b", r"\bFourier\(3\)", r"\bHAC\(7\)", r"\bPC1\b",
    r"\bx1\b", r"\bAppendix [A-C]\b", r"\b\d+\.\s", r"^#+ \d+(?:\.\d+)?", r"\bMay-Sep\b", r"trace_kxrain_2026\.md",
]


def lint(section: str, text: str):
    stripped = PH.sub("", text)
    for line in stripped.splitlines():
        s = line
        for pat in ALLOW:
            s = re.sub(pat, "", s)
        for m in re.finditer(r"\d[\d.,]*", s):
            LINT.append((section, f"'{m.group(0)}' in: {line.strip()[:110]}"))


def render(section: str, text: str) -> str:
    _SECTION[0] = section
    lint(section, text)
    return PH.sub(lambda m: _render_ph(m.group(1)), text)


# ---------------------------------------------------------------------------------------------------------
# Table helpers (tables are code: each carries its source path in the caption)
# ---------------------------------------------------------------------------------------------------------
def c(ref: str, f: str) -> str:
    try:
        return fmt(R(_m(ref)), f)
    except (KeyError, TypeError, IndexError):
        if ref.startswith("e03:"):
            MISSING_E03.append(ref[4:])
            return "n/a"
        raise


def co(ref: str, f: str) -> str:
    """optional cell: 'n/a' if the key is absent (used only where a group/year legitimately lacks a row)."""
    try:
        return fmt(R(_m(ref)), f)
    except (KeyError, TypeError, IndexError):
        return "n/a"


def table(head: list[str], rows: list[list[str]], caption: str) -> str:
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out) + f"\n\n*Source: {caption}*\n"


def est_ci(ref: str, f: str) -> str:
    return f"{c(ref + '.est', f)} {c(ref, 'ci' + f)}"


# ---------------------------------------------------------------------------------------------------------
# Section 3: pre-registration ledger and deviations
# ---------------------------------------------------------------------------------------------------------
def pf(v) -> str:
    return "PASS" if v is True else "FAIL" if v is False else str(v)


def t_ledger() -> str:
    e01f, e45f, e06f = (R("e01:meta.prereg_frozen"), R("e45:meta.prereg_frozen_utc"), R("e06:prereg_frozen_utc"))
    rows = [
        ["2 / EVAL-01", "T1", "liquid ladders, rule A, 24 h, pooled: HE_cover ≥ 0.85 and overround ≤ 20 %", e01f,
         f"HE_cover {c('e01:verdicts.T1.he_cover', 'f2')}, overround {c('e01:verdicts.T1.overround', 'pct1')}",
         pf(R("e01:verdicts.T1.pass"))],
        ["2 / EVAL-01", "T1b", "HE_ladder reported, no threshold (expected about 0.5)", e01f,
         f"{c('e01:verdicts.T1b.he_ladder', 'f2')} pooled", "below expectation (no bar)"],
        ["2 / EVAL-01", "T2", "thin ladders fail if 24 h overround > 100 %", e01f,
         f"EWR {c('e01:verdicts.T2.EWR.overround', 'pct0')}, TTN {c('e01:verdicts.T2.TTN.overround', 'pct0')}",
         "FAIL (both)" if R("e01:verdicts.T2.EWR.fail") and R("e01:verdicts.T2.TTN.fail") else "see results"],
        ["2 / EVAL-01", "T3", "daily rain binary: Brier(clim) − Brier(mid) ≥ 0.02 at 24 h", e01f,
         f"gain {c('e01:verdicts.T3.brier_gain', 'f3')}", pf(R("e01:verdicts.T3.pass"))],
        ["2 / EVAL-01", "T4", "liquid ladders: 24 h no-offer share ≤ 10 % in every city-year from 2024", e01f,
         f"worst {c('e01:verdicts.T4.worst', 'str')} {c('e01:verdicts.T4.worst_share', 'pct1')}",
         pf(R("e01:verdicts.T4.pass"))],
        ["2 / EVAL-01", "check", "ins1 reproduction within 5 % (premium, payout)", e01f,
         f"premium {c('e01:ins1_check.premium_dev', 'pct1')}, payout {c('e01:ins1_check.payout_dev', 'pct1')}",
         pf(R("e01:ins1_check.pass"))],
        ["4 / EVAL-04", "M1", "netting ratio ≥ 0.25 at ≥ 3 of 5 stations", e45f,
         f"{c('e45:verdicts.M1.stations_ge_0p25', 'int')} of 5", c("e45:verdicts.M1.verdict", "str")],
        ["4 / EVAL-04", "M2", "null netting < 0.10 → pitch must not lead with netting", e45f,
         f"null pooled {c('e45:verdicts.M2.null_pooled', 'f3')}", c("e45:verdicts.M2.verdict", "str")],
        ["4 / EVAL-05", "M3", "C_30 / 30-day pool notional ≤ 0.35", e45f,
         f"{c('e45:verdicts.M3.CPC', 'f3')}", c("e45:verdicts.M3.verdict", "str")],
        ["4 / EVAL-05", "M4", "CLI payout-moving revisions ≤ 2 % of units", e45f,
         f"{c('e45:verdicts.M4.share', 'pct1')}", c("e45:verdicts.M4.verdict", "str")],
        ["4 / EVAL-05", "M5", "Kupiec two-sided on 1-day VaR99 not rejected at 5 %", e45f,
         f"{c('e45:verdicts.M5.kupiec.x', 'int')} exceedance in {c('e45:verdicts.M5.kupiec.n', 'int')} days, "
         f"p = {c('e45:verdicts.M5.kupiec.p_value', 'f3')}", c("e45:verdicts.M5.verdict", "str")],
    ]
    t1 = {g: R(f"e06:verdicts.T1.{g}.pass") for g in ["G1", "G2"]}
    rows.append(["5 / EVAL-06", "T1", "group mu_heat and mu_wet nonzero at 95 % (G1, G2); fail = stop", e06f,
                 f"G1 mu_heat CI {c('e06:verdicts.T1.G1.heat_ci', 'ci4')}; G2 both nonzero",
                 f"G1 {pf(t1['G1'])}, G2 {pf(t1['G2'])} (G1 stop overruled post hoc, see rulings)"])
    rows.append(["5 / EVAL-06", "T2", "A3 median HE_cover heat+rain ≥ 0.20, LB > 0, ≥ 70 % units > 0 (G1, G2)", e06f,
                 f"G1 {c('e06:verdicts.T2.G1.heat_rain_median', 'f3')}, G2 {c('e06:verdicts.T2.G2.heat_rain_median', 'f3')}",
                 f"G1 {pf(R('e06:verdicts.T2.G1.pass'))}, G2 {pf(R('e06:verdicts.T2.G2.pass'))}"])
    rows.append(["5 / EVAL-06", "T3", "A3 median HE_ladder > 0 with LB > 0 and cost ≤ 25 % of payout", e06f,
                 f"G1 {c('e06:verdicts.T3.G1.ladder_median', 'f3')} (cost {c('e06:verdicts.T3.G1.cost_ratio', 'pct0')}); "
                 f"G2 {c('e06:verdicts.T3.G2.ladder_median', 'f3')}",
                 f"G1 {pf(R('e06:verdicts.T3.G1.pass'))}, G2 {pf(R('e06:verdicts.T3.G2.pass'))}"])
    t4 = ", ".join(f"{g} {pf(R(f'e06:verdicts.T4.{g}.pass'))}" for g in ["G1", "G2", "G3", "G4", "G5"])
    rows.append(["5 / EVAL-06", "T4", "A3 − A1 ≥ 0.02 with LB > 0 at n = 60-180, fewer negative units; no harm at 365",
                 e06f, f"G1 at n = 180: {c('e06:verdicts.T4.G1.short_n.180.diff', 'f3')}", t4])
    rows.append(["5 / EVAL-06", "T5", "days of history n* (descriptive)", e06f,
                 f"G1 own {c('e06:verdicts.T5.G1.n_star_A1', 'int')} / EB {c('e06:verdicts.T5.G1.n_star_A3', 'int')}; "
                 f"G2 own {c('e06:verdicts.T5.G2.n_star_A1', 'int')} / EB {c('e06:verdicts.T5.G2.n_star_A3', 'int')}; G3-G5 none",
                 "descriptive"])
    p1 = ", ".join(f"{g} {pf(R(f'e06:verdicts.P1.{g}.pass'))}" for g in ["G1", "G2", "G3", "G4", "G5"])
    rows.append(["5 / EVAL-06", "P1", "placebo: mu insignificant and median HE_cover ≤ 0.02; fail invalidates T2-T5",
                 e06f, "HE ≤ 0.02 in every group; DL mu 'significant' in every group",
                 f"{p1} (by the letter; passes on the day-block interval adopted post hoc)"])
    e03 = DATA.get("e03")
    if e03 is None:
        rows.append(["3 / EVAL-02, 03", "P1-P4, winner", "residual bake-off (03-RESEARCH draft; freezes as eval-03/PREREG.md)",
                     "not frozen yet", "Phase 3 pending", "pending"])
    else:
        fr = co("e03:meta.prereg_frozen_utc", "str")
        for var in ["temperature", "rain"]:
            w = co(f"e03:verdicts.winner.{var}", "winner")
            rows.append(["3 / EVAL-03", f"P1-P4 ({var})", "design survives if gain, breadth, efficiency and settleability all pass",
                         fr, f"winner: {w}", "see §6"])
    return table(["phase / req", "test", "rule (frozen)", "frozen (UTC)", "result", "verdict"], rows,
                 "verdict keys `verdicts.*` in reports/eval-01, eval-04-05 and eval-06 results.json; rule text quoted "
                 "from each PREREG.md; freeze times from each results.json meta")


DEVIATIONS = [
    # phase, id, UTC, relative to numbers, what, effect on verdicts
    ("2", "1", "13:31Z", "after the first run (13:29Z)",
     "Settled value filled from the NWS CLI high where Kalshi's expiration_value is empty and the CLI lies in the "
     "settled bracket (2025-10 to 2026-01, NWS era).", "none: strict frozen sample gives the same T1 and T4 verdicts"),
    ("2", "2", "13:28Z", "before the first run", "Ladder validity check added (brackets disjoint and contiguous); "
     "a few legacy 2022 events excluded.", "none"),
    ("2", "3", "13:28Z", "before the first run", "Rain Brier sample clarified: all quoted markets; cost and HE on "
     "executable markets only.", "none"),
    ("2", "4", "13:30Z", "pre-registered conditional", "Trace days settle YES in more than half the cases, so wet "
     "= precip > 0 including trace.", "as registered; the rain cover later dropped trace as wet (§4, §11)"),
    ("2", "5", "13:25Z", "before the first run", "KXRAINNY excluded (settles on the Hudson River Pier 26 gauge).",
     "none"),
    ("2", "6", "13:34Z", "after numbers", "Post-hoc descriptive pool 'liquid 2025+' added to the tables.",
     "not a verdict; this report labels it post hoc everywhere"),
    ("2", "7", "(caveat)", "no change", "Rule-B strike uses day t−1's final CLI high, which at the 24 h decision "
     "exists only as the preliminary.", "none (sets the strike, not a price)"),
    ("4", "D1", "13:26Z", "in PREREG", "Hedge-day sample rule written in place of Phase 2's (not frozen then); "
     "six-rung ladders start in 2023.", "none"),
    ("4", "D2", "13:33Z", "before any netting number", "Suppressed ZBP cells spread by the national size "
     "distribution (the research rule put most establishments in the 50+ classes).", "population changes; "
     "rules unchanged"),
    ("4", "D3", "13:35Z", "during the run", "TTN filled from PNE before 1998; joint history from 1959; two-leg "
     "capital uses 2000-2025 only.", "defines the capital sample"),
    ("4", "D4", "13:40Z", "during the run", "EWR/TTN May-Aug book by ratio; house co-ES on the absorb-all book.",
     "none stated"),
    ("4", "D5", "13:41Z", "seat request after Phase 2", "Climatology-priced capital sensitivity added.",
     "not in M3; station-leg CPC 0.36 under it (§7)"),
    ("4", "D6", "13:43-13:44Z", "after seeing the NYC residual markout", "Two residual fair-value sensitivities "
     "(ladder-conditional, trailing 5 years).", "primary rule kept"),
    ("4", "D7", "13:46Z", "during the run", "nClimGrid prelim-vs-scaled measured once plan 01-04 wrote vintages.",
     "descriptive; M4 is CLI only"),
    ("5", "1", "~13:25Z", "before numbers", "Chicago snow control from O'Hare (KMDW has no snowfall).", "none"),
    ("5", "2", "~13:25Z", "before numbers", "Midway climatology uses the years it has (record starts 1997).", "none"),
    ("5", "3", "13:43Z", "before any G2 number", "Divvy units keyed by station name (ids recoded in 2025).", "none"),
    ("5", "4", "13:44Z", "before any G1 number", "Citi Bike station-id normalisation.", "none"),
    ("5", "5", "13:47Z", "after trial runs for G3 and G5", "Missing precipitation dropped instead of coded dry.",
     "at most a few days; no direction"),
    ("5", "6", "~13:40Z", "mid-run", "Ladder shim delegates to Phase 2's ladder.py / fees.py; keeps 6 h staleness "
     "and sell-side no-bid rules.", "none"),
    ("5", "7", "build time", "before numbers", "Closed-form EB and HAC in numpy (checked against statsmodels).",
     "none"),
    ("5", "8", "~13:34Z", "after a G3 trial number", "Supplementary joint day-block bootstrap interval for mu.",
     "adopted post hoc as the primary interval by the seat (see rulings)"),
    ("5", "trial", "13:33-13:47Z", "before the final run", "100-200-draw trial runs for G3, G5, G1.",
     "no threshold, sample, arm or metric changed"),
    ("5", "9", "14:03Z", "after the first full run", "Two CHI ladders on 2024-02-28: use the one quoted at the "
     "decision time.", "one winter day, no heat payout"),
    ("5", "10", "13:46Z", "implementation", "Portal history length uses the calendar span.", "none"),
    ("6", "R1", "15:20Z", "post hoc (seat)", "Day-block bootstrap adopted as the primary interval for every mu; "
     "DL interval kept as the pre-registered one. P1 passes on it.", "P1 read as pass; reported both ways"),
    ("6", "R2", "15:20Z", "post hoc (seat)", "Pre-registered 'stop' on G1's T1 fail overruled: the join is sound, "
     "the instrument cannot fit Citi Bike's shape. G1 results stand, flagged.", "G1 results reported, flagged"),
    ("6", "R3", "15:20Z", "post hoc (seat)", "priors.json keeps the registered T4 rule (own OLS after n*); "
     "always-shrink is a candidate for the next pre-registration.", "none"),
    ("6", "R4", "15:20Z", "post hoc (seat)", "Portal elasticity advisory only; decks may not claim a learned "
     "hedge beats doing nothing.", "follows PREREG §10"),
    ("7", "E1", "14:16Z (machine clock)", "report assembly", "Phase 3 had not landed at first assembly; §5-6 were templates. "
     "They filled from reports/eval-03/results.json on the rebuild after Phase 3 landed (results written 16:14Z).",
     "none; EVAL-02/03 now covered"),
    ("7", "E4", "14:25Z (machine clock)", "report assembly", "Clock note: this Mac read 14:16-14:25Z while the report was "
     "built, but 05-SEAT-RULINGS.md and STATE.md carry times up to 15:25Z. One of the two clocks is about an hour off; the "
     "phase freeze and write times in the results files are internally consistent (freeze before results in every phase).",
     "none on verdicts"),
    ("7", "E2", "14:16Z", "report assembly", "PROJECT.md has no separate 'Evaluation' paragraph; the checklist "
     "used is the EVAL-01..07 requirement lines plus the Core Value sentence.", "none"),
    ("7", "E3", "14:16Z", "report assembly", "pandoc is not installed on this Mac, so the export is HTML, "
     "not PDF.", "none"),
]


def t_deviations() -> str:
    names = {"2": "Phase 2 (eval-01)", "4": "Phase 4 (eval-04-05)", "5": "Phase 5 (eval-06)",
             "6": "Seat rulings on Phase 5 (05-SEAT-RULINGS.md)", "7": "Phase 6 (this report)"}
    rows = [[names[p], i, t, rel, w, e] for p, i, t, rel, w, e in DEVIATIONS]
    e03 = DATA.get("e03")
    if e03 is not None:
        # reports/eval-03/deviations.json is the log that eval03.py copies into results.json; a resolution or entry
        # added after the last eval03 run is read from the log so the table never shows a resolved item as open.
        dpath = ROOT / "reports" / "eval-03" / "deviations.json"
        log = json.loads(dpath.read_text()) if dpath.exists() else []
        by_key = {(str(x.get("utc", "")), str(x.get("what", ""))): x for x in log}
        try:
            seen = set()
            for d in R("e03:deviations"):
                key = (str(d.get("utc", "")), str(d.get("what", "")))
                seen.add(key)
                x = by_key.get(key, d)
                eff = f"{x['status']}: {x['resolution']}" if x.get("resolution") else str(x.get("status", ""))
                rows.append(["Phase 3 (eval-03)", "", key[0], "", key[1], eff])
            for key, x in by_key.items():
                if key not in seen:
                    rows.append(["Phase 3 (eval-03)", "", key[0], "", key[1] + " (logged after the last eval03 run)",
                                 str(x.get("status", ""))])
        except KeyError:
            MISSING_E03.append("deviations")
    return table(["phase", "id", "time (UTC; 2026-09-30 unless dated)", "relative to numbers", "what changed", "effect"], rows,
                 "deviation logs in reports/eval-01/PREREG.md, reports/eval-04-05/RESULTS.md, reports/eval-06/RESULTS.md, "
                 ".planning/phases/05-elasticity-learning/05-SEAT-RULINGS.md; condensed wording")


# ---------------------------------------------------------------------------------------------------------
# Section 4 tables (EVAL-01)
# ---------------------------------------------------------------------------------------------------------
def t_e01_main() -> str:
    rows = []
    for label, sel in [("liquid NY+CHI+MIA", "pooled[rule=A,h=24,pool=liquid NY+CHI+MIA]"),
                       ("liquid 2025+ (post hoc)", "pooled[rule=A,h=24,pool=liquid 2025+ (post-hoc)]"),
                       ("NY (Central Park)", "city[rule=A,h=24,city=NY]"), ("CHI (Midway)", "city[rule=A,h=24,city=CHI]"),
                       ("MIA", "city[rule=A,h=24,city=MIA]"), ("EWR (thin)", "city[rule=A,h=24,city=EWR]"),
                       ("TTN (thin)", "city[rule=A,h=24,city=TTN]")]:
        b = f"e01:temperature.{sel}"
        rows.append([label, c(b + ".n_citydays", "int"), c(b + ".n_exec", "int"), est_ci(b + ".premium", "f2"),
                     c(b + ".payout.est", "f2"), est_ci(b + ".overround", "pct1"), c(b + ".fee.est", "f2"),
                     est_ci(b + ".he_cover", "f2"), est_ci(b + ".he_ladder", "f2")])
    return table(["ladder", "city-days", "executable", "premium", "payout", "overround", "fee", "HE_cover", "HE_ladder"],
                 rows, "reports/eval-01/results.json `temperature.pooled[rule=A,h=24,...]` and `temperature.city[rule=A,h=24,...]`; "
                 "per $1/°F unit, fees excluded from premium and overround; 95 % 7-day block bootstrap")


def t_e01_years() -> str:
    rows = []
    for city in ["NY", "CHI", "MIA"]:
        for yr in range(2022, 2027):
            b = f"e01:temperature.city_year[rule=A,h=24,city={city},year={yr}]"
            try:
                R(b + ".n_citydays")
            except KeyError:
                continue
            rows.append([f"{city} {yr}", c(b + ".n_citydays", "int"), c(b + ".overround.est", "pct1"),
                         c(b + ".spread.est", "f2"), c(b + ".no_offer_share", "pct1"), c(b + ".he_cover.est", "f2"),
                         est_ci(b + ".he_ladder", "f2")])
    return table(["city-year", "city-days", "overround", "spread cost / unit", "no-offer share", "HE_cover", "HE_ladder"],
                 rows, "reports/eval-01/results.json `temperature.city_year[rule=A,h=24,city,year]`")


def t_e01_horizons() -> str:
    rows = []
    for pool, plab in [("liquid NY+CHI+MIA", "liquid, all years"), ("liquid 2025+ (post-hoc)", "liquid 2025+ (post hoc)"),
                       ("thin EWR+TTN", "thin EWR+TTN")]:
        for h in [24, 12, 2]:
            b = f"e01:temperature.pooled[rule=A,h={h},pool={pool}]"
            rows.append([plab, f"{h} h", c(b + ".premium.est", "f2"), c(b + ".overround.est", "pct1"),
                         c(b + ".fee.est", "f3"), c(b + ".spread.est", "f2"), c(b + ".total_load.est", "pct1"),
                         c(b + ".no_offer_share", "pct1"), c(b + ".he_cover.est", "f2"), c(b + ".he_ladder.est", "f2")])
    return table(["pool", "horizon", "premium", "overround", "fee / unit", "spread / unit", "total load (with fees)",
                  "no-offer", "HE_cover", "HE_ladder"], rows,
                 "reports/eval-01/results.json `temperature.pooled[rule=A,h,pool]`")


def t_e01_ruleb() -> str:
    rows = []
    for pool, plab in [("liquid NY+CHI+MIA", "liquid, all years"), ("liquid 2025+ (post-hoc)", "liquid 2025+ (post hoc)")]:
        b = f"e01:temperature.pooled[rule=B,h=24,pool={pool}]"
        rows.append([plab, c(b + ".overround.est", "pct1"), c(b + ".he_cover.est", "f2"), c(b + ".he_ladder.est", "f2"),
                     c(b + ".unspanned_share", "pct1"), c(b + ".tail_outside_share", "pct1"),
                     c(b + ".tail_outside_payout_share", "pct1")])
    return table(["pool", "overround", "HE_cover", "HE_ladder", "ladder buys nothing (unspanned days)",
                  "tail outside ladder (days)", "payout lost to the tail"], rows,
                 "reports/eval-01/results.json `temperature.pooled[rule=B,h=24,pool]`")


def t_rain() -> str:
    rows = []
    for h in ["24", "12", "2"]:
        b = f"e01:rain_daily.horizons.{h}"
        rows.append([f"{h} h", c(b + ".n_quoted", "int"), c(b + ".brier_market", "f3"), c(b + ".brier_clim", "f3"),
                     est_ci(b + ".brier_gain_ci", "f3"), c(b + ".cost_per_dollar_payout", "f2"),
                     c(b + ".no_offer_share", "pct1"), est_ci(b + ".he_wet.he_cover", "f2"),
                     est_ci(b + ".he_wet.he_ladder", "f2")])
    return table(["horizon", "markets quoted", "Brier (market mid)", "Brier (climatology)", "gain", "cost per $1 payout (with fees)",
                  "no-offer", "wet-day HE_cover", "wet-day HE_ladder"], rows,
                 "reports/eval-01/results.json `rain_daily.horizons.<h>`")


def t_rain_monthly() -> str:
    rows = []
    for s in ["KXRAINNYCM", "KXRAINCHIM", "KXRAINMIAM"]:
        for t, lab in [("month_start", "1st of month 12:00Z"), ("close_24h", "close − 24 h")]:
            b = f"e01:rain_monthly.{s}|{t}"
            rows.append([s, lab, c(b + ".n", "int"), c(b + ".no_offer_share", "pct0"), c(b + ".spread_median", "f2"),
                         c(b + ".brier_mid", "f3")])
    return table(["series", "time", "strikes", "no-offer share", "median spread ($)", "Brier (mid)"], rows,
                 "reports/eval-01/results.json `rain_monthly.<series>|<time>`")


def t_depth() -> str:
    rows = []
    for tk in ["KXHIGHNY-26SEP30", "KXHIGHCHI-26SEP30", "KXHIGHMIA-26SEP30", "KXHIGHLAX-26SEP30"]:
        b = f"e01:depth.ladders.{tk}"
        d = R(b + ".depth_3c")
        rows.append([tk, c(b + ".K", "f0"), c(b + ".contracts_per_unit", "f1"), fmt(min(d.values()), "int"),
                     fmt(max(d.values()), "int"), c(b + ".max_units_3c", "f0")])
    return table(["ladder", "K", "contracts per unit", "thinnest rung (contracts within 3c)", "deepest rung",
                  "max units at ≤ 3c"], rows,
                 "reports/eval-01/results.json `depth.ladders.<ticker>` (one snapshot, prior/hl-mm-ins/reports/ins1/books.json)")


def t_mismatch() -> str:
    rows = []
    for m in R("e01:mismatch"):
        b = f"e01:mismatch[city={m['city']},settle_source={m['settle_source']}]"
        rows.append([m["city"], m["settle_source"], c(b + ".n", "int"), c(b + ".value_mismatch_share", "pct1"),
                     c(b + ".bracket_mismatch_share", "pct1")])
    return table(["city", "settle source", "city-days (2023+)", "CLI ≠ settled value", "CLI outside settled bracket"],
                 rows, "reports/eval-01/results.json `mismatch[city,settle_source]`")


def t_ins1_compare() -> str:
    rows = []
    for city, key in [("NYC", "NY"), ("CHI", "CHI"), ("MIA", "MIA")]:
        b = f"e01:temperature.city[rule=A,h=24,city={key}]"
        y = f"e01:temperature.city_year[rule=A,h=24,city={key},year=2026]"
        rows.append([city, f"{fmt(INS1[city + '.he'], 'f2')} / {fmt(INS1[city + '.premium'] / INS1[city + '.payout'] - 1, 'pct0')}",
                     f"{c(b + '.he_cover.est', 'f2')} / {c(b + '.overround.est', 'pct0')}",
                     f"{c(y + '.he_cover.est', 'f2')} / {c(y + '.overround.est', 'pct0')}"])
    for city in ["EWR", "TTN"]:
        b = f"e01:temperature.city[rule=A,h=24,city={city}]"
        rows.append([city, f"{fmt(INS1[city + '.he'], 'f2')} / {fmt(INS1[city + '.overpay'], 'pct0')}",
                     f"{c(b + '.he_cover.est', 'f2')} / {c(b + '.overround.est', 'pct0')}", "same days as ins1"])
    return table(["ladder", "ins1: HE / overround (68 or 34 days, 2026)", "this report: HE_cover / overround, full history",
                  "this report: 2026 only"], rows,
                 f"{INS1_SRC} (ins1 overround recomputed on the payout basis, premium ÷ payout − 1); "
                 "reports/eval-01/results.json `temperature.city[...]`, `temperature.city_year[...,year=2026]`")


# ---------------------------------------------------------------------------------------------------------
# Section 7 tables (EVAL-04/05)
# ---------------------------------------------------------------------------------------------------------
STN = ["NYC", "EWR", "TTN", "MDW", "MIA"]


def t_netting() -> str:
    rows = []
    for s in STN + ["pooled"]:
        rows.append([s, c(f"e45:netting.central.{s}", "f2"), c(f"e45:netting.null.{s}", "f3"),
                     f"{c(f'e45:netting.ensemble.{s}.p10', 'f2')}-{c(f'e45:netting.ensemble.{s}.p90', 'f2')}",
                     co(f"e45:netting.zip_level.{s}", "f2"),
                     co(f"e45:netting.participants.p2.{s}", "int"),
                     co(f"e45:netting.leftover_units_per_day.{s}.mean_units", "int"),
                     co(f"e45:netting.leftover_units_per_day.{s}.mean_max_payout_usd", "usdk")])
    return table(["station", "NR central priors", "NR under the null", "NR p10-p90 (1,000 prior draws)", "NR inside one ZIP",
                  "participants (2 %)", "leftover units / day", "leftover max payout / day"], rows,
                 "reports/eval-04-05/results.json `netting.{central,null,ensemble,zip_level,participants.p2,leftover_units_per_day}`")


def t_auction() -> str:
    rows = []
    for s in STN:
        b = f"e45:auction.{s}/station"
        rows.append([s, c(b + ".days", "int"), c(b + ".no_trade_share", "pct0"), c(b + ".clearing_minus_fair_cents", "f2"),
                     c(b + ".hedger_fill_share", "pct0"), c(b + ".house_fill_share", "pct0"), c(b + ".internalisation", "pct0"),
                     c(b + ".hedge_units_mean", "f1")])
    return table(["station (station leg)", "auction days", "no-trade share", "clearing − fair (scalar cents)",
                  "hedger units filled", "house share of fills", "internalised", "Kalshi hedge units / day"], rows,
                 "reports/eval-04-05/results.json `auction.<station>/station`")


def t_capital() -> str:
    rows = []
    for lab, key in [("both legs (headline, M3)", "pooled_both_legs"), ("station leg only", "pooled_station_leg_only"),
                     ("both legs, priced at climatology (D5)", "sensitivity_clim_priced_both_legs"),
                     ("station leg, priced at climatology (D5)", "sensitivity_clim_priced_station_only")]:
        b = f"e45:capital.deploy_detrended.{key}"
        rows.append([lab, c(b + ".H30.n_seasons", "int"), c(b + ".H1.C", "usdk"), c(b + ".H5.C", "usdk"),
                     c(b + ".H30.C", "usdk"), c(b + ".H30.ES99", "usdk"), c(b + ".H30.binding", "str"),
                     c(b + ".H30.ES95_junior", "usdk"), c(b + ".H30.CPC_notional", "f3"), c(b + ".H30.C_over_FC", "f2")])
    return table(["book", "seasons", "C (h = 1)", "C (h = 5)", "C_30", "ES99 (30 d)", "binding", "junior ES95 (30 d)",
                  "C_30 / notional", "C_30 / full collateral"], rows,
                 "reports/eval-04-05/results.json `capital.deploy_detrended.<book>.H{1,5,30}`")


def t_markouts() -> str:
    rows = []
    for s in STN:
        for leg in ["station", "residual"]:
            b = f"e45:markouts.{s}/{leg}"
            rows.append([f"{s} {leg}", c(b + ".hedged.mean", "usd0"), c(b + ".hedged.ci95", "ciusd0"),
                         c(b + ".per_unit_day_usd", "f2"), c(b + ".hedged.worst_day", "usd0"), c(b + ".hedged.win_rate", "pct0")])
    b = "e45:markouts.pooled.hedged"
    rows.append(["pooled", c(b + ".mean", "usd0"), c(b + ".ci95", "ciusd0"), "", c(b + ".worst_day", "usd0"),
                 c(b + ".win_rate", "pct0")])
    return table(["market", "house P&L after hedge, $/day", "95 % CI", "$ per unit-day", "worst day", "win rate"], rows,
                 "reports/eval-04-05/results.json `markouts.<station>/<leg>.hedged`, `markouts.pooled.hedged`")


def t_markout_summary() -> str:
    b = "e45:markouts.pooled.hedged"
    rows = [["mean house P&L per day, primary run", c(b + ".mean", "usd0") + " " + c(b + ".ci95", "ciusd0")]]
    for k, lab in [("resid_trailing5", "same, residual priced on the trailing 5 years (D6, after numbers)"),
                   ("resid_ladder_mu", "same, residual priced off the ladder plus metro-minus-station deltas (D6)"),
                   ("cutoff2h", "same, auction cutoff 2 h before close"), ("coc6", "same, cost of capital 6 %"),
                   ("coc30", "same, cost of capital 30 %")]:
        rows.append([lab, c(f"e45:auction_variants.{k}.mo_hedged_mean_daily", "usd0")])
    rows += [["station legs only, per pooled day (derived)", fmt(CALC["mo_station_per_day"][0](), "usd0")],
             ["worst day / worst 5 days / worst 30 days", f"{c(b + '.worst_day', 'usd0')} / {c(b + '.worst_5day', 'usd0')} / "
              f"{c(b + '.worst_30day', 'usd0')}"],
             ["max drawdown", c(b + ".max_drawdown", "usd0")], ["days", c(b + ".n_days", "int")]]
    return table(["house P&L measure (after the Kalshi hedge, fees in)", "value"], rows,
                 "reports/eval-04-05/results.json `markouts.pooled.hedged`, `auction_variants.<variant>.mo_hedged_mean_daily`; "
                 "station-leg row = Σ `markouts.<station>/station.hedged.total` / `markouts.pooled.hedged.n_days`")


def t_fees() -> str:
    rows = []
    for k, lab in [("bps10", "10 bps of notional (primary)"), ("bps25", "25 bps"), ("bps50", "50 bps"),
                   ("cow50", "50 % of price improvement, capped")]:
        rows.append([lab, c(f"e45:fees.{k}.per_usd_notional", "pct2"), c(f"e45:fees.{k}.per_season_usd", "usdk")])
    return table(["fee rule", "per $ of hedger notional", "per season"], rows,
                 "reports/eval-04-05/results.json `fees.<rule>`")


# ---------------------------------------------------------------------------------------------------------
# Section 8 tables (EVAL-06)
# ---------------------------------------------------------------------------------------------------------
GROUPS = [("G1", "NYC bike (Citi Bike)"), ("G2", "CHI bike (Divvy)"), ("G3", "CHI transit (CTA)"),
          ("G4", "CHI taxi"), ("G5", "NYC taxi (TLC)")]


def t_e06_t2() -> str:
    rows = []
    for g, lab in GROUPS:
        b = f"e06:groups.{g}.primary"
        rows.append([f"{g} {lab}", c(b + ".origin", "str"), c(b + ".eligibility.eligible", "int"), c(b + ".K", "f0"),
                     f"{c(f'e06:verdicts.T2.{g}.heat_rain_median', 'f3')} {c(f'e06:verdicts.T2.{g}.heat_rain_ci', 'ci3')}",
                     c(f"e06:verdicts.T2.{g}.share_pos", "pct0"), c(f"e06:verdicts.T2.{g}.heat_only_median", "f3"),
                     c(b + ".arms.A4.cover_heat_rain_daily.median", "f3"),
                     co(f"e06:groups.{g}.replication.arms.A3.cover_heat_rain_daily.median", "f3")])
    return table(["group", "origin", "units", "K (°F)", "HE_cover heat+rain (A3)", "units > 0", "heat only (Jun-Sep)",
                  "oracle A4", "replication (origin 2024)"], rows,
                 "reports/eval-06/results.json `verdicts.T2.<G>`, `groups.<G>.primary.{origin,eligibility,K,arms.A4}`, "
                 "`groups.<G>.replication.arms.A3`; medians across units, 5-95 % day-block bootstrap")


def t_e06_t4() -> str:
    rows = []
    for g, _ in GROUPS:
        cells = [c(f"e06:verdicts.T4.{g}.short_n.{n}.diff", "f3") for n in [60, 90, 120, 180]]
        rows.append([g] + cells + [f"{c(f'e06:verdicts.T4.{g}.n365_A3', 'f3')} vs {c(f'e06:verdicts.T4.{g}.n365_A1', 'f3')}",
                                   c(f"e06:verdicts.T4.{g}.short_n.60.share_neg_A1", "pct1") + " → " +
                                   c(f"e06:verdicts.T4.{g}.short_n.60.share_neg_A3", "pct1")])
    return table(["group", "A3 − A1, n = 60", "n = 90", "n = 120", "n = 180", "n = 365: A3 vs A1",
                  "units with HE < 0 at n = 60: own → EB"], rows,
                 "reports/eval-06/results.json `verdicts.T4.<G>.short_n.<n>` and `.n365_A{1,3}`")


def t_e06_p1() -> str:
    rows = []
    for g, _ in GROUPS:
        b = f"e06:verdicts.P1.{g}"
        db = f"e06:groups.{g}.placebo.mu_day_block_bootstrap_supplementary"
        rows.append([g, c(b + ".median_he_cover", "f3"), c(b + ".wet_ci", "ci3"),
                     "no" if not R(db + ".heat.excludes_zero") and not R(db + ".wet.excludes_zero") else "yes",
                     pf(R(b + ".pass"))])
    return table(["group", "placebo median HE_cover", "placebo mu_wet, DL interval (pre-registered)",
                  "placebo mu excludes 0 on the day-block interval (Deviation 8)", "P1 by the letter"], rows,
                 "reports/eval-06/results.json `verdicts.P1.<G>`, `groups.<G>.placebo.mu_day_block_bootstrap_supplementary`")


# ---------------------------------------------------------------------------------------------------------
# Section 9 tables (the brief's list: costs, liquidity, revisions, capital)
# ---------------------------------------------------------------------------------------------------------
def t_costs() -> str:
    rows = []
    for lab, b in [("Heat ladder, liquid, all years, 24 h", _m("@LIQ24")), ("Heat ladder, liquid 2025+ (post hoc), 24 h", _m("@L25_24")),
                   ("Heat ladder, liquid, all years, 2 h", _m("@LIQ2")), ("Heat ladder, thin EWR+TTN, 24 h", _m("@THIN24"))]:
        rows.append([lab, c(b + ".premium.est", "f2"), c(b + ".overround.est", "pct1"), c(b + ".spread.est", "f2"),
                     c(b + ".fee.est", "f3"), c(b + ".total_load.est", "pct1")])
    rb = "e01:rain_daily.horizons.24"
    rows.append(["Daily rain binary, 24 h (per $1 payout)", "", fmt(R(rb + ".cost_per_dollar_payout_ex_fee") - 1, "pct1"), "", "",
                 fmt(R(rb + ".cost_per_dollar_payout") - 1, "pct1")])
    rows.append(["Learned hedge G1, 24 h asks, buy side (hedge year 2025)", "", "", "", "",
                 c("e06:verdicts.T3.G1.cost_ratio", "pct1")])
    return table(["instrument", "premium / unit", "overround (ex fees)", "spread cost / unit", "fee / unit", "total load"], rows,
                 "reports/eval-01/results.json `temperature.pooled[...]`, `rain_daily.horizons.24.cost_per_dollar_payout{,_ex_fee}` "
                 "(load = cost − 1); reports/eval-06/results.json `verdicts.T3.G1.cost_ratio`")


def t_liquidity() -> str:
    rows = []
    for yr in [2023, 2024, 2025, 2026]:
        cells = [co(f"e01:temperature.city_year[rule=A,h=24,city={cty},year={yr}].no_offer_share", "pct1")
                 for cty in ["NY", "CHI", "MIA"]]
        rows.append([f"heat ladder 24 h no-offer, {yr}"] + cells)
    d = "e01:depth.ladders"
    rows.append(["max units at ≤ 3c slippage (one 2026-09-29 snapshot)", c(d + ".KXHIGHNY-26SEP30.max_units_3c", "f0"),
                 c(d + ".KXHIGHCHI-26SEP30.max_units_3c", "f0"), c(d + ".KXHIGHMIA-26SEP30.max_units_3c", "f0")])
    rows.append(["monthly rain ladder no-offer at month start", c("e01:rain_monthly.KXRAINNYCM|month_start.no_offer_share", "pct0"),
                 c("e01:rain_monthly.KXRAINCHIM|month_start.no_offer_share", "pct0"),
                 c("e01:rain_monthly.KXRAINMIAM|month_start.no_offer_share", "pct0")])
    rows.append(["pool leftover units / day (2 % participation) vs Kalshi hedge cap per city-day",
                 f"{c('e45:netting.leftover_units_per_day.NYC.mean_units', 'int')} vs {fmt(PRE['e45.hedge_cap_units'][0], 'int')}",
                 f"{c('e45:netting.leftover_units_per_day.MDW.mean_units', 'int')} vs {fmt(PRE['e45.hedge_cap_units'][0], 'int')}",
                 f"{c('e45:netting.leftover_units_per_day.MIA.mean_units', 'int')} vs {fmt(PRE['e45.hedge_cap_units'][0], 'int')}"])
    return table(["measure", "NY / NYC", "CHI / MDW", "MIA"], rows,
                 "reports/eval-01/results.json `temperature.city_year[...].no_offer_share`, `depth.ladders`, `rain_monthly`; "
                 "reports/eval-04-05/results.json `netting.leftover_units_per_day`; hedge cap from eval-04-05 PREREG")


def t_revision() -> str:
    rows = [
        ["Kalshi settled value vs NWS CLI high (2023+)", c("e01:mismatch[city=all,settle_source=all].value_mismatch_share", "pct2"),
         f"{c('e01:mismatch[city=all,settle_source=all].n', 'int')} city-days"],
        ["CLI final at D+1 12:00Z vs latest CLI (payout moves ≥ $0.50 / unit, M4)", c("e45:revision.revision_share_units_weighted", "pct1"),
         f"{c('e45:revision.n_station_days', 'int')} station-days; {c('e45:revision.days_with_multiple_final_products', 'int')} with a reissued final"],
        ["Same-day preliminary CLI vs final (high differs)", c("e45:revision.prelim_vs_final_differs_share", "pct1"), "so N ≥ D+1"],
        ["Station-days with no final CLI by D+1 12:00Z", str(sum(R("e45:revision.missing_final_by_D1_12Z").values())),
         "needs a retry rule"],
        ["CLI settle value vs later GHCN-D TMAX", c("e45:revision.cli_settle_vs_ghcn_tmax_differs_share", "pct2"), ""],
        ["nClimGrid prelim (label + 5 d) vs scaled: Tmax moves ≥ 0.5 °F", c("e45:revision.nclimgrid_prelim_vs_scaled.tmax_moves_ge_0p5F_share", "pct0"),
         f"{c('e45:revision.nclimgrid_prelim_vs_scaled.cell_days_compared', 'int')} cell-days; mean absolute change "
         f"{c('e45:revision.nclimgrid_prelim_vs_scaled.tmax_abs_change_mean_F', 'f2')} °F"],
        ["nClimGrid prelim vs scaled: wet-day flag flips", c("e45:revision.nclimgrid_prelim_vs_scaled.wet_flag_flip_share", "pct1"), ""],
    ]
    return table(["revision measure", "share", "sample"], rows,
                 "reports/eval-01/results.json `mismatch`; reports/eval-04-05/results.json `revision.*` "
                 "(the 'no final by D+1' count sums `revision.missing_final_by_D1_12Z` over stations)")


# ---------------------------------------------------------------------------------------------------------
# Section 11: checklist against the brief
# ---------------------------------------------------------------------------------------------------------
def t_checklist() -> str:
    p3 = "covered (Phase 3)" if DATA.get("e03") is not None else "PENDING (Phase 3 not landed)"
    rows = [
        ["Core Value: better than doing nothing", "§4, §8", "partly: yes for HE_cover at the station; at 24 h asks only on 2025+ days; not shown for a learned business hedge"],
        ["Core Value: cheaper than a bespoke contract", "§9, §11", "NOT measured: we have no bespoke quotes to compare against"],
        ["EVAL-01 five cities, temperature and rain", "§4", "covered; EWR/TTN on 34 days each; rain = daily binary + monthly ladders"],
        ["EVAL-01 hourly candles + recorded order books", "§4, §9", "candles yes; recorded books NO (S3 recorder not readable), one ins1 snapshot only"],
        ["EVAL-01 HE, overround, spread, depth, binning, settlement mismatch", "§4, §9", "covered (depth from one snapshot)"],
        ["EVAL-02 geography basis at nearby stations and grid points", "§5", p3],
        ["EVAL-03 residual bake-off (per-cell PRISM + nClimGrid, regional factor, pairs; temp + rain)", "§6", p3],
        ["EVAL-04 netting at zip / station / metro (CBP NAICS×zip × elasticities)", "§7", "covered; priors LOW confidence; ZBP 2023 used for CBP"],
        ["EVAL-04 what the batch auction leaves for the pool", "§7", "covered (simulated flow, 2 % participation)"],
        ["EVAL-05 capital for the tail / correlated heatwave days", "§7, §9", "covered for the two-leg book with R-A (picked before Phase 3); temperature lists the station leg alone; weekly two-leg rain book sized in §7 (modelled, not built)"],
        ["EVAL-05 house-MM markouts, trading costs", "§7, §9", "covered in simulation; markouts partly a pricing artefact"],
        ["EVAL-05 revision risk (prelim vs final)", "§9", "covered for CLI; nClimGrid measured on 2026 vintages; PRISM not measured"],
        ["EVAL-06 elasticity from stand-in sales (Citi Bike, Divvy, Rossmann, M5 or similar)", "§8", "covered on bikeshare/transit/taxi; Rossmann and M5 NOT used (not near a Kalshi city)"],
        ["EVAL-06 OOS HE vs no hedge vs pooled; days-of-history curve", "§8", "covered; T2 fails"],
        ["EVAL-07 rules before results, every number traced, one-command rebuild", "§3, Appendix B-C", "covered; PDF only if pandoc exists (HTML here)"],
    ]
    return table(["brief line (.planning/PROJECT.md)", "where", "status"], rows,
                 ".planning/PROJECT.md Core Value and Active EVAL-01..07")


# ---------------------------------------------------------------------------------------------------------
# Phase 3 sections (templated)
# ---------------------------------------------------------------------------------------------------------
DESIGNS = [("D0", "station only (baseline)"), ("G1-P", "per-cell PRISM spread"), ("G1-N", "per-cell nClimGrid spread"),
           ("G1-P*", "per-cell PRISM vs ASOS (ins2 form, continuity)"), ("G1-N*", "per-cell nClimGrid vs ASOS (continuity)"),
           ("C1-N", "nClimGrid county-average spread"), ("R-A", "regional factor, ASOS network, equal weight"),
           ("R-P", "regional factor, PRISM disc"), ("R-N", "regional factor, nClimGrid disc"),
           ("R-A-PC", "R-A with frozen PC1 weights (exploratory)"), ("R-N-PC", "R-N with frozen PC1 weights (exploratory)"),
           ("P-A", "nearest station pair"), ("P-A-IDW", "IDW of 3 nearest stations")]

BANNER = ("> **Phase 3 pending.** Phase 3 (geography basis and residual bake-off, reports/eval-03/) had not landed when "
          "this report was built. This section fills itself from reports/eval-03/results.json the next time `make report` "
          "runs after that file exists. Until then, nothing below is a Phase 3 result: it is the pre-registered method "
          "and the prior evidence from ins1 and ins2.\n")


def t_ins2_baseline() -> str:
    rows = []
    for s in STN:
        rows.append([s, c(f"ins2:{s}.n_days", "int"), c(f"ins2:{s}.cells", "int"), c(f"ins2:{s}.he_station", "f2"),
                     c(f"ins2:{s}.he_cell_median", "f2"), c(f"ins2:{s}.he_nearest_cell", "f2"),
                     c(f"ins2:{s}.nearest_cell_km", "f1"), c(f"ins2:{s}.mean_pair_corr", "f2")])
    return table(["station", "days", "cells", "HE at the station", "median cell HE", "nearest-cell HE", "nearest cell (km)",
                  "residual correlation between cells"], rows,
                 "prior/hl-mm-ins/reports/ins2/results.json `<station>.*` (nClimGrid, per-cell exposure hedged with the station ladder, 2026-07-23..09-25)")


def t_ins1_geo() -> str:
    rows = [[k.replace("geo.", "").replace("_", " "), fmt(v, "f2")] for k, v in INS1.items() if k.startswith("geo.")]
    return table(["nearby station hedged with the settlement ladder", "raw HE (ins1)"], rows, INS1_SRC)


def sec5() -> str:
    e03 = DATA.get("e03")
    head = "## 5. Geography basis (EVAL-02)\n\n"
    if e03 is None:
        body = render("5", """{{block:banner}}
**What Phase 3 will measure.** How much of a local exposure the settlement-station leg alone removes at nearby points. Truth is the held-out ASOS station (leave-one-out), never a grid cell, because in ins2 the grid cell was both truth and index and interpolation noise looked like geography. Train on 2024, test on {{pre:e03.test_days|int}} days from 2025-01-01 to 2026-08-31, joint circular block bootstrap with {{pre:e03.block_days|int}}-day blocks. The number reported is HE(D0) at each truth point, against distance.

**What we already know (prior evidence, not Phase 3).** ins1 hedged nearby airports with the settlement ladder over the 2026 summer and found the geography gap dominant:

{{table:ins1_geo}}
ins2 then tried nClimGrid cells around each station. Even the cell nearest the station did much worse than the station itself:

{{table:ins2_baseline}}
Part of that gap is day definition and interpolation noise, not distance (ins2 README, deviation 2). That is why Phase 3 uses same-source residuals and held-out stations as truth.
""")
        return head + body
    return head + render("5", """{{block:e03_meta}}
**Station leg alone at nearby points (D0).** Pooled median HE at held-out truth points within 50 km: temperature {{e03:eval02.temperature.pooled_median_he0|f2}} {{e03:eval02.temperature.pooled_median_he0_ci|ci2}}, rain (weekly) {{e03:eval02.rain.pooled_median_he0|f2}} {{e03:eval02.rain.pooled_median_he0_ci|ci2}}. Compare the station itself in §4 (HE_cover {{@LIQ24.he_cover.est|f2}}).

{{table:e03_he0_market}}
{{fig:fig8_geography}}
Prior evidence for comparison (ins1 raw HE at nearby airports, ins2 nearest-cell HE):

{{table:ins1_geo}}
{{table:ins2_baseline}}
""")


def t_e03_he0_market() -> str:
    rows = []
    for m in STN:
        rows.append([m, c(f"e03:eval02.temperature.by_market.{m}.median_he0", "f2"),
                     c(f"e03:eval02.rain.by_market.{m}.median_he0", "f2")])
    return table(["market", "median HE(D0), temperature", "median HE(D0), rain weekly"], rows,
                 "reports/eval-03/results.json `eval02.<variable>.by_market.<MKT>.median_he0`")


def t_e03_bakeoff(var: str) -> str:
    rows = []
    for d, lab in DESIGNS:
        b = f"e03:bakeoff.{var}.{d}"
        rows.append([f"{d}", lab, c(b + ".n_pairs", "int"), c(b + ".pooled_median_he", "f2"), c(b + ".pooled_median_dhe", "f3"), c(b + ".dhe_ci", "ci3"),
                     c(b + ".share_pairs_dhe_pos", "pct0"), c(b + ".markets_dhe_pos", "int"), c(b + ".pooled_median_eta", "f2"),
                     c(b + ".sd_r_median", "f2"), c(b + ".L_median", "f2"), c(b + ".settleable", "bool"), c(b + ".verdict", "str")])
    return table(["design", "what", "pairs", "pooled median HE", "ΔHE", "ΔHE 95 % CI", "pairs ΔHE > 0", "markets ΔHE > 0", "η",
                  "sd(r)", "loading L (λ = 0.25)", "settleable", "verdict"], rows,
                 f"reports/eval-03/results.json `bakeoff.{var}.<DESIGN>` (pairs = `.n_pairs`; G1-P has a PRISM cell at every "
                 "point since the 2026-10-02 re-pull, Phase 3 deviation 1, resolved)")


def sec6() -> str:
    e03 = DATA.get("e03")
    head = "## 6. Residual designs (EVAL-03)\n\n"
    if e03 is None:
        return head + render("6", """{{block:banner}}
**What Phase 3 will decide.** Which residual contract, if any, closes the gap between the station and the business. The designs are per-cell spreads on PRISM and nClimGrid, a nClimGrid county average, one regional factor per station ("metro minus station") on the ASOS network or a grid disc, the same with frozen PC1 weights, a nearest-station pair and an inverse-distance blend. Temperature is daily; rain is weekly totals.

**The pre-registered pass rule** (03-RESEARCH, to be frozen verbatim as reports/eval-03/PREREG.md). A design survives only if all four hold:
- P1 gain: pooled median ΔHE ≥ {{pre:e03.P1.dhe_min|f2}} with the bootstrap lower bound above zero.
- P2 breadth: ΔHE > 0 at ≥ {{pre:e03.P2.share_min|pct0}} of point pairs and in at least {{pre:e03.P2.markets_min|int}} of the five markets ({{pre:e03.rain_markets_min|int}} for rain).
- P3 efficiency: pooled median η ≥ {{pre:e03.P3.eta_min|f1}}, where η = 2β − 1 is the share of the variance handed to the pool that actually removes variance from the business.
- P4 settleable: a written formula on published data, fixed at sale, first value within {{pre:e03.P4.days_max|int}} days, stated revision policy.
A design with pooled median ΔHE ≤ 0 is killed. The winner is the survivor with the highest pooled median HE; PC1 weights replace equal weights only if they add at least {{pre:e03.pc1.margin|f2}} of HE with a CI that excludes zero. If nothing survives, Phase 7 ships station-only cover plus bespoke residuals by RFQ at a stated premium.

**What is already known.** ins2's per-cell nClimGrid overlay failed its own rule on every cell, and the cell residuals around one station moved together (correlation in the table in §5), so a book of per-cell residuals does not diversify. Phase 4 ran its capital numbers with R-A ("metro minus station" on the ASOS network) as a placeholder residual leg (§7). Those numbers change once Phase 3 picks a design.
""")
    return head + render("6", """{{block:e03_meta}}
**Verdict.** Winner, temperature: {{e03:verdicts.winner.temperature|winner}}. Winner, rain: {{e03:verdicts.winner.rain|winner}}. PC1 weights versus equal weights: HE difference {{e03:verdicts.pc1_vs_equal.he_diff|f3}} {{e03:verdicts.pc1_vs_equal.ci|ci3}}, adopted: {{e03:verdicts.pc1_vs_equal.adopted|bool}}.

Temperature, daily:

{{table:e03_bakeoff_temperature}}
Rain, weekly totals:

{{table:e03_bakeoff_rain}}
G1-P runs on {{e03:bakeoff.rain.G1-P.n_pairs|int}} of {{e03:bakeoff.rain.D0.n_pairs|int}} rain pairs and {{e03:bakeoff.temperature.G1-P.n_pairs|int}} of {{e03:bakeoff.temperature.D0.n_pairs|int}} temperature pairs. Until the 2026-10-02 PRISM re-pull it ran on fewer, because Phase 1 had kept no PRISM cell at some truth points (deviation 1, now resolved); every design now runs on the same pairs. Against R-A, the other rain survivor and the alternate, G1-P is ahead by {{e03:verdicts.winner_vs_next_survivor.rain.he_diff|f3}} HE {{e03:verdicts.winner_vs_next_survivor.rain.ci|ci3}}. Against P-A-IDW, which fails P1 but has the next-highest HE, its lead is {{e03:verdicts.winner_vs_runner_up.rain.he_diff|f3}} {{e03:verdicts.winner_vs_runner_up.rain.ci|ci3}}, a CI that includes zero. The rain gain is concentrated in May-Sep, PRISM's revisions from the early to the final grid are not measured, and the weekly station leg has no liquid Kalshi hedge.

**What this means for the product (seat ruling 2026-09-30).** Temperature cover ships as the station leg alone, with residuals only by RFQ; P-A-IDW is the reference formula for those quotes. Phase 4's capital (§7) used R-A as its residual leg because it ran before this bake-off; it was not re-run. For temperature the station-leg-alone C_30 of {{@DEP.pooled_station_leg_only.H30.C|usdk}} is the figure, next to {{e45:verdicts.M3.C30|usdk}} for the two-leg book. For rain the residual design is G1-P with R-A as the alternate; the weekly two-leg rain book has been capitalised but not built (§7).
""")


def e03_meta_block() -> str:
    return (f"Phase 3 pre-registration frozen {c('e03:meta.prereg_frozen_utc', 'str')}; results written "
            f"{c('e03:meta.written_utc', 'str')}.\n")


# ---------------------------------------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------------------------------------
FIGS: dict[str, tuple[str, str]] = {}


def _save(fig, name: str, caption: str):
    FIG.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(FIG / name, dpi=130)
    plt.close(fig)
    FIGS[name.rsplit(".", 1)[0]] = (name, caption)


def figures():
    cities = ["NY", "CHI", "MIA"]
    years = list(range(2022, 2027))
    # 1. HE_cover and HE_ladder by city-year
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.6), sharey=False)
    for cty in cities:
        xs, hc, hl, lo, hi = [], [], [], [], []
        for y in years:
            try:
                b = R(f"e01:temperature.city_year[rule=A,h=24,city={cty},year={y}]")
            except KeyError:
                continue
            xs.append(y), hc.append(b["he_cover"]["est"]), hl.append(b["he_ladder"]["est"])
            lo.append(b["he_ladder"]["lo"]), hi.append(b["he_ladder"]["hi"])
        ax[0].plot(xs, hc, marker="o", label=cty)
        ax[1].errorbar(xs, hl, yerr=[[h - l for h, l in zip(hl, lo)], [u - h for h, u in zip(hl, hi)]], marker="o",
                       capsize=3, label=cty)
    ax[0].set_title("HE_cover (payout tracks the loss)")
    ax[1].set_title("HE_ladder (after paying the 24 h ask)")
    ax[1].axhline(0, color="grey", lw=0.8)
    for a in ax:
        a.set_xticks(years)
        a.legend(fontsize=8)
    _save(fig, "fig1_he_by_year.png", "HE_cover and HE_ladder by city-year, strike rule A, 24 h before close "
          "(reports/eval-01/results.json `temperature.city_year`; error bars 95 % block bootstrap).")
    # 2. overround by city-year
    fig, ax = plt.subplots(figsize=(6.5, 3.4))
    for cty in cities:
        xs, ov = [], []
        for y in years:
            try:
                ov.append(100 * R(f"e01:temperature.city_year[rule=A,h=24,city={cty},year={y}].overround.est"))
                xs.append(y)
            except KeyError:
                continue
        ax.plot(xs, ov, marker="o", label=cty)
    ax.axhline(100 * PRE["e01.T1.overround_max"][0], color="red", ls="--", lw=1, label="T1 bar")
    ax.set_ylabel("overround at 24 h, %")
    ax.set_xticks(years)
    ax.legend(fontsize=8)
    _save(fig, "fig2_overround_by_year.png", "Overround of the replicating ladder at the 24 h ask by city-year "
          "(reports/eval-01/results.json `temperature.city_year`); dashed line = the T1 bar.")
    # 3. rain Brier by horizon
    fig, ax = plt.subplots(figsize=(5.5, 3.2))
    hs = ["24", "12", "2"]
    ax.bar([i - 0.2 for i in range(3)], [R(f"e01:rain_daily.horizons.{h}.brier_market") for h in hs], 0.4, label="market mid")
    ax.bar([i + 0.2 for i in range(3)], [R(f"e01:rain_daily.horizons.{h}.brier_clim") for h in hs], 0.4, label="climatology")
    ax.set_xticks(range(3), [f"{h} h" for h in hs])
    ax.set_ylabel("Brier score (lower is better)")
    ax.legend(fontsize=8)
    _save(fig, "fig3_rain_brier.png", "Daily rain binary: Brier score of the market mid vs leave-year-out climatology by "
          "horizon (reports/eval-01/results.json `rain_daily.horizons`).")
    # 4. netting
    fig, ax = plt.subplots(figsize=(6.5, 3.4))
    xs = STN + ["pooled"]
    cen = [R(f"e45:netting.central.{s}") for s in xs]
    p10 = [R(f"e45:netting.ensemble.{s}.p10") for s in xs]
    p90 = [R(f"e45:netting.ensemble.{s}.p90") for s in xs]
    nul = [R(f"e45:netting.null.{s}") for s in xs]
    ax.bar([i - 0.2 for i in range(len(xs))], cen, 0.4, yerr=[[c_ - a for c_, a in zip(cen, p10)], [b - c_ for c_, b in zip(cen, p90)]],
           capsize=3, label="central priors (p10-p90 of prior draws)")
    ax.bar([i + 0.2 for i in range(len(xs))], nul, 0.4, label="shrink-to-common null")
    ax.axhline(PRE["e45.M1.nr_min"][0], color="red", ls="--", lw=1, label="M1 bar")
    ax.set_xticks(range(len(xs)), xs)
    ax.set_ylabel("netting ratio")
    ax.legend(fontsize=7)
    _save(fig, "fig4_netting.png", "Share of gross hedge units that cancel inside one station-day auction "
          "(reports/eval-04-05/results.json `netting.{central,ensemble,null}`).")
    # 5. capital
    fig, ax = plt.subplots(figsize=(6.5, 3.4))
    books = [("both legs", "pooled_both_legs"), ("station leg", "pooled_station_leg_only"),
             ("both legs,\nclim-priced", "sensitivity_clim_priced_both_legs"), ("station leg,\nclim-priced", "sensitivity_clim_priced_station_only")]
    vals = [R(f"e45:capital.deploy_detrended.{k}.H30.CPC_notional") for _, k in books]
    ax.bar(range(len(books)), vals, color=["C0", "C0", "C1", "C1"])
    ax.axhline(PRE["e45.M3.cpc_max"][0], color="red", ls="--", lw=1, label="M3 bar")
    ax.set_xticks(range(len(books)), [b for b, _ in books], fontsize=8)
    ax.set_ylabel("C_30 / 30-day pool notional")
    ax.legend(fontsize=8)
    _save(fig, "fig5_capital.png", "30-day pool capital per $ of pool notional; orange = cover priced before the forecast "
          "is known (deviation D5) (reports/eval-04-05/results.json `capital.deploy_detrended.*.H30.CPC_notional`).")
    # 6. elasticity T2 / T3
    fig, ax = plt.subplots(figsize=(6.5, 3.4))
    gs = [g for g, _ in GROUPS]
    med = [R(f"e06:verdicts.T2.{g}.heat_rain_median") for g in gs]
    ci = [R(f"e06:verdicts.T2.{g}.heat_rain_ci") for g in gs]
    ax.bar(range(5), med, 0.5, yerr=[[m - l for m, (l, _) in zip(med, ci)], [h - m for m, (_, h) in zip(med, ci)]], capsize=3,
           label="HE_cover heat+rain (A3)")
    ax.scatter([0, 1], [R("e06:verdicts.T3.G1.ladder_median"), R("e06:verdicts.T3.G2.ladder_median")], color="k", zorder=3,
               label="HE_ladder at 24 h asks")
    ax.axhline(PRE["e06.T2.he_min"][0], color="red", ls="--", lw=1, label="T2 bar")
    ax.axhline(0, color="grey", lw=0.8)
    ax.set_xticks(range(5), [f"{g}\n{l.split(' (')[0]}" for g, l in GROUPS], fontsize=8)
    ax.legend(fontsize=7)
    _save(fig, "fig6_elasticity.png", "Out-of-sample HE of the learned hedge by stand-in group, median across units "
          "(reports/eval-06/results.json `verdicts.T2`, `verdicts.T3`).")
    # 7. learning curve
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.4))
    for k, g in enumerate(["G1", "G2"]):
        lc = R(f"e06:groups.{g}.learning_curve.pooled")
        ns = sorted(int(n) for n in lc)
        for arm, lab in [("A1", "own OLS"), ("A2", "sector prior"), ("A3", "empirical Bayes")]:
            ax[k].plot(ns, [lc[str(n)][arm]["median"] for n in ns], marker="o", label=lab)
        ax[k].axhline(PRE["e06.T2.he_min"][0], color="red", ls="--", lw=1)
        ax[k].set_xscale("log")
        ax[k].set_title(f"{g}: HE_cover heat+rain vs days of history")
        ax[k].legend(fontsize=7)
    _save(fig, "fig7_learning_curve.png", "Learning curve pooled over origins (reports/eval-06/results.json "
          "`groups.<G>.learning_curve.pooled`); dashed line = the T2 bar.")
    # 8. Phase 3 geography (only when eval-03 exists)
    if DATA.get("e03") is not None:
        try:
            pts = R("e03:eval02.points")
            fig, ax = plt.subplots(figsize=(6.5, 3.6))
            for var, mk in [("temperature", "o"), ("rain", "^")]:
                p = [x for x in pts if x.get("variable") == var]
                ax.scatter([x["dist_km"] for x in p], [x["he0"] for x in p], marker=mk, label=var)
            ax.set_xlabel("distance to settlement station, km")
            ax.set_ylabel("HE of the station leg alone")
            ax.legend(fontsize=8)
            _save(fig, "fig8_geography.png", "Geography basis: HE of the station leg at held-out points vs distance "
                  "(reports/eval-03/results.json `eval02.points`).")
        except (KeyError, TypeError):
            MISSING_E03.append("eval02.points")


def fig_md(name: str) -> str:
    if name not in FIGS:
        return "*(figure pending: Phase 3)*\n" if name.startswith("fig8") else ""
    f, cap = FIGS[name]
    return f"![{cap}](figures/{f})\n\n*Figure: {cap}*\n"


# ---------------------------------------------------------------------------------------------------------
# The report text
# ---------------------------------------------------------------------------------------------------------
TEXT_FRONT = """# Localized weather insurance on Kalshi station ladders: evaluation report

Codename `weather-insurance`. Evidence milestone v0.1 (EVAL-07). Built by `make report` from the phase results files listed in Appendix C; every number in the prose is listed with its source key in Appendix B.

## The short version

- **The station ladders track the exposure.** Bought as a replicating ladder, Kalshi's daily high-temperature contracts in New York, Chicago and Miami pay out in line with a capped heat cover at the settlement station: HE_cover {{@LIQ24.he_cover.est|f2}} {{@LIQ24.he_cover|ci2}} pooled over {{@LIQ24.n_citydays|int}} city-days since 2022, and about the same in every year.
- **But at 24 hours they are expensive, and they hedge only the forecast miss.** The 24 h ask already contains tomorrow's forecast. On 2025+ days (a post-hoc pool) the premium-inclusive HE, HE_ladder, is {{@L25_24.he_ladder.est|f2}} {{@L25_24.he_ladder|ci2}}; over all years it is {{@LIQ24.he_ladder.est|f2}}, worse than doing nothing, because 2023-24 markups were noisy. The pre-registered T1 fails on price: overround {{@LIQ24.overround.est|pct1}} against a {{pre:e01.T1.overround_max|pct0}} bar. Today's market is cheaper ({{@L25_24.overround.est|pct1}} on 2025+ days), but that is a post-hoc reading.
- **Netting is modest and rests on priors.** Under the frozen sector priors, {{e45:netting.central.pooled|pct0}} of gross hedge units cancel inside one station-day auction and the M1 test passes with the minimum of {{e45:verdicts.M1.stations_ge_0p25|int}} stations out of five. If sectors mostly move together, netting falls to {{e45:netting.null.pooled|pct1}}. The pre-registered consequence is that the pitch must not lead with netting.
- **Capital leverage holds only with daily forecast repricing.** The pool needs {{e45:verdicts.M3.CPC|f3}} of capital per $ of 30-day notional (both legs; {{@CAP.per_usd_pool_notional_station_leg_only|f2}} for the station leg alone), under the {{pre:e45.M3.cpc_max|f2}} bar. If the cover is priced before the forecast is known, the station-leg number is {{@CAP.per_usd_pool_notional_clim_priced_station_only|f2}}, over the bar.
- **Learning a business's sensitivity failed its bar on public proxies.** Out of sample, the learned hedge took {{e06:verdicts.T2.G1.heat_rain_median|f3}} (NYC bikeshare) and {{e06:verdicts.T2.G2.heat_rain_median|f3}} (Chicago bikeshare) of daily revenue-surprise variance, against a {{pre:e06.T2.he_min|f2}} bar, and about nothing for transit and taxi. At real 24 h asks the NYC bike hedge keeps {{e06:verdicts.T3.G1.ladder_median|f3}}. These datasets are stand-ins for retail sales, not retail sales; whether a café's weather sensitivity is learnable and hedgeable is untested.
{{block:p3front}}
"""

TEXT_S1 = """## 1. Question and setup

The brief asks whether a small business can hedge the weather at its own address with Kalshi's liquid station contracts plus a small residual contract, better than doing nothing and cheaper than a bespoke contract. This report pulls together the numbers from the evaluation phases that answer parts of that. Each phase froze its rules (sample, method, pass/fail thresholds) before producing a number and logged every change afterwards. §3 lists all of them.

The policy under test is the ins1 heat cover: it pays $1 for each °F the daily high at the settlement station goes above a strike K, capped at {{e01:meta.cap|f0}} °F. The hedge is the Kalshi daily high-temperature ladder that replicates it, bought at real hourly YES asks with Kalshi's taker fee, 24 h, 12 h or 2 h before the market closes.

Two hedge-effectiveness numbers appear throughout, and they answer different questions:
- **HE_cover** = 1 − var(exposure − ladder payout) / var(exposure). Does the ladder's payout track the loss?
- **HE_ladder** = 1 − var(exposure − (ladder payout − premium − fees)) / var(exposure). After paying the price at the decision time, is the buyer's result steadier than doing nothing?

HE = 1 removes all the variance, 0 removes none, and below 0 adds variance. Brackets after a number are 95 % bootstrap intervals (5-95 % for Phase 5); point estimates decide pass or fail.

| phase | brief item | results | status |
|---|---|---|---|
| Phase 2 | EVAL-01 station hedge quality | reports/eval-01/ | done |
| Phase 3 | EVAL-02 geography basis, EVAL-03 residual bake-off | reports/eval-03/ | {{block:p3status}} |
| Phase 4 | EVAL-04 netting, EVAL-05 pool economics | reports/eval-04-05/ | done |
| Phase 5 | EVAL-06 learning a business's sensitivity | reports/eval-06/ | done, with seat rulings made after the results |
"""

TEXT_S2 = """## 2. Data

All data is free and was pulled keyless and read-only. The full manifest, with URLs, bytes, md5s and pull times, is data/manifests/DATA.md; the day and settlement conventions live only in docs/CONVENTIONS.md.

- **Kalshi markets and hourly candles** ({{man:D1.series|int}} weather series in the five cities; {{man:D1.markets|int}} markets and {{man:D1.candle_rows|int}} candle rows). Phase 2 used every settled daily high ladder for New York ({{e01:meta.date_range.NY[0]|str}} to {{e01:meta.date_range.NY[1]|str}}), Chicago/Midway (same span), Miami (from {{e01:meta.date_range.MIA[0]|str}}), and EWR and TTN (from {{e01:meta.date_range.EWR[0]|str}}), plus {{e01:rain_daily.n_markets|int}} daily rain binaries.
- **Order books.** Kalshi keeps no book archive. The hl-mm recorder's S3 prefix was not readable from this Mac when Phase 2 ran (anonymous access denied, the default profile's session expired), so depth comes from one snapshot: {{e01:depth.snapshot|str}}.
- **NWS climate reports (CLI)** for the five settlement stations ({{man:D4.cli_rows|int}} rows, 2023 onward), used as the settlement-grade value where Kalshi's own value is missing; IEM ASOS daily summaries for {{man:D3.stations|int}} stations; the IEM AFOS archive of every CLI issuance ({{e45:revision.n_products|int}} products) for the revision test.
- **GHCN-Daily** station records back to the 1950s for the capital scenarios (the joint five-station history starts in 1959; the two-leg book uses 2000-2025, deviation D3).
- **Census ZIP Business Patterns 2023 and SUSB 2022** for the business population: {{e45:population.small_business.est_small|int}} small establishments in the priors' sectors, {{e45:population.rows|int}} population rows.
- **nClimGrid-Daily prelim vintages** from the AWS mirror ({{e45:revision.nclimgrid_prelim_vs_scaled.n_vintages|int}} vintages) for the gridded revision measurement.
- **Sales stand-ins (Phase 5).** Citi Bike ({{e06:panels.G1.units_total|int}} stations), Divvy ({{e06:panels.G2.units_total|int}}), CTA 'L' ({{e06:panels.G3.units_total|int}}), Chicago taxi ({{e06:panels.G4.units_total|int}} community areas) and NYC TLC taxi ({{e06:panels.G5.units_total|int}} zones), daily from {{e06:panels.G1.first|str}}. Raw trips were streamed and aggregated, never stored.
- **Grids for Phase 3** (PRISM 4 km cells, nClimGrid, GHCN-D nearby stations; DATA.md D7-D10). Phase 1 kept 40 km discs around each settlement station and Phase 3 topped up station cells and county averages. Some truth points sat outside those discs and had no PRISM cell (Phase 3 deviation 1); a PRISM re-pull on 2026-10-02 added those cells, so the PRISM designs now run on every pair (§6).

Conventions that matter for reading the numbers: the join key is the NWS climate day (midnight to midnight local standard time); every decision time is computed from each market's own close time, never a constant; the settled value is Kalshi's expiration value, then the CLI; a grid labelled D describes calendar day D−1; and the fee formula (0.07 × C × P × (1 − P) per order, rounded up to the cent) is medium confidence because Kalshi's fee PDF could not be fetched.
"""

TEXT_S3 = """## 3. Pre-registration ledger

Every test below was written down before the phase produced a number. The verdict column is read from the phase's results.json, not typed by hand. Fails are listed with the passes.

{{table:ledger}}
### Deviations, with timestamps

Changes made after a freeze, in the order the phases logged them. "After numbers" means the change was made after the phase had seen at least one result. The seat's rulings on Phase 5 were made after the results and are reported as post hoc.

{{table:deviations}}
"""

TEXT_S4 = """## 4. Station hedge quality (EVAL-01)

**The payout works.** Across all years and all three liquid cities, the replicating ladder's payout tracks the capped heat cover at the settlement station with HE_cover {{@LIQ24.he_cover.est|f2}}. Binning (the ladder pays in 2 °F steps, the cover is linear) costs little: RMSE {{@LIQ24.binning_rmse|f2}} per unit. The settled value matches the NWS climate report on all but {{e01:mismatch[city=all,settle_source=all].value_mismatch_share|pct1}} of {{e01:mismatch[city=all,settle_source=all].n|int}} city-days since 2023.

{{table:e01_main}}
**The price is the problem, and it depends on the year.** T1 needed HE_cover ≥ {{pre:e01.T1.he_min|f2}} and overround ≤ {{pre:e01.T1.overround_max|pct0}}. It fails on the second half: {{@LIQ24.overround.est|pct1}} {{@LIQ24.overround|cipct1}} pooled. The pooled number mixes three markets. In 2023-24 the ladders were marked up heavily and often could not be bought at all; from 2025 they are close to fair. The 2025+ pool below was added after seeing the numbers (deviation 6) and is not a verdict.

{{table:e01_years}}
{{fig:fig1_he_by_year}}
{{fig:fig2_overround_by_year}}
**Why HE_ladder is so much lower than HE_cover.** Bought 24 h ahead, the ask already knows tomorrow's forecast. A buyer swaps the weather swing for a price swing of about the same size and keeps only the forecast miss. On 2025+ days that leaves HE_ladder {{@L25_24.he_ladder.est|f2}}, close to the {{pre:e01.T1b.expect|f1}} ins1 suggested; pooled over the noisy 2023-24 markups it is {{@LIQ24.he_ladder.est|f2}}. At 2 h the price already knows the answer, so HE_ladder is {{@L25_2.he_ladder.est|f2}} on 2025+ days. The gap HE_cover − HE_ladder ({{calc:gap_2025|f2}} on 2025+ days) is the forecast-level risk. On the default path, where the business buys one fixed-price policy and the house hedges daily, the house carries that risk; §7 prices it.

{{table:e01_horizons}}
**Fixed strike.** A policy with a strike set in advance (rule B: the trailing 7-day mean) fits the ladder less well: the high settles outside the ladder's range on {{@B24.tail_outside_share|pct1}} of days and the ladder buys nothing at all on {{@B24.unspanned_share|pct0}} of days. HE_ladder is {{@B24.he_ladder.est|f2}} pooled, {{@B25.he_ladder.est|f2}} on 2025+ days, because more of the exposure is predictable level that the 24 h price charges for.

{{table:e01_ruleb}}
**Thin ladders.** EWR and TTN (T2) fail as ins1 said: {{e01:verdicts.T2.EWR.overround|pct0}} and {{e01:verdicts.T2.TTN.overround|pct0}} overround at 24 h, on {{e01:meta.n_citydays.EWR|int}} days each. They are only executable near the close. A business near Newark or Trenton should be hedged on the NYC ladder plus a residual (Phase 3).

**Liquidity.** T4 fails on 2024 alone: the worst city-year, {{e01:verdicts.T4.worst|str}}, had no offer on at least one needed rung on {{e01:verdicts.T4.worst_share|pct1}} of days. In 2025 and 2026 it is at most {{e01:verdicts.T4.per_city_year.NY 2025|pct1}}. Depth rests on one book snapshot: at ≤ 3c of slippage the thinnest needed rung caps a policy at {{e01:depth.ladders.KXHIGHNY-26SEP30.max_units_3c|f0}} units in New York, {{e01:depth.ladders.KXHIGHCHI-26SEP30.max_units_3c|f0}} in Chicago and {{e01:depth.ladders.KXHIGHMIA-26SEP30.max_units_3c|f0}} in Miami, i.e. a few dozen dollars per °F per city-day.

{{table:depth}}
**Settlement source.** Against the official climate report, the settlement leg is almost exact:

{{table:mismatch}}
**Rain.** The daily "any rain" binary passes T3 easily: the market's 24 h Brier score is {{@RAIN24.brier_market|f3}} against {{@RAIN24.brier_clim|f3}} for climatology. It costs ${{@RAIN24.cost_per_dollar_payout|f2}} per $1 of payout at the 24 h ask including fees, and for a wet-day exposure HE_cover is {{@RAIN24.he_wet.he_cover.est|f2}} but HE_ladder only {{@RAIN24.he_wet.he_ladder.est|f2}}, the same forecast effect as for heat. Trace days settle YES {{e01:rain_daily.trace_yes_share|pct0}} of the time, but that is the all-series figure: it pools {{e01:rain_daily.trace_days|int}} trace days across every rain series in the sample ({{e01:rain_daily.n_markets|int}} markets, 2021 to 2026), mostly from the older KXRAINNYC series. The KXRAIN series the house hedges with behaved differently. From July to September 2026 it settled all {{trace:trace_days|int}} trace days NO, all {{trace:measurable_days|int}} measurable-rain days YES and all {{trace:dry_days|int}} dry days NO, across {{trace:settled_markets|int}} settled markets in New York, Chicago and Miami (reports/eval-01/trace_kxrain_2026.md). So the rain cover pays on measurable rain only ({{pre:rain.measurable_min_in|f2}} in or more) and counts a trace as dry. The cover and the hedge treat a trace the same way. With the rule the product actually uses (trace = dry), HE_wet is {{sens:rain_daily_dry.horizons.24.he_wet.he_cover.est|f2}} as HE_cover (primary {{@RAIN24.he_wet.he_cover.est|f2}}) and {{sens:rain_daily_dry.horizons.24.he_wet.he_ladder.est|f2}} as HE_ladder (primary {{@RAIN24.he_wet.he_ladder.est|f2}}) at 24 h, and the Brier gain over climatology is {{sens:rain_daily_dry.horizons.24.brier_gain|f3}} (primary {{@RAIN24.brier_gain|f3}}). The market's own Brier score does not use the wet rule and stays at {{sens:rain_daily_dry.horizons.24.brier_market|f3}}, so T3 still passes. The primary numbers stay as registered; this is a labelled sensitivity run (reports/eval-01/sensitivity_trace_dry.md). Monthly rain ladders are not usable as insurance yet: at the start of the month most strikes have no offer.

{{table:rain}}
{{table:rain_monthly}}
{{fig:fig3_rain_brier}}
**Against ins1.** ins1 found HE {{ins1:he_lo|f2}}-{{ins1:he_hi|f2}} and overpay up to {{ins1:overpay_hi|pct0}} on {{ins1:n_citydays|int}} city-days in the 2026 summer and passed T1. The same engine reproduces ins1's New York premium and payout within {{e01:ins1_check.payout_dev|pct1}} (check in §3). On the full history the fit holds and the price does not: ins1 looked at the cheapest stretch the market has had. ins1's "overpay" for New York divides by the premium; on the payout basis used here it is {{calc:overround_ins1_nyc_payout_basis|pct0}}. ins1 counted {{ins1:mismatch_days|int}} settlement mismatches in {{ins1:n_citydays|int}} days ({{calc:mismatch_pct_ins1|pct1}}), but against IEM ASOS, which ran about half a degree low before 2025-10; against the CLI the mismatch is {{e01:mismatch[city=all,settle_source=all].value_mismatch_share|pct1}}. ins1 put depth at {{ins1:depth_units_lo|int}}-{{ins1:depth_units_hi|int}} units without sizing by rung; the rung-level sizing gives more.

{{table:ins1_compare}}
"""

TEXT_S7 = """## 7. Netting and pool capital (EVAL-04, EVAL-05)

Phase 4 built a synthetic business population around each settlement station from Census ZIP Business Patterns and published sector weather sensitivities, had {{pre:e45.participation|pct0}} of small establishments hedge every warm-season day, ran one uniform-price auction per station-leg-day on real Kalshi-era days, and measured what the pool is left holding. The residual leg in these runs is R-A ("metro minus station" on the ASOS network), picked before Phase 3 ran. Phase 3 (§6) found no temperature residual that clears its bar, so the listed temperature product is the station leg alone (C_30 {{@DEP.pooled_station_leg_only.H30.C|usdk}}, next to {{e45:verdicts.M3.C30|usdk}} for the two-leg book below). Phase 4 has no weekly rain leg, so the rain residual Phase 3 picked is not in these numbers.

**Netting.** With the central priors, {{e45:netting.central.pooled|pct0}} of gross units cancel (Miami {{e45:netting.central.MIA|f2}}, Central Park {{e45:netting.central.NYC|f2}}, Midway {{e45:netting.central.MDW|f2}}). EWR ({{e45:netting.central.EWR|f2}}) and TTN ({{e45:netting.central.TTN|f2}}) miss the bar on September 2026 alone. M1 passes with the minimum of three stations out of five. Across {{pre:e45.ensemble_draws|int}} prior draws the pooled number ranges {{e45:netting.ensemble.pooled.p10|f2}}-{{e45:netting.ensemble.pooled.p90|f2}}, and {{e45:netting.ensemble_M1_material_share|pct0}} of draws still pass M1. But if sector sensitivities are mostly common (the best US daily evidence points that way), netting falls to {{e45:netting.null.pooled|f3}} (M2), and rain nets to about zero because almost every sector loses on wet days. Netting inside one ZIP is roughly half the station number ({{e45:netting.zip_level.NYC|f2}} at Central Park), so the station, not the neighbourhood, is the natural pool.

{{table:netting}}
{{fig:fig4_netting}}
**What the pool carries.** Under the central priors the long-heat businesses (liquor and convenience stores, snack bars, HVAC contractors) outweigh the short-heat ones everywhere, so the house ends up buying heat cover. Around Central Park that leaves about {{e45:netting.leftover_units_per_day.NYC.mean_units|int}} $1/°F units a day, {{e45:netting.leftover_units_per_day.NYC.mean_max_payout_usd|usdk}} of maximum payout, against a Kalshi hedge capped at {{pre:e45.hedge_cap_units|int}} units per city-day. The house cannot lay the flow off at today's depth; capital, not hedging, is the business.

**The auction works mechanically.** Every station-leg-day cleared, most hedger units filled, and the clearing price sat under a cent (scalar) below Kalshi-implied fair value because the leftover is on the sell side. The clearing function conserved units and cash in its property test on random books (tests/test_clear_money.py).

{{table:auction}}
**Capital.** Revaluing the pool's average book on joint-date history, the 30-day capital is {{e45:verdicts.M3.C30|usdk}}: the worst historical 30-day window, which binds ahead of the 30-day ES99 of {{e45h:ES99_30d_usd|usdk}}. That is {{e45:verdicts.M3.CPC|f3}} per $ of pool notional (M3 passes) and {{@CAP.C_over_full_collateral|f2}} of full collateral. The junior layer at ES95 is {{e45h:junior_ES95_30d_usd|usdk}}, {{calc:junior_share_pct|pct0}} of C_30. Three things make the headline look better than it is. The residual leg has a large notional and small risk, so it inflates the denominator: the station leg alone is {{@CAP.per_usd_pool_notional_station_leg_only|f2}}. The scenarios price the cover daily at a forecast-based fair value; priced before the forecast is known (deviation D5), the station leg needs {{@CAP.per_usd_pool_notional_clim_priced_station_only|f2}}, over the bar, and both legs {{@CAP.per_usd_pool_notional_clim_priced_both_legs|f2}}. And the worst-window floor rests on {{@DEP.pooled_both_legs.H30.n_seasons|int}} joint seasons for the two-leg book. So the leverage story holds only if the cover is repriced every day off the forecast.

{{table:capital}}
{{fig:fig5_capital}}
**Backtest (M5).** The capital model's 1-day VaR99, fit on 1951-2020, was beaten {{e45:verdicts.M5.kupiec.x|int}} time in {{e45:verdicts.M5.kupiec.n|int}} Kalshi-era days against {{e45:verdicts.M5.kupiec.expected|f0}} expected. Kupiec rejects (p = {{e45:verdicts.M5.kupiec.p_value|f3}}) in the conservative direction: the persistence forecast in the scenarios is worse than the market's forecast, so the model over-reserves. The worst realised 30-day loss was {{e45:verdicts.M5.worst_realized_30day_loss|usdk}} against a backtest C_30 of {{e45:verdicts.M5.C30_backtest_model|usdk}}.

**Season basis and the junior layer (added 2026-09-30; modelled).** C_30 covers a 30-day window, and a whole summer can lose more. Phase 4's junior add-on replays {{e45j:model.n_seasons|int}} seasons: the worst modelled summer (2009) loses {{calc:season_worst_loss|usdk}} on the simulated book, against C_30 of {{e45j:model.C30_check|usdk}}. On a season basis the same capital carries {{calc:season_book_fraction|f2}} of the simulated book, which is {{calc:cpc_season|f2}} of capital per $ of pool notional against {{e45:verdicts.M3.CPC|f3}} on the 30-day basis (M3). SPEC now caps writing at capital ÷ worst modelled season loss and always states both horizons. With senior paid {{e45j:senior_share|pct0}} of kept margin (SPEC's 30 bps of gross premium approximates this) and a {{e45j:treasury_cuts[0]|pct0}} treasury cut, the junior layer's modelled return on its {{e45j:capital.J0|usdk}} is {{e45j:model.splits.margin_t10.boot_median|pct0}} in the median season, {{e45j:model.splits.margin_t10.boot_p05_1in20|pct0}} in a one-in-twenty season ({{e45j:model.splits.margin_t10.sens_whole_season.p05_1in20|pct0}} resampling whole summers) and {{e45j:model.splits.margin_t10.hist_worst|pct0}} in the worst historical season (2009). Past a total loss the junior layer is gone and senior pays. These come from a 7-day block bootstrap on the capital scenario, not from observed seasons (reports/eval-04-05/junior_returns.md).

**House markouts are not a result to lean on.** Pooled house P&L after the Kalshi hedge was {{e45:markouts.pooled.hedged.mean|usd0}} a day {{e45:markouts.pooled.hedged.ci95|ciusd0}}. Almost all of it comes from the residual legs ({{calc:mo_resid_per_day|usd0}} per pooled day), mostly Central Park's ({{e45:markouts.NYC/residual.hedged.mean|usd0}} a day on the days it traded), and that is a pricing artefact: Central Park reads cool against its airport neighbours and the gap has grown, so a long climatology underprices the residual. Priced on the trailing five years, pooled house P&L drops to {{e45h:house_markout_mean_daily_usd.resid_trailing5|usd0}} a day. The station legs net to about {{calc:mo_station_per_day|usd0}} per pooled day: the house loses at NYC, EWR and TTN and wins at Midway and Miami, which follows the sign of the Kalshi mid's bias in each city. The worst day is {{calc:mo_worst_over_mean|f0}} times the mean daily P&L; ins1's sell-side test found worst days {{ins1:V1.worst_over_mean_lo|int}}-{{ins1:V1.worst_over_mean_hi|int}} times the mean, so the tail shape is familiar. Pool return on C_30 was {{e45:pool_return.mean_season_return_on_C30|pct0}} a season in the primary run and {{e45:pool_return.mean_season_return_on_C30_resid_trailing5|pct0}} with the trailing-five-year residual price; neither is a pre-registered verdict.

{{table:markouts}}
**Fees.** At 10 bps of notional on hedger fills, the protocol earns {{e45:fees.bps10.per_season_usd|usdk}} a season on the simulated flow; a rule that takes half of each hedger's price improvement earns {{e45:fees.cow50.per_usd_notional|pct2}} of notional ({{e45:fees.cow50.per_season_usd|usdk}} a season), because hedger limits carry up to a quarter of loading and the uniform price hands most of it back.

{{table:fees}}
**A weekly rain book (added 2026-09-30; modelled).** Rain was run as its own two-leg book: wet-day cover, a station leg on the daily Kalshi rain markets and a residual leg on PRISM grid cells (reports/eval-04-05/rain_book.json; rules frozen in PREREG-rain.md first). Almost nothing nets: {{rain:netting.central.pooled|f3}} of units cancel, because nearly every sector loses on wet days. At {{pre:e45.participation|pct0}} take-up the pool is short {{calc:rain_leftover_total|usdk}} of payout on each wet day across the five cities. Kalshi's daily rain markets can absorb about {{calc:rain_depth_total|int}} contracts a day against about {{calc:rain_need_total|int}} needed, so they are roughly {{calc:rain_thin_x|int}} times too thin to lay it off. That depth is a volume proxy ({{pre:rain.depth_share|pct0}} of pre-cutoff volume), because no rain order-book history exists. The house carries it. The 30-day capital is {{rain:capital.two_leg_joint.H30.C|usdk}} on the 2024-26 window, against {{e45h:C30_usd|usdk}} for Phase 4's heat book. That is {{rain:R2.CPC|f2}} of 30-day notional, and {{rain:capital.station_long_1999_2025.H30.C|usdk}} for the station leg on 1999-2025. The whole-season figure is {{rain:capital.two_leg_joint.H153.C|usdk}}. The residual leg adds little capital: ×{{rain:R3.ratio|f2}} as priced, ×{{rain:D1_absorb_all.ratio30|f2}} if the house wrote every residual unit. With senior paid out of the margin we keep, the junior layer returns {{rain:junior.model_MaySep.splits.margin_t10.median|pct0}} in a median May-Sep season and {{rain:junior.model_MaySep.splits.margin_t10.p05_1in20|pct0}} in a one-in-twenty one. The three-season test fails under all four splits ({{rain:R5.margin_t10.three_season_sum_p05|pct0}} at the fifth percentile on the kinder one). The two observed full years were positive on that rule ({{rain:junior.observed_all_year.margin_t10.2025.junior_return|pct0}} in 2025, {{rain:junior.observed_all_year.margin_t10.2026.junior_return|pct0}} in 2026), but they are mostly New York and short.
"""

TEXT_S8 = """## 8. Learning a business's sensitivity (EVAL-06)

Phase 5 asked whether a year of daily sales is enough to learn how weather moves a business's revenue, prescribe a heat call plus a wet-day binary, and cut next year's revenue surprise. No public retail sales panel sits near a Kalshi city, so it used stand-ins: bikeshare station starts, transit entries and pooled taxi fares. **These are demand proxies, not a shop's revenue.** Bikeshare is far more weather-driven than a café, so its numbers are an upper bound, not a small-business estimate. The product hypothesis, that a café's heat and rain sensitivity is learnable and hedgeable, is untested on real sales; that is what a pilot is for.

**T2 fails in both bike groups, in both hedge years.** The empirical-Bayes hedge (A3) removes {{e06:verdicts.T2.G1.heat_rain_median|f3}} {{e06:verdicts.T2.G1.heat_rain_ci|ci3}} of daily revenue-surprise variance for Citi Bike and {{e06:verdicts.T2.G2.heat_rain_median|f3}} {{e06:verdicts.T2.G2.heat_rain_ci|ci3}} for Divvy, about a third of the {{pre:e06.T2.he_min|f2}} bar. Transit and taxi get about nothing. Almost all of the bike cover comes from the rain leg; the summer heat-only number is {{e06:verdicts.T2.G1.heat_only_median|f3}} for Citi Bike. The limit is the instruments, not the estimator: an oracle fitted on the hedge year itself reaches only {{e06:groups.G1.primary.arms.A4.cover_heat_rain_daily.median|f3}} (G1) and {{e06:groups.G2.primary.arms.A4.cover_heat_rain_daily.median|f3}} (G2). A heat call above K plus a wet-day binary misses cold-side temperature, rain amount, lags and ordinary noise.

{{table:e06_t2}}
{{fig:fig6_elasticity}}
**T3 fails too.** At real 24 h Kalshi asks with fees, the Citi Bike hedge keeps HE_ladder {{e06:verdicts.T3.G1.ladder_median|f3}} {{e06:verdicts.T3.G1.ladder_ci|ci3}}, and the buy side cost {{e06:verdicts.T3.G1.cost_ratio|pct0}} of payout over the hedge year, over the {{pre:e06.T3.cost_max|pct0}} cap. The same forecast effect as in §4: the 24 h ask keeps about {{e06:groups.G1.primary.ladder_transferable_share.A3_heat_rain|f2}} of the cover, and the gap ({{calc:e06_gap_G1|f3}} for G1) is forecast-level risk that the default house-hedge path would carry.

**T1 fails for Citi Bike, and the seat overruled the pre-registered stop.** The wet-day effect is large and precise (the wet-day effect on starts is {{e06:verdicts.T1.G1.mu_wet|pct1}}), but the heat slope above K = 75 °F is indistinguishable from zero, because Citi Bike starts rise, stay flat through the hot range and drop only on the hottest days, and one slope above K averages that to nothing. The pre-registration said a T1 fail means stop. The seat ruled after the results that the join is sound and the instrument is the problem, so the G1 results stand with a flag (post hoc, 05-SEAT-RULINGS.md).

**P1 fails by the letter; the seat adopted a corrected interval after the results.** The placebo (another year's weather on the same sales) gives a median HE at or below {{pre:e06.P1.he_max|f2}} in every group, so the controls are not passing seasonality off as weather. But the pre-registered DerSimonian-Laird interval calls the placebo group means "significant" everywhere, because it treats units as independent while every unit in a city shares the same weather days. A joint day-block bootstrap (Deviation 8, added after a trial number) puts every placebo mean across zero and keeps the real wet effects significant (Citi Bike {{e06:groups.G1.primary.mu_day_block_bootstrap_supplementary.wet.p025|f3}} to {{e06:groups.G1.primary.mu_day_block_bootstrap_supplementary.wet.p975|f3}}). The seat adopted it as the primary interval, post hoc. Under it, Divvy's heat mean also loses significance.

{{table:e06_p1}}
**T4 fails by the letter, but shrinkage never hurt the bike groups.** The pre-registered rule needed empirical Bayes to beat own-history estimates by {{pre:e06.T4.gain_min|f2}} at every short history. The gain falls under that at n = 180 for Citi Bike ({{e06:verdicts.T4.G1.short_n.180.diff|f3}}) and at n = 120 and n = 180 for Divvy. Yet empirical Bayes was ahead at every history length in G1-G4, and it cut the share of Citi Bike stations with a negative HE at n = 60 from {{e06:verdicts.T4.G1.short_n.60.share_neg_A1|pct0}} to {{e06:verdicts.T4.G1.short_n.60.share_neg_A3|pct1}}. The portal ships the registered rule (own estimates after n*); "always shrink" is the candidate for the next pre-registration (seat ruling, post hoc).

{{table:e06_t4}}
**T5 (days of history).** For bikes, own estimates clear the descriptive bar from {{e06:verdicts.T5.G1.n_star_A1|int}} days of history (Citi Bike) and {{e06:verdicts.T5.G2.n_star_A1|int}} (Divvy); with a sector prior the bar is met from day one. Transit and taxi never clear it.

{{fig:fig7_learning_curve}}
**What the pre-registered kill rule says.** T2 failed for both bike groups, so the portal shows the elasticity as advisory only and the decks may not claim that a learned hedge beats doing nothing. What can be said honestly: rain sensitivity is real and learnable for bikeshare, and a wet-day hedge learned from a year of sales took between {{calc:bike_he_min|pct0}} and {{calc:bike_he_max|pct0}} out of daily revenue-surprise variance out of sample, in two cities and two hedge years. The replication year (origin 2024) gives the same picture ({{e06:groups.G1.replication.arms.A3.cover_heat_rain_daily.median|f3}} and {{e06:groups.G2.replication.arms.A3.cover_heat_rain_daily.median|f3}}).
"""

TEXT_S9 = """## 9. Costs, liquidity, revisions, capital

The brief lists these four as the ways a hedge can fail even when the payout fits. One table each; every cell is read from a results.json path named under the table.

### 9.1 Costs

{{table:costs}}
### 9.2 Liquidity

{{table:liquidity}}
### 9.3 Revisions and settlement source

The station leg settles cleanly: settle on the latest final CLI at D+1 12:00Z and nothing later changed a payout. The same-day preliminary report differs from the final on {{e45:revision.prelim_vs_final_differs_share|pct1}} of days, so settlement must wait for D+1. Gridded data is different: an nClimGrid prelim value five days after the label differs from the scaled file by at least half a degree on {{e45:revision.nclimgrid_prelim_vs_scaled.tmax_moves_ge_0p5F_share|pct0}} of cell-days, so anything settled on nClimGrid must wait for the scaled file. PRISM revisions were not measured (PRISM keeps no prior versions).

{{table:revision}}
### 9.4 Capital and the house's P&L

The capital table is in §7; the per-horizon numbers are repeated here with the house's P&L after the Kalshi paper hedge, because the brief asks for them together.

{{table:capital}}
{{table:markout_summary}}
"""

TEXT_S10 = """## 10. What the numbers mean for the product

**The station leg is a real payout, and it is sold at the forecast.** If a business near Central Park, Midway or Miami airport wants money on hot days, the Kalshi ladder pays it: the payout tracks the loss about {{@LIQ24.he_cover.est|f2}} of the way and settles on the official number. What the ladder cannot do is sell tomorrow's heat at last month's price. Bought the day before, it only moves the forecast miss, which on today's market is about {{@L25_24.he_ladder.est|f2}} of the variance. A business that buys the ladder itself (the fallback path) gets that, not {{@LIQ24.he_cover.est|f2}}.

**So the default product has to be one fixed-price policy with the house hedging daily, and the house is then an insurer carrying forecast risk.** That is where the {{@LIQ24.he_cover.est|f2}} comes from. The capital to carry it looks affordable only if the house reprices every day off the forecast ({{@CAP.per_usd_pool_notional_station_leg_only|f2}} of notional on the station leg); priced once up front it is {{@CAP.per_usd_pool_notional_clim_priced_station_only|f2}}. And the house cannot pass the flow to Kalshi: at {{pre:e45.participation|pct0}} participation the leftover around Central Park is about {{e45:netting.leftover_units_per_day.NYC.mean_units|int}} units a day against a hedge cap of {{pre:e45.hedge_cap_units|int}}. The protocol is a capitalised pool that uses Kalshi for pricing and some hedging, not a pass-through.

**Netting is a bonus, not the pitch.** It is material only under our sector priors and nearly vanishes if businesses respond to weather alike. The decks should lead with the pool.

**The "we learn your sensitivity" step is not proven.** On the best stand-ins we have, it found a real rain effect and almost no usable heat effect, and it removed a small share of revenue noise. The portal should say the estimate is advisory. The only way to test the actual claim is a pilot with real sales from a few weather-exposed shops.

**Where it stands for a first pilot.** Rain-day cover on Kalshi's daily binary is the cleanest thing to sell (the market beats climatology easily, at about a {{calc:rain_load|pct0}} load), with a trace counted as dry, the way the Kalshi contract settles. Heat cover near a liquid station works on the payout side, with the forecast risk priced into a fixed premium. {{block:p3product}}
"""

TEXT_S11 = """## 11. Caveats and gaps

**Caveats that apply to the numbers above.**
- Executable prices come from hourly candles, not order books. A missing hour is read as "no change". Median staleness at 24 h is about an hour ({{@LIQ24.stale_median_h|f1}} h).
- Depth is one top-of-book snapshot from 2026-09-29. Nothing about depth in 2022-25 or intraday.
- The fee formula is medium confidence and applied in every year.
- The 2025+ pool, the climatology-priced capital row and the residual fair-value sensitivities were added after seeing numbers. They are labelled wherever they appear.
- Phase 4's sector priors are low confidence; M1 passes with the minimum number of stations; EWR and TTN rest on one September.
- The capital tail is one worst window on {{@DEP.pooled_both_legs.H30.n_seasons|int}} joint seasons (both legs); overlapping windows are not independent.
- Phase 4's residual leg is R-A, picked before Phase 3. No temperature residual cleared Phase 3's bar and the rain residual is a weekly PRISM design, so the two-leg capital describes a book the product will not list. It was not re-run (seat ruling 2026-09-30). The weekly rain book was sized separately (§7).
- The rain book's history counted a trace as wet, and it was not rerun after the rain cover switched to measurable rain only (§4). Its verdicts (no netting, depth far too thin, junior fails) do not turn on trace days.
- The rain book (§7) rests on a {{pre:rain.history_months|int}}-month two-leg history. Its residual leg is paid on weekly wet-day counts, which Phase 3 did not test (it scored inches), and the Kalshi depth is a guess at {{pre:rain.depth_share|pct0}} of volume, not an order book.
- Phase 5's datasets are stand-ins, one hedge year per split, and every unit in a city shares the same weather days, so the effective sample is about a summer of days, not hundreds of units.
- Phase 5's P1 and T1 readings and its G1 stop rely on seat rulings made after the results.

**Gaps against the brief.** Each line of the brief's evaluation list (.planning/PROJECT.md, Core Value plus EVAL-01..07), where this report answers it, and what is missing:

{{table:checklist}}
"""


def appendix_figs() -> str:
    lines = ["## Appendix A. Figures", "",
             "Built by this script into reports/figures/ (embedded in the sections above):", ""]
    for k, (f, cap) in FIGS.items():
        lines.append(f"- `figures/{f}`: {cap}")
    if DATA.get("e03") is None:
        lines.append("- `figures/fig8_geography.png`: pending (Phase 3).")
    lines += ["", "Phase figures (built by each phase's script, not rebuilt here):", ""]
    for d in ["eval-01", "eval-04-05", "eval-06", "eval-03"]:
        p = REP / d / "figures"
        if p.exists():
            for f in sorted(p.glob("*.png")):
                lines.append(f"- [{d}/figures/{f.name}]({d}/figures/{f.name})")
    return "\n".join(lines) + "\n"


def appendix_keymap() -> str:
    lines = ["## Appendix B. Key map (every number in the prose)", "",
             "One row per number rendered in the prose, in order of appearance. `ins1`, `DATA.md` and threshold rows are "
             "quoted constants, not results.json keys; each names its file. Table cells are not repeated here: each table "
             "names its source path under it.", "", "| # | section | value | source |", "|---|---|---|---|"]
    seen = set()
    n = 0
    for sec, val, ref, lab in KEYMAP:
        k = (sec, ref, val)
        if k in seen:
            continue
        seen.add(k)
        n += 1
        lines.append(f"| {n} | {sec} | {val} | `{lab.replace('|', '¦')}` |")
    return "\n".join(lines) + "\n"


def appendix_rebuild() -> str:
    rows = []
    for k, p in FILES.items():
        if p.exists():
            md5 = hashlib.md5(p.read_bytes()).hexdigest()
            meta = ""
            try:
                d = DATA[k]
                meta = (d.get("meta", {}).get("run_utc") or d.get("meta", {}).get("written_utc") or d.get("written_utc") or "")
            except AttributeError:
                pass
            rows.append([k, str(rel(p)), meta, md5])
        else:
            rows.append([k, str(rel(p)), "not present", ""])
    t = table(["source id", "file", "written (UTC)", "md5"], rows, "computed by scripts/build_report.py at build time")
    lint_line = ("Prose lint: no digit outside a placeholder." if not LINT else
                 f"Prose lint: {len(LINT)} digit(s) outside placeholders (printed by the build; listed here).\n\n"
                 + "\n".join(f"- §{s}: {m}" for s, m in LINT))
    miss = ""
    if DATA.get("e03") is not None and MISSING_E03:
        miss = ("\n\nPhase 3 keys this report expected but did not find (see "
                ".planning/phases/06-evaluation-report/06-EVAL03-CONTRACT.md):\n\n" +
                "\n".join(f"- `{k}`" for k in sorted(set(MISSING_E03))))
    return ("## Appendix C. How to rebuild\n\n`make report` runs `uv run python scripts/build_report.py`. It reads the files "
            "below, rewrites reports/EVALUATION.md and reports/figures/, and exports reports/EVALUATION.pdf with pandoc if "
            "pandoc is installed, otherwise reports/EVALUATION.html (self-contained, figures embedded). It computes no new "
            "statistic. To refresh a number, re-run the phase script (scripts/eval02.py, eval04.py, eval05.py, eval03.py) and "
            "then `make report`.\n\n" + t + "\n" + lint_line + miss + "\n")


# ---------------------------------------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------------------------------------
_BIKE = ["e06:verdicts.T2.G1.heat_rain_median", "e06:verdicts.T2.G2.heat_rain_median",
         "e06:groups.G1.replication.arms.A3.cover_heat_rain_daily.median",
         "e06:groups.G2.replication.arms.A3.cover_heat_rain_daily.median"]
CALC["bike_he_min"] = (lambda: min(R(k) for k in _BIKE), "min of e06 A3 HE_cover heat+rain, G1/G2, primary and replication")
CALC["bike_he_max"] = (lambda: max(R(k) for k in _BIKE), "max of e06 A3 HE_cover heat+rain, G1/G2, primary and replication")
CALC["rain_load"] = (lambda: R("e01:rain_daily.horizons.24.cost_per_dollar_payout") - 1,
                     "e01 rain_daily.horizons.24.cost_per_dollar_payout − 1")

TABLES = {
    "ledger": t_ledger, "deviations": t_deviations, "e01_main": t_e01_main, "e01_years": t_e01_years,
    "e01_horizons": t_e01_horizons, "e01_ruleb": t_e01_ruleb, "rain": t_rain, "rain_monthly": t_rain_monthly,
    "depth": t_depth, "mismatch": t_mismatch, "ins1_compare": t_ins1_compare, "netting": t_netting,
    "auction": t_auction, "capital": t_capital, "markouts": t_markouts, "markout_summary": t_markout_summary, "fees": t_fees, "e06_t2": t_e06_t2,
    "e06_t4": t_e06_t4, "e06_p1": t_e06_p1, "costs": t_costs, "liquidity": t_liquidity, "revision": t_revision,
    "checklist": t_checklist, "ins2_baseline": t_ins2_baseline, "ins1_geo": t_ins1_geo,
    "e03_he0_market": t_e03_he0_market, "e03_bakeoff_temperature": lambda: t_e03_bakeoff("temperature"),
    "e03_bakeoff_rain": lambda: t_e03_bakeoff("rain"),
}
P3FRONT_PENDING = ("- **Geography and the residual contract are not in yet.** Phase 3 (EVAL-02, EVAL-03) had not landed when "
                   "this report was built; §5 and §6 fill themselves when it does.\n")
P3FRONT_DONE = ("- **Geography and the residual contract (Phase 3).** At held-out points near the settlement stations, the "
                "station leg alone reaches a pooled median HE of {{e03:eval02.temperature.pooled_median_he0|f2}} for temperature "
                "(against {{@LIQ24.he_cover.est|f2}} at the station itself). Winning residual design: "
                "{{e03:verdicts.winner.temperature|winner}} for temperature, {{e03:verdicts.winner.rain|winner}} for rain (§6).\n")
P3PROD_PENDING = "Anything away from the station waits on Phase 3."
P3PROD_DONE = ("Away from the station, the residual bake-off (§6) gives temperature winner: "
               "{{e03:verdicts.winner.temperature|winner}}. So heat cover ships as the station leg alone "
               "(C_30 {{@DEP.pooled_station_leg_only.H30.C|usdk}} against {{e45:verdicts.M3.C30|usdk}} for Phase 4's two-leg book), "
               "with residuals by RFQ quoted on P-A-IDW. For rain the winner is {{e03:verdicts.winner.rain|winner}} "
               "(ΔHE {{e03:bakeoff.rain.G1-P.pooled_median_dhe|f3}} on {{e03:bakeoff.rain.G1-P.n_pairs|int}} of "
               "{{e03:bakeoff.rain.D0.n_pairs|int}} pairs), with R-A the alternate; the weekly two-leg rain book is sized in §7 but not built yet.")


def _p3(done: str, pending: str, sec: str) -> str:
    if DATA.get("e03") is None:
        return pending
    keep = _SECTION[0]
    out = render(sec, done)
    _SECTION[0] = keep
    return out


BLOCKS = {
    "p3front": lambda: _p3(P3FRONT_DONE, P3FRONT_PENDING, "front"),
    "p3product": lambda: _p3(P3PROD_DONE, P3PROD_PENDING, "10"),
    "banner": lambda: BANNER,
    "p3status": lambda: "done" if DATA.get("e03") is not None else "**pending**",
    "e03_meta": e03_meta_block,
}

DIRECTIVE = re.compile(r"\{\{(table|fig|block):([^}]+)\}\}")


def expand(text: str) -> str:
    def sub(m):
        kind, name = m.group(1), m.group(2)
        if kind == "table":
            return TABLES[name]()
        if kind == "fig":
            return fig_md(name)
        return BLOCKS[name]()
    return DIRECTIVE.sub(sub, text)


def section(label: str, tmpl: str) -> str:
    # lint + render placeholders in the prose first, then insert tables/figures/blocks (code-built, own captions)
    return expand(render(label, tmpl))


def build_md() -> str:
    parts = [section("front", TEXT_FRONT), section("1", TEXT_S1), section("2", TEXT_S2), section("3", TEXT_S3),
             section("4", TEXT_S4)]
    _SECTION[0] = "5"
    parts.append(expand(sec5()))
    _SECTION[0] = "6"
    parts.append(expand(sec6()))
    parts += [section("7", TEXT_S7), section("8", TEXT_S8), section("9", TEXT_S9), section("10", TEXT_S10),
              section("11", TEXT_S11)]
    parts.append(appendix_figs())
    km = appendix_keymap()
    parts.append(km)
    parts.append(appendix_rebuild())
    return "\n".join(parts)


# ---------------------------------------------------------------------------------------------------------
# Export: pandoc PDF if available, else a small self-contained HTML renderer
# ---------------------------------------------------------------------------------------------------------
def _inline(s: str) -> str:
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*([^*\n]+?)\*(?![\w*])", r"<em>\1</em>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
    return s


def _img(alt: str, path: str) -> str:
    p = REP / path
    if p.exists():
        b64 = base64.b64encode(p.read_bytes()).decode()
        return f'<figure><img alt="{html.escape(alt)}" src="data:image/png;base64,{b64}"></figure>'
    return f"<p>[missing image {html.escape(path)}]</p>"


def md_to_html(md: str) -> str:
    out, lines, i = [], md.splitlines(), 0
    while i < len(lines):
        ln = lines[i]
        if not ln.strip():
            i += 1
            continue
        m = re.match(r"^(#{1,6}) (.*)", ln)
        if m:
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>{_inline(m.group(2))}</h{lvl}>")
            i += 1
            continue
        m = re.match(r"^!\[(.*)\]\((.*)\)$", ln)
        if m:
            out.append(_img(m.group(1), m.group(2)))
            i += 1
            continue
        if ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(lines[i])
                i += 1
            cells = [[x.strip() for x in r.strip().strip("|").split(" | ")] for r in rows]
            h = "".join(f"<th>{_inline(x)}</th>" for x in cells[0])
            body = "".join("<tr>" + "".join(f"<td>{_inline(x)}</td>" for x in r) + "</tr>" for r in cells[2:])
            out.append(f"<table><thead><tr>{h}</tr></thead><tbody>{body}</tbody></table>")
            continue
        if ln.startswith("> "):
            buf = []
            while i < len(lines) and lines[i].startswith(">"):
                buf.append(lines[i][1:].strip())
                i += 1
            out.append(f"<blockquote>{_inline(' '.join(buf))}</blockquote>")
            continue
        if re.match(r"^- ", ln):
            items = []
            while i < len(lines) and (re.match(r"^- ", lines[i]) or (lines[i].startswith("  ") and items)):
                if lines[i].startswith("- "):
                    items.append(lines[i][2:])
                else:
                    items[-1] += " " + lines[i].strip()
                i += 1
            out.append("<ul>" + "".join(f"<li>{_inline(x)}</li>" for x in items) + "</ul>")
            continue
        buf = []
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#|\||- |> |!\[)", lines[i]):
            buf.append(lines[i])
            i += 1
        out.append(f"<p>{_inline(' '.join(buf))}</p>")
    css = ("body{font-family:-apple-system,Helvetica,Arial,sans-serif;max-width:1100px;margin:2em auto;padding:0 1em;"
           "line-height:1.45;color:#222}table{border-collapse:collapse;margin:.6em 0;font-size:.82em}"
           "th,td{border:1px solid #ccc;padding:3px 6px;text-align:left;vertical-align:top}th{background:#f3f3f3}"
           "blockquote{border-left:4px solid #c33;background:#fdf1f1;margin:1em 0;padding:.5em 1em}"
           "img{max-width:100%}figure{margin:.5em 0}code{font-size:.9em;background:#f5f5f5;padding:0 2px}"
           "h2{border-bottom:1px solid #ddd;padding-bottom:.2em;margin-top:1.8em}")
    return (f"<!doctype html><html><head><meta charset='utf-8'><title>weather-insurance evaluation report</title>"
            f"<style>{css}</style></head><body>{''.join(out)}</body></html>")


def export(md_text: str) -> str:
    if shutil.which("pandoc"):
        pdf = REP / "EVALUATION.pdf"
        r = subprocess.run(["pandoc", str(OUT_MD), "-o", str(pdf), "--resource-path", str(REP)], cwd=REP,
                           capture_output=True, text=True)
        if r.returncode == 0:
            return str(rel(pdf))
        print("build_report: pandoc PDF failed, falling back to HTML:", r.stderr.strip()[:300])
    out = REP / "EVALUATION.html"
    out.write_text(md_to_html(md_text))
    return str(rel(out))


def contract_md() -> str:
    lines = ["# Phase 3 results.json keys read by scripts/build_report.py", "",
             "Written by the Phase 6 worker so that §5-6 of reports/EVALUATION.md fill automatically. Keys follow the "
             "Phase 3 pre-registration draft (03-RESEARCH.md) and 03-PLAN.md. A missing key renders as n/a and is listed in "
             "Appendix C of the report; nothing crashes. Add keys freely; renaming these needs a matching edit in "
             "build_report.py.", "",
             "| key | type | meaning |", "|---|---|---|",
             "| `meta.prereg_frozen_utc`, `meta.written_utc` | str | freeze and write times (UTC, ISO) |",
             "| `eval02.<variable>.pooled_median_he0` | float | pooled median HE of the station leg alone (D0) at held-out truth points ≤ 50 km |",
             "| `eval02.<variable>.pooled_median_he0_ci` | [lo, hi] | joint circular block bootstrap 95 % CI |",
             "| `eval02.<variable>.by_market.<MKT>.median_he0` | float | market median HE(D0) |",
             "| `eval02.points` | list of {market, point, variable, dist_km, he0} | one row per (market, truth point, variable); drives the basis-vs-distance figure |",
             "| `bakeoff.<variable>.<DESIGN>.pooled_median_he` | float | pooled median HE with station leg + residual |",
             "| `bakeoff.<variable>.<DESIGN>.pooled_median_dhe`, `.dhe_ci` | float, [lo, hi] | P1 gain and its CI |",
             "| `bakeoff.<variable>.<DESIGN>.share_pairs_dhe_pos`, `.markets_dhe_pos` | float, int | P2 breadth |",
             "| `bakeoff.<variable>.<DESIGN>.pooled_median_eta` | float | P3 efficiency η = 2β − 1 |",
             "| `bakeoff.<variable>.<DESIGN>.sd_r_median`, `.L_median` | float | residual sd and loading L at λ = 0.25 |",
             "| `bakeoff.<variable>.<DESIGN>.settleable` | bool | P4 |",
             "| `bakeoff.<variable>.<DESIGN>.verdict` | str | SURVIVES / FAILS / KILLED / continuity / exploratory / baseline |",
             "| `verdicts.winner.<variable>` | str or null | winning design id, null if none survives |",
             "| `verdicts.pc1_vs_equal.he_diff`, `.ci`, `.adopted` | float, [lo, hi], bool | the Q2 rule |",
             "| `deviations` | list of {utc, what} | every post-freeze change |", "",
             "`<variable>` ∈ {temperature, rain}. `<MKT>` ∈ {NYC, EWR, TTN, MDW, MIA}. `<DESIGN>` ∈ {"
             + ", ".join(d for d, _ in DESIGNS) + "}.", ""]
    return "\n".join(lines)


def main():
    if "--contract" in sys.argv:
        print(contract_md())
        return
    load()
    figures()
    md = build_md()
    OUT_MD.write_text(md)
    CONTRACT_MD.parent.mkdir(parents=True, exist_ok=True)
    CONTRACT_MD.write_text(contract_md())
    exp = export(md)
    n_nums = len({(s, r, v) for s, v, r, _ in KEYMAP})
    print(f"build_report: wrote {rel(OUT_MD)} ({len(md.splitlines())} lines, {n_nums} traced prose numbers), "
          f"{len(FIGS)} figures in reports/figures/, export {exp}")
    print("build_report: Phase 3 " + ("present" if DATA.get("e03") is not None else "PENDING (sections 5-6 templated)"))
    if DATA.get("e03") is not None and MISSING_E03:
        print(f"build_report: {len(set(MISSING_E03))} expected Phase 3 key(s) missing; listed in Appendix C")
    if LINT:
        print(f"build_report: lint: {len(LINT)} digit(s) in prose outside placeholders:")
        for s, m in LINT:
            print(f"  §{s}: {m}")


if __name__ == "__main__":
    main()
