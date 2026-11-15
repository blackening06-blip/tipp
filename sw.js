// Minimaler Service Worker, damit Android die Seite als App installiert.
// Fragt bei jedem Laden bei GitHub nach, ob es eine neue Version gibt.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", e => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", e => e.respondWith(fetch(e.request, {cache: "no-cache"}).catch(() => fetch(e.request))));
