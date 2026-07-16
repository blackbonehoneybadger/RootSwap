import { useCallback, useEffect, useRef, useState } from 'react'
import { cancelOrder, disputeOrder, getOrder } from '../lib/api'
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
import { useLocale } from '../lib/locale'

const POLL_INTERVAL_MS = 5000

/** Statuses in which the user may open a dispute (matches backend state machine). */
const DISPUTABLE = new Set([
  'PAYMENT_DETECTED',
  'PAYMENT_CONFIRMING',
  'PROCESSING',
  'PAYOUT_SENT',
  'COMPLETED',
])

const CANCELLABLE = new Set(['AWAITING_PAYMENT', 'QUOTE_CONFIRMED', 'CREATED'])

interface OrderScreenProps {
  orderId: string
  initialOrder?: Order | null
  onBack: () => void
}

function paymentField(
  pi: NonNullable<Order['payment_instructions']>,
  fullKey: 'recipient_name' | 'account_number' | 'card_number' | 'sbp_phone',
  maskedKey: 'masked_recipient_name' | 'masked_account' | 'masked_card' | 'masked_phone',
): string | null {
  const full = pi[fullKey]
  if (full) return full
  return pi[maskedKey]
}

export function OrderScreen({ orderId, initialOrder, onBack }: OrderScreenProps) {
  const { t, locale } = useLocale()
  const [order, setOrder] = useState<Order | null>(initialOrder ?? null)
  const [error, setError] = useState<string | null>(null)
  const [disputing, setDisputing] = useState(false)
  const [cancelling, setCancelling] = useState(false)
  const timerRef = useRef<number | null>(null)

  const refresh = useCallback(async () => {
    try {
      const o = await getOrder(orderId)
      setOrder(o)
      setError(null)
      return o
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t('loadOrderError'))
      return null
    }
  }, [orderId, t])

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
    const reason = window.prompt(t('describeDispute'))
    if (!reason || !reason.trim()) return
    setDisputing(true)
    try {
      const o = await disputeOrder(orderId, reason.trim())
      setOrder(o)
      setError(null)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t('disputeFailed'))
    } finally {
      setDisputing(false)
    }
  }

  const cancel = async () => {
    if (!window.confirm(t('cancelConfirm'))) return
    setCancelling(true)
    try {
      const o = await cancelOrder(orderId)
      setOrder(o)
      setError(null)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t('cancelFailed'))
    } finally {
      setCancelling(false)
    }
  }

  if (!order) {
    return (
      <div className="screen">
        <div className="wizard-header">
          <button type="button" className="back-btn" onClick={onBack}>
            ← {t('back')}
          </button>
          <span className="wizard-title">{t('orderWord')}</span>
        </div>
        {error ? (
          <div className="error-box">{error}</div>
        ) : (
          <div className="muted center-note">{t('orderLoading')}</div>
        )}
      </div>
    )
  }

  const pi = order.payment_instructions
  const isRefund = REFUND_STATUSES.has(order.status)
  const recipient = pi ? paymentField(pi, 'recipient_name', 'masked_recipient_name') : null
  const account = pi ? paymentField(pi, 'account_number', 'masked_account') : null
  const card = pi ? paymentField(pi, 'card_number', 'masked_card') : null
  const phone = pi ? paymentField(pi, 'sbp_phone', 'masked_phone') : null

  return (
    <div className="screen">
      <div className="wizard-header">
        <button type="button" className="back-btn" onClick={onBack}>
          ← {t('back')}
        </button>
        <span className="wizard-title">
          {t('orderWord')} {order.id.slice(0, 8)}…
        </span>
      </div>

      {error && <div className="error-box">{error}</div>}

      <div className="card">
        <div className="order-status-line">
          <span className={`chip chip-${statusTone(order.status)}`}>
            {statusLabel(locale, order.status)}
          </span>
          <SourceBadge source={order.quote_source_type} />
        </div>
        <div className="order-card-amounts">
          {fmtAmount(order.amount_in)}{' '}
          {assetWithNetwork(order.from_asset, order.from_network)} →{' '}
          {fmtAmount(order.amount_out)}{' '}
          {assetWithNetwork(order.to_asset, order.to_network)}
        </div>
        <div className="muted">
          {t('createdAtLabel')}: {fmtDate(order.created_at, locale)}
        </div>

        <div className="fees-grid fees-grid-order">
          <span className="muted">{t('rate')}</span>
          <span>{fmtAmount(order.exchange_rate)}</span>
          <span className="muted">{t('serviceFee')}</span>
          <span>{fmtAmount(order.service_fee)}</span>
          <span className="muted">{t('partnerFee')}</span>
          <span>{fmtAmount(order.partner_fee)}</span>
          <span className="muted">{t('networkFee')}</span>
          <span>{fmtAmount(order.network_fee)}</span>
          <span className="muted">{t('totalFee')}</span>
          <span>{fmtAmount(order.total_fee)}</span>
        </div>

        {order.wallet_address_masked && (
          <div className="profile-row">
            <span className="muted">{t('walletShort')}</span>
            <span className="mono-inline">{order.wallet_address_masked}</span>
          </div>
        )}
        {order.payout_details_masked && (
          <div className="profile-row">
            <span className="muted">{t('payoutShort')}</span>
            <span className="mono-inline">{order.payout_details_masked}</span>
          </div>
        )}
      </div>

      {isRefund && (
        <div className="card refund-card">
          <div className="notice-title">{t('refundTitle')}</div>
          <p className="notice-text">
            {order.status === 'REFUND_REQUESTED' && t('refundRequestedMsg')}
            {order.status === 'REFUND_PROCESSING' && t('refundProcessingMsg')}
            {order.status === 'REFUNDED' && t('refundDoneMsg')}
            {order.status === 'REFUND_FAILED' && t('refundFailedMsg')}
          </p>
        </div>
      )}

      {pi && (
        <div className="card payment-card">
          <div className="notice-title">{t('paymentInstructions')}</div>
          <Countdown expiresAt={pi.expires_at} prefix={t('payWithin')} />

          <div className="pay-rows">
            <div className="pay-row">
              <span className="muted">{t('method')}</span>
              <span>{pi.payment_method}</span>
            </div>
            <div className="pay-row">
              <span className="muted">{t('bank')}</span>
              <span>{pi.bank_name}</span>
            </div>
            {recipient && (
              <div className="pay-row pay-row-copy">
                <span className="muted">{t('recipient')}</span>
                <span>{recipient}</span>
                <CopyButton value={recipient} small />
              </div>
            )}
            {account && (
              <div className="pay-row pay-row-copy">
                <span className="muted">{t('accountWord')}</span>
                <span className="mono-inline">{account}</span>
                <CopyButton value={account} small />
              </div>
            )}
            {card && (
              <div className="pay-row pay-row-copy">
                <span className="muted">{t('cardWord')}</span>
                <span className="mono-inline">{card}</span>
                <CopyButton value={card} small />
              </div>
            )}
            {phone && (
              <div className="pay-row pay-row-copy">
                <span className="muted">{t('phoneWord')}</span>
                <span className="mono-inline">{phone}</span>
                <CopyButton value={phone} small />
              </div>
            )}
            <div className="pay-row pay-row-copy">
              <span className="muted">{t('amount')}</span>
              <span>
                {fmtAmount(pi.amount)} {pi.currency}
              </span>
              <CopyButton value={pi.amount} small />
            </div>
            {pi.payment_comment && (
              <div className="pay-row pay-row-copy">
                <span className="muted">{t('commentWord')}</span>
                <span className="mono-inline">{pi.payment_comment}</span>
                <CopyButton value={pi.payment_comment} small />
              </div>
            )}
          </div>
          <p className="muted pay-note">{t('payCommentNote')}</p>
        </div>
      )}

      {order.deposit_address && (
        <div className="card deposit-card">
          <div className="notice-title">
            {t('depositAddress')}
            {order.deposit_network ? ` (${order.deposit_network})` : ''}
          </div>
          <QrPlaceholder value={order.deposit_address} />
          <div className="mono-block">{order.deposit_address}</div>
          <CopyButton value={order.deposit_address} />
          <p className="muted pay-note">
            {t('sendOnlyNote', {
              asset: order.from_asset,
              network: order.deposit_network ?? order.from_network ?? '—',
            })}
          </p>
        </div>
      )}

      <div className="card">
        <div className="notice-title">{t('orderStatusTitle')}</div>
        <ol className="timeline">
          {order.events.length === 0 ? (
            <li className="timeline-item">
              <span className="timeline-dot" />
              <div>
                <div>{statusLabel(locale, order.status)}</div>
                <div className="muted timeline-date">
                  {fmtDate(order.created_at, locale)}
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
                  <div className="timeline-status">
                    {statusLabel(locale, ev.status)}
                  </div>
                  {ev.message && <div className="muted">{ev.message}</div>}
                  <div className="muted timeline-date">
                    {fmtDate(ev.created_at, locale)}
                  </div>
                </div>
              </li>
            ))
          )}
        </ol>
      </div>

      {CANCELLABLE.has(order.status) && (
        <button
          type="button"
          className="btn btn-secondary"
          disabled={cancelling}
          onClick={() => void cancel()}
        >
          {cancelling ? t('cancelling') : t('cancelOrderBtn')}
        </button>
      )}

      {DISPUTABLE.has(order.status) && (
        <button
          type="button"
          className="btn btn-danger"
          disabled={disputing}
          onClick={() => void openDispute()}
        >
          {disputing ? t('sending') : t('openDisputeBtn')}
        </button>
      )}

      {order.status === 'DISPUTED' && (
        <div className="card notice-card">
          <div className="notice-title">{t('disputeOpenTitle')}</div>
          <p className="notice-text">{t('disputeReviewing')}</p>
        </div>
      )}
    </div>
  )
}
