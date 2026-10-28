// The README's demo: the 5-minute story on the real API, with a caption on every scene.
// Run: npx playwright test -c playwright.video.config.ts
// Then: backend/.venv python backend/scripts/demo_gif.py frontend/test-results/demo-frames docs/demo/pathtopro-demo.gif
import { mkdirSync, writeFileSync } from "node:fs";
import { expect, test, type Page } from "@playwright/test";

const OUT = "test-results/demo-frames";
const frames: { file: string; hold: number }[] = [];

async function caption(page: Page, text: string) {
  await page.evaluate((t) => {
    let el = document.getElementById("demo-caption");
    if (!el) {
      el = document.createElement("div");
      el.id = "demo-caption";
      el.setAttribute(
        "style",
        "position:fixed;left:50%;bottom:28px;transform:translateX(-50%);z-index:99999;max-width:86%;" +
          "padding:12px 22px;border-radius:14px;background:rgba(7,23,15,.92);color:#fff;" +
          "font:600 19px/1.35 system-ui,sans-serif;text-align:center;box-shadow:0 6px 24px rgba(0,0,0,.35)",
      );
      document.body.appendChild(el);
    }
    el.textContent = t;
  }, text);
}

// One still of the current screen, held for `hold` ms in the GIF
async function shot(page: Page, text: string, hold: number, settle = 400) {
  await caption(page, text);
  await page.waitForTimeout(settle); // let charts, fonts and fade-in animations settle
  const file = `${String(frames.length).padStart(2, "0")}.png`;
  await page.screenshot({ path: `${OUT}/${file}` });
  frames.push({ file, hold });
}

async function signIn(page: Page, email: string, password = "demo1234") {
  await page.evaluate(() => localStorage.clear()).catch(() => undefined);
  await page.goto("login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL((u) => !u.pathname.endsWith("/login"));
}

test("PathToPro in two minutes", async ({ page }) => {
  test.setTimeout(180_000);
  mkdirSync(OUT, { recursive: true });

  await page.goto("");
  await shot(page, "PathToPro: training plans for young footballers that change before problems happen", 3200, 2000);
  await page.getByRole("heading", { name: /One loop/i }).evaluate((e) => e.scrollIntoView({ block: "start" }));
  await shot(page, "Code computes, the LLM plans and explains, a fixed policy decides who approves", 3200, 1800);

  // Player: the morning check-in
  await signIn(page, "p03@demo.pathtopro");
  await expect(page.getByRole("heading", { name: /Hi / })).toBeVisible();
  await shot(page, "Player: today's session and a readiness score from sleep, HRV and a check-in", 3000);
  await page.getByText("Pre-match warm-up").click();
  await shot(page, "The morning check-in: four quick questions and a mood, under 30 seconds", 1600);
  for (let i = 0; i < 4; i++) {
    await page.getByRole("button", { name: "Next" }).click();
    if (i % 2 === 1) await shot(page, "The morning check-in: four quick questions and a mood, under 30 seconds", 900);
  }
  await page.getByRole("button", { name: /Good/ }).click();
  await page.getByRole("button", { name: "Kick-off!" }).click();
  await page.waitForURL("**/player");
  await expect(page.getByLabel(/Readiness \d+ of 100/)).toBeVisible();
  await shot(page, "Readiness updates at once, with recovery tasks for the day", 2600);

  // Coach: the squad, then the approval
  await signIn(page, "coach@demo.pathtopro");
  await expect(page.getByRole("heading", { name: "Dressing room" })).toBeVisible();
  await shot(page, "Coach: readiness per player and day, growth-zone rings and load flags", 3400);
  await page.getByRole("link", { name: "Substitution board" }).click();
  const card = page.getByRole("article", { name: /^(Session swap|Load cut|Intensity change|Match minutes limit): Leon U.$/ });
  await expect(card).toBeVisible();
  await card.evaluate((e) => e.scrollIntoView({ block: "center" }));
  await shot(page, "Leon (U15) is tired and in his growth spurt: the planner proposes a lighter week", 3400);
  await card.click();
  await page.keyboard.press("a");
  await expect(page.getByText("Applied: Leon U.")).toBeVisible();
  await shot(page, "Bigger changes wait for the coach: one key press approves it", 2400);

  // Leon sees why
  await signIn(page, "p15@demo.pathtopro");
  await page
    .getByRole("button", { name: /Your sessions were changed|Your week was made lighter|Your match minutes are limited|Session intensity adjusted/ })
    .first()
    .click();
  await expect(page.getByText("Approved by Alex Weber").first()).toBeVisible();
  await page.getByText("Approved by Alex Weber").first().evaluate((e) => e.scrollIntoView({ block: "center" }));
  await shot(page, "Leon sees what changed, the data behind it, and who approved it", 3400);
  await page.getByRole("link", { name: "My week" }).click();
  await expect(page.getByRole("img", { name: "Week plan on a pitch" })).toBeVisible();
  await shot(page, "His week, re-planned under hard rules: no plan can break them", 3000);

  // Safety: a person, not the agent
  await signIn(page, "physio@demo.pathtopro");
  await page.goto("physio");
  await expect(page.getByText("Pain reported").first()).toBeVisible();
  await shot(page, "Pain or a red mood goes straight to a named adult by email and push; the agents step back", 3400);

  // Pro leagues
  await signIn(page, "coach@demo.pathtopro");
  await page.getByRole("link", { name: "Pro leagues" }).click();
  await page.getByRole("link", { name: "La Liga 2015/16" }).click();
  await page.getByRole("link", { name: /Real Madrid/ }).first().click();
  await expect(page.getByRole("heading", { name: "Team analysis: Real Madrid" })).toBeVisible();
  await shot(page, "Pro leagues: how real teams play, from StatsBomb open data", 3200);

  // Club setup
  await signIn(page, "admin@demo.pathtopro", "e2e-admin-password");
  await expect(page).toHaveURL(/\/admin$/);
  await page.getByRole("tab", { name: /^Players/ }).click();
  await shot(page, "Club admin: teams, staff invitations, players by form or CSV import", 3200);

  await page.evaluate(() => localStorage.clear());
  await page.goto("");
  await shot(page, "Try the live demo: bachcodingg.github.io/path_to_pro", 4200, 2000);

  writeFileSync(`${OUT}/timeline.json`, JSON.stringify(frames, null, 1));
});
