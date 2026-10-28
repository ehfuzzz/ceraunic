#!/usr/bin/env python3
"""Generate the two pitch decks (crypto, fintech) as Slides-type files under decks/<deck>/project/."""
import json, os, datetime
ROOT = os.path.dirname(os.path.abspath(__file__))
NOW = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

BLOBS = {
 "crypto": {"fig1":"/_blob/a6f88ebe0a5081bbd5cfdb937b111ecc","fig2":"/_blob/52aa38ae52282df44a20d8f0856dbe98","fig3":"/_blob/b22baa36f8d0e207a240bbcd1b778c8c","fig4":"/_blob/5c34437ab8dd95a92fe74ab6e22aa755","fig5":"/_blob/58e0dd1ae4f53cdaeeb85525142fd63d","fig6":"/_blob/735796ed84c1ae27a0ee5bd71ff0a2d9","s03":"/_blob/519055dc3aae58caa2524d6c79853a98","s04":"/_blob/dd66db982c5d8a7b8cffbd38d8428f3a","s06":"/_blob/10188d5d4455fafd6f92714d14f40164","s07":"/_blob/468d3f0e490ab48f5c26878d473904cb","s11":"/_blob/b4c7ca7b913495a5c0e60727c59ad517"},
 "fintech": {"fig1":"/_blob/ad164e98bb01e6f03b74aab4be846df6","fig2":"/_blob/dcd37eb997430ec7ef8fa06f32c65a25","fig3":"/_blob/e1640e18579cf21eadf20a6dfea63790","fig4":"/_blob/15f9e902d80a62da15074af2474415e2","fig5":"/_blob/94d12e3bca7642fb72a5b6948203d998","fig6":"/_blob/3592a7d60d0616e47e0dc56b71629f2f","s03":"/_blob/d68fd75badda10ac479154dc48bb974f","s04":"/_blob/33a39a848eb0b9ff4536f27ade05338c","s06":"/_blob/a8239325597c7b89a5fb14143c3350f2","s07":"/_blob/458abd058a75548c8fc3bac24bc46064","s11":"/_blob/43f8c1d01bbc0a2579d855a8515c5f3f"},
}

# Palette and type
LIGHT="#F7F4EE"; LIGHT2="#ECE7DD"; DARK="#1E2A38"; BODY="#3E4A57"; MUTED="#6B7480"; ACCENT="#B5451B"; ACCENT_ON_DARK="#E8A587"; LINE="#D9D2C4"; CARD="#FDFCFA"; LIGHT_ON_DARK="#F1EDE4"; BODY_ON_DARK="#C9D1DA"
HEAD="'Libre Baskerville', Georgia, serif"; TEXT="'Public Sans', Arial, sans-serif"

def sec(id, inner, notes, n, source, dark=False, transition="fade"):
    bg = DARK if dark else LIGHT
    col = LIGHT_ON_DARK if dark else DARK
    foot = BODY_ON_DARK if dark else MUTED
    s = (f'<section id="{id}" data-transition="{transition}" style="background:{bg};color:{col};font-family:{TEXT};'
         f'padding:128px 128px 160px;display:flex;flex-direction:column;gap:36px">\n{inner}\n'
         f'<p style="position:absolute;left:128px;bottom:64px;width:1664px;font-size:24px;color:{foot}">{n} / 15 · {source}</p>\n')
    if notes:
        s += f"<aside>{notes}</aside>\n"
    return s + "</section>\n"

def h2(t, dark=False):
    return f'<h2 style="font-family:{HEAD};font-size:60px;font-weight:400;line-height:1.1;color:{LIGHT_ON_DARK if dark else DARK}">{t}</h2>'
def lead(t, dark=False):
    return f'<p style="font-size:30px;line-height:1.4;color:{BODY_ON_DARK if dark else BODY}">{t}</p>'
def eyebrow(t, dark=False):
    return f'<p style="font-size:24px;font-weight:600;letter-spacing:2px;text-transform:uppercase;color:{ACCENT_ON_DARK if dark else ACCENT}">{t}</p>'
def card(title, body, flex="1"):
    return (f'<div style="flex:{flex};display:flex;flex-direction:column;gap:14px;background:{CARD};padding:32px;border:1px solid {LINE};border-radius:12px">'
            f'<h3 style="font-size:30px;font-weight:600;line-height:1.2;color:{DARK}">{title}</h3>'
            f'<p style="font-size:26px;line-height:1.4;color:{BODY}">{body}</p></div>')
def bignum(num, label, dark=False):
    return (f'<div style="flex:1;display:flex;flex-direction:column;gap:8px">'
            f'<p style="font-family:{HEAD};font-size:88px;line-height:1;color:{ACCENT_ON_DARK if dark else ACCENT}">{num}</p>'
            f'<p style="font-size:26px;line-height:1.35;color:{BODY_ON_DARK if dark else BODY}">{label}</p></div>')
def row(*items, gap=32):
    return f'<div style="display:flex;gap:{gap}px;align-items:stretch">' + "".join(items) + '</div>'
def img(src, w, h, alt, fit="cover", crop=None):
    c = f' data-crop="{crop}"' if crop else ""
    return f'<img src="{src}" alt="{alt}"{c} style="width:{w}px;height:{h}px;object-fit:{fit};border:1px solid {LINE};border-radius:12px;background:{CARD}">'
def ul(items, size=26, dark=False):
    lis = "".join(f"<li>{i}</li>" for i in items)
    return f'<ul style="font-size:{size}px;line-height:1.45;color:{BODY_ON_DARK if dark else BODY};padding:0 0 0 36px">{lis}</ul>'
def table(rows, widths, size=26, first_col_left=True):
    out = f'<table style="font-size:{size}px;color:{BODY};border:1px solid {LINE};border-radius:8px;width:1664px">'
    for r_i, r in enumerate(rows):
        tag = "th" if r_i == 0 else "td"
        cells = ""
        for c_i, c in enumerate(r):
            wd = f'width:{widths[c_i]}%;' if r_i == 0 else ""
            align = "left" if c_i == 0 and first_col_left else "right"
            cells += f'<{tag} style="{wd}text-align:{align}">{c}</{tag}>'
        bg = f' style="background:{LIGHT2}"' if r_i == 0 else ""
        out += f"<tr{bg}>{cells}</tr>"
    return out + "</table>"

def shared_slides(B, num):
    """Slides S-A..S-I keyed by tag; num maps tag -> slide number in this deck."""
    S = {}
    # S-A station contracts pay
    S["S-A"] = sec("sa",
        h2("The station contracts pay when they should") +
        lead("Kalshi's daily high-temperature contracts, bought as a set, pay out in line with a simple heat payout at the weather station: they track 0.95 of the variance, about the same in every year since 2022.") +
        row(bignum("0.95", "hedge effectiveness, before price [0.95, 0.96], 4,462 city-days in New York, Chicago and Miami"),
            bignum("0.2%", "of 3,822 days where the settled number differed from the official NWS climate report"),
            bignum("241% / 266%", "over fair value a day ahead at Newark and Trenton: too thin to use")) +
        img(B["fig1"], 1664, 380, "Hedge effectiveness by city and year: HE_cover near 0.95 every year; HE_ladder lower", "contain"),
        "This is the part that works. If you run a shop near Central Park, Midway or Miami airport, there is already a liquid contract that pays on the number you care about, and the official number it settles on is clean. The catch is on the next slide.",
        num["S-A"], "Sources: eval-01 results.json temperature.pooled[rule=A,h=24,pool=liquid].he_cover; mismatch[all].value_mismatch_share; verdicts.T2.EWR/TTN.overround")
    # S-B forecast
    S["S-B"] = sec("sb",
        h2("A day ahead, you are paying for the forecast") +
        lead("Bought 24 hours before the close, the price already contains tomorrow's forecast, so a buyer only hedges the forecast miss: 0.37 of the variance on 2025-26 days, and worse than doing nothing over all years.") +
        row(f'<div style="flex:1;display:flex;flex-direction:column;gap:24px">' +
            row(bignum("0.37", "hedge effectiveness counting the price paid, 2025+ days [0.33, 0.42]"), bignum("−0.32", "the same over 2022-26: worse than no hedge")) +
            card("Our pre-registered price test failed", "24.6% over fair value against a 20% bar. Today's market is cheaper, 9.7% on 2025+ days, but we picked that window after seeing the numbers.") + '</div>',
            img(B["fig2"], 760, 470, "Overround by city and year with the 20% bar as a dashed line", "contain")),
        "This is the number that changed the product. A business that buys the contracts itself a day ahead gets 0.37, not 0.95. So the default has to be one fixed-price policy where the house hedges every day, and that makes us the ones carrying the forecast risk. We are a capitalised pool that uses Kalshi for pricing and some hedging, not a pass-through.",
        num["S-B"], "Sources: eval-01 results.json temperature.pooled[...].he_ladder.est (2025+ pool is post hoc, deviation 6); overround.est vs PREREG T1 = FAIL")
    # S-C pool is the business
    S["S-C"] = sec("sc",
        h2("The pool is the business, not the matching") +
        lead("Businesses with opposite exposure do cancel some risk, but not much, and the station contracts are far too thin to absorb the rest, so a capitalised pool carries most of what we sell.") +
        row(f'<div style="flex:1;display:flex;flex-direction:column;gap:24px">' +
            row(bignum("4,426", "units a day left over around Central Park in our simulation (2% of nearby small businesses hedging every warm-season day)"), bignum("33", "units one real order-book snapshot supported near the best price; our paper hedge was capped at 5")) +
            row(bignum("40%", "of hedge units cancel inside one station's daily auction under our sector guesses (3 of 5 stations pass, the minimum)"), bignum("1.9%", "if businesses mostly react to weather the same way, so pricing and capital do not count on netting")) + '</div>',
            img(B["fig4"], 640, 470, "Share of hedge units that cancel: central priors, 1,000 prior draws, and the null", "contain")),
        "Before we ran this, we wrote down that if netting in the everyone-moves-together case came in under 10%, we could not lead with it. It came in at 1.9%, so we do not. The honest picture is a pool that carries the risk and gets paid a margin for it.",
        num["S-C"], "Sources: eval-04-05 results.json netting.leftover_units_per_day.NYC; netting.central.pooled; netting.null.pooled; eval-01 depth.ladders.KXHIGHNY-26SEP30.max_units_3c")
    # S-D capital (dark statement slide)
    S["S-D"] = sec("sd",
        h2("Capital: affordable only with daily repricing, and one bad summer can wipe the first-loss layer", dark=True) +
        lead("The pool needs about 13 cents of capital per dollar of 30-day cover if we reprice every day off the forecast. Priced once up front, or measured over a whole summer, it needs more. In a 1-in-20 summer the junior layer is gone.", dark=True) +
        row(bignum("0.126", "capital per dollar of 30-day notional ($412k), under our 0.35 bar; 0.25 for the station leg alone; 0.36 if priced before the forecast is known, over the bar", dark=True),
            bignum("$731k", "worst modelled summer loss (2009), so about 0.22 per dollar on a season basis; we always quote both horizons", dark=True),
            bignum("−144%", "junior ($206k) return in a 1-in-20 modelled season: wiped out, and senior money starts paying claims. Temperature cover ships as the station leg alone: about $416k of 30-day capital, next to $412k for the two-leg book", dark=True)),
        "I want to be clear about this one. The capital looks affordable only if we reprice every day. And a 30-day number is not what a depositor cares about; a whole summer is. By our model, about one summer in twenty wipes out the first-loss money. The halt rules stop new sales when it runs thin, but policies already sold still pay.",
        num["S-D"], "Sources: eval-04-05 verdicts.M3.C30/CPC; handoff.json capital_per_usd_cover_H30.*; junior_returns.json model.weather_pnl_hist.2009, model.splits.margin_t10.boot_p05_1in20 (modelled, not observed); 03-SUMMARY (station leg alone about $416k)", dark=True)
    # S-E elasticity
    S["S-E"] = sec("se",
        h2("Learning a shop's weather sensitivity failed on public stand-ins") +
        lead("We tried to learn weather sensitivity from a year of daily demand on public datasets and it missed our bar. These are bike, transit and taxi counts, not a shop's sales, so the café question is still open.") +
        row(f'<div style="flex:1;display:flex;flex-direction:column;gap:24px">' +
            row(bignum("7% / 5%", "of daily revenue surprise removed out of sample by the learned hedge (New York, Chicago bikeshare) against a 20% bar: FAIL. Transit and taxi got about nothing"),
                bignum("0.006", "kept at real day-ahead prices for the New York bike hedge")) +
            card("The rain effect is real and precise", "About −10.5% on wet days for Citi Bike. The heat leg did not fit: bikeshare demand rises then flattens with temperature, which a heat contract cannot follow. Seat rulings on this phase came after the results and are reported as post hoc.") + '</div>',
            img(B["fig6"], 700, 470, "Out-of-sample hedge effectiveness of the learned hedge by stand-in group with the 0.20 bar", "contain")),
        "Bikeshare is far more weather-driven than a café, so if anything this is an upper bound. That is why the portal shows its estimate as advice only, and why we cannot tell you a learned hedge beats doing nothing. The only way to answer the real question is real sales from real shops. That is the pilot.",
        num["S-E"], "Sources: eval-06 results.json verdicts.T2.G1/G2.heat_rain_median vs PREREG T2 (FAIL); verdicts.T3.G1.ladder_median; verdicts.T1.G1.mu_wet")
    # S-F built
    S["S-F"] = sec("sf",
        h2("What is built, and how we checked it") +
        lead("The whole loop runs today in simulation, from sales upload to quote, purchase, auction, settlement and pool accounting. The same scenario run through the real contracts on a local test chain gives exactly the same money.") +
        row(f'<div style="flex:1;display:flex;flex-direction:column;gap:20px">' +
            card("Engine and contracts agree to the unit", "64 auction books, 192 payouts, 23 pool sequences, 14 oracle cases. 41 Foundry tests pass after a hardening pass fixed 6 audit findings; the full protocol runs under the chain's 3M-gas small blocks.") +
            card("A planted tamper is caught", "A 3-day New York scenario through the deployed contracts on a local chain (710 transactions) matches the simulator's money exactly. Minting USDC behind the engine's back makes every call refuse.") +
            card("Live in sim at public URLs", "Portal wi-portal.vercel.app sells heat, cool and rain cover; engine wi-engine.vercel.app. Rain pays a fixed amount per day of measurable rain at the city's Kalshi station, the same rule the Kalshi contract settles on. Square connect passes on 107k recorded orders with zero network calls. The testnet deploy script is written; the founder runs it.") + '</div>',
            img(B["s03"], 700, 640, "The seeded LaGuardia-minus-Central-Park auction cleared at 69 cents for 20 units with the conservation check", "cover", crop="1 50% 55%")),
        "Everything you will see is simulated: test dollars, a simulated clock, a simulated chain. The weather readings and Kalshi prices in the demo world are real history from this summer. Nothing is on testnet yet because I run that deploy myself, and nothing is on mainnet. Demo cue: switch to https://wi-portal.vercel.app here and follow reports/pitch/DEMO-WALKTHROUGH.md, about five minutes.",
        num["S-F"], "Sources: 08-SUMMARY + 08-AUDIT hardening pass (parity counts, 41 forge tests, 6 findings); 13-RAIN-SUMMARY (rain cover, 216/216 trace evidence); 09-SUMMARY (710 txs, golden scenario, CHAIN_DIVERGED); 07-SUMMARY (3,248 events, 79,000 USDC conserved); 12-01-SUMMARY (A1-A4)")
    # S-H legal (dark)
    S["S-H"] = sec("sh",
        h2("The legal fork: swap or insurance", dark=True) +
        lead("A weather payout with no proof of loss is a swap under US law unless a licensed insurer issues it. How we sell this is a question for counsel, and nothing goes to mainnet, takes real money or faces a real customer before we have the answer.", dark=True) +
        row(f'<div style="flex:1;display:flex;flex-direction:column;gap:12px;background:#2A3849;padding:32px;border:1px solid #3C4B5E;border-radius:12px"><h3 style="font-size:30px;font-weight:600;color:{LIGHT_ON_DARK}">Offshore + geo-block</h3><p style="font-size:26px;line-height:1.4;color:{BODY_ON_DARK}">Our read: does not work for us. Every business we would serve sits near a US station. Polymarket and Opyn were charged on close facts; blocking US IPs was not enough.</p></div>',
            f'<div style="flex:1;display:flex;flex-direction:column;gap:12px;background:#2A3849;padding:32px;border:1px solid #3C4B5E;border-radius:12px"><h3 style="font-size:30px;font-weight:600;color:{LIGHT_ON_DARK}">Carrier-issued parametric policy</h3><p style="font-size:26px;line-height:1.4;color:{BODY_ON_DARK}">Our read: the last-mile gap sold as a filed policy from a licensed insurer; the on-chain pool as fully collateralised reinsurance for eligible investors.</p></div>',
            f'<div style="flex:1;display:flex;flex-direction:column;gap:12px;background:#2A3849;padding:32px;border:1px solid #3C4B5E;border-radius:12px"><h3 style="font-size:30px;font-weight:600;color:{LIGHT_ON_DARK}">Exchange-listed contracts</h3><p style="font-size:26px;line-height:1.4;color:{BODY_ON_DARK}">Our read: station and regional legs on a regulated exchange. Off-exchange swaps to businesses under about $10M in assets are unlawful, and many cafés will not clear that bar.</p></div>') +
        f'<p style="font-size:26px;line-height:1.4;color:{ACCENT_ON_DARK}"><b>We take all three to counsel and pick after the answer.</b> The memo also sketches a hybrid (exchange legs + carrier policy + on-chain reinsurance) for counsel to test. Research for counsel, not legal advice; our reading is tagged as an estimate in the memo.</p>',
        "This is the biggest single unknown, and I would rather you hear it from me. We have not picked a route; all three go to counsel and we decide on the answer. Our own reading is that offshore is weakest for us, because every business we would serve sits near a US station. The open-wallet auction stays in the design until counsel says otherwise.",
        num["S-H"], "Sources: legal memo §2 (CEA §1a(47), 17 CFR 1.3 Swap para 4, CEA §12(h), §2(e)); §4 (CEA §5h(a)(1); CFTC PR 8478-22, PR 8774-23); §7 (routes, hybrid, 10 gates)", dark=True)
    # S-G proven / not proven / money
    S["S-G"] = sec("sg",
        h2("Where it stands: proven, not proven, and what the money buys") +
        row(f'<div style="flex:1;display:flex;flex-direction:column;gap:14px;background:{CARD};padding:32px;border:1px solid {LINE};border-radius:12px"><h3 style="font-size:30px;font-weight:600;color:{DARK}">Proven</h3>' +
            ul(["Station contracts track the exposure (0.95); within 50 km the station alone still gives 0.81 for temperature", "Daily rain market beats climatology (Brier 0.106 vs 0.247)", "Settlement data is clean: no payout-moving revision in 4,573 station-days", "A weekly rain residual on PRISM cells beats the station alone (+0.23, on all 26 pairs)", "Rain sensitivity is learnable on bikeshare (−10.5% wet days)", "On-chain auction and pool built with exact engine-to-contract parity (6 audit findings fixed); portal sells heat, cool and rain cover in the live sim demo, and the rain hedge matched the cover on all 216 settled 2026 markets"], 24) + '</div>',
            f'<div style="flex:1;display:flex;flex-direction:column;gap:14px;background:{CARD};padding:32px;border:1px solid {LINE};border-radius:12px"><h3 style="font-size:30px;font-weight:600;color:{DARK}">Not proven</h3>' +
            ul(["A café's sensitivity on real sales", "A day-ahead price that passes our bar", "A temperature residual that clears our +0.10 bar (best design +0.06), so heat cover ships as the station leg plus RFQ residuals", "Junior capital surviving a bad season (three-season test fails); a rain book the pool can afford (junior fails under every split)", "Demand: no customers; nothing on testnet or mainnet", "The legal route; \"cheaper than bespoke\" never measured"], 24) + '</div>',
            f'<div style="flex:1;display:flex;flex-direction:column;gap:14px;background:{CARD};padding:32px;border:1px solid {LINE};border-radius:12px"><h3 style="font-size:30px;font-weight:600;color:{DARK}">What the money buys</h3>' +
            ul(["A pilot with real sales from weather-exposed shops, its test written down first", "Counsel's answer on the legal fork", "A re-run of price and depth on our own recorded order books", "Testnet, audits, then mainnet only after the counsel gates"], 24) + '</div>'),
        "If you remember one slide, make it this one. I would rather show you what failed than have you find it in the appendix. Most of what is unproven can only be answered with real shops, a lawyer and a season of data, which is what we are raising for.",
        num["S-G"], "Sources: eval-01 he_cover, rain_daily.horizons.24.brier_*; eval-03 results.json (basis 0.81, temperature best +0.061 vs +0.10 bar, rain G1-P +0.229 on 26/26 pairs); eval-04-05 verdicts.M4.share; eval-06 verdicts.T1.G1.mu_wet; junior_returns.json three_season_sum_p05 = −190%; EVALUATION.md §11")
    # S-I ask
    S["S-I"] = sec("si",
        h2("The ask") +
        lead("A pre-seed of roughly $500k to $1.5M to get counsel's answer, run a pilot on real sales, and take the contracts through audits, going to mainnet only once the legal gates are met.") +
        table([["Raise", "Runway", "What it covers"],
               ["$500k", "about 12 months", "counsel's answer, one audit, a pilot with 10-15 businesses"],
               ["$1M", "about 18 months", "a second audit, a pilot with 25-40 businesses and an engineer; a season of policies settling"],
               ["$1.5M", "18-24 months", "everything above, token readiness if counsel clears it (entity, token opinion, KYC, geo-blocking), room to grow the book"]],
              [14, 22, 64], 26) +
        f'<p style="font-size:26px;line-height:1.4;color:{BODY}">The house seed is the pilot book\'s first-loss target, at most $206k for a book the size of our simulation; a first pilot needs far less. The rest is runway and hedging float.</p>' +
        f'<p style="font-size:26px;line-height:1.4;color:{ACCENT}">{{{{TEAM_LINE}}}}</p>',
        "The first dollars go to the things that could kill this: the legal answer and whether real shops' sales move with the weather enough to pay for cover. If either comes back badly, we will know within a year and we will not have spent the money pretending otherwise.",
        num["S-I"], "Sources: token memo §7 (uses of funds; audit costs from published 2026 pricing; counsel, team and pilot figures are estimates until quoted); handoff.json junior_ES95_30d_usd; memo Appendix B (comparable round sizes)")
    return S

def crypto(B):
    num = {"S-A":6,"S-B":7,"S-C":8,"S-D":9,"S-E":11,"S-F":12,"S-H":13,"S-G":14,"S-I":15}
    S = shared_slides(B, num)
    slides = {}
    slides["c01"] = sec("c01",
        f'<div style="flex:1"></div>' + eyebrow("weather-insurance · pre-seed · September 2026") +
        f'<h1 style="font-family:{HEAD};font-size:88px;font-weight:400;line-height:1.1;color:{DARK}">Weather cover for small businesses, carried by an on-chain pool</h1>' +
        lead("A small business gets paid when the weather hurts its sales. The risk is carried by a USDC pool on Hyperliquid's EVM chain, and the first loss is owned by the pool's token.") +
        row(card("Where we are", "Working prototype in simulation, contracts ready for testnet. No customers and nothing on mainnet yet."),
            card("The ask", "Pre-seed, roughly $500k to $1.5M.")) + '<div style="flex:1"></div>',
        "I will show you what we proved, what failed, and the demo. The short version: the payout works, the pool is the business, and the legal route is the open question.",
        1, "Sources: PROJECT.md (Out of Scope, Constraints); legal memo §1 Status; OWNER-RULINGS.md (the ask)")
    slides["c02"] = sec("c02",
        h2("A café loses money on the wrong weather, and the only liquid weather contracts settle at an airport") +
        lead("Small businesses have real weather risk, but the liquid contracts settle at a few official stations and bespoke cover is priced for big buyers.") +
        row(card("The risk is at the door", "An ice cream shop in Queens does well on hot days and loses on cool, rainy ones. A café can be the opposite."),
            card("The contracts are at the airport", "The liquid US weather contracts settle at a handful of stations: Central Park, Midway, Miami airport, Newark, Trenton."),
            card("Bespoke cover is for big buyers", "One provider's minimum premium is usually $50,000. The small-business version has been tried before and died on demand and analyst cost.")),
        "The risk is at the shop's door, but the only contracts anyone trades settle at the airport. That gap is what we are trying to close without paying an analyst to write a custom contract for every café.",
        2, "Sources: EVALUATION.md §2; CONVENTIONS.md; legal memo §7 ($50,000 minimum, Descartes, 25 Jun 2025); PROJECT.md Context (WeatherBill)")
    slides["c03"] = sec("c03",
        h2("How it works, and why Hyperliquid's EVM chain") +
        lead("A business buys one policy. The house hedges the station part on Kalshi. The gap between the station and the shop is quoted on request for heat; for rain it settles weekly on PRISM grid cells and trades in the daily on-chain batch auction. A USDC pool takes whatever does not match.") +
        row(f'<div style="flex:1;display:flex;flex-direction:column;gap:20px">' +
            card("Two ways to buy", "We handle the hedge (default), or the business places the station contracts itself and we sell only the local gap.") +
            card("Why this chain", "Ordinary HyperEVM smart contracts, so no HYPE stake is needed. The auction clears in a fixed number of steps; its worst case (about 480k gas) fits the chain's 3M-gas small blocks. Deploying needs big-block mode once.") +
            card("Untested", "Whether Hyperliquid users want to hold weather risk. Nobody has tested that.") + '</div>',
            img(B["s07"], 700, 640, "The two purchase paths side by side in the portal: we handle the hedge, or you place the Kalshi part", "cover", crop="1 50% 62%")),
        "The chain choice is practical. We do not need a native market or a big stake, just contracts that clear cheaply once a day. The part I cannot tell you yet is whether people on Hyperliquid want to hold weather risk; nobody has tested that.",
        3, "Sources: token memo §1, §8; legal memo §1; OWNER-RULINGS.md (hedge leg); PROJECT.md Out of Scope (no stake); 08-SUMMARY gas table (clear 479,473 gas)")
    slides["c04"] = sec("c04",
        h2("The pool, and who loses first") +
        lead("All pool money is USDC in one vault. The house's own money loses first, outside depositors lose only after it is gone, and every live policy's maximum payout is set aside before the policy binds.") +
        row(f'<div style="flex:1;display:flex;flex-direction:column;gap:20px">' +
            card("Junior layer", "Protocol-owned USDC, seeded by the house, then retained premium. It takes every loss first and all the hedge profit or loss.") +
            card("Senior layer", "Outside stablecoin depositors, later, and only if counsel allows. Senior gets about a fifth of the margin we keep, not a fifth of the premium.") +
            card("Why margin, not premium", "Under the first rule junior lost money in all four simulated seasons, because on this product the premium is almost all expected payout. The house trades only as the pool's agent and returns or writes off each day's money within a 10-day window; both books are published.") + '</div>',
            img(B["s04"], 700, 640, "The pool page: junior and senior tranches and the junior-loses-first note (the 0.30% senior rate is the v0 parameter, not a measured return)", "cover", crop="1 50% 18%")),
        "Our first draft paid senior 20% of the whole premium, and the junior layer lost money every season, because on this product the premium is almost all expected payout. So senior now shares the margin we keep. That is the kind of thing the simulation is for.",
        4, "Sources: token memo §2; seat ruling 2026-09-30 (07-CONTEXT addenda); 08-SUMMARY invariant_juniorFirst; junior_returns.json observed.primary.spec_t10.by_season.*.junior_return")
    slides["c05"] = sec("c05",
        h2("What the token is, and what it is not") +
        lead("WI is how you own the first-loss layer: staked WI is burned in proportion to junior losses, and the design has it vote on the pool's risk settings inside fixed ranges with a delay (in v0 an owner key sets those parameters; the voting is not built yet). It never pays a claim, has a fixed supply and no emissions, and in the first version stakers earn nothing.") +
        row(card("Claims are paid in USDC", "We never sell our own token into a falling market to pay one."),
            card("Burned, never sold", "If the junior layer loses 10% on a day, every staked position is cut 10% (capped at 30% a day) and the cut WI is burned. The cut follows dollars lost, so there is no WI price feed to manipulate. Unstaking takes 12 days, so nobody exits ahead of a heatwave everyone can see coming."),
            card("What stakers earn is for counsel", "The pilot does not need a token at all. We describe WI as junior capital in a pool, offered only to eligible investors under an exemption.")),
        "Every rule here comes from a protocol that got hurt. Aave dropped its own-token backstop because a loss meant selling the token into a crash. Maple's stakers left right before a default. So the money is USDC, the token is burned instead of sold, and you cannot unstake ahead of a heatwave everyone can see coming. We will not pitch staking as a way to make money. Right now it earns nothing.",
        5, "Sources: token memo §3, §4, Appendix A; SPEC §17 (12-day cooldown, seat ruling); 08-SUMMARY (5,940 WI burned on a loss day in the local-chain run); legal memo §5 (rights to future income)")
    slides["c10"] = sec("c10",
        h2("What the first-loss layer earns, and why it is not good enough yet") +
        lead("The median modelled season earns 43% on the junior money, but a 1-in-20 season wipes it out and our own three-season test fails, so the risk load has to go up.") +
        table([["", "2023", "2024", "2025", "2026", "Median season", "1-in-20", "Worst (2009)"],
               ["Junior return, simulated on real Kalshi prices", "+123%", "+97%", "+159%", "−65%", "", "", ""],
               ["Junior return, modelled over 26 past summers", "", "", "", "", "+43%", "−144%", "−332%"]],
              [30, 9, 9, 9, 9, 12, 10, 12], 26) +
        row(card("What passing would take", "About $177k a season of kept margin; the junior layer keeps about $47k now. Premium is $2.63M a season with only $40k (1.5%) of margin inside it."),
            card("The fix, and the open question", "A bigger risk load, a smaller book per junior dollar, or both. The pilot has to show whether businesses pay for that. All of this is a simulated book, not customers.")),
        "I am not going to dress this up. On today's settings the junior money has good years and then loses everything about once every twenty summers. That is fixable, but only by charging businesses more, and we do not know yet whether they will pay. That is a pilot question, not a spreadsheet question.",
        10, "Sources: junior_returns.json observed.primary.margin_t10.by_season.*; model.splits.margin_t10.boot_median/.boot_p05_1in20/.hist_worst/.junior_income_needed_per_season_for_rule_usd; premium_split_mean_observed_season.*")
    order = ["c01","c02","c03","c04","c05","sa","sb","sc","sd","c10","se","sf","sh","sg","si"]
    files = {**slides, **{k: v for k, v in S.items()}}
    # map tags to ids
    byid = {"c01":slides["c01"],"c02":slides["c02"],"c03":slides["c03"],"c04":slides["c04"],"c05":slides["c05"],"c10":slides["c10"],
            "sa":S["S-A"],"sb":S["S-B"],"sc":S["S-C"],"sd":S["S-D"],"se":S["S-E"],"sf":S["S-F"],"sh":S["S-H"],"sg":S["S-G"],"si":S["S-I"]}
    sections = {"problem":{"description":"The problem and the ask","start":"c01"},
                "how":{"description":"How it works: chain, pool, token","start":"c03"},
                "evidence":{"description":"What we proved and what failed","start":"sa"},
                "built":{"description":"What is built, the legal fork, status","start":"sf"},
                "ask":{"description":"The ask","start":"si"}}
    return "Weather cover pitch (crypto)", order, byid, sections

def fintech(B):
    num = {"S-A":5,"S-B":6,"S-E":8,"S-C":9,"S-D":10,"S-F":11,"S-H":12,"S-G":14,"S-I":15}
    S = shared_slides(B, num)
    slides = {}
    slides["f01"] = sec("f01",
        f'<div style="flex:1"></div>' + eyebrow("weather-insurance · pre-seed · September 2026") +
        f'<h1 style="font-family:{HEAD};font-size:88px;font-weight:400;line-height:1.1;color:{DARK}">Weather cover for small businesses, paid from the public weather record</h1>' +
        lead("A small business picks a payout tied to the temperature or rain near it, pays a premium, and gets paid automatically when the official weather number crosses the line. No claim to file.") +
        row(card("Where we are", "Working prototype in simulation. No customers and no real money yet."),
            card("The ask", "Pre-seed, roughly $500k to $1.5M.")) + '<div style="flex:1"></div>',
        "I will walk you through what the business sees, what our numbers say, what failed, and what we would do with the money.",
        1, "Sources: PROJECT.md (Out of Scope); legal memo §1 Status; OWNER-RULINGS.md (the ask)")
    slides["f02"] = sec("f02",
        h2("Weather moves small-business sales, and nobody sells them simple cover") +
        lead("A café or ice cream shop has real weather risk, but bespoke weather cover is priced for big buyers, and the one small-business attempt we know of died on demand and underwriting cost.") +
        row(card("The risk is real", "An ice cream shop does well on hot days and loses on cool, rainy ones. A café can be the opposite."),
            card("Bespoke cover has high minimums", "One provider's minimum premium is usually $50,000."),
            card("Small parametric cover can be sold", "A filed tornado policy on an NWS trigger sells for about $88 a year in 15 states. Nobody does it for daily heat or rain yet, as far as we found.")),
        "The reason this does not exist is not that the risk is fake. It is that writing a custom contract for a café costs more than the café would pay. So the question is whether we can price it from public data and liquid contracts instead of analysts.",
        2, "Sources: legal memo §7 (Descartes $50,000 minimum, 25 Jun 2025; Sola tornado policy about $88 a year, Artemis 31 Aug 2023, secondary); PROJECT.md Context (WeatherBill)")
    slides["f03"] = sec("f03",
        h2("What the business sees") +
        lead("Upload a year of daily sales or connect Square, see how the weather has moved them, pick a cover, buy it, and watch it settle day by day on the official climate report. The hedge-fit numbers on these screens come from demo data, not evidence.") +
        row(img(B["s06"], 530, 560, "Sales upload and the learned weather sensitivity, shown as advice", "cover", crop="1 50% 80%"),
            img(B["s07"], 530, 560, "Two ways to buy, every price broken out", "cover", crop="1 50% 62%"),
            img(B["s11"], 530, 560, "A policy settling day by day on the NWS climate report with a data-version hash", "cover", crop="1 50% 20%")),
        "The whole point is that the owner of a shop never has to understand a weather contract. They see a line, a price and a payout. The hedge-fit number on these screens comes from demo data; the real evidence is on the next slides.",
        3, "Sources: 10-SUMMARY (end-to-end smoke: balance after settlement = start − premium + payouts, to the cent); 12-01-SUMMARY (A1-A4 on 107k recorded Square orders); eval-06 priors.json advisory_only = true")
    slides["f04"] = sec("f04",
        h2("How we pay for it") +
        lead("Most of the payout is backed by liquid station contracts, a small local contract covers the gap between the station and the shop, and a capitalised pool carries what is left.") +
        row(f'<div style="flex:1;display:flex;flex-direction:column;gap:20px">' +
            card("Default: one fixed-price policy", "The business buys one policy and the house hedges the station part every day.") +
            card("Fallback: place the station contracts yourself", "The business buys the station contracts itself and we sell only the local gap.") +
            card("Why the default carries forecast risk", "A day ahead, the station contracts only hedge the forecast miss (next two slides). Think of it as a small insurer with a very good, very cheap hedge for most of its risk, and a pool for the rest. Whether it legally is one is slide 12.") + '</div>',
            img(B["s07"], 700, 640, "We handle the hedge versus you place the Kalshi part, side by side", "cover", crop="1 50% 62%")),
        "Think of it as a small insurer that happens to have a very good, very cheap hedge for most of its risk, and a pool for the rest. I say insurer loosely; whether it legally is one is slide 12.",
        4, "Sources: OWNER-RULINGS.md (hedge leg); legal memo §1; EVALUATION.md §10")
    slides["f07"] = sec("f07",
        h2("Rain is the cleanest first product") +
        lead("Kalshi's daily rain market forecasts far better than climatology and costs about 20% over fair value, so rain-day cover is the simplest thing to sell first, with one rule we have to write down for trace days.") +
        row(f'<div style="flex:1;display:flex;flex-direction:column;gap:24px">' +
            row(bignum("0.106", "the market's day-ahead Brier score, against 0.247 for climatology: a pre-registered pass"), bignum("$1.20", "per $1 of payout a day ahead, fees included; a wet-day exposure tracks 0.83 before price, 0.27 after (0.76 and 0.23 under the trace-is-dry rule the cover uses)")) +
            card("What the pool has to carry", "Kalshi's daily rain contract pays only on measurable rain (0.01 in or more), and our rain cover uses the same rule, so the hedge matches the cover on every day (216 of 216 settled 2026 markets). Rain does not net (0.003) and Kalshi's daily rain markets are about 300 times too thin to lay it off, so a rain book is the pool's own risk: about $1.08M of 30-day capital at 2% take-up, and the junior layer loses money in a bad year.") + '</div>',
            img(B["fig3"], 640, 470, "Market versus climatology Brier score by horizon for the daily rain market", "contain")),
        "If I had to sell one thing to a café next month, it would be: we pay you on rainy days. It is easy to explain and the market prices it well. What we still do not know is whether a café's sales drop enough on rainy days to make the cover worth its price.",
        7, "Sources: eval-01 rain_daily.horizons.24.brier_market/.brier_clim (T3 PASS, gain 0.141); .cost_per_dollar_payout; .he_wet.*; rain_daily.trace_yes_share; EVALUATION.md §7; 09-SUMMARY (rain peril not yet in the API)")
    slides["f13"] = sec("f13",
        h2("The pool and the token, briefly") +
        lead("The pool is plain USDC with the house's own money losing first. A token comes later, if at all, as junior capital offered to eligible investors under an exemption. The pilot does not need one.") +
        row(f'<div style="flex:1;display:flex;flex-direction:column;gap:20px">' +
            card("Every policy is fully reserved", "Its maximum payout is set aside before it binds. The house's money takes losses first; outside depositors come later and only if counsel allows.") +
            card("Under the hybrid route", "The pool becomes collateralised reinsurance behind a licensed carrier, which may take it out of commodity-pool rules.") +
            card("On today's settings", "The first-loss layer earns +43% in a median modelled season and is wiped out in a 1-in-20 season, so the risk load has to go up.") + '</div>',
            img(B["s04"], 700, 640, "The pool page: tranches and the junior-loses-first note (the 0.30% senior rate is the v0 parameter, not a result)", "cover", crop="1 50% 18%")),
        "For a fintech investor the token is an option, not the plan. If counsel says the right home is a carrier plus reinsurance, the pool still works, and the token becomes an interest in that vehicle sold to eligible investors.",
        13, "Sources: token memo §2-3; legal memo §5, §7 (route ii); junior_returns.json model.splits.margin_t10.boot_median/.boot_p05_1in20 (modelled)")
    order = ["f01","f02","f03","f04","sa","sb","f07","se","sc","sd","sf","sh","f13","sg","si"]
    byid = {"f01":slides["f01"],"f02":slides["f02"],"f03":slides["f03"],"f04":slides["f04"],"f07":slides["f07"],"f13":slides["f13"],
            "sa":S["S-A"],"sb":S["S-B"],"sc":S["S-C"],"sd":S["S-D"],"se":S["S-E"],"sf":S["S-F"],"sh":S["S-H"],"sg":S["S-G"],"si":S["S-I"]}
    sections = {"problem":{"description":"The problem, the product and the ask","start":"f01"},
                "evidence":{"description":"What we proved and what failed","start":"sa"},
                "built":{"description":"What is built, the legal fork, the pool","start":"sf"},
                "ask":{"description":"Status and the ask","start":"sg"}}
    return "Weather cover pitch (fintech)", order, byid, sections

FACES = {"libre-baskerville":{"family":"Libre Baskerville","href":"https://fonts.googleapis.com/css2?family=Libre+Baskerville:ital,wght@0,400;0,700;1,400&display=swap"},
         "public-sans":{"family":"Public Sans","href":"https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;600;700&display=swap"}}

for deck, build in (("crypto", crypto), ("fintech", fintech)):
    title, order, byid, sections = build(BLOBS[deck])
    base = os.path.join(ROOT, deck, "project")
    os.makedirs(os.path.join(base, "slides"), exist_ok=True)
    for sid in order:
        with open(os.path.join(base, "slides", f"{sid}.html"), "w") as f:
            f.write(byid[sid])
    index = {"v":4, "createdOnFiles":{"v":1,"at":NOW}, "lists":"css", "title":title, "order":order, "cover":order[0], "sections":sections, "faces":FACES, "designSystems":[]}
    with open(os.path.join(base, "deck.json"), "w") as f:
        json.dump(index, f, indent=1)
    print(deck, len(order), "slides")
