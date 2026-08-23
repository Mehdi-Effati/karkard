// سرویس‌ورکر ساده تقویم کاری.
// فقط فایل‌های استاتیک (css/js/icons) را کش می‌کند تا لود بعدی سریع‌تر شود
// و اپ قابل نصب (PWA) باشد. صفحات داینامیک و لاگین‌محور را عمداً کش نمی‌کند
// تا هیچ‌وقت اطلاعات قدیمی یا صفحه اشتباه کاربر دیگری نشان داده نشود.

const CACHE_NAME = 'karkard-static-v1';
const STATIC_ASSETS = [
  '/static/attendance/css/style.css',
  '/static/attendance/js/calendar.js',
  '/static/attendance/icons/icon-192.png',
  '/static/attendance/icons/icon-512.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS)).catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // فقط درخواست‌های GET به فایل‌های استاتیک را از کش پاسخ بده؛ بقیه (صفحات، API) همیشه از شبکه
  if (event.request.method !== 'GET' || !url.pathname.startsWith('/static/')) {
    return;
  }

  event.respondWith(
    caches.match(event.request).then((cached) => {
      const networkFetch = fetch(event.request)
        .then((response) => {
          if (response && response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          }
          return response;
        })
        .catch(() => cached);
      return cached || networkFetch;
    })
  );
});
