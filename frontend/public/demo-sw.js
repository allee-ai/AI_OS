/**
 * Demo Mode Service Worker
 * Intercepts all /api/* requests and returns mock data from demo-data.json.
 * Registered only when VITE_DEMO_MODE=true at build time.
 *
 * v2 – per-profile fact keys, removed dead /api/database endpoints
 */

let MOCK_DATA = {};

/** Fetch (or re-fetch) the mock payload, busting the HTTP cache. */
function loadMockData() {
  return fetch('./demo-data.json', { cache: 'no-cache' })
    .then(res => res.json())
    .then(data => { MOCK_DATA = data; });
}

// Load mock data on install and immediately take over
self.addEventListener('install', (event) => {
  event.waitUntil(loadMockData().then(() => self.skipWaiting()));
});

// Re-load on activate so an updated SW always has fresh data
self.addEventListener('activate', (event) => {
  event.waitUntil(loadMockData().then(() => self.clients.claim()));
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

  const pathname = url.pathname;
  const method = event.request.method;

  // Try matching with sorted query params first (e.g. docs/content?path=X)
  let mockResponse = null;
  if (url.search) {
    const params = new URLSearchParams(url.searchParams);
    params.sort();
    const keyWithQuery = `${method} ${pathname}?${params.toString()}`;
    if (MOCK_DATA[keyWithQuery]) {
      mockResponse = MOCK_DATA[keyWithQuery];
    }
  }

  // Fall back to path-only matching
  if (!mockResponse) {
    mockResponse = findMockResponse(method, pathname);
  }

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
