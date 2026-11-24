/**
 * Supplier Saarthi - Service Worker (Task 5C-1)
 * Caches core app shells and assets for seamless offline operation.
 */

const CACHE_NAME = 'supplier-saarthi-cache-v1';
const CORE_ASSETS = [
  '/',
  '/delivery',
  '/promise',
  '/pending',
  '/suppliers',
  '/confirmation',
  '/static/css/style.css',
  '/static/app.js',
  '/static/manifest.json',
  '/static/img/icon.svg',
  '/static/img/icon-192.png',
  '/static/img/icon-512.png',
];

// Install: Pre-cache static shell & pages
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[SW] Pre-caching offline app shell');
      return cache.addAll(CORE_ASSETS).catch((err) => {
        console.warn('[SW] Some assets failed to pre-cache:', err);
      });
    })
  );
  self.skipWaiting();
});

// Activate: Purge older caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            console.log('[SW] Deleting old cache:', key);
            return caches.delete(key);
          }
        })
      );
    })
  );
  self.clients.claim();
});

// Fetch: Network-first for dynamic navigation, Cache-first for static assets
self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);

  // Skip non-GET requests (e.g. POST /api/records handled by app.js offline drafts)
  if (request.method !== 'GET') {
    return;
  }

  // API calls: Network only (client app.js handles offline fallback)
  if (url.pathname.startsWith('/api/')) {
    return;
  }

  // HTML page navigations: Network-first, fallback to cached page
  if (request.mode === 'navigate' || request.headers.get('accept')?.includes('text/html')) {
    event.respondWith(
      fetch(request)
        .then((networkResponse) => {
          if (networkResponse && networkResponse.status === 200) {
            const clone = networkResponse.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
          }
          return networkResponse;
        })
        .catch(() => {
          console.log('[SW] Offline - serving cached navigation:', url.pathname);
          return caches.match(request).then((cached) => {
            if (cached) return cached;
            // Fallback to Home if specific sub-page not cached
            return caches.match('/');
          });
        })
    );
    return;
  }

  // Static Assets (CSS, JS, Images, Fonts): Cache-first with background network update
  event.respondWith(
    caches.match(request).then((cachedResponse) => {
      if (cachedResponse) {
        // Fetch in background to update cache (stale-while-revalidate)
        fetch(request)
          .then((networkResponse) => {
            if (networkResponse && networkResponse.status === 200) {
              caches.open(CACHE_NAME).then((cache) => cache.put(request, networkResponse));
            }
          })
          .catch(() => {});
        return cachedResponse;
      }

      return fetch(request)
        .then((networkResponse) => {
          if (networkResponse && networkResponse.status === 200) {
            const clone = networkResponse.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
          }
          return networkResponse;
        })
        .catch(() => {
          // Fallback if totally offline
          return caches.match('/static/css/style.css');
        });
    })
  );
});
