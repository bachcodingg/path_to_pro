import { createHmac } from "node:crypto";
import { expect, test } from "@playwright/test";
import { login, SHOTS } from "./helpers";

// Club setup, accounts and the legal pages need the full system (not the static demo)
test.skip(!!process.env.E2E_DEMO, "needs the API");

test("club admin adds a team and invites its coach", async ({ page }) => {
  await page.goto("login");
  await page.getByLabel("Email").fill("admin@demo.pathtopro");
  await page.getByLabel("Password").fill("e2e-admin-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/admin$/);
  await page.getByLabel("Name").fill("U14 Green");
  await page.getByLabel("Age group").selectOption("U14");
  await page.getByRole("button", { name: "Add team" }).click();
  await expect(page.getByText("U14 Green added")).toBeVisible();

  await page.getByRole("tab", { name: /^Staff/ }).click();
  await page.getByLabel("Name").fill("Rosa Trainer");
  await page.getByLabel("Email").fill("rosa@club.example");
  await page.locator("form").getByLabel(/^Team/).selectOption({ label: "U14 Green" });
  await page.getByRole("button", { name: "Send invitation" }).click();
  await expect(page.getByText("Invitation sent to rosa@club.example")).toBeVisible();
  await expect(page.getByRole("row", { name: /Rosa Trainer/ }).getByText("Invited")).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/admin-staff.png` });

  await page.getByRole("tab", { name: "Import players" }).click();
  await expect(page.getByRole("button", { name: "Check the file" })).toBeDisabled();
});

test("coach adds and removes a fixture on the schedule", async ({ page }) => {
  await login(page, "coach@demo.pathtopro");
  await page.getByRole("link", { name: "Schedule" }).first().click();
  await expect(page.getByRole("heading", { name: "Schedule" })).toBeVisible();
  // Far beyond the seeded weeks, so no other test's sessions are touched
  const text = await page.evaluate(async () => (await (await fetch("/api/health")).json()).today as string);
  const day = new Date(text + "T12:00:00Z");
  day.setUTCDate(day.getUTCDate() + 70);
  const iso = day.toISOString().slice(0, 10);
  await page.getByRole("textbox", { name: "Opponent" }).fill("FC Faraway");
  await page.getByLabel("Kick-off").fill(`${iso}T15:00`);
  await page.getByRole("button", { name: "Add match" }).click();
  await expect(page.getByText("FC Faraway")).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/coach-schedule.png` });
  await page.getByRole("button", { name: "Remove the match against FC Faraway" }).click();
  await expect(page.getByText("FC Faraway")).toHaveCount(0);
});

test("account settings, forgot password and the legal pages", async ({ page }) => {
  await login(page, "p03@demo.pathtopro");
  await page.goto("account");
  await expect(page.getByRole("heading", { name: "Your account" })).toBeVisible();
  await expect(page.getByText("p03@demo.pathtopro is confirmed.")).toBeVisible();
  await expect(page.getByText(/Your club holds your academy data/)).toBeVisible();

  await page.goto("privacy");
  await expect(page.getByRole("heading", { name: "Privacy notice" })).toBeVisible();
  await expect(page.getByText("Template.")).toBeVisible();
  await page.getByRole("link", { name: "Imprint" }).first().click();
  await expect(page.getByRole("heading", { name: "Imprint" })).toBeVisible();

  await page.evaluate(() => localStorage.clear());
  await page.goto("forgot-password");
  await page.getByLabel("Email").fill("p03@demo.pathtopro");
  await page.getByRole("button", { name: "Send the link" }).click();
  await expect(page.getByText("Check your inbox")).toBeVisible();
  await page.goto("set-password?token=not-a-real-token-1234");
  await expect(page.getByText(/expired or was already used/)).toBeVisible();
});

test("availability and a message to the team", async ({ page }) => {
  await login(page, "p07@demo.pathtopro");
  await page.goto("player/team");
  const first = page.getByRole("listitem").filter({ has: page.getByRole("button", { name: "Can't make it" }) }).first();
  await first.getByRole("button", { name: "Can't make it" }).click();
  await first.getByLabel(/Why you can't make/).selectOption("school");
  await expect(first.getByText("Can't make it", { exact: true }).first()).toBeVisible();

  await page.evaluate(() => localStorage.clear());
  await login(page, "coach@demo.pathtopro");
  await page.getByRole("link", { name: "Availability" }).first().click();
  await expect(page.getByText("(School or exams)").first()).toBeVisible();
  await page.getByLabel("Message").fill("Bring both kits on Saturday.");
  await page.getByRole("button", { name: "Post" }).click();
  await expect(page.getByText(/^Posted\./)).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/coach-availability.png` });

  await page.evaluate(() => localStorage.clear());
  await login(page, "p07@demo.pathtopro");
  await expect(page.getByText("From your coach")).toBeVisible();
  await expect(page.getByText("Bring both kits on Saturday.")).toBeVisible();

  // Leave the demo as it was for the other tests' screenshots
  await page.evaluate(() => localStorage.clear());
  await login(page, "coach@demo.pathtopro");
  await page.getByRole("link", { name: "Availability" }).first().click();
  await page.getByRole("button", { name: "Delete message" }).first().click();
  await expect(page.getByText("No messages yet.")).toBeVisible();
});

// RFC 6238 code, computed the way an authenticator app does
function totp(secret: string): string {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  let bits = "";
  for (const c of secret.replace(/\s/g, "")) bits += alphabet.indexOf(c).toString(2).padStart(5, "0");
  const key = Buffer.from(bits.match(/.{8}/g)!.map((b) => parseInt(b, 2)));
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(Math.floor(Date.now() / 30000)));
  const h = createHmac("sha1", key).update(counter).digest();
  const o = h[h.length - 1] & 0xf;
  return String((h.readUInt32BE(o) & 0x7fffffff) % 1_000_000).padStart(6, "0");
}

test("administrator turns on two-step sign-in and signs in with a code", async ({ page }) => {
  const signIn = async () => {
    await page.goto("login");
    await page.getByLabel("Email").fill("admin@demo.pathtopro");
    await page.getByLabel("Password").fill("e2e-admin-password");
    await page.getByRole("button", { name: "Sign in" }).click();
  };
  await signIn();
  await expect(page).toHaveURL(/\/admin$/);
  await page.goto("account");
  await page.getByRole("button", { name: "Set up two-step sign-in" }).click();
  const key = (await page.locator("p.font-mono").textContent())!;
  await page.getByLabel("2. Enter the 6-digit code it shows").fill(totp(key));
  await page.getByRole("button", { name: "Turn on" }).click();
  await expect(page.getByText(/Recovery codes/)).toBeVisible();
  await page.getByRole("button", { name: "I've saved them" }).click();

  await page.evaluate(() => localStorage.clear());
  await signIn();
  await page.getByLabel("Code").fill("000000");
  await page.getByRole("button", { name: "Verify" }).click();
  await expect(page.getByText("That code is not right")).toBeVisible();
  await page.getByLabel("Code").fill(totp(key));
  await page.getByRole("button", { name: "Verify" }).click();
  await expect(page).toHaveURL(/\/admin$/);

  // Off again, so a re-run of the suite starts from the same state
  await page.goto("account");
  await page.getByLabel("Password, to turn it off").fill("e2e-admin-password");
  await page.getByRole("button", { name: "Turn off" }).click();
  await expect(page.getByText("Two-step sign-in is off.")).toBeVisible();
});
