import { expect, test } from "@playwright/test";
import { login, SHOTS } from "./helpers";

const LIVE = !process.env.E2E_DEMO; // sign-up and the planner need the server, not the offline demo

test("academy player sees a position-specific gym session", async ({ page }) => {
  await login(page, "p03@demo.pathtopro");
  await page.getByRole("link", { name: "Gym", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Gym", exact: true })).toBeVisible();
  await expect(page.getByText("Your position", { exact: true })).toBeVisible();
  await expect(page.getByText("Warm-up").first()).toBeVisible();
  await expect(page.getByText(/· everyone/).first()).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/player-gym.png`, fullPage: true });
});

test("ball skills for the player's position next to the gym, and match tips", async ({ page }) => {
  await login(page, "p15@demo.pathtopro"); // a striker in the growth zone
  await page.getByRole("link", { name: /Ball skills for your position/ }).click();
  await expect(page.getByRole("heading", { name: "Ball skills" })).toBeVisible();
  const today = page.getByRole("region", { name: "Today's session" });
  await expect(today.getByText("Striker skills session")).toBeVisible();
  await expect(today.getByText(/Growth zone: half the shooting/)).toBeVisible();
  await today.getByRole("button", { name: /Timing runs|Hold-up|Attacking headers|Finishing|First-time|Follow every/ }).first().click();
  await expect(today.getByText("Focus on")).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/player-skills.png`, fullPage: true });
  await page.getByLabel("Drills for position").selectOption("full_back");
  await expect(page.getByRole("button", { name: /1v1 on the flank/ })).toBeVisible();
  await page.getByRole("link", { name: "Gym session" }).click();
  await expect(page.getByRole("heading", { name: "Gym", exact: true })).toBeVisible();

  await page.getByRole("link", { name: "Today" }).click();
  await expect(page.getByText("Tip for today")).toBeVisible();
  await page.getByRole("link", { name: "All tips →" }).click();
  await expect(page.getByRole("heading", { name: "Match tips" })).toBeVisible();
  await page.getByRole("button", { name: "After a mistake: reset in five seconds" }).click();
  await expect(page.getByText(/Ask for the ball again within two minutes/)).toBeVisible();
  await page.getByRole("tab", { name: "Positions" }).click();
  await page.getByRole("combobox").selectOption("full_back");
  await page.getByRole("button", { name: "Defending as a left back" }).click();
  await expect(page.getByText(/tuck in towards your centre-back/)).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/player-tips.png`, fullPage: true });
  await page.getByRole("link", { name: /Practise it/ }).first().click();
  await expect(page.getByRole("heading", { name: "Ball skills" })).toBeVisible();
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

  await page.getByRole("link", { name: "Gym", exact: true }).click();
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
