/**
 * API client for the RootSwap backend.
 * - Base URL from VITE_API_BASE_URL (default "/api/v1").
 * - Auth via POST /auth/telegram with the raw Telegram initData string.
 * - Access token is kept in memory only (never in localStorage).
 * - 401 responses trigger a single re-authentication + retry.
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
    // token expired or invalid: re-authenticate once and retry
    accessToken = null
    await authenticate()
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
