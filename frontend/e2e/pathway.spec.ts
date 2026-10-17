import { expect, test } from "@playwright/test";
import { login, SHOTS } from "./helpers";

const LIVE = !process.env.E2E_DEMO; // sign-up and the planner need the server, not the offline demo

test("academy player sees a position-specific gym session", async ({ page }) => {
  await login(page, "p03@demo.pathtopro");
  await page.getByRole("link", { name: "Gym" }).click();
  await expect(page.getByRole("heading", { name: "Gym", exact: true })).toBeVisible();
  await expect(page.getByText("Your position", { exact: true })).toBeVisible();
  await expect(page.getByText("Warm-up").first()).toBeVisible();
  await expect(page.getByText(/· everyone/).first()).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/player-gym.png`, fullPage: true });
});

test("self-guided player logs a test and levels up", async ({ page }) => {
  await login(page, "amateur@demo.pathtopro");
  await expect(page.getByText("Level 2: Grassroots")).toBeVisible();
  await expect(page.getByText("Log what you did")).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/amateur-today.png`, fullPage: true });

  await page.getByRole("link", { name: "Levels" }).click();
  await expect(page.getByRole("heading", { name: "Grassroots" })).toBeVisible();
  await expect(page.getByText("Benchmarks met: 3 of 4 needed")).toBeVisible();
  await page.getByRole("button", { name: /Wall passes in 30 s/ }).click();
  await page.getByPlaceholder("Result (passes)").fill("19");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("Level up! You're now Competitive amateur.")).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/amateur-levels.png`, fullPage: true });

  await page.getByRole("link", { name: "Gym" }).click();
  await expect(page.getByText(/This week · Home: band and dumbbells/)).toBeVisible();
  await expect(page.getByText("Striker work").first()).toBeVisible();
});

test("a new player signs up and gets a week built around their club", async ({ page }) => {
  test.skip(!LIVE, "sign-up needs the live server");
  await page.goto("register");
  await page.getByLabel("First name and initial").fill("Jo T.");
  await page.getByLabel("Email").fill(`jo${Date.now()}@example.com`);
  await page.getByLabel("Password").fill("a-good-password");
  await page.getByLabel("Date of birth").fill("2008-05-01");
  await page.getByLabel("Position").selectOption("full_back");
  await page.getByRole("checkbox").check();
  await page.screenshot({ path: `${SHOTS}/register.png`, fullPage: true });
  await page.getByRole("button", { name: "Create my plan" }).click();
  await page.waitForURL("**/player");
  await expect(page.getByText(/Level 2: Grassroots/)).toBeVisible();
  await page.getByRole("link", { name: "My week" }).click();
  await expect(page.getByRole("img", { name: "Week plan on a pitch" })).toBeVisible();
});
