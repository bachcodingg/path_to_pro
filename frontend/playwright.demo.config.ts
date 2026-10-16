import { defineConfig } from "@playwright/test";
import base from "./playwright.config";

// Same end-to-end tests, against the static demo website (VITE_DEMO=1 build under
// /path_to_pro/, as on GitHub Pages). Build first: npm run build:demo
process.env.E2E_DEMO = "1";
export default defineConfig({
  ...base,
  use: { ...base.use, baseURL: "http://127.0.0.1:4174/path_to_pro/" },
  webServer: {
    command: "npx vite preview --host 127.0.0.1 --port 4174 --strictPort",
    url: "http://127.0.0.1:4174/path_to_pro/",
    reuseExistingServer: false,
    env: { VITE_BASE: "/path_to_pro/" },
  },
});
