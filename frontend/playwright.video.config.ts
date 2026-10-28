import { defineConfig } from "@playwright/test";
import base from "./playwright.config";

// Records the README demo (e2e-video/demo.spec.ts) on the real API: a still per scene for
// the GIF, and the whole run as a .webm in test-results. Same servers and seed as the e2e tests.
export default defineConfig({
  ...base,
  testDir: "e2e-video",
  timeout: 180_000,
  projects: [
    {
      name: "video",
      use: {
        viewport: { width: 1280, height: 720 },
        deviceScaleFactor: 1,
        video: { mode: "on", size: { width: 1280, height: 720 } },
      },
    },
  ],
});
