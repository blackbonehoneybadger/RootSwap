import type { Direction, PaymentMethod } from './types'

export interface RouteOption {
  asset: string
  network: string | null
  label: string
}

/** BUY: RUB -> crypto */
export const BUY_ROUTES: RouteOption[] = [
  { asset: 'USDT', network: 'TRC20', label: 'USDT (TRC20)' },
  { asset: 'BTC', network: 'BTC', label: 'BTC (Bitcoin)' },
  { asset: 'XMR', network: 'XMR', label: 'XMR (Monero)' },
]

/** SELL: crypto -> RUB */
export const SELL_ROUTES: RouteOption[] = [
  { asset: 'USDT', network: 'TRC20', label: 'USDT (TRC20)' },
  { asset: 'BTC', network: 'BTC', label: 'BTC (Bitcoin)' },
  { asset: 'XMR', network: 'XMR', label: 'XMR (Monero)' },
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
