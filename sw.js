// Network-first Service Worker: immer frische Daten, Offline-Fallback aus Cache
const CACHE = 'alphacycle-v3';
self.addEventListener('install', e => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(
  caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => clients.claim())
));
self.addEventListener('fetch', e => {
  const noStore = e.request.url.includes('data.js');
  e.respondWith(
    fetch(e.request, noStore ? {cache: 'no-store'} : {}).then(r => {
      const copy = r.clone();
      caches.open(CACHE).then(c => c.put(e.request, copy)).catch(()=>{});
      return r;
    }).catch(() => caches.match(e.request))
  );
});
