/**
 * Minimal RU/EN i18n. Telegram language_code is the default; manual override
 * persists in localStorage and must NEVER re-trigger Telegram auth.
 */

export type Locale = 'ru' | 'en'

const STORAGE_KEY = 'rootswap_locale'

const dict = {
  ru: {
    brand: 'RootSwap',
    loading: 'Загрузка…',
    openInTelegram: 'Откройте внутри Telegram',
    openInTelegramBody:
      'Это мини-приложение работает внутри Telegram. Откройте бота и запустите приложение оттуда.',
    noInitData: 'Данные Telegram (initData) недоступны в этом окружении.',
    authFailed: 'Не удалось авторизоваться.',
    retry: 'Повторить',
    buy: 'Купить крипту',
    sell: 'Продать крипту',
    history: 'История',
    referral: 'Рефералы',
    profile: 'Профиль',
    support: 'Поддержка',
    legal: 'Документы',
    terms: 'Условия использования',
    privacy: 'Конфиденциальность',
    risk: 'Раскрытие рисков',
    partners: 'Раскрытие о партнёрах',
    aml: 'AML / KYC',
    demoBanner: 'Demo / Sandbox. Реальные деньги отключены.',
    aggregator:
      'RootSwap агрегирует предложения партнёров. KYC и лимиты зависят от выбранного партнёра.',
    comingSoon: 'Скоро',
    sandbox: 'Sandbox',
    language: 'Язык',
    amount: 'Сумма',
    network: 'Сеть',
    wallet: 'Адрес получения',
    getQuotes: 'Получить предложения',
    confirm: 'Подтвердить',
    createOrder: 'Создать заявку',
    cancel: 'Отмена',
    wrongNetwork:
      'Отправка на неверный адрес или в другую сеть может привести к безвозвратной потере средств.',
    quoteExpired: 'Котировка истекла. Получите новую.',
    back: 'Назад',
  },
  en: {
    brand: 'RootSwap',
    loading: 'Loading…',
    openInTelegram: 'Open inside Telegram',
    openInTelegramBody:
      'This mini app runs inside Telegram. Open the bot and launch the app from there.',
    noInitData: 'Telegram initData is unavailable in this environment.',
    authFailed: 'Authentication failed.',
    retry: 'Retry',
    buy: 'Buy crypto',
    sell: 'Sell crypto',
    history: 'History',
    referral: 'Referrals',
    profile: 'Profile',
    support: 'Support',
    legal: 'Legal',
    terms: 'Terms of Service',
    privacy: 'Privacy Policy',
    risk: 'Risk Disclosure',
    partners: 'Partner Disclosure',
    aml: 'AML / KYC',
    demoBanner: 'Demo / Sandbox. Real money disabled.',
    aggregator:
      'RootSwap aggregates partner offers. KYC and limits depend on the selected partner.',
    comingSoon: 'Coming soon',
    sandbox: 'Sandbox',
    language: 'Language',
    amount: 'Amount',
    network: 'Network',
    wallet: 'Receiving address',
    getQuotes: 'Get quotes',
    confirm: 'Confirm',
    createOrder: 'Create order',
    cancel: 'Cancel',
    wrongNetwork:
      'Sending to the wrong address or network may result in irreversible loss of funds.',
    quoteExpired: 'Quote expired. Get a new one.',
    back: 'Back',
  },
} as const

export type MsgKey = keyof typeof dict.ru

export function detectLocale(telegramLang?: string): Locale {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved === 'ru' || saved === 'en') return saved
  } catch {
    /* private mode */
  }
  if (telegramLang?.toLowerCase().startsWith('en')) return 'en'
  return 'ru'
}

export function persistLocale(locale: Locale): void {
  try {
    localStorage.setItem(STORAGE_KEY, locale)
  } catch {
    /* ignore */
  }
}

export function t(locale: Locale, key: MsgKey): string {
  return dict[locale][key] || dict.ru[key]
}
