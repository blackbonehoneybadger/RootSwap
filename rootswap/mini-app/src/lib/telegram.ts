/**
 * Central Telegram Mini Apps WebApp access.
 * Uses the official telegram-web-app.js script (index.html).
 * Do not import window.Telegram elsewhere — go through this module.
 */

export type TelegramThemeParams = Record<string, string | undefined>;

export interface TelegramWebAppLike {
  initData: string;
  initDataUnsafe: {
    user?: {
      id: number;
      username?: string;
      first_name?: string;
      language_code?: string;
    };
    start_param?: string;
  };
  version: string;
  platform: string;
  colorScheme: 'light' | 'dark';
  themeParams: TelegramThemeParams;
  isExpanded: boolean;
  viewportHeight: number;
  viewportStableHeight: number;
  ready: () => void;
  expand: () => void;
  close: () => void;
  setHeaderColor?: (color: string) => void;
  setBackgroundColor?: (color: string) => void;
  enableClosingConfirmation?: () => void;
  disableClosingConfirmation?: () => void;
  BackButton: {
    isVisible: boolean;
    show: () => void;
    hide: () => void;
    onClick: (cb: () => void) => void;
    offClick: (cb: () => void) => void;
  };
  MainButton: {
    text: string;
    isVisible: boolean;
    isActive: boolean;
    setText: (t: string) => void;
    show: () => void;
    hide: () => void;
    enable: () => void;
    disable: () => void;
    onClick: (cb: () => void) => void;
    offClick: (cb: () => void) => void;
    showProgress: (leaveActive?: boolean) => void;
    hideProgress: () => void;
  };
  HapticFeedback?: {
    impactOccurred: (style: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft') => void;
    notificationOccurred: (type: 'error' | 'success' | 'warning') => void;
  };
  safeAreaInset?: { top: number; bottom: number; left: number; right: number };
  contentSafeAreaInset?: { top: number; bottom: number; left: number; right: number };
  onEvent?: (event: string, cb: () => void) => void;
  offEvent?: (event: string, cb: () => void) => void;
}

declare global {
  interface Window {
    Telegram?: { WebApp?: TelegramWebAppLike };
  }
}

export function getWebApp(): TelegramWebAppLike | null {
  return window.Telegram?.WebApp ?? null;
}

export function isTelegramAvailable(): boolean {
  const wa = getWebApp();
  return Boolean(wa && typeof wa.ready === 'function');
}

/** True when launched inside Telegram with signed initData. */
export function isInsideTelegram(): boolean {
  const wa = getWebApp();
  return Boolean(wa?.initData && wa.initData.length > 0);
}

export function getInitData(): string {
  return getWebApp()?.initData || '';
}

export function getInitDataUnsafe() {
  return getWebApp()?.initDataUnsafe;
}

export function getPlatform(): string {
  return getWebApp()?.platform || 'unknown';
}

export function getVersion(): string {
  return getWebApp()?.version || '0';
}

export function getColorScheme(): 'light' | 'dark' {
  return getWebApp()?.colorScheme || 'light';
}

export function getThemeParams(): TelegramThemeParams {
  return getWebApp()?.themeParams || {};
}

export function getLanguageCode(): string {
  return getWebApp()?.initDataUnsafe?.user?.language_code || 'ru';
}

export function getStartParam(): string | undefined {
  return getWebApp()?.initDataUnsafe?.start_param;
}

export function initTelegramApp(): void {
  const wa = getWebApp();
  if (!wa) return;
  wa.ready();
  wa.expand();
  try {
    wa.enableClosingConfirmation?.();
  } catch {
    /* older clients */
  }
  applyTelegramTheme();
}

/** Map Telegram themeParams → CSS variables on :root */
export function applyTelegramTheme(): void {
  const root = document.documentElement;
  const tp = getThemeParams();
  const scheme = getColorScheme();
  root.dataset.theme = scheme;

  const bg = tp.bg_color || (scheme === 'dark' ? '#0e0e0e' : '#ffffff');
  const text = tp.text_color || (scheme === 'dark' ? '#ffffff' : '#111111');
  const hint = tp.hint_color || (scheme === 'dark' ? '#aaaaaa' : '#707579');
  const link = tp.link_color || '#2481cc';
  const button = tp.button_color || '#2481cc';
  const buttonText = tp.button_text_color || '#ffffff';
  const secondary = tp.secondary_bg_color || (scheme === 'dark' ? '#1c1c1d' : '#f4f4f5');

  root.style.setProperty('--tg-bg', bg);
  root.style.setProperty('--tg-text', text);
  root.style.setProperty('--tg-hint', hint);
  root.style.setProperty('--tg-link', link);
  root.style.setProperty('--tg-button', button);
  root.style.setProperty('--tg-button-text', buttonText);
  root.style.setProperty('--tg-secondary', secondary);
  const wa = getWebApp();
  const sai = wa?.safeAreaInset;
  const csai = wa?.contentSafeAreaInset;
  const top = Math.max(sai?.top ?? 0, csai?.top ?? 0);
  const bottom = Math.max(sai?.bottom ?? 0, csai?.bottom ?? 0);
  const left = Math.max(sai?.left ?? 0, csai?.left ?? 0);
  const right = Math.max(sai?.right ?? 0, csai?.right ?? 0);

  root.style.setProperty(
    '--safe-top',
    top ? `${top}px` : 'env(safe-area-inset-top, 0px)',
  );
  root.style.setProperty(
    '--safe-bottom',
    bottom ? `${bottom}px` : 'env(safe-area-inset-bottom, 0px)',
  );
  root.style.setProperty(
    '--safe-left',
    left ? `${left}px` : 'env(safe-area-inset-left, 0px)',
  );
  root.style.setProperty(
    '--safe-right',
    right ? `${right}px` : 'env(safe-area-inset-right, 0px)',
  );

  try {
    wa?.setBackgroundColor?.(bg);
    wa?.setHeaderColor?.(bg);
  } catch {
    /* ignore */
  }
}

/** Re-apply theme when Telegram notifies about theme / viewport changes. */
export function watchTelegramTheme(): () => void {
  const wa = getWebApp();
  if (!wa?.onEvent) return () => undefined;
  const onTheme = () => applyTelegramTheme();
  wa.onEvent('themeChanged', onTheme);
  wa.onEvent('viewportChanged', onTheme);
  wa.onEvent('safeAreaChanged', onTheme);
  wa.onEvent('contentSafeAreaChanged', onTheme);
  return () => {
    wa.offEvent?.('themeChanged', onTheme);
    wa.offEvent?.('viewportChanged', onTheme);
    wa.offEvent?.('safeAreaChanged', onTheme);
    wa.offEvent?.('contentSafeAreaChanged', onTheme);
  };
}

type BackHandler = () => void;
let backHandler: BackHandler | null = null;

function onBackClick() {
  backHandler?.();
}

/** Show Telegram BackButton and bind handler (replaces previous). */
export function bindBackButton(handler: BackHandler): () => void {
  const wa = getWebApp();
  if (!wa?.BackButton) {
    backHandler = handler;
    return () => {
      if (backHandler === handler) backHandler = null;
    };
  }
  if (backHandler) {
    wa.BackButton.offClick(onBackClick);
  }
  backHandler = handler;
  wa.BackButton.onClick(onBackClick);
  wa.BackButton.show();
  return () => {
    wa.BackButton.offClick(onBackClick);
    if (backHandler === handler) {
      backHandler = null;
      wa.BackButton.hide();
    }
  };
}

export function hideBackButton(): void {
  const wa = getWebApp();
  if (backHandler && wa?.BackButton) {
    wa.BackButton.offClick(onBackClick);
  }
  backHandler = null;
  wa?.BackButton?.hide();
}

export function hapticSuccess(): void {
  try {
    getWebApp()?.HapticFeedback?.notificationOccurred('success');
  } catch {
    /* ignore */
  }
}

export function hapticError(): void {
  try {
    getWebApp()?.HapticFeedback?.notificationOccurred('error');
  } catch {
    /* ignore */
  }
}

export function closeMiniApp(): void {
  getWebApp()?.close();
}
