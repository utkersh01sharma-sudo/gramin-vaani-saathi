// Service worker: app shell offline, API always live.
//
// The split matters. The shell (HTML/CSS/JS/icons) is cache-first, so the app
// opens in a dead zone. Anything under /api/ is network-only: a cached balance
// served as if it were live is worse than no balance at all, so cached reads are
// handled in app.js where they can be stamped with the time they were taken.

const CACHE = 'gvs-shell-v2';
const SHELL = [
  '/',
  '/index.html',
  '/styles.css',
  '/app.js',
  '/i18n.js',
  '/content.js',
  '/cursor.js',
  '/manifest.webmanifest',
  '/icons/icon.svg',
  '/icons/maskable.svg',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/admin/')) return;

  event.respondWith(
    caches.match(request).then((hit) => {
      if (hit) {
        // Refresh in the background so the next open is current.
        event.waitUntil(
          fetch(request)
            .then((res) => res.ok && caches.open(CACHE).then((c) => c.put(request, res.clone())))
            .catch(() => {})
        );
        return hit;
      }
      return fetch(request)
        .then((res) => {
          if (res.ok) {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(request, copy));
          }
          return res;
        })
        .catch(() => caches.match('/index.html'));
    })
  );
});
