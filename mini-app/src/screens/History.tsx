import { useEffect, useState } from 'react'
import { listOrders } from '../lib/api'
import type { Order } from '../lib/types'
import {
  assetWithNetwork,
  fmtAmount,
  fmtDate,
  statusLabel,
  statusTone,
} from '../lib/format'
import { SourceBadge } from '../components/SourceBadge'
import { useLocale } from '../lib/locale'

interface HistoryProps {
  refreshKey: number
  onOpenOrder: (orderId: string) => void
  onRepeat: (order: Order) => void
}

export function History({ refreshKey, onOpenOrder, onRepeat }: HistoryProps) {
  const { t, locale } = useLocale()
  const [orders, setOrders] = useState<Order[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    listOrders()
      .then((r) => {
        if (!cancelled) {
          setOrders(r.orders)
          setError(null)
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : t('loadError'))
      })
    return () => {
      cancelled = true
    }
  }, [refreshKey, t])

  if (error) {
    return (
      <div className="screen">
        <h2 className="screen-title">{t('history')}</h2>
        <div className="error-box">{t('historyLoadFailed')} {error}</div>
      </div>
    )
  }

  if (orders === null) {
    return (
      <div className="screen">
        <h2 className="screen-title">{t('history')}</h2>
        <div className="muted center-note">{t('loading')}</div>
      </div>
    )
  }

  return (
    <div className="screen">
      <h2 className="screen-title">{t('history')}</h2>
      {orders.length === 0 ? (
        <div className="muted center-note">{t('noExchangesYet')}</div>
      ) : (
        <ul className="order-list">
          {orders.map((o) => (
            <li key={o.id} className="card order-card">
              <button
                type="button"
                className="order-card-main"
                onClick={() => onOpenOrder(o.id)}
              >
                <div className="order-card-top">
                  <span className="order-dir">
                    {o.direction === 'BUY' ? t('purchase') : t('sale')}
                  </span>
                  <span className={`chip chip-${statusTone(o.status)}`}>
                    {statusLabel(locale, o.status)}
                  </span>
                </div>
                <div className="order-card-amounts">
                  {fmtAmount(o.amount_in)}{' '}
                  {assetWithNetwork(o.from_asset, o.from_network)} →{' '}
                  {fmtAmount(o.amount_out)}{' '}
                  {assetWithNetwork(o.to_asset, o.to_network)}
                </div>
                <div className="order-card-meta muted">
                  {fmtDate(o.created_at, locale)}{' '}
                  <SourceBadge source={o.quote_source_type} />
                </div>
              </button>
              <div className="order-card-actions">
                <button
                  type="button"
                  className="btn btn-secondary btn-small"
                  onClick={() => onRepeat(o)}
                >
                  {t('repeat')}
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
