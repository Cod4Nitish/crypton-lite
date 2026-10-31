// CRYPTON service worker (shared by the workspace at / and the lite UI at /lite).
// Pages are always fetched fresh (cache is only an offline fallback), so a new
// deploy is never hidden behind a stale shell. /api is never touched.
const CACHE = "crypton-v3";

self.addEventListener("install", () => self.skipWaiting());

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin || url.pathname.startsWith("/api/")) return;

  if (e.request.mode === "navigate") {
    e.respondWith(
      fetch(url.href, { cache: "no-store" })
        .then((r) => { const copy = r.clone(); caches.open(CACHE).then((c) => c.put(url.pathname, copy)); return r; })
        .catch(() => caches.match(url.pathname))
    );
    return;
  }
  // hashed build assets and icons: cache-first is safe
  if (url.pathname.startsWith("/assets/") || url.pathname.startsWith("/static/")) {
    e.respondWith(
      caches.match(e.request).then((hit) => hit || fetch(e.request).then((r) => {
        const copy = r.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copy));
        return r;
      }))
    );
  }
});
