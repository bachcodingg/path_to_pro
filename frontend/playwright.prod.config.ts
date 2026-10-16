import { defineConfig } from "@playwright/test";
import base from "./playwright.config";

// Same end-to-end tests against a running production deployment (single container:
// API + website, demo data auto-seeded). E2E_URL defaults to a local container.
process.env.E2E_DEMO = "1"; // no seeding from the test: the deployment seeds itself
export default defineConfig({
  ...base,
  webServer: undefined,
  use: { ...base.use, baseURL: process.env.E2E_URL ?? "http://127.0.0.1:8080/" },
});
