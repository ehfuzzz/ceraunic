// Hosted-demo smoke (Phase 13): drives the public portal alias in installed Chrome (Playwright channel "chrome").
//
//   node scripts/smoke-demo.mjs                                   # https://wi-portal.vercel.app
//   PORTAL_URL=http://localhost:3010 node scripts/smoke-demo.mjs  # any portal in sim mode
//
// Part A reads the seeded shared `demo` world (read-only) and checks the page shows the numbers in
// reports/demo/seed-state.json. Part B is the visitor loop in a private world: onboard -> upload the Phase 12
// fixture CSV -> elasticity -> recommendation -> quote -> buy -> auction (post an order, clock past the cutoff,
// see it clear) -> settle (clock past D+2 of the last covered day). Money checks: after buying, the balance is exactly
// faucet - premium; after settlement it is exactly (balance after the auction cleared) + the sum of every payout row
// the page shows. The clock moves with plain POST /api/v1/sim/advance calls on the portal origin for the private
// world (no admin token: only the shared demo world's clock needs one, and this script never touches it).
// B8 (13-RAIN) buys a 7-day rain cover in the same private world and checks each wet day at O'Hare paid $20.
// Writes reports/demo/screenshots/*.png and reports/demo/SMOKE.md (step timings). Exit 1 on the first failure.
import { createRequire } from "node:module";
import { mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const require = createRequire(path.join(ROOT, "apps/portal/package.json"));
const { chromium } = require("@playwright/test");

const PORTAL = (process.env.PORTAL_URL ?? "https://wi-portal.vercel.app").replace(/\/$/, "");
const SHOTS = path.join(ROOT, "reports/demo/screenshots");
const CSV = path.join(ROOT, "apps/portal/fixtures/square/csv-export.csv");
const SEED = JSON.parse(readFileSync(path.join(ROOT, "reports/demo/seed-state.json"), "utf8"));
const T = 45_000;

const cents = (s) => Math.round(Number(String(s).replace(/[^0-9.-]/g, "")) * 100);
const money = (c) => `$${(c / 100).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const e6c = (e6) => Math.round(e6 / 10_000);

const steps = [];
const facts = [];
let page;

function fail(msg) {
  throw new Error(msg);
}
async function until(what, fn, ms = T) {
  const t0 = Date.now();
  let last;
  while (Date.now() - t0 < ms) {
    try {
      const v = await fn();
      if (v) return v;
    } catch (e) {
      last = e;
    }
    await page.waitForTimeout(300);
  }
  fail(`timed out waiting for: ${what}${last ? ` (${last.message.split("\n")[0]})` : ""}`);
}
const text = (tid) => page.getByTestId(tid).first().innerText();
const visible = (tid, ms) => until(`${tid} visible`, () => page.getByTestId(tid).first().isVisible(), ms);
const contains = (tid, s, ms) => until(`${tid} contains ${s}`, async () => (await text(tid)).includes(s), ms);
async function shot(name) {
  await page.screenshot({ path: path.join(SHOTS, name), fullPage: true });
  return name;
}
async function step(name, fn) {
  const t0 = Date.now();
  process.stdout.write(`- ${name} ... `);
  try {
    const note = await fn();
    const s = (Date.now() - t0) / 1000;
    steps.push({ name, s, ok: true, note: note ?? "" });
    console.log(`ok ${s.toFixed(1)}s${note ? `  (${note})` : ""}`);
  } catch (e) {
    const s = (Date.now() - t0) / 1000;
    steps.push({ name, s, ok: false, note: e.message });
    console.log(`FAILED ${s.toFixed(1)}s: ${e.message}`);
    try {
      await shot("FAILED.png");
    } catch {}
    throw e;
  }
}
async function advance(world, days) {
  const r = await page.request.post(`${PORTAL}/api/v1/sim/advance`, { headers: { "X-WI-World": world }, data: { days } });
  if (!r.ok()) fail(`advance ${days}: HTTP ${r.status()} ${await r.text()}`);
  return (await r.json()).simTime;
}
async function apiGet(world, p) {
  const r = await page.request.get(`${PORTAL}/api/v1${p}`, { headers: { "X-WI-World": world } });
  if (!r.ok()) fail(`GET ${p}: HTTP ${r.status()}`);
  return r.json();
}
const balanceText = async () => (await text("usdc-balance")).replace(" test USDC", "");

async function main() {
  mkdirSync(SHOTS, { recursive: true });
  rmSync(path.join(SHOTS, "FAILED.png"), { force: true });
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  let ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: "light" });
  page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const tAll = Date.now();
  let ok = false;
  try {
    // ------------------------------------------------------------ 0. the alias is up and proxies the engine
    await step("health: portal alias proxies the engine in sim mode", async () => {
      const r = await page.request.get(`${PORTAL}/api/v1/health`);
      const h = await r.json();
      if (!r.ok() || h.mode !== "sim") fail(`health ${r.status()} ${JSON.stringify(h)}`);
      if (h.simTime !== SEED.simTime) fail(`demo world clock ${h.simTime}, seeded ${SEED.simTime} (re-run scripts/seed-demo.py?)`);
      return `mode ${h.mode}, demo clock ${h.simTime}`;
    });

    // ------------------------------------------------------------ A. the seeded shared world
    const chi = SEED.merchants.chi;
    await step("A1 seeded world: Chicago bakery policy, first day paid", async () => {
      await page.goto(`${PORTAL}/app/demo?as=chi`);
      await until("redirect to policies", () => page.url().endsWith("/app/policies"));
      await contains("policy-row", chi.policyId);
      const nRows = chi.settlements.length + (chi.rain?.settlements.length ?? 0); // heat + rain (13-RAIN) settled days
      await until(`${nRows} settlement rows`, async () => (await page.getByTestId("settlement-row").count()) === nRows);
      const rows = await page.getByTestId("settlement-row").allInnerTexts();
      const row = rows.find((r) => r.includes(chi.policyId)) ?? "";
      if (!row.includes(money(e6c(chi.paidOutE6)))) fail(`settlement row "${row}" lacks ${money(e6c(chi.paidOutE6))}`);
      await until("balance", async () => (await balanceText()) === money(e6c(chi.usdcE6)));
      await shot("01-seeded-policies-chicago.png");
      return `${chi.policyId}: paid ${money(e6c(chi.paidOutE6))} on ${chi.settlements[0].day}, wallet ${money(e6c(chi.usdcE6))}`;
    });
    if (chi.rain) {
      await step("A1r seeded world: the bakery's 7-day rain cover (O'Hare)", async () => {
        const r = chi.rain;
        const rows = (await page.getByTestId("policy-row").allInnerTexts()).filter((x) => x.includes(r.policyId));
        if (rows.length !== 1 || !rows[0].includes("Rainy days") || !rows[0].includes(money(e6c(r.premiumE6))))
          fail(`rain policy row: ${rows.join(" / ")}`);
        await page.goto(`${PORTAL}/app/policies/${r.policyId}`);
        await visible("policy-detail");
        const body = await page.locator("main").innerText();
        if (!body.includes("Chicago O'Hare") || !body.includes("trace")) fail("rain policy detail lacks O'Hare / trace wording");
        const settled = await page.getByTestId("settlement-row").count();
        if (settled !== r.settlements.length) fail(`${settled} settled rain days, seeded ${r.settlements.length}`);
        await shot("13-rain-seeded-policy.png");
        return `${r.policyId}: $${r.units}/wet day ${r.days[0]}..${r.days[r.days.length - 1]}, premium ${money(e6c(r.premiumE6))}, ${settled} day settled (${r.settlements.map((x) => `${x.day} ${x.value ? "wet" : "dry"} ${money(e6c(x.payoutE6))}`).join(", ")})`;
      });
    }
    for (const k of ["nyc", "mia"]) {
      const m = SEED.merchants[k];
      await step(`A1 seeded world: ${m.name}`, async () => {
        await page.goto(`${PORTAL}/app/demo?as=${k}`);
        await until("redirect", () => page.url().endsWith("/app/policies"));
        await contains("policy-row", m.policyId);
        await until("balance", async () => (await balanceText()) === money(e6c(m.usdcE6)));
        const row = await page.getByTestId("settlement-row").first().innerText();
        if (!row.includes(money(e6c(m.paidOutE6)))) fail(`settlement row "${row}" lacks ${money(e6c(m.paidOutE6))}`);
        if (k === "mia") await shot("02-seeded-policies-miami.png");
        return `paid ${money(e6c(m.paidOutE6))}, wallet ${money(e6c(m.usdcE6))}`;
      });
    }
    const au = SEED.auction;
    await step("A2 seeded world: the cleared LaGuardia auction", async () => {
      await page.goto(`${PORTAL}/app/trade`);
      await page.getByRole("button", { name: "cleared", exact: true }).click();
      const row = page.locator("tr", { hasText: "RES-LGA-NYC" }).filter({ hasText: au.day });
      await until("auction row", () => row.first().isVisible());
      await row.first().getByRole("button").first().click();
      const panel = page.getByText("Conservation check").first();
      await until("conservation text", () => panel.isVisible());
      const t = await panel.innerText();
      if (!t.includes("They match")) fail(`conservation: ${t}`);
      const body = await page.locator("main").innerText();
      if (!body.includes(`${Math.round(au.priceE6 / 10_000)}¢`)) fail(`clearing price ${au.priceE6} not shown`);
      await shot("03-seeded-auction-cleared.png");
      return `${au.auctionId}: ${Math.round(au.priceE6 / 10_000)}c, ${au.filledQty} units, conservation ok`;
    });
    await step("A3 seeded world: pool", async () => {
      await page.goto(`${PORTAL}/app/pool`);
      const want = money(e6c(SEED.pool.juniorAssetsE6)).replace(/\.\d\d$/, "");
      await until(`junior ${want}`, async () => (await page.locator("main").innerText()).includes(want));
      await shot("04-seeded-pool.png");
      return `junior ${money(e6c(SEED.pool.juniorAssetsE6))}, senior ${money(e6c(SEED.pool.seniorAssetsE6))}`;
    });

    // ------------------------------------------------------------ B. the visitor loop in a private world
    let world, premium, policyId, covered, balAfterClear, auctionId, fillQty;
    // a new visitor: fresh browser storage (no demo address, no world), like opening the link on another laptop
    await ctx.close();
    ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: "light" });
    page = await ctx.newPage();
    page.on("pageerror", (e) => errors.push(e.message));
    await step("B1 onboard: business in Chicago (private world)", async () => {
      await page.goto(`${PORTAL}/app/onboard`);
      await page.getByTestId("use-demo-address").click();
      await contains("holder-card", "demo address");
      await page.getByTestId("business-name").fill("Bakehouse on Archer");
      await page.getByTestId("business-address").fill("5700 S Cicero Ave, Chicago, IL 60638");
      await contains("geocode-result", "Chicago");
      await page.getByTestId("business-naics").selectOption("311811");
      await page.getByTestId("business-save").click();
      await contains("business-card", "KMDW");
      world = await page.evaluate(() => localStorage.getItem("wi.world"));
      if (!/^w_[0-9a-f]{12}$/.test(world ?? "")) fail(`private world id ${world}`);
      await shot("05-onboard-business.png");
      return `world ${world}`;
    });
    await step("B2 upload: fixture CSV -> sales summary -> elasticity", async () => {
      await page.getByTestId("sales-upload-input").setInputFiles(CSV);
      await page.getByTestId("sales-location").selectOption("LFIXCHI000002");
      await visible("sales-send");
      const sent = Number((await text("sales-send")).match(/Send (\d+) days/)[1]);
      await page.getByTestId("sales-send").click();
      await contains("sales-summary", `${sent} days of sales`);
      await visible("elasticity-beta");
      const beta = await text("elasticity-beta");
      await shot("06-sales-elasticity.png");
      return `${sent} days sent; heat effect ${beta.replace(/\s+/g, " ").slice(0, 60)}`;
    });
    await step("B3 recommend + quote (line raised to 90 F)", async () => {
      await page.getByTestId("to-coverage").click();
      await visible("recommend-card");
      const rec = (await text("recommend-card")).replace(/\s+/g, " ");
      await page.getByTestId("terms-strike").fill("90");
      await page.getByTestId("quote-button").click();
      await visible("quote-total");
      await visible("quote-total-ladder");
      premium = cents(await text("quote-total"));
      await shot("07-recommend-quotes.png");
      return `recommendation: ${rec.slice(0, 90)}...; house-hedge total ${money(premium)}`;
    });
    await step("B4 buy (house-hedge path)", async () => {
      await page.getByTestId("faucet-button").click();
      await contains("usdc-balance", "$1,000.00");
      await page.getByTestId("buy-button").click();
      await visible("exec-status-done");
      policyId = (await text("receipt-policy-id")).trim();
      if (!/^pol_/.test(policyId)) fail(`policy id ${policyId}`);
      await page.getByTestId("receipt-policy-link").click();
      await visible("policy-detail");
      covered = await page.getByTestId("pending-row").count();
      if (covered !== 7) fail(`${covered} pending days, expected 7`);
      await page.goto(`${PORTAL}/app/policies`);
      await contains("policy-row", policyId);
      await until("balance = faucet - premium", async () => (await balanceText()) === money(100_000 - premium));
      await shot("08-bought-policy.png");
      return `${policyId}, premium ${money(premium)}, balance ${money(100_000 - premium)}`;
    });
    await step("B5 auction: order on tomorrow's LaGuardia auction, clock past the cutoff, cleared", async () => {
      const t1 = await advance(world, 1);
      await page.goto(`${PORTAL}/app/trade`);
      const row = page.locator("tr", { hasText: "RES-LGA-NYC" }).filter({ hasText: "open" });
      await until("open LGA auction", () => row.first().isVisible());
      await row.first().getByRole("button").first().click();
      const detail = await page.locator("main").innerText();
      auctionId = detail.match(/auc_RES-LGA-NYC_\d{4}-\d\d-\d\d/)[0];
      const a = await apiGet(world, `/auctions/${auctionId}`);
      const askC = Math.round(a.houseQuote.askE6 / 10_000);
      fillQty = 5;
      await page.getByRole("button", { name: "buy", exact: true }).click();
      await page.getByLabel("Units").fill(String(fillQty));
      await page.getByLabel("Limit price (cents, 1 to 99)").fill(String(askC));
      await page.getByRole("button", { name: "Place buy order" }).click();
      await until("order listed", async () => (await page.locator("main").innerText()).includes("ord_"));
      await shot("09-auction-order.png");
      await advance(world, 1);
      await page.reload();
      await page.getByRole("button", { name: "cleared", exact: true }).click();
      const crow = page.locator("tr", { hasText: "RES-LGA-NYC" }).filter({ hasText: auctionId.slice(-10) });
      await until("cleared row", () => crow.first().isVisible());
      await crow.first().getByRole("button").first().click();
      const cons = page.getByText("Conservation check").first();
      await until("conservation", () => cons.isVisible());
      if (!(await cons.innerText()).includes("They match")) fail(await cons.innerText());
      const res = (await apiGet(world, `/auctions/${auctionId}`)).result;
      const me = await page.evaluate(() => localStorage.getItem("wi.trade.address"));
      const mine = res.fills.filter((f) => f.trader.toLowerCase() === me.toLowerCase()).reduce((s, f) => s + f.qty, 0);
      if (mine !== fillQty) fail(`filled ${mine} of ${fillQty}`);
      await shot("10-auction-cleared.png");
      balAfterClear = e6c((await apiGet(world, `/accounts/${me}/balances`)).usdcE6);
      return `clock ${t1} -> +1 day; ${auctionId} cleared at ${Math.round(res.priceE6 / 10_000)}c, ${res.filledQty} units (pool took ${res.poolFilledQty}), ours ${mine}; balance after clear ${money(balAfterClear)}`;
    });
    await step("B6 settle: clock past D+2 of the last covered day", async () => {
      const t = await advance(world, 7);
      await page.goto(`${PORTAL}/app/policies/${policyId}`);
      await until("Settled", async () => (await text("policy-status")) === "Settled");
      const n = await page.getByTestId("settlement-row").count();
      if (n !== covered) fail(`${n} settlement rows on the policy, expected ${covered}`);
      await shot("11-policy-settled.png");
      await page.goto(`${PORTAL}/app/policies`);
      await until("rows", async () => (await page.getByTestId("settlement-row").count()) >= covered);
      const payouts = await page.getByTestId("settlement-row").evaluateAll((rows) => rows.map((r) => r.lastElementChild.innerText));
      const paid = payouts.reduce((s, x) => s + cents(x), 0);
      const want = money(balAfterClear + paid);
      await until(`balance ${want}`, async () => (await balanceText()) === want);
      await shot("12-policies-settled.png");
      return `clock ${t}; ${payouts.length} payout rows (${covered} policy days + ${payouts.length - covered} auction position) = ${money(paid)}; balance ${want} = ${money(balAfterClear)} + ${money(paid)}`;
    });
    await step("B8 rain cover: quote Rainy days, buy $20 per wet day for 7 days, clock past D+2, wet days paid", async () => {
      await page.goto(`${PORTAL}/app/coverage`);
      await visible("recommend-card");
      await page.locator("#t-peril").selectOption("rain");
      await visible("rain-rule");
      await page.getByTestId("terms-units").fill("20");
      await page.getByTestId("quote-button").click();
      await visible("quote-total");
      await visible("rain-note");
      const house = page.getByTestId("rungs-house");
      const nContracts = await house.getByTestId("rain-contract-row").count();
      if (nContracts !== 7) fail(`${nContracts} KXRAIN rows on our path, expected 7`);
      const ladderRows = await page.getByTestId("rungs-ladder").getByTestId("rain-contract-row").count();
      if (ladderRows !== 7) fail(`${ladderRows} KXRAIN rows on the self-place path, expected 7`);
      const first = await house.getByTestId("rain-contract-row").first().innerText();
      if (!/KXRAIN-\d\d[A-Z]{3}\d\d-CHI/.test(first)) fail(`first contract row "${first}"`);
      const rainPremium = cents(await text("quote-total"));
      const houseCol = await text("quote-house-hedge");
      if (/insurance/i.test(houseCol + (await text("quote-business-ladder")))) fail("the word insurance on the quote card");
      await shot("13-rain-quote.png");
      const balBefore = await until("balance loaded", async () => {
        const c = cents(await balanceText());
        return c > 0 ? c : null;
      });
      await page.getByTestId("buy-button").click();
      await visible("exec-status-done");
      const rainPolicy = (await text("receipt-policy-id")).trim();
      await shot("13-rain-bought.png");
      await advance(world, 9);
      await page.goto(`${PORTAL}/app/policies/${rainPolicy}`);
      await until("Settled", async () => (await text("policy-status")) === "Settled");
      const rows = await page.getByTestId("settlement-row").allInnerTexts();
      if (rows.length !== 7) fail(`${rows.length} settled rain days, expected 7`);
      const wet = rows.filter((r) => r.includes("Wet day"));
      if (wet.length === 0) fail("no wet day in the week");
      for (const r of rows) {
        const want = r.includes("Wet day") ? "$20.00" : "$0.00";
        if (!r.trim().endsWith(want)) fail(`rain row "${r}" should pay ${want}`);
      }
      const paidRain = wet.length * 2000;
      await shot("13-rain-settled.png");
      await page.goto(`${PORTAL}/app/policies`);
      const want = money(balBefore - rainPremium + paidRain);
      await until(`balance ${want}`, async () => (await balanceText()) === want);
      facts.push("", `Rain step (B8): ${rainPolicy}, $20 per wet day at O'Hare, premium ${money(rainPremium)}; ${wet.length} of 7 days wet (${wet.map((r) => r.split(/\s/)[0]).join(", ")}), paid ${money(paidRain)}; first contract row: ${first.replace(/\s+/g, " ")}.`);
      return `${rainPolicy}: premium ${money(rainPremium)}; wet days ${wet.map((r) => r.split(/\s/)[0]).join(", ")} paid ${money(paidRain)}; balance ${want} = ${money(balBefore)} - ${money(rainPremium)} + ${money(paidRain)}`;
    });
    await step("B7 Square card (fixture mode) answers on the hosted route", async () => {
      const r = await page.request.get(`${PORTAL}/api/pos/square`);
      const j = await r.json();
      if (!r.ok() || j.mode !== "fixture" || j.locations.length !== 3) fail(`GET /api/pos/square ${r.status()} ${JSON.stringify(j).slice(0, 200)}`);
      const p = await page.request.post(`${PORTAL}/api/pos/square`, {
        data: { locationIds: [], start: "2026-09-01", end: "2026-09-30" }, // what the card sends: all locations, last 30 days
      });
      if (!p.ok()) fail(`POST /api/pos/square ${p.status()} ${(await p.text()).slice(0, 200)}`);
      const pj = await p.json();
      return `GET 3 locations; POST 30-day pull ok (${JSON.stringify(pj).length} bytes)`;
    });
    if (errors.length) fail(`page errors: ${errors.join(" | ")}`);
    ok = true;
  } finally {
    await browser.close();
    const total = (Date.now() - tAll) / 1000;
    const lines = [
      "# Hosted demo smoke",
      "",
      `Run ${new Date().toISOString().replace(/\.\d+Z$/, "Z")} against ${PORTAL} with \`node scripts/smoke-demo.mjs\` (installed Chrome, headless, 1440x900).`,
      `Result: **${ok ? "PASS" : "FAIL"}**, ${steps.filter((s) => s.ok).length}/${steps.length} steps, ${total.toFixed(1)} s end to end.`,
      "",
      "| Step | Seconds | Result | What it saw |",
      "|---|---:|---|---|",
      ...steps.map((s) => `| ${s.name} | ${s.s.toFixed(1)} | ${s.ok ? "ok" : "FAILED"} | ${s.note.replace(/\|/g, "/")} |`),
      "",
      "Screenshots: `reports/demo/screenshots/` (full page, light scheme).",
      "Part A reads the shared `demo` world seeded by `scripts/seed-demo.py` and compares against `reports/demo/seed-state.json`.",
      "Part B runs in a fresh private world, so it never moves the shared demo clock. Clock moves in part B are API calls",
      "(`POST /api/v1/sim/advance` on the portal origin); in the live demo the owner uses the Admin page instead.",
      ...facts,
      "",
    ];
    writeFileSync(path.join(ROOT, "reports/demo/SMOKE.md"), lines.join("\n"));
  }
  console.log(ok ? "SMOKE PASS" : "SMOKE FAIL");
  return ok;
}

main().then(
  (ok) => process.exit(ok ? 0 : 1),
  (e) => {
    console.error(e.message);
    process.exit(1);
  },
);
