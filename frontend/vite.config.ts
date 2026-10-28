/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { VitePWA } from "vite-plugin-pwa";

const base = process.env.VITE_BASE ?? "/";

export default defineConfig({
  base,
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["icon.svg", "push-sw.js"],
      manifest: {
        name: "PathToPro",
        short_name: "PathToPro",
        description: "Your training, recovery and development, planned around you.",
        theme_color: "#0f3d2e",
        background_color: "#0b1f17",
        display: "standalone",
        start_url: "./",
        scope: "./",
        icons: [
          { src: "icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "icon-512.png", sizes: "512x512", type: "image/png" },
          { src: "icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any maskable" },
        ],
      },
      workbox: {
        navigateFallback: `${base}index.html`,
        // Push notifications: public/push-sw.js handles "push" and "notificationclick"
        importScripts: ["push-sw.js"],
        runtimeCaching: [
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
