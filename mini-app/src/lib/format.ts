import type { OrderStatus, QuoteSourceType } from './types'

/** Russian labels for order statuses. */
export const STATUS_LABELS: Record<OrderStatus, string> = {
  CREATED: 'Создан',
  QUOTE_CONFIRMED: 'Курс зафиксирован',
  AWAITING_PAYMENT: 'Ожидает оплаты',
  PAYMENT_DETECTED: 'Платёж обнаружен',
  PAYMENT_CONFIRMING: 'Подтверждение платежа',
  PROCESSING: 'Обработка',
  PAYOUT_SENT: 'Выплата отправлена',
  COMPLETED: 'Завершён',
  EXPIRED: 'Истёк',
  FAILED: 'Ошибка',
  DISPUTED: 'Открыт спор',
  REFUND_REQUESTED: 'Запрошен возврат',
  REFUND_PROCESSING: 'Возврат в обработке',
  REFUNDED: 'Возврат выполнен',
  REFUND_FAILED: 'Ошибка возврата',
  CANCELLED: 'Отменён',
}

export function statusLabel(status: string): string {
  return STATUS_LABELS[status as OrderStatus] ?? status
}

/** Statuses after which polling can stop. */
export const FINAL_STATUSES: ReadonlySet<OrderStatus> = new Set<OrderStatus>([
  'COMPLETED',
  'EXPIRED',
  'FAILED',
  'REFUNDED',
  'REFUND_FAILED',
  'CANCELLED',
])

export function isFinalStatus(status: OrderStatus): boolean {
  return FINAL_STATUSES.has(status)
}

export type StatusTone = 'ok' | 'progress' | 'warn' | 'bad'

export function statusTone(status: OrderStatus): StatusTone {
  switch (status) {
    case 'COMPLETED':
    case 'REFUNDED':
      return 'ok'
    case 'EXPIRED':
    case 'CANCELLED':
      return 'warn'
    case 'FAILED':
    case 'DISPUTED':
    case 'REFUND_FAILED':
      return 'bad'
    default:
      return 'progress'
  }
}

export const REFUND_STATUSES: ReadonlySet<OrderStatus> = new Set<OrderStatus>([
  'REFUND_REQUESTED',
  'REFUND_PROCESSING',
  'REFUNDED',
  'REFUND_FAILED',
])

/** Russian labels for quote badges. */
export const QUOTE_LABELS: Record<string, string> = {
  best: 'Лучший',
  fastest: 'Самый быстрый',
  lowest_fee: 'Мин. комиссия',
}

export function quoteLabelText(label: string): string {
  return QUOTE_LABELS[label] ?? label
}

export function sourceTypeLabel(source: QuoteSourceType): string {
  switch (source) {
    case 'MOCK':
      return 'DEMO'
    case 'SANDBOX':
      return 'SANDBOX'
    case 'REAL':
      return 'REAL'
  }
}

/** Trim trailing zeros of a decimal string without float precision loss. */
export function fmtAmount(value: string | null | undefined): string {
  if (!value) return '—'
  if (!/^-?\d+(\.\d+)?$/.test(value)) return value
  if (value.includes('.')) {
    const trimmed = value.replace(/0+$/, '').replace(/\.$/, '')
    return trimmed === '' || trimmed === '-' ? '0' : trimmed
  }
  return value
}

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** Seconds remaining until an ISO timestamp (never negative). */
export function secondsUntil(iso: string): number {
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return 0
  return Math.max(0, Math.floor((t - Date.now()) / 1000))
}

export function fmtCountdown(totalSeconds: number): string {
  const m = Math.floor(totalSeconds / 60)
  const s = totalSeconds % 60
  if (m >= 60) {
    const h = Math.floor(m / 60)
    return `${h}:${String(m % 60).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  }
  return `${m}:${String(s).padStart(2, '0')}`
}

export function assetWithNetwork(asset: string, network: string | null): string {
  if (!network || network === asset) return asset
  return `${asset} (${network})`
}
