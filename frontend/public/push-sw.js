// Loaded into the generated service worker (vite.config.ts: workbox.importScripts).
// Shows PathToPro's push messages and opens the right page when one is tapped.
self.addEventListener("push", (event) => {
  let data = { title: "PathToPro", body: "", url: "/" };
  try {
    data = { ...data, ...event.data.json() };
  } catch {
    /* not JSON: show the default */
  }
  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: "icon-192.png",
      badge: "icon-192.png",
      data: { url: data.url },
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  // Paths from the server are relative to where the app is installed (it may live under a base path)
  const path = ((event.notification.data && event.notification.data.url) || "/").replace(/^\//, "");
  const target = new URL(path, self.registration.scope).href;
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((windows) => {
      for (const w of windows) {
        if ("focus" in w) {
          w.navigate(target);
          return w.focus();
        }
      }
      return self.clients.openWindow(target);
    }),
  );
});
