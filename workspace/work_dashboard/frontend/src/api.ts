const BASE = '/api'

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('token')
  const h: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) h['Authorization'] = `Bearer ${token}`
  return h
}

async function request<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: authHeaders(),
    ...opts,
  })
  if (res.status === 401) {
    localStorage.removeItem('token')
    localStorage.removeItem('role')
    localStorage.removeItem('username')
    window.location.href = '/login'
    throw new Error('Unauthorized')
  }
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

export interface BalanceSummary {
  deposits: number
  completed: number
  scheduled: number
  pending: number
  balance: number
}

export interface Job {
  id: number
  property_id: number
  property_address: string
  description: string
  cost: number
  billing_type: 'flat' | 'hourly'
  hours: number
  status: string
}

export const api = {
  // Auth
  login: (username: string, password: string) =>
    request<{ token: string; role: string; username: string }>('/auth/login', {
      method: 'POST', body: JSON.stringify({ username, password }),
    }),

  // Balance
  getBalance: () => request<BalanceSummary>('/balance'),

  // Dashboard (legacy format)
  getData: () => request<Record<string, string[][]>>('/data'),
  saveData: (data: Record<string, string[][]>) =>
    request('/data', { method: 'POST', body: JSON.stringify(data) }),

  // Properties
  getProperties: () => request<any[]>('/properties'),
  createProperty: (p: { address: string; owner_name?: string; tenant_url_slug?: string; access_notes?: string }) =>
    request('/properties', { method: 'POST', body: JSON.stringify(p) }),
  updateProperty: (id: number, p: { address: string; owner_name?: string; tenant_url_slug?: string; access_notes?: string }) =>
    request(`/properties/${id}`, { method: 'PATCH', body: JSON.stringify(p) }),
  deleteProperty: (id: number) =>
    request(`/properties/${id}`, { method: 'DELETE' }),

  // Jobs
  getJobs: (status?: string) => request<Job[]>(status ? `/jobs?status=${status}` : '/jobs'),
  createJob: (j: { property_id: number; description: string; cost: number; billing_type?: string; hours?: number; status?: string }) =>
    request('/jobs', { method: 'POST', body: JSON.stringify(j) }),
  updateJob: (id: number, patch: Partial<{ description: string; cost: number; billing_type: string; hours: number; status: string }>) =>
    request(`/jobs/${id}`, { method: 'PATCH', body: JSON.stringify(patch) }),
  deleteJob: (id: number) =>
    request(`/jobs/${id}`, { method: 'DELETE' }),

  // Payments
  getPayments: () => request<any[]>('/payments'),
  createPayment: (p: { amount: number; date: string; note?: string }) =>
    request('/payments', { method: 'POST', body: JSON.stringify(p) }),
  deletePayment: (id: number) =>
    request(`/payments/${id}`, { method: 'DELETE' }),

  // Tenant
  getTenantProperties: () => request<{ id: number; address: string }[]>('/tenant/properties'),
  submitWorkOrder: (wo: { property_id: number; description: string; urgency: string }) =>
    request('/tenant/work-order', { method: 'POST', body: JSON.stringify(wo) }),

  // Users (admin only)
  getUsers: () => request<{ id: number; username: string; role: string; created_at: string }[]>('/auth/users'),
  createUser: (u: { username: string; password: string; role: string }) =>
    request<{ id: number; username: string; role: string }>('/auth/users', { method: 'POST', body: JSON.stringify(u) }),
  resetUserPassword: (id: number, password: string) =>
    request(`/auth/users/${id}/password`, { method: 'PATCH', body: JSON.stringify({ password }) }),
  deleteUser: (id: number) =>
    request(`/auth/users/${id}`, { method: 'DELETE' }),

  // Sync
  sync: () => request<{ ok: boolean; output: string }>('/sync', { method: 'POST' }),
}
