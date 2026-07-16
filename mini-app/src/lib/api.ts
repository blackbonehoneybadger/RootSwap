/**
 * API client for the RootSwap backend.
 * - Base URL from VITE_API_BASE_URL (default "/api/v1").
 * - Auth via POST /auth/telegram with the raw Telegram initData string.
 * - Access token is kept in memory ONLY (never in localStorage/sessionStorage).
 * - The refresh token lives in an HttpOnly cookie the server sets; JS never
 *   reads it. A readable CSRF token accompanies it for the double-submit guard.
 * - On 401 the client first tries a silent cookie refresh (rotating the token);
 *   only if that fails does it fall back to a full initData re-authentication.
 */

import { getInitData, getStartParam } from './telegram'
import type {
  AuthResponse,
  AuthUser,
  CreateOrderRequest,
  Order,
  OrdersResponse,
  QuoteRequest,
  QuotesResponse,
  ReferralStats,
} from './types'

const BASE_URL: string = import.meta.env.VITE_API_BASE_URL || '/api/v1'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** In-memory only — intentionally not persisted. */
let accessToken: string | null = null
let currentUser: AuthUser | null = null
/** Double-submit CSRF token, held in memory for /auth/refresh and /auth/logout. */
let csrfToken: string | null = null
let authPromise: Promise<AuthUser> | null = null

async function readErrorMessage(res: Response): Promise<string> {
  try {
    const text = await res.text()
    if (!text) return `HTTP ${res.status}`
    try {
      const data = JSON.parse(text) as { detail?: unknown; message?: unknown }
      if (typeof data.detail === 'string') return data.detail
      if (typeof data.message === 'string') return data.message
    } catch {
      /* not JSON */
    }
    return text.slice(0, 300)
  } catch {
    return `HTTP ${res.status}`
  }
}

function referralCodeFromStartParam(): string | null {
  const sp = getStartParam()
  if (sp && sp.startsWith('ref_') && sp.length > 4) {
    return sp.slice(4)
  }
  return null
}

async function doAuthenticate(): Promise<AuthUser> {
  const initData = getInitData()
  if (!initData) {
    throw new ApiError(0, 'NO_INIT_DATA')
  }
  const res = await fetch(`${BASE_URL}/auth/telegram`, {
    method: 'POST',
    // credentials so the browser stores the Set-Cookie refresh + csrf cookies
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      init_data: initData,
      referral_code: referralCodeFromStartParam(),
    }),
  })
  if (!res.ok) {
    throw new ApiError(res.status, await readErrorMessage(res))
  }
  const data = (await res.json()) as AuthResponse
  accessToken = data.access_token
  currentUser = data.user
  csrfToken = data.csrf_token ?? null
  return data.user
}

/** Authenticate (deduplicates concurrent calls). */
export function authenticate(): Promise<AuthUser> {
  if (!authPromise) {
    authPromise = doAuthenticate().finally(() => {
      authPromise = null
    })
  }
  return authPromise
}

/**
 * Silent refresh: rotate the refresh cookie and mint a new access token without
 * re-reading initData. Returns true on success. Never throws.
 */
async function tryRefresh(): Promise<boolean> {
  if (!csrfToken) return false
  try {
    const res = await fetch(`${BASE_URL}/auth/refresh`, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRF-Token': csrfToken,
      },
    })
    if (!res.ok) return false
    const data = (await res.json()) as AuthResponse
    accessToken = data.access_token
    currentUser = data.user
    csrfToken = data.csrf_token ?? csrfToken
    return true
  } catch {
    return false
  }
}

/** Revoke the server-side session and clear in-memory auth state. */
export async function logout(): Promise<void> {
  try {
    if (csrfToken) {
      await fetch(`${BASE_URL}/auth/logout`, {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': csrfToken,
        },
      })
    }
  } catch {
    /* best-effort */
  } finally {
    accessToken = null
    currentUser = null
    csrfToken = null
  }
}

export function getCurrentUser(): AuthUser | null {
  return currentUser
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  allowRetry = true,
): Promise<T> {
  if (!accessToken) {
    await authenticate()
  }
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
      Authorization: `Bearer ${accessToken ?? ''}`,
    },
  })
  if (res.status === 401 && allowRetry) {
    // Access token expired: try a silent cookie refresh first (cheap, keeps the
    // session), and only fall back to a full initData re-auth if that fails.
    accessToken = null
    const refreshed = await tryRefresh()
    if (!refreshed) {
      await authenticate()
    }
    return request<T>(path, options, false)
  }
  if (!res.ok) {
    throw new ApiError(res.status, await readErrorMessage(res))
  }
  return (await res.json()) as T
}

export function fetchQuotes(body: QuoteRequest): Promise<QuotesResponse> {
  return request<QuotesResponse>('/quotes', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function createOrder(body: CreateOrderRequest): Promise<Order> {
  return request<Order>('/orders', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function listOrders(): Promise<OrdersResponse> {
  return request<OrdersResponse>('/orders')
}

export function getOrder(id: string): Promise<Order> {
  return request<Order>(`/orders/${encodeURIComponent(id)}`)
}

export function disputeOrder(id: string, reason: string): Promise<Order> {
  return request<Order>(`/orders/${encodeURIComponent(id)}/dispute`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  })
}

export function cancelOrder(id: string): Promise<Order> {
  return request<Order>(`/orders/${encodeURIComponent(id)}/cancel`, {
    method: 'POST',
    body: JSON.stringify({}),
  })
}

export function getReferralStats(): Promise<ReferralStats> {
  return request<ReferralStats>('/referral/stats')
}

/** RFC 4122 v4 UUID, generated client-side (for idempotency keys). */
export function uuidv4(): string {
  const c: Crypto | undefined =
    typeof crypto !== 'undefined' ? crypto : undefined
  if (c && typeof c.randomUUID === 'function') {
    return c.randomUUID()
  }
  const bytes = new Uint8Array(16)
  crypto.getRandomValues(bytes)
  bytes[6] = ((bytes[6] ?? 0) & 0x0f) | 0x40
  bytes[8] = ((bytes[8] ?? 0) & 0x3f) | 0x80
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}
