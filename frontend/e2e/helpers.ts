import type { Page } from "@playwright/test";

export const SHOTS = process.env.E2E_DEMO ? "test-results/demo-screenshots" : "../docs/screenshots";

export async function login(page: Page, email: string) {
  await page.goto("login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("demo1234");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL((u) => !u.pathname.endsWith("/login"));
}
