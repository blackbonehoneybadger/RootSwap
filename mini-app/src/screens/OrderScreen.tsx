import { useCallback, useEffect, useRef, useState } from 'react'
import { disputeOrder, getOrder } from '../lib/api'
import type { Order } from '../lib/types'
import {
  REFUND_STATUSES,
  assetWithNetwork,
  fmtAmount,
  fmtDate,
  isFinalStatus,
  statusLabel,
  statusTone,
} from '../lib/format'
import { Countdown } from '../components/Countdown'
import { CopyButton } from '../components/CopyButton'
import { SourceBadge } from '../components/SourceBadge'
import { QrPlaceholder } from '../components/QrPlaceholder'

const POLL_INTERVAL_MS = 5000

/** Statuses in which the user may still open a dispute. */
const DISPUTABLE = new Set([
  'AWAITING_PAYMENT',
  'PAYMENT_DETECTED',
  'PAYMENT_CONFIRMING',
  'PROCESSING',
  'PAYOUT_SENT',
  'FAILED',
  'EXPIRED',
])

interface OrderScreenProps {
  orderId: string
  initialOrder?: Order | null
  onBack: () => void
}

export function OrderScreen({ orderId, initialOrder, onBack }: OrderScreenProps) {
  const [order, setOrder] = useState<Order | null>(initialOrder ?? null)
  const [error, setError] = useState<string | null>(null)
  const [disputing, setDisputing] = useState(false)
  const timerRef = useRef<number | null>(null)

  const refresh = useCallback(async () => {
    try {
      const o = await getOrder(orderId)
      setOrder(o)
      setError(null)
      return o
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Ошибка загрузки ордера')
      return null
    }
  }, [orderId])

  // initial load + poll every 5s while the status is not final
  useEffect(() => {
    let cancelled = false

    const tick = async () => {
      const o = await refresh()
      if (cancelled) return
      if (o && isFinalStatus(o.status)) return
      timerRef.current = window.setTimeout(() => void tick(), POLL_INTERVAL_MS)
    }
    void tick()

    return () => {
      cancelled = true
      if (timerRef.current !== null) window.clearTimeout(timerRef.current)
    }
  }, [refresh])

  const openDispute = async () => {
    const reason = window.prompt('Опишите причину спора:')
    if (!reason || !reason.trim()) return
    setDisputing(true)
    try {
      const o = await disputeOrder(orderId, reason.trim())
      setOrder(o)
      setError(null)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Не удалось открыть спор')
    } finally {
      setDisputing(false)
    }
  }

  if (!order) {
    return (
      <div className="screen">
        <div className="wizard-header">
          <button type="button" className="back-btn" onClick={onBack}>
            ← Назад
          </button>
          <span className="wizard-title">Ордер</span>
        </div>
        {error ? (
          <div className="error-box">{error}</div>
        ) : (
          <div className="muted center-note">Загрузка…</div>
        )}
      </div>
    )
  }

  const pi = order.payment_instructions
  const isRefund = REFUND_STATUSES.has(order.status)

  return (
    <div className="screen">
      <div className="wizard-header">
        <button type="button" className="back-btn" onClick={onBack}>
          ← Назад
        </button>
        <span className="wizard-title">Ордер {order.id.slice(0, 8)}…</span>
      </div>

      {error && <div className="error-box">{error}</div>}

      <div className="card">
        <div className="order-status-line">
          <span className={`chip chip-${statusTone(order.status)}`}>
            {statusLabel(order.status)}
          </span>
          <SourceBadge source={order.quote_source_type} />
        </div>
        <div className="order-card-amounts">
          {fmtAmount(order.amount_in)}{' '}
          {assetWithNetwork(order.from_asset, order.from_network)} →{' '}
          {fmtAmount(order.amount_out)}{' '}
          {assetWithNetwork(order.to_asset, order.to_network)}
        </div>
        <div className="muted">Создан: {fmtDate(order.created_at)}</div>

        <div className="fees-grid fees-grid-order">
          <span className="muted">Курс</span>
          <span>{fmtAmount(order.exchange_rate)}</span>
          <span className="muted">Комиссия сервиса</span>
          <span>{fmtAmount(order.service_fee)}</span>
          <span className="muted">Комиссия партнёра</span>
          <span>{fmtAmount(order.partner_fee)}</span>
          <span className="muted">Комиссия сети</span>
          <span>{fmtAmount(order.network_fee)}</span>
          <span className="muted">Комиссия итого</span>
          <span>{fmtAmount(order.total_fee)}</span>
        </div>

        {order.wallet_address_masked && (
          <div className="profile-row">
            <span className="muted">Кошелёк</span>
            <span className="mono-inline">{order.wallet_address_masked}</span>
          </div>
        )}
        {order.payout_details_masked && (
          <div className="profile-row">
            <span className="muted">Выплата</span>
            <span className="mono-inline">{order.payout_details_masked}</span>
          </div>
        )}
      </div>

      {isRefund && (
        <div className="card refund-card">
          <div className="notice-title">Возврат средств</div>
          <p className="notice-text">
            {order.status === 'REFUND_REQUESTED' &&
              'Запрос на возврат зарегистрирован и ожидает обработки.'}
            {order.status === 'REFUND_PROCESSING' &&
              'Возврат выполняется. Обычно это занимает немного времени.'}
            {order.status === 'REFUNDED' &&
              'Возврат выполнен. Средства отправлены обратно.'}
            {order.status === 'REFUND_FAILED' &&
              'Возврат не удался. Обратитесь в поддержку.'}
          </p>
        </div>
      )}

      {pi && (
        <div className="card payment-card">
          <div className="notice-title">Инструкции по оплате</div>
          <Countdown expiresAt={pi.expires_at} prefix="Оплатите в течение:" />

          <div className="pay-rows">
            <div className="pay-row">
              <span className="muted">Способ</span>
              <span>{pi.payment_method}</span>
            </div>
            <div className="pay-row">
              <span className="muted">Банк</span>
              <span>{pi.bank_name}</span>
            </div>
            <div className="pay-row">
              <span className="muted">Получатель</span>
              <span>{pi.masked_recipient_name}</span>
            </div>
            {pi.masked_account && (
              <div className="pay-row pay-row-copy">
                <span className="muted">Счёт</span>
                <span className="mono-inline">{pi.masked_account}</span>
                <CopyButton value={pi.masked_account} small />
              </div>
            )}
            {pi.masked_card && (
              <div className="pay-row pay-row-copy">
                <span className="muted">Карта</span>
                <span className="mono-inline">{pi.masked_card}</span>
                <CopyButton value={pi.masked_card} small />
              </div>
            )}
            {pi.masked_phone && (
              <div className="pay-row pay-row-copy">
                <span className="muted">Телефон</span>
                <span className="mono-inline">{pi.masked_phone}</span>
                <CopyButton value={pi.masked_phone} small />
              </div>
            )}
            <div className="pay-row pay-row-copy">
              <span className="muted">Сумма</span>
              <span>
                {fmtAmount(pi.amount)} {pi.currency}
              </span>
              <CopyButton value={pi.amount} small />
            </div>
            {pi.payment_comment && (
              <div className="pay-row pay-row-copy">
                <span className="muted">Комментарий</span>
                <span className="mono-inline">{pi.payment_comment}</span>
                <CopyButton value={pi.payment_comment} small />
              </div>
            )}
          </div>
          <p className="muted pay-note">
            Укажите комментарий к платежу точно как выше — по нему платёж
            сопоставляется с ордером.
          </p>
        </div>
      )}

      {order.deposit_address && (
        <div className="card deposit-card">
          <div className="notice-title">
            Адрес для депозита
            {order.deposit_network ? ` (${order.deposit_network})` : ''}
          </div>
          <QrPlaceholder value={order.deposit_address} />
          <div className="mono-block">{order.deposit_address}</div>
          <CopyButton value={order.deposit_address} />
          <p className="muted pay-note">
            Отправляйте только {order.from_asset} в сети{' '}
            {order.deposit_network ?? order.from_network ?? '—'}. Отправка в
            другой сети приведёт к потере средств (в DEMO-режиме — условной).
          </p>
        </div>
      )}

      <div className="card">
        <div className="notice-title">Статус ордера</div>
        <ol className="timeline">
          {order.events.length === 0 ? (
            <li className="timeline-item">
              <span className="timeline-dot" />
              <div>
                <div>{statusLabel(order.status)}</div>
                <div className="muted timeline-date">
                  {fmtDate(order.created_at)}
                </div>
              </div>
            </li>
          ) : (
            order.events.map((ev, i) => (
              <li
                key={`${ev.status}-${ev.created_at}-${i}`}
                className={`timeline-item ${
                  i === order.events.length - 1 ? 'timeline-item-current' : ''
                }`}
              >
                <span className="timeline-dot" />
                <div>
                  <div className="timeline-status">{statusLabel(ev.status)}</div>
                  {ev.message && <div className="muted">{ev.message}</div>}
                  <div className="muted timeline-date">{fmtDate(ev.created_at)}</div>
                </div>
              </li>
            ))
          )}
        </ol>
      </div>

      {DISPUTABLE.has(order.status) && (
        <button
          type="button"
          className="btn btn-danger"
          disabled={disputing}
          onClick={() => void openDispute()}
        >
          {disputing ? 'Отправляем…' : 'Открыть спор'}
        </button>
      )}

      {order.status === 'DISPUTED' && (
        <div className="card notice-card">
          <div className="notice-title">Спор открыт</div>
          <p className="notice-text">
            Мы рассматриваем ваш спор. Следите за статусом на этом экране.
          </p>
        </div>
      )}
    </div>
  )
}
