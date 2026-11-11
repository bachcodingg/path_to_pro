/// <reference types="vitest/config" />
import { resolve } from "node:path";
import { defineConfig, type Connect, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { VitePWA } from "vite-plugin-pwa";

const base = process.env.VITE_BASE ?? "/";

// Two apps, one build: PathToPro (index.html) and Pro League Data Tracking (leagues/index.html).
// The dev and preview servers send an address inside the Pro League app to that app's page, as
// the production servers do (backend/api/main.py, nginx.conf, the demo website's 404.html).
const leaguesPage: Connect.NextHandleFunction = (req, _res, next) => {
  const url = req.url ?? "";
  const path = url.split("?")[0];
  const inApp = path === `${base}leagues` || path.startsWith(`${base}leagues/`);
  const isFile = /\.[a-z0-9]+$/i.test(path);
  const wantsPage = (req.headers.accept ?? "").includes("text/html");
  if (inApp && !isFile && wantsPage) req.url = `${base}leagues/index.html`;
  next();
};
const twoApps: Plugin = {
  name: "pathtopro-two-apps",
  configureServer: (server) => void server.middlewares.use(leaguesPage),
  configurePreviewServer: (server) => void server.middlewares.use(leaguesPage),
};

export default defineConfig({
  base,
  build: {
    rollupOptions: {
      input: { pathtopro: resolve(__dirname, "index.html"), leagues: resolve(__dirname, "leagues/index.html") },
    },
  },
  plugins: [
    twoApps,
    react(),
    tailwindcss(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["icon.svg", "push-sw.js", "manifest.webmanifest", "leagues/icon.svg", "leagues/manifest.webmanifest"],
      // Each app has its own install manifest (public/manifest.webmanifest and
      // public/leagues/manifest.webmanifest), linked from its own page
      manifest: false,
      workbox: {
        navigateFallback: `${base}index.html`,
        // Pages inside the Pro League app come from its own entry page, never PathToPro's
        navigateFallbackDenylist: [new RegExp(`^${base}leagues(/|$)`)],
        // Push notifications: public/push-sw.js handles "push" and "notificationclick"
        importScripts: ["push-sw.js"],
        runtimeCaching: [
          {
            urlPattern: ({ request, url }) => request.mode === "navigate" && url.pathname.startsWith(`${base}leagues`),
            handler: "NetworkFirst",
            options: { cacheName: "leagues-pages", networkTimeoutSeconds: 4 },
          },
          {
            urlPattern: ({ url }) => url.pathname.includes("/api/me/"),
            handler: "NetworkFirst",
            options: { cacheName: "player-api", networkTimeoutSeconds: 4 },
          },
        ],
      },
    }),
  ],
  preview: {
    port: 4173,
    proxy: { "/api": { target: process.env.VITE_API ?? "http://127.0.0.1:8000", changeOrigin: true } },
  },
  server: {
    port: 5173,
    proxy: { "/api": { target: process.env.VITE_API ?? "http://127.0.0.1:8000", changeOrigin: true } },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
    globals: true,
  },
});
