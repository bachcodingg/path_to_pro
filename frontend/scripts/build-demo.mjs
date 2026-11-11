// Static demo website build (GitHub Pages): demo mode, served under /path_to_pro/.
// Expects public/demo/snapshot.json (backend/scripts/demo_snapshot.py).
import { execSync } from "node:child_process";
import { existsSync, readFileSync, writeFileSync } from "node:fs";

if (!existsSync("public/demo/snapshot.json")) {
  console.error("Missing public/demo/snapshot.json: run backend/scripts/demo_snapshot.py first");
  process.exit(1);
}
execSync("npm run build", {
  stdio: "inherit",
  env: { ...process.env, VITE_DEMO: "1", VITE_BASE: process.env.VITE_BASE ?? "/path_to_pro/" },
});
// SPA deep links on GitHub Pages: unknown addresses get 404.html, which is PathToPro's page. An
// address inside the Pro League app is handed to that app's page as ?p=<path> instead
// (src/leagues/main.tsx puts it back).
const base = process.env.VITE_BASE ?? "/path_to_pro/";
const handOver = `<script>(function(){var b=${JSON.stringify(`${base}leagues`)},l=location;if(l.pathname===b||l.pathname.indexOf(b+"/")===0){l.replace(b+"/?p="+encodeURIComponent(l.pathname.slice(b.length+1)+l.search+l.hash))}})()</script>`;
writeFileSync("dist/404.html", readFileSync("dist/index.html", "utf8").replace("<head>", `<head>${handOver}`));
