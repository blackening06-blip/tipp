// Minimaler Service Worker, damit Android die Seite als App installiert. Lädt immer frisch aus dem Netz.
self.addEventListener("fetch", e => e.respondWith(fetch(e.request)));
