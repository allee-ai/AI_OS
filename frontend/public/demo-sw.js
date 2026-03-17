/**
 * Demo Mode Service Worker
 * Intercepts all /api/* requests and returns mock data from demo-data.json.
 * Registered only when VITE_DEMO_MODE=true at build time.
 */

let MOCK_DATA = {};

// Load mock data on activation
self.addEventListener('install', (event) => {
  event.waitUntil(
    fetch('./demo-data.json')
      .then(res => res.json())
      .then(data => { MOCK_DATA = data; })
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

/**
 * Match a request path against the mock data routes.
 * Supports exact matches and parameterized routes like /api/identity/profiles/:id
 */
function findMockResponse(method, pathname) {
  const key = `${method} ${pathname}`;

  // 1. Exact match
  if (MOCK_DATA[key]) return MOCK_DATA[key];

  // 2. Pattern match — try replacing trailing path segments with :param
  // e.g. GET /api/identity/profiles/some-id → GET /api/identity/profiles/:id
  const segments = pathname.split('/');
  for (let i = segments.length - 1; i >= 2; i--) {
    const pattern = [...segments.slice(0, i), ':param', ...segments.slice(i + 1)].join('/');
    const patternKey = `${method} ${pattern}`;
    if (MOCK_DATA[patternKey]) return MOCK_DATA[patternKey];

    // Also try with :id, :name, :section
    for (const placeholder of [':id', ':name', ':section', ':module']) {
      const altPattern = [...segments.slice(0, i), placeholder, ...segments.slice(i + 1)].join('/');
      const altKey = `${method} ${altPattern}`;
      if (MOCK_DATA[altKey]) return MOCK_DATA[altKey];
    }
  }

  return null;
}

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Only intercept /api/* requests
  if (!url.pathname.startsWith('/api/')) return;

  // Strip query string for matching
  const pathname = url.pathname;
  const method = event.request.method;

  const mockResponse = findMockResponse(method, pathname);

  if (mockResponse) {
    event.respondWith(
      new Response(JSON.stringify(mockResponse), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      })
    );
  } else {
    // For any unmatched API call, return an empty success
    event.respondWith(
      new Response(JSON.stringify({}), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      })
    );
  }
});
