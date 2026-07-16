/**
 * Minimal i18n — Russian / English.
 * Prefer Telegram language_code; allow manual override via localStorage.
 */

export type Locale = 'ru' | 'en';

const STORAGE_KEY = 'rootswap_locale';

const dict = {
  ru: {
    brand: 'RootSwap',
    subtitle: 'Лучший безопасный маршрут обмена',
    demoNotice: 'Demo / Sandbox. Реальные деньги отключены. Условия партнёров могут отличаться.',
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
    comingSoon: 'Скоро',
    sandbox: 'Sandbox',
    getQuotes: 'Получить предложения',
    searching: 'Ищем…',
    confirm: 'Подтвердить',
    createOrder: 'Создать заявку',
    creating: 'Создаём…',
    cancel: 'Отмена',
    amount: 'Сумма',
    network: 'Сеть',
    wallet: 'Адрес получения',
    paymentMethod: 'Способ оплаты',
    bank: 'Банк',
    quotes: 'Предложения',
    bestOverall: 'Лучший общий вариант',
    lowestFee: 'Самая низкая комиссия',
    fastest: 'Самое быстрое исполнение',
    rootScore: 'RootScore',
    expires: 'Истекает',
    quoteExpired: 'Котировка истекла. Получите новую.',
    wrongNetworkWarn:
      'Отправка на неверный адрес или в другую сеть может привести к безвозвратной потере средств.',
    aggregatorNotice:
      'RootSwap агрегирует предложения партнёров. KYC и лимиты зависят от выбранного партнёра.',
    loading: 'Загрузка RootSwap…',
    authRequired: 'Нужна авторизация через Telegram Mini App.',
    authFailed: 'Ошибка авторизации',
    noQuotes: 'Нет доступных предложений. Попробуйте другую сумму.',
    back: 'Назад',
    language: 'Язык',
  },
  en: {
    brand: 'RootSwap',
    subtitle: 'Best safe exchange route',
    demoNotice: 'Demo / Sandbox. Real money disabled. Partner terms may vary.',
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
    comingSoon: 'Coming soon',
    sandbox: 'Sandbox',
    getQuotes: 'Get quotes',
    searching: 'Searching…',
    confirm: 'Confirm',
    createOrder: 'Create order',
    creating: 'Creating…',
    cancel: 'Cancel',
    amount: 'Amount',
    network: 'Network',
    wallet: 'Receiving address',
    paymentMethod: 'Payment method',
    bank: 'Bank',
    quotes: 'Quotes',
    bestOverall: 'Best overall',
    lowestFee: 'Lowest fee',
    fastest: 'Fastest',
    rootScore: 'RootScore',
    expires: 'Expires',
    quoteExpired: 'Quote expired. Get a new one.',
    wrongNetworkWarn:
      'Sending to the wrong address or network may result in irreversible loss of funds.',
    aggregatorNotice:
      'RootSwap aggregates partner offers. KYC and limits depend on the selected partner.',
    loading: 'Loading RootSwap…',
    authRequired: 'Open RootSwap inside Telegram Mini App to sign in.',
    authFailed: 'Auth failed',
    noQuotes: 'No quotes available. Try another amount.',
    back: 'Back',
    language: 'Language',
  },
} as const;

export type MsgKey = keyof typeof dict.ru;

export function detectLocale(telegramLang?: string): Locale {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved === 'ru' || saved === 'en') return saved;
  if (telegramLang?.toLowerCase().startsWith('en')) return 'en';
  return 'ru';
}

export function setLocale(locale: Locale): void {
  localStorage.setItem(STORAGE_KEY, locale);
}

export function t(locale: Locale, key: MsgKey): string {
  return dict[locale][key] || dict.ru[key];
}
