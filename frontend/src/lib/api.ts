import type { TokenPair } from '../types/api'

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1'
const ACCESS_KEY = 'alejandria_access_token'
const REFRESH_KEY = 'alejandria_refresh_token'

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: unknown,
  ) {
    super(typeof detail === 'string' ? detail : 'La solicitud no pudo completarse')
  }
}

export const sessionStorageKeys = { access: ACCESS_KEY, refresh: REFRESH_KEY }

export function saveSession(tokens: TokenPair) {
  localStorage.setItem(ACCESS_KEY, tokens.access_token)
  localStorage.setItem(REFRESH_KEY, tokens.refresh_token)
}

export function clearSession() {
  localStorage.removeItem(ACCESS_KEY)
  localStorage.removeItem(REFRESH_KEY)
}

let refreshPromise: Promise<boolean> | null = null

async function refreshSession(): Promise<boolean> {
  const refreshToken = localStorage.getItem(REFRESH_KEY)
  if (!refreshToken) return false
  if (!refreshPromise) {
    refreshPromise = fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
      .then(async (response) => {
        if (!response.ok) return false
        saveSession((await response.json()) as TokenPair)
        return true
      })
      .finally(() => {
        refreshPromise = null
      })
  }
  return refreshPromise
}

function errorDetail(payload: unknown): unknown {
  if (payload && typeof payload === 'object' && 'detail' in payload) {
    return (payload as { detail: unknown }).detail
  }
  return payload
}

export async function api<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  const headers = new Headers(init.headers)
  const token = localStorage.getItem(ACCESS_KEY)
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const response = await fetch(`${API_BASE}${path}`, { ...init, headers })
  if (response.status === 401 && retry && (await refreshSession())) {
    return api<T>(path, init, false)
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }))
    if (response.status === 401) clearSession()
    throw new ApiError(response.status, errorDetail(payload))
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export async function loginRequest(email: string, password: string): Promise<TokenPair> {
  const body = new URLSearchParams({ username: email, password })
  const response = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body,
  })
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: 'Credenciales inválidas' }))
    throw new ApiError(response.status, errorDetail(payload))
  }
  return (await response.json()) as TokenPair
}
