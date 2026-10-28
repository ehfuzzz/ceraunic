"""Elasticity + recommendation: the Phase 5 portal estimator (wi.elasticity.portal.estimate, numpy only)
fed with the business's sales and the settlement station's NWS CLI weather, both strictly before the
simulated day (no look-ahead: a sale dated on or after the sim day has not happened yet in the world).

Priors come from data/demo/priors.json (reports/eval-06). The public stand-in panels are bikeshare,
transit and taxi (Phase 5 seat ruling 2: stand-ins, not retail); the estimate is ADVISORY ONLY
(ruling 4). A business whose sector has no panel borrows its city's bikeshare prior and is flagged
`learned = false` (05-RESEARCH Pitfall 9). HE per path is the EVAL-06 group median (arm A3, daily,
heat+rain): house-hedge = HE_cover, business-ladder = HE_ladder.
"""
from __future__ import annotations

import math

from . import catalog as cat
from . import snapshot_data as sd

CITY_GROUPS = {"NYC": {"bike": "G1", "taxi": "G5"}, "CHI": {"bike": "G2", "transit": "G3", "taxi": "G4"}}


def sector_of(naics: str | None) -> str:
    n = naics or ""
    if n.startswith("4853"):
        return "taxi"
    if n.startswith("485"):
        return "transit"
    return "bike"  # foot-traffic retail and food service: bikeshare is the weather-heavy stand-in


def group_for(metro: str, naics: str | None) -> tuple[str, bool, str]:
    """(group id, learned, why)."""
    sec = sector_of(naics)
    city = metro if metro in CITY_GROUPS else "NYC"
    g = CITY_GROUPS[city].get(sec) or CITY_GROUPS[city]["bike"]
    learned = metro in CITY_GROUPS and sec in CITY_GROUPS[city] and sec != "bike"
    why = f"{g} {sd.priors()['groups'][g]['label']}"
    if metro not in CITY_GROUPS:
        why += f" (no {metro} panel: borrowed from NYC)"
    if not learned:
        why += " as a stand-in prior; no panel exists for this sector"
    return g, learned, why


def he_for(group: str) -> dict:
    return sd.he()["groups"].get(group, {})


def estimate(biz: dict, sales: dict[str, int], sim_day: int) -> dict:
    """Run the Phase 5 estimator. Returns a dict shaped for models.Elasticity plus the raw prescription."""
    from wi.engine.units import day_to_iso

    site = biz["locationSite"]
    metro, settle = cat.SITES[site][4], cat.SITES[site][5]
    gid, learned, why = group_for(metro, biz.get("naics"))
    pr = dict(sd.priors()["groups"][gid])
    cut = day_to_iso(sim_day)
    rows = [{"date": d, "sales": c / 100} for d, c in sorted(sales.items()) if d < cut]
    ignored = sum(1 for d in sales if d >= cut)
    wx = sd.weather_rows(settle, sim_day)
    he = he_for(gid)
    base = {"prior_group": gid, "advisory_only": bool(pr.get("advisory_only", True)), "he_cover": he.get("heCover"),
            "he_ladder": he.get("heLadder"),
            "he_by_path": {"house-hedge": he.get("heCover"), "business-ladder": he.get("heLadder")},
            "rows_ignored_after_sim_day": ignored, "warnings": []}
    if ignored:
        base["warnings"].append(f"{ignored} sales days dated on or after the simulated day {cut} were left out")
    prior = {"sector": pr["sector"], "mu": pr["mu_heat"], "tau2": pr["tau2_heat"], "learned": learned}
    try:
        from wi.elasticity.portal import estimate as est

        out = est(rows, wx, pr)
    except ValueError as e:  # fewer than 30 usable days: the sector prior alone
        base["warnings"].append(str(e))
        se_h = math.sqrt(pr["tau2_heat"]) if pr["tau2_heat"] > 0 else pr["se_mu_heat"]
        se_w = math.sqrt(pr["tau2_wet"]) if pr["tau2_wet"] > 0 else pr["se_mu_wet"]
        n = len(rows)
        recent = sum(r["sales"] for r in rows[-28:]) / max(1, len(rows[-28:])) if rows else 0.0
        return {**base, "heat": {"beta": pr["mu_heat"], "se": se_h, "n": 0},
                "wet": {"beta": pr["mu_wet"], "se": se_w, "n": 0}, "shrink_weight": 0.0, "prior": prior,
                "origin": "prior", "method": f"sector prior {why}; own history too short ({n} days)",
                "model": "prior_only", "heat_usd_per_deg_f": recent * -pr["mu_heat"],
                "rain_contracts": recent * (1 - math.exp(pr["mu_wet"])),
                "recent_mean_daily_sales_cents": recent * 100, "rows_used": 0, "K": pr["K"], "cap": pr["cap"]}
    ps = out["prescription"]
    h, wt = out["heat"], out["wet"]
    used_own = ps["used"] == "own"

    def coef(leg: dict) -> dict:
        b = leg["beta_own"] if used_own and leg["identified"] else leg["beta_shrunk"]
        se = leg["se_own"] if leg["se_own"] is not None and math.isfinite(leg["se_own"]) else math.sqrt(leg["prior_tau2"])
        return {"beta": float(b), "se": float(se), "n": int(out["n_rows_fit"])}

    return {**base, "heat": coef(h), "wet": coef(wt), "shrink_weight": 1.0 if used_own else float(h["credibility_B"]),
            "prior": prior, "origin": "own-shrunk",
            "method": (f"wi.elasticity.portal.estimate ({out['model']}, OLS + HAC(7)); "
                       f"{'own OLS (n >= n*)' if used_own else 'credibility-shrunk toward the prior'}; prior {why}"),
            "model": out["model"], "heat_usd_per_deg_f": ps["heat_usd_per_degF"], "rain_contracts": ps["rain_contracts"],
            "recent_mean_daily_sales_cents": ps["recent_mean_daily_sales"] * 100, "rows_used": out["n_rows_fit"],
            "K": out["K"], "cap": out["cap"]}


def recommend(biz: dict, e: dict, sim_day: int) -> dict:
    """Peril, strike, cap and units from the estimate. Loses sales on hot days -> heat cover (capped call);
    gains on hot days -> cool-day cover (capped put). Units = dollars per degree F x cap in degrees F."""
    from wi.engine.units import day_to_iso

    usd_per_f = e.get("heat_usd_per_deg_f") or 0.0
    K10, C10 = int(round(e.get("K", 75.0) * 10)), int(round(e.get("cap", 10.0) * 10))
    if usd_per_f > 0:
        peril, strike = "heat", K10
    else:
        peril, strike = "cold", K10
    dollars = max(1, min(50, int(round(abs(usd_per_f)))))
    units = dollars * C10 // 10
    start = min(sim_day + 1, cat.LAST_DAY)
    end = min(start + 6, cat.LAST_DAY)
    why = [f"heat effect {e['heat']['beta'] * 100:+.2f}% of sales per degree F above {K10 / 10:g} F "
           f"({'your own history' if e['origin'] == 'own-shrunk' else 'sector prior only'})",
           ("sales fall on hot days, so the loss is a hot day: cover heat" if peril == "heat"
            else "sales do not fall on hot days, so the cover that pays is a cool-day cover"),
           f"size: about ${dollars}/F over a {C10 / 10:g} F range = {units} units a day (each unit pays at most $1)",
           "advisory only: the estimate is learned from public stand-in panels, not retail sales (Phase 5)"]
    return {"peril": peril, "strike_tenths_f": strike, "cap_tenths_f": C10, "units_per_day": units,
            "path": "house-hedge", "he_estimate": e.get("he_cover") or 0.0, "rationale": why,
            "start_day": day_to_iso(start), "end_day": day_to_iso(end)}


def recommend_rain(biz: dict, e: dict, sim_day: int) -> dict:
    """Rain cover sized from the wet-day effect: dollars per wet day ~ the sales a wet day costs
    (prescription rain_contracts = recent daily sales x (1 - exp(beta_wet))), 1..50. Settles on the metro's Kalshi
    rain station (13-RAIN). House-hedge HE = the EVAL-01 wet-day HE_cover."""
    from wi.engine.units import day_to_iso

    rs = cat.RAIN_SITE[cat.SITES[biz["locationSite"]][4]]
    lost = float(e.get("rain_contracts") or 0.0)
    dollars = max(1, min(50, int(round(lost)))) if lost >= 0.5 else 1  # sales that rise on wet days: smallest size
    start = min(sim_day + 1, cat.LAST_DAY)
    end = min(start + 6, cat.LAST_DAY)
    he = sd.rain().get("he", {})
    why = [f"wet-day effect {e['wet']['beta'] * 100:+.1f}% of sales on a day with rain "
           f"({'your own history' if e['origin'] == 'own-shrunk' else 'sector prior only'})",
           (f"a wet day costs you about ${lost:,.0f} of sales, so the cover pays ${dollars} for each wet day"
            if lost >= 0.5 else "no recent sales to size it from; rain cover is shown at the smallest size"
            if not e.get("recent_mean_daily_sales_cents") and e["wet"]["beta"] < 0
            else "your sales do not fall on wet days; rain cover is shown at the smallest size"),
           f"settles on the National Weather Service daily report for {cat.SITES[rs][1]}; it pays on 0.01 in "
           "or more (a trace is no rain, as on Kalshi)",
           "advisory only: the estimate is learned from public stand-in panels, not retail sales (Phase 5)"]
    return {"peril": "rain", "strike_tenths_f": 0, "cap_tenths_f": 1, "units_per_day": dollars, "path": "house-hedge",
            "he_estimate": he.get("heCover") or 0.0, "rationale": why, "start_day": day_to_iso(start),
            "end_day": day_to_iso(end)}
