import { useEffect, useState } from 'react'
import { getReferralStats } from '../lib/api'
import type { ReferralStats } from '../lib/types'
import { CopyButton } from '../components/CopyButton'
import { fmtAmount, fmtDate } from '../lib/format'

const BOT_USERNAME: string = import.meta.env.VITE_BOT_USERNAME || 'RootSwapBot'

const REWARD_STATUS_LABELS: Record<string, string> = {
  pending: 'Ожидает',
  PENDING: 'Ожидает',
  confirmed: 'Подтверждена',
  CONFIRMED: 'Подтверждена',
  paid: 'Выплачена',
  PAID: 'Выплачена',
  cancelled: 'Отменена',
  CANCELLED: 'Отменена',
}

export function Referral() {
  const [stats, setStats] = useState<ReferralStats | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    getReferralStats()
      .then((s) => {
        if (!cancelled) {
          setStats(s)
          setError(null)
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Ошибка загрузки')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (loading) {
    return (
      <div className="screen">
        <h2 className="screen-title">Рефералы</h2>
        <div className="muted center-note">Загрузка…</div>
      </div>
    )
  }

  if (error || !stats) {
    return (
      <div className="screen">
        <h2 className="screen-title">Рефералы</h2>
        <div className="error-box">Не удалось загрузить статистику. {error}</div>
      </div>
    )
  }

  const link = `https://t.me/${BOT_USERNAME}?start=ref_${stats.referral_code}`

  return (
    <div className="screen">
      <h2 className="screen-title">Рефералы</h2>

      <div className="card">
        <div className="notice-title">Ваша ссылка</div>
        <div className="mono-block referral-link">{link}</div>
        <CopyButton value={link} />
      </div>

      <div className="stat-grid">
        <div className="card stat-card">
          <div className="stat-value">{stats.referred_count}</div>
          <div className="muted">приглашено</div>
        </div>
        <div className="card stat-card">
          <div className="stat-value">{stats.active_referred_count}</div>
          <div className="muted">активных</div>
        </div>
      </div>

      <div className="card">
        <div className="notice-title">Всего наград</div>
        {stats.total_rewards.length === 0 ? (
          <div className="muted">Пока нет наград</div>
        ) : (
          stats.total_rewards.map((r) => (
            <div className="profile-row" key={r.currency}>
              <span className="muted">{r.currency}</span>
              <span className="profile-value">{fmtAmount(r.amount)}</span>
            </div>
          ))
        )}
      </div>

      <div className="card">
        <div className="notice-title">Начисления</div>
        {stats.rewards.length === 0 ? (
          <div className="muted">Список пуст</div>
        ) : (
          <ul className="reward-list">
            {stats.rewards.map((r, i) => (
              <li className="reward-item" key={`${r.order_id}-${i}`}>
                <div className="reward-main">
                  <span className="reward-amount">
                    +{fmtAmount(r.reward_amount)} {r.reward_currency}
                  </span>
                  <span className={`chip chip-reward-${r.status.toLowerCase()}`}>
                    {REWARD_STATUS_LABELS[r.status] ?? r.status}
                  </span>
                </div>
                <div className="muted reward-meta">
                  Ордер {r.order_id.slice(0, 8)}… · {fmtDate(r.created_at)}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
