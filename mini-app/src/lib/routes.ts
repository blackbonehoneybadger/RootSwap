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

export interface PaymentMethodOption {
  value: PaymentMethod
  label: string
}

export const PAYMENT_METHODS: PaymentMethodOption[] = [
  { value: 'SBP', label: 'СБП' },
  { value: 'bank_transfer', label: 'Банковский перевод' },
  { value: 'card_transfer', label: 'Перевод на карту' },
]

export const BANKS: string[] = ['Sber', 'Tinkoff', 'Alfa', 'Raiffeisen', 'AnyBank']

export const BANK_LABELS: Record<string, string> = {
  Sber: 'Сбер',
  Tinkoff: 'Т-Банк (Тинькофф)',
  Alfa: 'Альфа-Банк',
  Raiffeisen: 'Райффайзен',
  AnyBank: 'Любой банк',
}

export function bankLabel(bank: string): string {
  return BANK_LABELS[bank] ?? bank
}

export function paymentMethodLabel(method: string): string {
  const found = PAYMENT_METHODS.find((m) => m.value === method)
  return found ? found.label : method
}

/** Positive decimal string without float conversion. */
export function isPositiveDecimalString(value: string): boolean {
  const v = value.trim()
  if (!/^\d+(\.\d+)?$/.test(v)) return false
  if (v === '0' || /^0+\.0+$/.test(v)) return false
  return true
}
