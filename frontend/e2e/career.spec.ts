import { expect, test } from "@playwright/test";
import { login, SHOTS } from "./helpers";

test("dual-registered player: shared match minutes, career and match diary", async ({ page }) => {
  await login(page, "dual@demo.pathtopro");
  await page.getByRole("link", { name: "My week" }).click();
  await expect(page.getByRole("img", { name: "Week plan on a pitch" })).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/dual-week.png` });

  await page.getByRole("link", { name: "Career" }).click();
  await expect(page.getByRole("heading", { name: "My career" })).toBeVisible();
  await expect(page.getByText(/dual registration/).first()).toBeVisible();
  await expect(page.getByText("Recent matches")).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/player-career.png`, fullPage: true });

  const diary = page.getByRole("region", { name: "Match diary" });
  await expect(diary).toBeVisible();
  const before = await diary.getByRole("button", { name: /Fill in/ }).count();
  await diary.getByRole("button", { name: /Fill in/ }).first().click();
  await diary.getByRole("button", { name: "Assists plus one" }).click();
  await diary.getByRole("button", { name: "Self-rating 7" }).click();
  await page.screenshot({ path: `${SHOTS}/match-diary.png`, fullPage: true });
  await diary.getByRole("button", { name: "Save match diary" }).click();
  if (before > 1) await expect(diary.getByRole("button", { name: /Fill in/ })).toHaveCount(before - 1);
  else await expect(diary).toHaveCount(0);
});
