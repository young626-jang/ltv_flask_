const CACHE_NAME = 'ltv-calculator-v2';
const urlsToCache = [
  '/static/manifest.json',
  '/static/icons/icon-192x192.png',
  '/static/icons/icon-512x512.png'
];

// Install event - cache resources
self.addEventListener('install', event => {
  console.log('Service Worker installing...');
  self.skipWaiting(); // 새 버전 즉시 활성화
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('Opened cache');
        return cache.addAll(urlsToCache);
      })
      .catch(error => {
        console.log('Cache failed:', error);
      })
  );
});

// Fetch event - 네트워크 우선, 실패 시에만 캐시 (오프라인 대비)
// API 요청(/api/)은 절대 캐시하지 않음
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // API 요청은 항상 네트워크로
  if (url.pathname.startsWith('/api/')) {
    return; // 브라우저 기본 동작 (네트워크)
  }

  // 나머지(HTML/CSS/JS): 네트워크 우선 → 성공하면 캐시 갱신, 실패하면 캐시 사용
  event.respondWith(
    fetch(event.request)
      .then(response => {
        if (response && response.status === 200 && event.request.method === 'GET') {
          const responseClone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, responseClone));
        }
        return response;
      })
      .catch(() => caches.match(event.request))
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', event => {
  console.log('Service Worker activating...');
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME) {
            console.log('Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => self.clients.claim()) // 열려있는 탭도 즉시 새 SW 적용
  );
});

// Handle background sync (optional)
self.addEventListener('sync', event => {
  if (event.tag === 'background-sync') {
    console.log('Background sync triggered');
  }
});

// Handle push notifications (optional)
self.addEventListener('push', event => {
  if (event.data) {
    const data = event.data.json();
    const options = {
      body: data.body,
      icon: '/static/icons/icon-192x192.png',
      badge: '/static/icons/icon-72x72.png',
      vibrate: [200, 100, 200],
      data: data.data || {},
      actions: [
        { action: 'open', title: '열기' },
        { action: 'close', title: '닫기' }
      ]
    };

    event.waitUntil(
      self.registration.showNotification(data.title, options)
    );
  }
});

// Handle notification clicks
self.addEventListener('notificationclick', event => {
  event.notification.close();

  if (event.action === 'open') {
    event.waitUntil(
      clients.openWindow('/')
    );
  }
});
