/**
 * Typed wrapper around the Telegram WebApp SDK loaded via
 * <script src="https://telegram.org/js/telegram-web-app.js"> in index.html.
 * Provides safe fallbacks when running outside of Telegram.
 */

export interface TelegramWebAppUser {
  id: number
  first_name?: string
  last_name?: string
  username?: string
  language_code?: string
}

export interface TelegramInitDataUnsafe {
  user?: TelegramWebAppUser
  start_param?: string
  auth_date?: number
  hash?: string
}

export interface TelegramThemeParams {
  bg_color?: string
  text_color?: string
  hint_color?: string
  link_color?: string
  button_color?: string
  button_text_color?: string
  secondary_bg_color?: string
  [key: string]: string | undefined
}

export interface TelegramHapticFeedback {
  impactOccurred(style: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft'): void
  notificationOccurred(type: 'error' | 'success' | 'warning'): void
  selectionChanged(): void
}

export interface TelegramWebApp {
  initData: string
  initDataUnsafe: TelegramInitDataUnsafe
  version: string
  platform: string
  colorScheme: 'light' | 'dark'
  themeParams: TelegramThemeParams
  isExpanded: boolean
  ready(): void
  expand(): void
  close(): void
  setHeaderColor?(color: string): void
  setBackgroundColor?(color: string): void
  openTelegramLink?(url: string): void
  openLink?(url: string): void
  HapticFeedback?: TelegramHapticFeedback
}

declare global {
  interface Window {
    Telegram?: {
      WebApp?: TelegramWebApp
    }
  }
}

/** Fake initData used only in local development (vite dev server). */
const DEV_INIT_DATA =
  'user=%7B%22id%22%3A1%2C%22first_name%22%3A%22Dev%22%7D&auth_date=1&hash=dev'

export function getWebApp(): TelegramWebApp | null {
  if (typeof window === 'undefined') return null
  return window.Telegram?.WebApp ?? null
}

/** True when the app is really opened inside a Telegram client. */
export function isInsideTelegram(): boolean {
  const wa = getWebApp()
  return !!wa && typeof wa.initData === 'string' && wa.initData.length > 0
}

/**
 * Raw initData string for backend auth.
 * Outside Telegram: empty string in production; in DEV mode returns
 * a fake initData string so the app remains usable against a sandbox backend.
 */
export function getInitData(): string {
  const wa = getWebApp()
  if (wa && wa.initData) return wa.initData
  if (import.meta.env.DEV) return DEV_INIT_DATA
  return ''
}

/** start_param from Telegram (e.g. "ref_ABC123"), with URL fallback. */
export function getStartParam(): string | null {
  const wa = getWebApp()
  const sp = wa?.initDataUnsafe?.start_param
  if (sp) return sp
  try {
    const url = new URL(window.location.href)
    return (
      url.searchParams.get('tgWebAppStartParam') ??
      url.searchParams.get('start_param')
    )
  } catch {
    return null
  }
}

export function getTelegramUser(): TelegramWebAppUser | null {
  return getWebApp()?.initDataUnsafe?.user ?? null
}

/** Notify Telegram that the app is ready and expand to full height. */
export function initTelegram(): void {
  const wa = getWebApp()
  if (!wa) return
  try {
    wa.ready()
    wa.expand()
  } catch {
    // non-fatal: older clients may not support all methods
  }
}

export function hapticSuccess(): void {
  try {
    getWebApp()?.HapticFeedback?.notificationOccurred('success')
  } catch {
    /* noop */
  }
}

export function hapticError(): void {
  try {
    getWebApp()?.HapticFeedback?.notificationOccurred('error')
  } catch {
    /* noop */
  }
}

/** Open a t.me link, preferring the in-Telegram method. */
export function openTelegramLink(url: string): void {
  const wa = getWebApp()
  if (wa?.openTelegramLink) {
    try {
      wa.openTelegramLink(url)
      return
    } catch {
      /* fall through */
    }
  }
  window.open(url, '_blank', 'noopener')
}
