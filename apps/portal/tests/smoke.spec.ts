// Sim-mode smoke: onboard -> upload the Phase 12 fixture CSV -> elasticity -> quote (both paths) -> buy ->
// policy visible -> clock forward -> settlements visible. Screenshots go to reports/portal/.
// Money checks: the balance after buying is exactly faucet minus premium, and after settlement it is
// faucet minus premium plus the payouts the page shows.
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

const SHOTS = path.resolve(__dirname, "../../../reports/portal");
const CSV = path.resolve(__dirname, "../fixtures/square/csv-export.csv");
const cents = (s: string) => Math.round(Number(s.replace(/[^0-9.-]/g, "")) * 100);
const shot = (page: Page, name: string) => page.screenshot({ path: path.join(SHOTS, name), fullPage: true });

test("onboard, quote, buy, see the policy settle", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));

  // 1. Business
  await page.goto("/app/onboard");
  await page.getByTestId("use-demo-address").click();
  await expect(page.getByTestId("holder-card")).toContainText("demo address");
  await page.getByTestId("business-name").fill("Scoops on 42nd");
  await page.getByTestId("business-address").fill("350 W 42nd St, New York, NY 10036");
  await expect(page.getByTestId("geocode-result")).toContainText("Times Square");
  await page.getByTestId("business-naics").selectOption("722515");
  await page.getByTestId("business-save").click();
  await expect(page.getByTestId("business-card")).toContainText("Central Park (KNYC)");
  await shot(page, "01-business.png");

  // 2. Sales CSV -> panel -> engine
  await page.getByTestId("sales-upload-input").setInputFiles(CSV);
  await page.getByTestId("sales-location").selectOption("LFIXNYC000001");
  const send = page.getByTestId("sales-send");
  await expect(send).toBeVisible();
  const sentDays = Number((await send.innerText()).match(/Send (\d+) days/)![1]);
  await send.click();
  await expect(page.getByTestId("sales-summary")).toContainText(`${sentDays} days of sales`);
  await expect(page.getByTestId("elasticity-beta")).toBeVisible();
  await expect(page.getByTestId("elasticity-learned")).toBeVisible();
  await shot(page, "02-sales-elasticity.png");

  // 3. Recommendation + quotes on both paths
  await page.getByTestId("to-coverage").click();
  await expect(page.getByTestId("recommend-card")).toBeVisible();
  await page.getByTestId("quote-button").click();
  await expect(page.getByTestId("quote-total")).toBeVisible();
  await expect(page.getByTestId("quote-total-ladder")).toBeVisible();
  await expect(page.getByTestId("ladder-note")).toContainText("we never place them");
  await shot(page, "03-quotes.png");

  // 4. Buy (house-hedge path)
  await page.getByTestId("faucet-button").click();
  await expect(page.getByTestId("usdc-balance")).toContainText("$1,000.00");
  const premium = cents(await page.getByTestId("quote-total").innerText());
  await page.getByTestId("buy-button").click();
  await expect(page.getByTestId("exec-status-done")).toBeVisible();
  const policyId = (await page.getByTestId("receipt-policy-id").innerText()).trim();
  expect(policyId).toMatch(/^pol_/);
  await shot(page, "04-bought.png");

  // 5. Policy visible, days pending
  await page.getByTestId("receipt-policy-link").click();
  await expect(page.getByTestId("policy-detail")).toBeVisible();
  const covered = await page.getByTestId("pending-row").count();
  expect(covered).toBe(7);
  await page.goto("/app/policies");
  await expect(page.getByTestId("policy-row")).toContainText(policyId);
  await expect(page.getByTestId("usdc-balance")).toHaveText(`$${((100_000 - premium) / 100).toLocaleString("en-US", { minimumFractionDigits: 2 })} test USDC`);
  await shot(page, "05-policies-active.png");

  // 6. Move the demo clock past D+2 of the last covered day (Phase 11's admin page does this in the UI).
  const world = await page.evaluate(() => localStorage.getItem("wi.world"));
  expect(world).toMatch(/^w_/);
  const adv = await page.request.post("/api/v1/sim/advance", { headers: { "X-WI-World": world! }, data: { days: 10 } });
  expect(adv.ok()).toBeTruthy();

  await page.goto(`/app/policies/${policyId}`);
  await expect(page.getByTestId("policy-status")).toHaveText("Settled");
  await expect(page.getByTestId("settlement-row")).toHaveCount(covered);
  await shot(page, "06-policy-settled.png");

  await page.goto("/app/policies");
  await expect(page.getByTestId("settlement-row")).toHaveCount(covered);
  const payouts = await page.getByTestId("settlement-row").evaluateAll((rows) =>
    rows.map((r) => (r.lastElementChild as HTMLElement).innerText),
  );
  const paidOut = payouts.reduce((s, x) => s + cents(x), 0);
  const expected = 100_000 - premium + paidOut;
  await expect(page.getByTestId("usdc-balance")).toHaveText(`$${(expected / 100).toLocaleString("en-US", { minimumFractionDigits: 2 })} test USDC`);
  await shot(page, "07-policies-settled.png");

  expect(errors).toEqual([]);
});
