/**
 * Centralized API configuration.
 *
 * Reads from Vite env vars when available, otherwise derives from
 * `window.location` so the frontend works behind any reverse proxy
 * or on any host/port without code changes.
 *
 * Environment variables (set in .env or .env.local):
 *   VITE_API_URL   – e.g. "http://192.168.1.50:8000"
 *   VITE_WS_URL    – e.g. "ws://192.168.1.50:8000/ws"
 */

function resolveBaseUrl(): string {
  // Explicit override via Vite env
  if (import.meta.env.VITE_API_URL) {
    return (import.meta.env.VITE_API_URL as string).replace(/\/+$/, '');
  }
  // Derive from current page origin (works behind reverse proxy)
  return window.location.origin;
}

function resolveWsUrl(): string {
  if (import.meta.env.VITE_WS_URL) {
    return import.meta.env.VITE_WS_URL as string;
  }
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}/ws`;
}

/** Absolute base URL for REST calls, e.g. "http://localhost:8000" */
export const BASE_URL = resolveBaseUrl();

/** WebSocket URL, e.g. "ws://localhost:8000/ws" */
export const WS_URL = resolveWsUrl();

/** True when built with VITE_DEMO_MODE=true */
export const IS_DEMO = import.meta.env.VITE_DEMO_MODE === 'true';

/** Build a full API URL from a relative path like "/api/chat/history" */
export function apiUrl(path: string): string {
  return `${BASE_URL}${path}`;
}

// Register demo service worker on startup
if (IS_DEMO && 'serviceWorker' in navigator) {
  const swPath = `${import.meta.env.BASE_URL}demo-sw.js`;
  navigator.serviceWorker.register(swPath, { scope: import.meta.env.BASE_URL }).then(() => {
    // If controller isn't active yet, reload once so SW intercepts fetches
    if (!navigator.serviceWorker.controller) {
      navigator.serviceWorker.ready.then(() => window.location.reload());
    }
  });
}
