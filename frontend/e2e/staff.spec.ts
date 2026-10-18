import { expect, test } from "@playwright/test";
import { login, SHOTS } from "./helpers";

test("coach heatmap shows the squad with PHV rings and load flags", async ({ page }) => {
  await login(page, "coach@demo.pathtopro");
  await expect(page.getByRole("heading", { name: "Dressing room" })).toBeVisible();
  await expect(page.getByRole("row")).toHaveCount(26); // header + 25 players
  await expect(page.getByLabel("Growth zone").first()).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/coach-heatmap.png` });
});

test("coach approves the tired player's lighter week with one key press", async ({ page }) => {
  await login(page, "coach@demo.pathtopro");
  await page.getByRole("link", { name: "Substitution board" }).click();
  const card = page.getByRole("article", { name: /^(Session swap|Load cut|Intensity change|Match minutes limit): Leon U.$/ });
  await expect(card).toBeVisible();
  await expect(card.getByText("Growth zone", { exact: true })).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/coach-inbox.png` });

  const started = Date.now();
  await card.click();
  await page.keyboard.press("a");
  await expect(page.getByText("Applied: Leon U.")).toBeVisible();
  expect(Date.now() - started).toBeLessThan(20_000);
});

test("tired player sees the Why? card with the approver", async ({ page }) => {
  // Approve as coach if still pending (the previous test does it on the real server; the
  // static demo keeps state per browser), then switch to the player.
  await login(page, "coach@demo.pathtopro");
  await page.getByRole("link", { name: "Substitution board" }).click();
  await expect(page.getByRole("heading", { name: "Substitution board" })).toBeVisible();
  const card = page.getByRole("article", { name: /^(Session swap|Load cut|Intensity change|Match minutes limit): Leon U.$/ });
  if (await card.count()) {
    await card.getByRole("button", { name: "Approve" }).click();
    await expect(page.getByText("Applied: Leon U.")).toBeVisible();
  }
  await page.getByRole("button", { name: "Sign out" }).click();
  await page.setViewportSize({ width: 412, height: 915 });
  await login(page, "p15@demo.pathtopro");
  await page.getByRole("button", { name: /Your sessions were changed|Your week was made lighter|Your match minutes are limited|Session intensity adjusted/ }).first().click();
  await expect(page.getByText("Approved by Alex Weber").first()).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/player-why.png`, fullPage: true });
});

test("tactics board, scouting report and match commentary", async ({ page }) => {
  await login(page, "coach@demo.pathtopro");
  await page.getByRole("link", { name: "Tactics board" }).click();
  await expect(page.getByRole("img", { name: "Formation" })).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/coach-tactics.png` });

  await page.getByRole("link", { name: "Dressing room" }).click();
  await page.getByRole("link", { name: "Leon U." }).click();
  await expect(page.getByRole("heading", { name: "Leon U." })).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/coach-profile.png`, fullPage: true });

  await page.getByRole("link", { name: "Match commentary" }).click();
  await expect(page.getByRole("listitem").first()).toContainText(/Planner|Monitor|Development Coach|Safety flag/);
  await page.screenshot({ path: `${SHOTS}/coach-log.png` });
});

test("physio queue has the pain report and can acknowledge it", async ({ page }) => {
  await login(page, "physio@demo.pathtopro");
  await page.goto("physio");
  await expect(page.getByText("Pain reported").first()).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/physio-queue.png` });
  const before = await page.getByRole("button", { name: "I've spoken to them" }).count();
  await page.getByRole("button", { name: "I've spoken to them" }).first().click();
  await expect(page.getByRole("button", { name: "I've spoken to them" })).toHaveCount(before - 1);
});

test("guardian sees summary and can switch consent", async ({ page }) => {
  await login(page, "guardian02@demo.pathtopro");
  await expect(page.getByText("sessions done")).toBeVisible();
  const sw = page.getByRole("checkbox", { name: /Heart-rate variability/ });
  const was = await sw.isChecked();
  await sw.locator("..").click();
  await expect(sw).toBeChecked({ checked: !was });
  await sw.locator("..").click();
  await expect(sw).toBeChecked({ checked: was });
  await page.screenshot({ path: `${SHOTS}/guardian.png`, fullPage: true });
});

test("coach rates a player and reviews the readiness calibration", async ({ page }) => {
  await login(page, "coach@demo.pathtopro");
  await page.getByRole("button", { name: /Leon U\. .*: \d+/ }).first().click();
  await page.getByRole("button", { name: "Take care" }).click();
  await expect(page.getByText("Saved. Used to calibrate the score.")).toBeVisible();

  await page.getByRole("link", { name: "Calibration" }).click();
  await expect(page.getByRole("heading", { name: "Readiness calibration" })).toBeVisible();
  await expect(page.getByText("Staff red days the score also calls red")).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/coach-calibration.png`, fullPage: true });
});

test("coach turns a plain-words note into a plan change", async ({ page }) => {
  test.skip(!!process.env.E2E_DEMO, "the planner runs on the server");
  await login(page, "coach@demo.pathtopro");
  await page.getByRole("link", { name: "Elias O." }).click();
  await page.getByLabel("Coach instruction").fill("keep him light until tomorrow, no gym this week");
  await page.getByRole("button", { name: "Preview" }).click();
  await expect(page.getByText("No strength sessions")).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/coach-instruction.png` });
  await page.getByRole("button", { name: /Apply to Elias's week/ }).click();
  await expect(page.getByText(/Applied\. Elias sees the new week/)).toBeVisible();
});

test("training pitch: a team session is checked for every player", async ({ page }) => {
  await login(page, "coach@demo.pathtopro");
  await page.getByRole("link", { name: "Training pitch" }).click();
  await expect(page.getByRole("heading", { name: "Training pitch" })).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/coach-pitch.png` });
  test.skip(!!process.env.E2E_DEMO, "placing sessions runs the planner on the server");
  await page.getByRole("button", { name: "Speed" }).click();
  await page.getByRole("button", { name: "Place on Friday" }).click();
  const preview = page.getByRole("status", { name: "Team session preview" });
  await expect(preview).toContainText("adjusted for safety");
  await page.screenshot({ path: `${SHOTS}/coach-pitch-preview.png` });
  await preview.getByRole("button", { name: "Apply to squad" }).click();
  await expect(page.getByText(/Applied: \d+ as planned, \d+ adjusted for safety/)).toBeVisible();
});

test("match ratings with a breakdown, and the second team's coach view", async ({ page }) => {
  await login(page, "coach@demo.pathtopro");
  await page.getByRole("link", { name: "Match ratings" }).click();
  await expect(page.getByRole("heading", { name: "Match ratings" })).toBeVisible();
  await page.getByRole("link", { name: /PathToPro Academy .* vs/ }).first().click();
  await expect(page.getByText(/Player of the match/)).toBeVisible();
  await page.getByRole("button", { name: /Rating breakdown for/ }).first().click();
  await expect(page.getByText(/Pass accuracy|Goals|Tackles|Interceptions|Duels/).first()).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/coach-match-ratings.png`, fullPage: true });
  if (!process.env.E2E_DEMO) {
    await page.getByRole("button", { name: "Save and rate" }).click();
    await expect(page.getByText("Saved. Ratings updated.")).toBeVisible();
  }

  await page.getByRole("button", { name: /Sign out/ }).click();
  await login(page, "mencoach@demo.pathtopro");
  await expect(page.getByRole("link", { name: /\./ }).first()).toBeVisible();
  await page.getByRole("link", { name: "Match ratings" }).click();
  await expect(page.getByRole("link", { name: /PathToPro FC Men vs/ }).first()).toBeVisible();
});
