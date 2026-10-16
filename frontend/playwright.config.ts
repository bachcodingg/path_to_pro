import { defineConfig, devices } from "@playwright/test";

// Needs the API on :8000 and Vite on :5173 (see README). The demo data is
// reset before the run, so tests follow the 5-minute demo script.
export default defineConfig({
  testDir: "e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 30_000,
  use: { baseURL: process.env.E2E_URL ?? "http://127.0.0.1:5173", trace: "retain-on-failure" },
  globalSetup: "./e2e/global-setup.ts",
  projects: [
    { name: "phone", use: { ...devices["Pixel 7"] }, testMatch: /player\.spec/ },
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } }, testMatch: /staff\.spec/ },
  ],
});
