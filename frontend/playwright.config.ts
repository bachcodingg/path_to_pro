import { defineConfig, devices } from "@playwright/test";

// Playwright starts the API (uvicorn, :8000) and the web app (Vite, :5173) itself, or reuses
// ones already running. Everything binds to 127.0.0.1: on some systems "localhost" resolves
// to IPv6 only. Set E2E_PYTHON to the backend's Python (default: "python").
// The demo data is reset before the run, so the tests follow the 5-minute demo script.
const python = process.env.E2E_PYTHON ?? "python";

export default defineConfig({
  testDir: "e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 30_000,
  use: { baseURL: process.env.E2E_URL ?? "http://127.0.0.1:5173", trace: "retain-on-failure" },
  globalSetup: "./e2e/global-setup.ts",
  webServer: [
    {
      command: `"${python}" -m uvicorn api.main:app --host 127.0.0.1 --port 8000`,
      cwd: "../backend",
      url: "http://127.0.0.1:8000/api/health",
      reuseExistingServer: true,
      timeout: 120_000,
      env: { PATHTOPRO_LLM: "off", PATHTOPRO_SCHEDULER: "off" },
    },
    {
      command: "npx vite --host 127.0.0.1 --port 5173 --strictPort",
      url: "http://127.0.0.1:5173",
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
  projects: [
    { name: "phone", use: { ...devices["Pixel 7"] }, testMatch: /(player|pathway|career)\.spec/ },
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } }, testMatch: /staff\.spec/ },
  ],
});
