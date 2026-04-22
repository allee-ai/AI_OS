import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

// Mobile bookmark flow: http://host:8000/?key=<token>
// Captures the token, stores it, and strips it from the URL so the
// bookmark works once and the address bar stays clean after.
try {
  const params = new URLSearchParams(window.location.search)
  const key = params.get('key')
  if (key) {
    localStorage.setItem('aios_api_token', key.trim())
    params.delete('key')
    const qs = params.toString()
    const clean = window.location.pathname + (qs ? `?${qs}` : '') + window.location.hash
    window.history.replaceState({}, '', clean)
  }
} catch {
  // non-fatal — fall through to normal login gate
}

const nativeFetch = window.fetch.bind(window)

window.fetch = (input: RequestInfo | URL, init?: RequestInit) => {
  const token = localStorage.getItem('aios_api_token')
  if (!token) {
    return nativeFetch(input, init)
  }

  const headers = new Headers(init?.headers)
  if (!headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  return nativeFetch(input, { ...init, headers })
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
