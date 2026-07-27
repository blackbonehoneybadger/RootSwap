/**
 * RU/EN i18n. Telegram language_code is the default; a manual override persists
 * in localStorage and must NEVER re-trigger Telegram auth.
 *
 * `t(locale, key, params?)` supports `{name}` interpolation so templated
 * strings (amounts, asset names) stay a single translatable unit per language.
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
    getQuotes: 'Получить котировки',
    confirm: 'Подтвердить',
    createOrder: 'Создать заявку',
    cancel: 'Отмена',
    wrongNetwork:
      'Отправка на неверный адрес или в другую сеть может привести к безвозвратной потере средств.',
    quoteExpired: 'Котировка истекла. Получите новую.',
    back: 'Назад',

    // Wizard chrome
    wizardBuyTitle: 'Покупка криптовалюты',
    wizardSellTitle: 'Продажа криптовалюты',
    wizardDetailsTitle: 'Детали обмена',
    wizardQuotesTitle: 'Выбор предложения',
    wizardConfirmTitle: 'Подтверждение',
    buyShort: 'Купить',
    sellShort: 'Продать',
    next: 'Далее',
    choose: 'Выбрать',
    demoModeInline: 'DEMO-режим — без реальных денег',
    payRubGet: 'Вы платите RUB и получаете:',
    sendCryptoGetRub: 'Вы отправляете криптовалюту и получаете RUB:',
    amountInRub: 'Сумма в RUB',
    amountInAsset: 'Сумма в {asset}',
    egAmountBuy: 'например, 10000',
    egAmountSell: 'например, 100',
    enterPositive: 'Введите положительное число',
    paymentMethod: 'Способ оплаты',
    payoutMethod: 'Способ получения RUB',
    bank: 'Банк',
    walletForAsset: 'Адрес кошелька для получения {asset}',
    addressInNetwork: 'Адрес в сети {network}',
    addressTooShort: 'Адрес выглядит слишком коротким (мин. 11 символов)',
    checkAddressNetwork: 'Внимательно проверьте адрес и сеть ({network}).',
    phoneForSbp: 'Телефон для СБП',
    cardNumber: 'Номер карты',
    accountNumber: 'Номер счёта',
    payoutPlaceholder: 'Реквизиты для выплаты RUB',
    detailsTooShort: 'Реквизиты слишком короткие',
    searchingOffers: 'Ищем предложения…',
    failedQuotes: 'Не удалось получить котировки',
    failedOrder: 'Не удалось создать ордер',
    noOffers: 'Нет доступных предложений. Попробуйте изменить сумму.',
    youReceiveColon: 'Вы получите:',
    rate: 'Курс',
    minutesShort: 'мин',
    rootScore: 'RootScore',
    feesSummary: 'Комиссии: {total} всего',
    feeService: 'Сервис',
    feePartner: 'Партнёр',
    feeNetwork: 'Сеть',
    feeTotal: 'Итого',
    validFor: 'Действует:',
    updating: 'Обновляем…',
    refreshQuotes: 'Обновить котировки',
    directionLabel: 'Направление',
    purchase: 'Покупка',
    sale: 'Продажа',
    asset: 'Актив',
    youGive: 'Вы отдаёте',
    youReceive: 'Вы получите',
    partner: 'Партнёр',
    serviceFee: 'Комиссия сервиса',
    partnerFee: 'Комиссия партнёра',
    networkFee: 'Комиссия сети',
    totalFee: 'Комиссия итого',
    quoteSource: 'Источник котировки',
    kycMayRequire: 'Партнёр может запросить верификацию',
    receivingAddressFor: 'Адрес получения ({asset})',
    payoutRequisites: 'Реквизиты для выплаты RUB',
    method: 'Способ',
    quoteValidFor: 'Котировка действует:',
    confirmedAddress: 'Я проверил адрес и сеть',
    understandDemo: 'Я понимаю, что это DEMO-режим без реальных денег',
    creatingOrder: 'Создаём ордер…',
    confirmExchange: 'Подтвердить обмен',

    // Order screen
    orderWord: 'Ордер',
    orderLoading: 'Загрузка…',
    loadOrderError: 'Ошибка загрузки ордера',
    describeDispute: 'Опишите причину спора:',
    disputeFailed: 'Не удалось открыть спор',
    cancelConfirm: 'Отменить ордер? Это действие нельзя отменить.',
    cancelFailed: 'Не удалось отменить ордер',
    createdAtLabel: 'Создан',
    walletShort: 'Кошелёк',
    payoutShort: 'Выплата',
    refundTitle: 'Возврат средств',
    refundRequestedMsg: 'Запрос на возврат зарегистрирован и ожидает обработки.',
    refundProcessingMsg: 'Возврат выполняется. Обычно это занимает немного времени.',
    refundDoneMsg: 'Возврат выполнен. Средства отправлены обратно.',
    refundFailedMsg: 'Возврат не удался. Обратитесь в поддержку.',
    paymentInstructions: 'Инструкции по оплате',
    payWithin: 'Оплатите в течение:',
    recipient: 'Получатель',
    accountWord: 'Счёт',
    cardWord: 'Карта',
    phoneWord: 'Телефон',
    commentWord: 'Комментарий',
    payCommentNote:
      'Укажите комментарий к платежу точно как выше — по нему платёж сопоставляется с ордером.',
    depositAddress: 'Адрес для депозита',
    sendOnlyNote:
      'Отправляйте только {asset} в сети {network}. Отправка в другой сети приведёт к потере средств (в DEMO-режиме — условной).',
    orderStatusTitle: 'Статус ордера',
    cancelling: 'Отменяем…',
    cancelOrderBtn: 'Отменить ордер',
    sending: 'Отправляем…',
    openDisputeBtn: 'Открыть спор',
    disputeOpenTitle: 'Спор открыт',
    disputeReviewing:
      'Мы рассматриваем ваш спор. Следите за статусом на этом экране.',

    // History
    historyLoadFailed: 'Не удалось загрузить историю.',
    noExchangesYet: 'Пока нет обменов. Начните с главного экрана.',
    repeat: 'Повторить',
    loadError: 'Ошибка загрузки',

    // Referral
    yourLink: 'Ваша ссылка',
    invited: 'приглашено',
    activeShort: 'активных',
    totalRewards: 'Всего наград',
    noRewardsYet: 'Пока нет наград',
    accruals: 'Начисления',
    emptyList: 'Список пуст',
    referralStatsFailed: 'Не удалось загрузить статистику.',

    // Shared components
    home: 'Главная',
    copy: 'Копировать',
    copied: '✓ Скопировано',
    copyAria: 'Скопировать',
    copyAddressManually: 'скопируйте адрес вручную',
    expiredShort: 'истекло',
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

    // Wizard chrome
    wizardBuyTitle: 'Buy crypto',
    wizardSellTitle: 'Sell crypto',
    wizardDetailsTitle: 'Exchange details',
    wizardQuotesTitle: 'Choose an offer',
    wizardConfirmTitle: 'Confirmation',
    buyShort: 'Buy',
    sellShort: 'Sell',
    next: 'Next',
    choose: 'Choose',
    demoModeInline: 'DEMO mode — no real money',
    payRubGet: 'You pay RUB and receive:',
    sendCryptoGetRub: 'You send crypto and receive RUB:',
    amountInRub: 'Amount in RUB',
    amountInAsset: 'Amount in {asset}',
    egAmountBuy: 'e.g. 10000',
    egAmountSell: 'e.g. 100',
    enterPositive: 'Enter a positive number',
    paymentMethod: 'Payment method',
    payoutMethod: 'How to receive RUB',
    bank: 'Bank',
    walletForAsset: 'Receiving wallet address for {asset}',
    addressInNetwork: 'Address on the {network} network',
    addressTooShort: 'Address looks too short (min. 11 characters)',
    checkAddressNetwork: 'Double-check the address and network ({network}).',
    phoneForSbp: 'Phone for SBP',
    cardNumber: 'Card number',
    accountNumber: 'Account number',
    payoutPlaceholder: 'RUB payout details',
    detailsTooShort: 'Details are too short',
    searchingOffers: 'Searching offers…',
    failedQuotes: 'Failed to fetch quotes',
    failedOrder: 'Failed to create order',
    noOffers: 'No offers available. Try changing the amount.',
    youReceiveColon: 'You receive:',
    rate: 'Rate',
    minutesShort: 'min',
    rootScore: 'RootScore',
    feesSummary: 'Fees: {total} total',
    feeService: 'Service',
    feePartner: 'Partner',
    feeNetwork: 'Network',
    feeTotal: 'Total',
    validFor: 'Valid for:',
    updating: 'Updating…',
    refreshQuotes: 'Refresh quotes',
    directionLabel: 'Direction',
    purchase: 'Buy',
    sale: 'Sell',
    asset: 'Asset',
    youGive: 'You give',
    youReceive: 'You receive',
    partner: 'Partner',
    serviceFee: 'Service fee',
    partnerFee: 'Partner fee',
    networkFee: 'Network fee',
    totalFee: 'Total fee',
    quoteSource: 'Quote source',
    kycMayRequire: 'The partner may request verification',
    receivingAddressFor: 'Receiving address ({asset})',
    payoutRequisites: 'RUB payout details',
    method: 'Method',
    quoteValidFor: 'Quote valid for:',
    confirmedAddress: 'I have verified the address and network',
    understandDemo: 'I understand this is DEMO mode with no real money',
    creatingOrder: 'Creating order…',
    confirmExchange: 'Confirm exchange',

    // Order screen
    orderWord: 'Order',
    orderLoading: 'Loading…',
    loadOrderError: 'Failed to load order',
    describeDispute: 'Describe the reason for the dispute:',
    disputeFailed: 'Failed to open dispute',
    cancelConfirm: 'Cancel the order? This action cannot be undone.',
    cancelFailed: 'Failed to cancel order',
    createdAtLabel: 'Created',
    walletShort: 'Wallet',
    payoutShort: 'Payout',
    refundTitle: 'Refund',
    refundRequestedMsg: 'A refund request has been registered and is awaiting processing.',
    refundProcessingMsg: 'The refund is in progress. This usually takes a little while.',
    refundDoneMsg: 'The refund is complete. Funds have been sent back.',
    refundFailedMsg: 'The refund failed. Please contact support.',
    paymentInstructions: 'Payment instructions',
    payWithin: 'Pay within:',
    recipient: 'Recipient',
    accountWord: 'Account',
    cardWord: 'Card',
    phoneWord: 'Phone',
    commentWord: 'Comment',
    payCommentNote:
      'Include the payment comment exactly as shown above — it is how the payment is matched to your order.',
    depositAddress: 'Deposit address',
    sendOnlyNote:
      'Send only {asset} on the {network} network. Sending on another network will result in loss of funds (notional in DEMO mode).',
    orderStatusTitle: 'Order status',
    cancelling: 'Cancelling…',
    cancelOrderBtn: 'Cancel order',
    sending: 'Submitting…',
    openDisputeBtn: 'Open dispute',
    disputeOpenTitle: 'Dispute opened',
    disputeReviewing: 'We are reviewing your dispute. Track the status on this screen.',

    // History
    historyLoadFailed: 'Failed to load history.',
    noExchangesYet: 'No exchanges yet. Start from the home screen.',
    repeat: 'Repeat',
    loadError: 'Loading error',

    // Referral
    yourLink: 'Your link',
    invited: 'invited',
    activeShort: 'active',
    totalRewards: 'Total rewards',
    noRewardsYet: 'No rewards yet',
    accruals: 'Accruals',
    emptyList: 'Empty',
    referralStatsFailed: 'Failed to load stats.',

    // Shared components
    home: 'Home',
    copy: 'Copy',
    copied: '✓ Copied',
    copyAria: 'Copy',
    copyAddressManually: 'copy the address manually',
    expiredShort: 'expired',
  },
} as const

export type MsgKey = keyof typeof dict.ru
export type TParams = Record<string, string | number>

/** Exposed for tests: assert RU/EN key parity and completeness. */
export const messages = dict

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

function interpolate(template: string, params?: TParams): string {
  if (!params) return template
  return template.replace(/\{(\w+)\}/g, (_m, name: string) =>
    name in params ? String(params[name]) : `{${name}}`,
  )
}

export function t(locale: Locale, key: MsgKey, params?: TParams): string {
  const template = dict[locale][key] || dict.ru[key]
  return interpolate(template, params)
}
