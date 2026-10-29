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
  await page.waitForURL(/\/coach\/matches\/[^/]+$/);
  await expect(page.getByRole("tab", { name: "Line-up" })).toBeVisible();
  await expect(page.getByText("Player of the match", { exact: true })).toBeVisible();
  await expect(page.getByRole("img", { name: /Starting line-up, \d-\d/ })).toBeVisible();
  await expect(page.getByText("Substitutes")).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/coach-match-lineup.png`, fullPage: true });
  await page.getByRole("tab", { name: "Stat sheet" }).click();
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

test("club finances: fees, salaries, bonuses and the ledger", async ({ page }) => {
  await login(page, "coach@demo.pathtopro");
  await page.getByRole("link", { name: "Club finances" }).click();
  await expect(page.getByRole("heading", { name: "Club finances" })).toBeVisible();
  await expect(page.getByText("Fees outstanding")).toBeVisible();
  await expect(page.getByText("Players pay the club")).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/coach-finance.png`, fullPage: true });
  await page.getByRole("tab", { name: "Ledger" }).click();
  await page.getByRole("button", { name: "Not paid yet" }).click();
  await expect(page.getByText("Academy fee").first()).toBeVisible();
  if (!process.env.E2E_DEMO) {
    await page.getByRole("button", { name: "Book this month" }).click();
    await expect(page.getByText(/already booked|Booked \d+ entries/)).toBeVisible();
  }
  await page.getByRole("button", { name: /Sign out/ }).click();
  await login(page, "physio@demo.pathtopro");
  await expect(page.getByRole("link", { name: "Club finances" })).toHaveCount(0);
});

test("pro leagues: its own section; an opponent's style, shots, set pieces and players", async ({ page }) => {
  await login(page, "coach@demo.pathtopro");
  await page.getByRole("link", { name: "Pro leagues" }).click();
  await expect(page.getByRole("heading", { name: "Pro league analysis" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Staff navigation" })).toHaveCount(0); // a section of its own
  await page.screenshot({ path: `${SHOTS}/pro-leagues.png` });
  await page.getByRole("link", { name: "La Liga 2015/16" }).click();
  await page.getByRole("link", { name: /Real Madrid/ }).first().click();
  await expect(page.getByRole("heading", { name: "Team analysis: Real Madrid" })).toBeVisible();
  await expect(page.getByLabel("Form, oldest first: won, won, won, won, won").first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "Strengths" })).toBeVisible();
  await expect(page.getByRole("table", { name: "League table" })).toBeVisible();
  await page.getByLabel("Compare with").selectOption("barcelona");
  await expect(page).toHaveURL(/vs=barcelona/);
  await page.screenshot({ path: `${SHOTS}/coach-team-analysis.png`, fullPage: true });

  await page.getByRole("tab", { name: "Attack" }).click();
  await expect(page.getByRole("img", { name: /shots on the attacking half/ })).toBeVisible();
  await page.getByRole("button", { name: "Header" }).click();
  await expect(page.getByRole("button", { name: "Header" })).toHaveAttribute("aria-pressed", "true");
  await page.screenshot({ path: `${SHOTS}/coach-team-analysis-attack.png`, fullPage: true });

  await page.getByRole("tab", { name: "Set pieces" }).click();
  await expect(page.getByText("Main corner taker:")).toBeVisible();
  await expect(page.getByRole("img", { name: /corner deliveries on the attacking half/ })).toBeVisible();

  await page.getByRole("tab", { name: "Players" }).click();
  await expect(page.getByRole("region", { name: "Squad leaders" })).toContainText("Cristiano Ronaldo");
  await expect(page.getByRole("cell", { name: "Cristiano Ronaldo" })).toBeVisible();
  await page.getByRole("button", { name: "Passing" }).click();
  await expect(page.getByRole("button", { name: /Pass %/ })).toBeVisible();

  await page.getByLabel("Team", { exact: true }).selectOption("atletico-madrid");
  await expect(page).toHaveURL(/\/pro\/la-liga\/teams\/atletico-madrid\?/);
  await expect(page.getByRole("cell", { name: "Antoine Griezmann" })).toBeVisible();

  // Full table as on the league site: all / home / away, zones, form; the club strip switches team
  await page.getByRole("tab", { name: "Table", exact: true }).click();
  const table = page.getByRole("table", { name: "League table" });
  await expect(table.getByRole("row")).toHaveCount(21);
  await expect(page.getByRole("list", { name: "Key" })).toContainText("Champions League");
  await page.getByRole("tab", { name: "Home" }).click();
  await expect(table.getByRole("row").nth(1)).toContainText("19");
  await page.screenshot({ path: `${SHOTS}/coach-league-table.png`, fullPage: true });
  await page.getByRole("navigation", { name: "Clubs" }).getByRole("button", { name: "Barcelona" }).click();
  await expect(page).toHaveURL(/\/pro\/la-liga\/teams\/barcelona\?/);
  await expect(page.getByRole("heading", { name: "Team analysis: Barcelona" })).toBeVisible();

  // The old staff address still works
  await page.goto("coach/analysis/real-madrid");
  await expect(page).toHaveURL(/\/pro\/la-liga$/);
});

test("pro leagues: Premier League, Leverkusen's unbeaten season, a Champions League final", async ({ page }) => {
  await login(page, "p03@demo.pathtopro"); // players can study the pros too
  await page.goto("pro/premier-league?tab=table");
  const table = page.getByRole("table", { name: "League table" });
  await expect(table.getByRole("row").nth(1)).toContainText("Leicester City");
  await expect(table.getByRole("row").nth(1)).toContainText("81");

  await page.getByRole("navigation", { name: "Competitions" }).getByRole("link", { name: "Bundesliga" }).click();
  await page.getByRole("link", { name: /Bayer Leverkusen/ }).first().click();
  await expect(page.getByRole("heading", { name: "Team analysis: Bayer Leverkusen" })).toBeVisible();
  await expect(page.getByText("W28 D6 L0")).toBeVisible();
  await expect(page.getByRole("tab", { name: "Table" })).toHaveCount(0); // one club's season: nothing to rank
  await expect(page.getByText(/opponents/).first()).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/pro-club-season.png`, fullPage: true });

  await page.getByRole("navigation", { name: "Competitions" }).getByRole("link", { name: "Champions League" }).click();
  await expect(page.getByRole("tab", { name: "Finals" })).toBeVisible();
  await page.getByRole("link", { name: /AC Milan 3-3 Liverpool/ }).click();
  await expect(page.getByRole("heading", { name: "AC Milan 3-3 Liverpool" })).toBeVisible();
  await expect(page.getByText(/Liverpool won 3-2 on penalties/)).toBeVisible();
  await expect(page.getByRole("listitem").filter({ hasText: "Steven Gerrard" })).toContainText("54'");
  await expect(page.getByRole("img", { name: /Shot map/ })).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/pro-match-centre.png`, fullPage: true });
  await page.getByRole("link", { name: "my app" }).click();
  await expect(page.getByRole("heading", { name: /^Hi / })).toBeVisible();
});

test("player app on a laptop: sidebar instead of bottom tabs, pages in columns", async ({ page }) => {
  await login(page, "p15@demo.pathtopro");
  const nav = page.getByRole("navigation", { name: "Player navigation" });
  await expect(nav).toHaveCount(1); // the phone tab bar is hidden at this width
  await expect(nav.getByRole("link", { name: "Road to Pro" })).toBeVisible();
  await expect(page.getByRole("heading", { name: /^Hi / })).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/player-desktop-today.png` });
  await nav.getByRole("link", { name: "My week" }).click();
  const week = page.getByRole("list", { name: "Week at a glance" });
  await expect(week.getByRole("listitem")).toHaveCount(7);
  await week.getByRole("button").nth(3).click();
  await expect(page.getByRole("dialog", { name: "Day details" })).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/player-desktop-week.png` });
});

test("sign-in on a laptop: what the app does, demo accounts by role, skip link once inside", async ({ page }) => {
  await page.goto("login");
  await expect(page.getByRole("heading", { name: /Train smart/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /Coach.*Squad, matches, analysis/ })).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/sign-in.png` });
  await page.getByRole("button", { name: /Physio.*Escalation queue/ }).click();
  await expect(page.getByRole("heading", { name: "Physio queue" })).toBeVisible();
  await expect(page).toHaveTitle("Physio queue · PathToPro");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to main content" })).toBeFocused();
});

test("demo: coach schedule and availability load from the snapshot", async ({ page }) => {
  test.skip(!process.env.E2E_DEMO, "the live server is covered in club.spec.ts");
  await login(page, "coach@demo.pathtopro");
  await page.getByRole("link", { name: "Schedule" }).first().click();
  await expect(page.getByRole("heading", { name: "Schedule" })).toBeVisible();
  const today = (await page.getByLabel("Kick-off").getAttribute("min"))!.slice(0, 10);
  const day = new Date(today + "T12:00:00Z");
  day.setUTCDate(day.getUTCDate() + 70);
  await page.getByRole("textbox", { name: "Opponent" }).fill("FC Faraway");
  await page.getByLabel("Kick-off").fill(`${day.toISOString().slice(0, 10)}T15:00`);
  await page.getByRole("button", { name: "Add match" }).click();
  await expect(page.getByText("FC Faraway")).toBeVisible();
  await page.getByRole("button", { name: "Remove the match against FC Faraway" }).click();
  await expect(page.getByText("FC Faraway")).toHaveCount(0);

  await page.getByRole("link", { name: "Availability" }).first().click();
  await expect(page.getByRole("heading", { name: "Availability" })).toBeVisible();
  await page.getByLabel("Message").fill("Bring both kits on Saturday.");
  await page.getByRole("button", { name: "Post" }).click();
  await expect(page.getByText(/^Posted\./)).toBeVisible();
  await page.getByRole("button", { name: "Delete message" }).first().click();
  await expect(page.getByText("No messages yet.")).toBeVisible();
});