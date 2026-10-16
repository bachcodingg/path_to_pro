// Static demo website build (GitHub Pages): demo mode, served under /path_to_pro/.
// Expects public/demo/snapshot.json (backend/scripts/demo_snapshot.py).
import { execSync } from "node:child_process";
import { copyFileSync, existsSync } from "node:fs";

if (!existsSync("public/demo/snapshot.json")) {
  console.error("Missing public/demo/snapshot.json: run backend/scripts/demo_snapshot.py first");
  process.exit(1);
}
execSync("npm run build", {
  stdio: "inherit",
  env: { ...process.env, VITE_DEMO: "1", VITE_BASE: process.env.VITE_BASE ?? "/path_to_pro/" },
});
copyFileSync("dist/index.html", "dist/404.html"); // SPA deep links on GitHub Pages
