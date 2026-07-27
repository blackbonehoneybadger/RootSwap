import type { Locale } from './i18n'
import type { Direction, PaymentMethod } from './types'

export type AssetStatus = 'sandbox' | 'planned' | 'disabled' | 'real'

export interface RouteOption {
  asset: string
  network: string | null
  label: string
  status: AssetStatus
  enabled: boolean
  addressHint?: string
  memoRequired?: boolean
}

/** BUY: RUB -> crypto. Planned assets shown as Coming soon (disabled). */
export const BUY_ROUTES: RouteOption[] = [
  { asset: 'USDT', network: 'TRC20', label: 'USDT (TRC20)', status: 'sandbox', enabled: true, addressHint: 'T…' },
  { asset: 'BTC', network: 'BTC', label: 'BTC (Bitcoin)', status: 'sandbox', enabled: true, addressHint: 'bc1…' },
  { asset: 'XMR', network: 'XMR', label: 'XMR (Monero · sandbox)', status: 'sandbox', enabled: true },
  { asset: 'ETH', network: 'ERC20', label: 'ETH (ERC20)', status: 'planned', enabled: false },
  { asset: 'SOL', network: 'SOL', label: 'SOL', status: 'planned', enabled: false },
  { asset: 'TON', network: 'TON', label: 'TON', status: 'planned', enabled: false },
  { asset: 'XRP', network: 'XRP', label: 'XRP', status: 'planned', enabled: false, memoRequired: true },
  { asset: 'DOGE', network: 'DOGE', label: 'DOGE', status: 'planned', enabled: false },
  { asset: 'DASH', network: 'DASH', label: 'DASH', status: 'planned', enabled: false },
  { asset: 'BNB', network: 'BSC', label: 'BNB (BSC)', status: 'planned', enabled: false },
  { asset: 'USDT', network: 'ERC20', label: 'USDT (ERC20)', status: 'planned', enabled: false },
  { asset: 'USDT', network: 'SOL', label: 'USDT (SOL)', status: 'planned', enabled: false },
  { asset: 'USDT', network: 'TON', label: 'USDT (TON)', status: 'planned', enabled: false, memoRequired: true },
  { asset: 'USDT', network: 'BSC', label: 'USDT (BSC)', status: 'planned', enabled: false },
  { asset: 'USDC', network: 'ERC20', label: 'USDC (ERC20)', status: 'planned', enabled: false },
  { asset: 'USDC', network: 'SOL', label: 'USDC (SOL)', status: 'planned', enabled: false },
]

/** SELL: crypto -> RUB (sandbox routes only for now). */
export const SELL_ROUTES: RouteOption[] = [
  { asset: 'USDT', network: 'TRC20', label: 'USDT (TRC20)', status: 'sandbox', enabled: true },
  { asset: 'BTC', network: 'BTC', label: 'BTC (Bitcoin)', status: 'sandbox', enabled: true },
  { asset: 'XMR', network: 'XMR', label: 'XMR (Monero · sandbox)', status: 'sandbox', enabled: true },
]

export function routesFor(direction: Direction): RouteOption[] {
  return direction === 'BUY' ? BUY_ROUTES : SELL_ROUTES
}

/**
 * Payment methods and banks use STABLE internal codes as their wire value; only
 * the display label is localized. The code is what the backend stores; changing
 * a translation never changes a stored order.
 */
export interface PaymentMethodOption {
  value: PaymentMethod
}

export const PAYMENT_METHODS: PaymentMethodOption[] = [
  { value: 'SBP' },
  { value: 'bank_transfer' },
  { value: 'card_transfer' },
]

const PAYMENT_METHOD_LABELS: Record<Locale, Record<string, string>> = {
  ru: {
    SBP: 'СБП',
    bank_transfer: 'Банковский перевод',
    card_transfer: 'Перевод на карту',
  },
  en: {
    SBP: 'SBP (Faster Payments)',
    bank_transfer: 'Bank transfer',
    card_transfer: 'Card transfer',
  },
}

/** Stable bank codes (wire values). */
export const BANKS: string[] = ['Sber', 'Tinkoff', 'Alfa', 'Raiffeisen', 'AnyBank']

const BANK_LABELS: Record<Locale, Record<string, string>> = {
  ru: {
    Sber: 'Сбер',
    Tinkoff: 'Т-Банк (Тинькофф)',
    Alfa: 'Альфа-Банк',
    Raiffeisen: 'Райффайзен',
    AnyBank: 'Любой банк',
  },
  en: {
    Sber: 'Sber',
    Tinkoff: 'T-Bank (Tinkoff)',
    Alfa: 'Alfa-Bank',
    Raiffeisen: 'Raiffeisen',
    AnyBank: 'Any bank',
  },
}

export function bankLabel(locale: Locale, bank: string): string {
  return BANK_LABELS[locale][bank] ?? bank
}

export function paymentMethodLabel(locale: Locale, method: string): string {
  return PAYMENT_METHOD_LABELS[locale][method] ?? method
}

/** Positive decimal string without float conversion. */
export function isPositiveDecimalString(value: string): boolean {
  const v = value.trim()
  if (!/^\d+(\.\d+)?$/.test(v)) return false
  if (v === '0' || /^0+\.0+$/.test(v)) return false
  return true
}
