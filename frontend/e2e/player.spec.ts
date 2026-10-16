import { expect, test } from "@playwright/test";
import { login, SHOTS } from "./helpers";

test("morning check-in takes under 30 s and updates Today", async ({ page }) => {
  await login(page, "p03@demo.pathtopro");
  await expect(page.getByRole("heading", { name: /Hi / })).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/player-today-before.png` });

  const started = Date.now();
  await page.getByText("Pre-match warm-up").click();
  for (let i = 0; i < 4; i++) await page.getByRole("button", { name: "Next" }).click();
  await page.getByRole("button", { name: /Good/ }).click();
  await page.getByRole("button", { name: "Kick-off!" }).click();
  await page.waitForURL("**/player");
  expect(Date.now() - started).toBeLessThan(30_000);

  await expect(page.getByLabel(/Readiness \d+ of 100/)).toBeVisible();
  await expect(page.getByText("Recovery tasks")).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/player-today.png`, fullPage: true });
});

test("player screens render", async ({ page }) => {
  await login(page, "p15@demo.pathtopro");
  await page.getByRole("link", { name: "My week" }).click();
  await expect(page.getByRole("img", { name: "Week plan on a pitch" })).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/player-week.png` });

  await page.getByRole("link", { name: "Growth" }).click();
  await expect(page.getByRole("heading", { name: "Growth zone" })).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/player-growth.png`, fullPage: true });

  await page.getByRole("link", { name: "My card" }).click();
  await expect(page.getByText("avg percentile")).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/player-card.png` });

  await page.getByRole("link", { name: "Road to Pro" }).click();
  await expect(page.getByRole("img", { name: "Season map" })).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/player-road.png`, fullPage: true });
});

test("red check-in tells the player a person will follow up", async ({ page }) => {
  await login(page, "p07@demo.pathtopro");
  await page.getByText("Pre-match warm-up").click();
  for (let i = 0; i < 4; i++) await page.getByRole("button", { name: "Next" }).click();
  await page.getByRole("button", { name: /Not good/ }).click();
  await page.getByRole("button", { name: "Kick-off!" }).click();
  await expect(page.getByText(/Someone from the staff will talk to you today/)).toBeVisible();
});
