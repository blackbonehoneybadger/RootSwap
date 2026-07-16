/**
 * Central Telegram Mini Apps WebApp access.
 * Official script: https://telegram.org/js/telegram-web-app.js (index.html).
 * Do not touch window.Telegram outside this module.
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

export interface TelegramBackButton {
  isVisible: boolean
  show(): void
  hide(): void
  onClick(cb: () => void): void
  offClick(cb: () => void): void
}

export interface SafeAreaInset {
  top: number
  bottom: number
  left: number
  right: number
}

export interface TelegramWebApp {
  initData: string
  initDataUnsafe: TelegramInitDataUnsafe
  version: string
  platform: string
  colorScheme: 'light' | 'dark'
  themeParams: TelegramThemeParams
  isExpanded: boolean
  viewportHeight?: number
  viewportStableHeight?: number
  safeAreaInset?: SafeAreaInset
  contentSafeAreaInset?: SafeAreaInset
  ready(): void
  expand(): void
  close(): void
  setHeaderColor?(color: string): void
  setBackgroundColor?(color: string): void
  enableClosingConfirmation?(): void
  disableClosingConfirmation?(): void
  openTelegramLink?(url: string): void
  openLink?(url: string): void
  onEvent?(event: string, cb: () => void): void
  offEvent?(event: string, cb: () => void): void
  BackButton?: TelegramBackButton
  HapticFeedback?: TelegramHapticFeedback
}

declare global {
  interface Window {
    Telegram?: { WebApp?: TelegramWebApp }
  }
}

/** Fake initData for Vite DEV only — never used for production auth. */
const DEV_INIT_DATA =
  'user=%7B%22id%22%3A1%2C%22first_name%22%3A%22Dev%22%7D&auth_date=1&hash=dev'

export function getWebApp(): TelegramWebApp | null {
  if (typeof window === 'undefined') return null
  return window.Telegram?.WebApp ?? null
}

export function isTelegramAvailable(): boolean {
  const wa = getWebApp()
  return Boolean(wa && typeof wa.ready === 'function')
}

/** True when launched inside Telegram with non-empty signed initData. */
export function isInsideTelegram(): boolean {
  const wa = getWebApp()
  return Boolean(wa && typeof wa.initData === 'string' && wa.initData.length > 0)
}

/**
 * Raw initData for backend auth.
 * Outside Telegram: empty in production builds; DEV returns a fake string.
 * Never use initDataUnsafe for server auth.
 */
export function getInitData(): string {
  const wa = getWebApp()
  if (wa?.initData) return wa.initData
  if (import.meta.env.DEV) return DEV_INIT_DATA
  return ''
}

export function getInitDataUnsafe(): TelegramInitDataUnsafe | undefined {
  return getWebApp()?.initDataUnsafe
}

export function getLanguageCode(): string {
  return getWebApp()?.initDataUnsafe?.user?.language_code || 'ru'
}

export function getPlatform(): string {
  return getWebApp()?.platform || 'unknown'
}

export function getVersion(): string {
  return getWebApp()?.version || '0'
}

export function getColorScheme(): 'light' | 'dark' {
  return getWebApp()?.colorScheme || 'light'
}

export function getThemeParams(): TelegramThemeParams {
  return getWebApp()?.themeParams || {}
}

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

/** Map Telegram theme + safe areas onto CSS variables. */
export function applyTelegramTheme(): void {
  const root = document.documentElement
  const tp = getThemeParams()
  const scheme = getColorScheme()
  root.dataset.theme = scheme

  const bg = tp.bg_color || (scheme === 'dark' ? '#0e0e0e' : '#ffffff')
  const text = tp.text_color || (scheme === 'dark' ? '#ffffff' : '#111111')
  const hint = tp.hint_color || (scheme === 'dark' ? '#aaaaaa' : '#707579')
  const link = tp.link_color || '#2481cc'
  const button = tp.button_color || '#2481cc'
  const buttonText = tp.button_text_color || '#ffffff'
  const secondary = tp.secondary_bg_color || (scheme === 'dark' ? '#1c1c1d' : '#f4f4f5')

  root.style.setProperty('--tg-bg', bg)
  root.style.setProperty('--tg-text', text)
  root.style.setProperty('--tg-hint', hint)
  root.style.setProperty('--tg-link', link)
  root.style.setProperty('--tg-button', button)
  root.style.setProperty('--tg-button-text', buttonText)
  root.style.setProperty('--tg-secondary', secondary)

  const wa = getWebApp()
  const sai = wa?.safeAreaInset
  const csai = wa?.contentSafeAreaInset
  const top = Math.max(sai?.top ?? 0, csai?.top ?? 0)
  const bottom = Math.max(sai?.bottom ?? 0, csai?.bottom ?? 0)
  const left = Math.max(sai?.left ?? 0, csai?.left ?? 0)
  const right = Math.max(sai?.right ?? 0, csai?.right ?? 0)

  root.style.setProperty('--safe-top', top ? `${top}px` : 'env(safe-area-inset-top, 0px)')
  root.style.setProperty('--safe-bottom', bottom ? `${bottom}px` : 'env(safe-area-inset-bottom, 0px)')
  root.style.setProperty('--safe-left', left ? `${left}px` : 'env(safe-area-inset-left, 0px)')
  root.style.setProperty('--safe-right', right ? `${right}px` : 'env(safe-area-inset-right, 0px)')

  try {
    wa?.setBackgroundColor?.(bg)
    wa?.setHeaderColor?.(bg)
  } catch {
    /* older clients */
  }
}

export function watchTelegramTheme(): () => void {
  const wa = getWebApp()
  if (!wa?.onEvent) return () => undefined
  const onTheme = () => applyTelegramTheme()
  wa.onEvent('themeChanged', onTheme)
  wa.onEvent('viewportChanged', onTheme)
  wa.onEvent('safeAreaChanged', onTheme)
  wa.onEvent('contentSafeAreaChanged', onTheme)
  return () => {
    wa.offEvent?.('themeChanged', onTheme)
    wa.offEvent?.('viewportChanged', onTheme)
    wa.offEvent?.('safeAreaChanged', onTheme)
    wa.offEvent?.('contentSafeAreaChanged', onTheme)
  }
}

/** Notify Telegram that the app is ready and expand to full height. */
export function initTelegram(): void {
  const wa = getWebApp()
  if (!wa) {
    applyTelegramTheme()
    return
  }
  try {
    wa.ready()
    wa.expand()
    wa.enableClosingConfirmation?.()
  } catch {
    /* non-fatal */
  }
  applyTelegramTheme()
}

type BackHandler = () => void
let backHandler: BackHandler | null = null

function onBackClick(): void {
  backHandler?.()
}

export function bindBackButton(handler: BackHandler): () => void {
  const wa = getWebApp()
  if (!wa?.BackButton) {
    backHandler = handler
    return () => {
      if (backHandler === handler) backHandler = null
    }
  }
  if (backHandler) wa.BackButton.offClick(onBackClick)
  backHandler = handler
  wa.BackButton.onClick(onBackClick)
  wa.BackButton.show()
  return () => {
    wa.BackButton?.offClick(onBackClick)
    if (backHandler === handler) {
      backHandler = null
      wa.BackButton?.hide()
    }
  }
}

export function hideBackButton(): void {
  const wa = getWebApp()
  if (backHandler && wa?.BackButton) wa.BackButton.offClick(onBackClick)
  backHandler = null
  wa?.BackButton?.hide()
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

export function closeMiniApp(): void {
  getWebApp()?.close()
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
