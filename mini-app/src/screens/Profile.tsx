import type { AuthUser } from '../lib/types'
import { useLocale } from '../lib/locale'

interface ProfileProps {
  user: AuthUser | null
}

export function Profile({ user }: ProfileProps) {
  const { t, locale, setLocale } = useLocale()

  return (
    <div className="screen">
      <h2 className="screen-title">{t('profile')}</h2>

      <div className="card">
        <div className="profile-row">
          <span className="muted">Telegram</span>
          <span className="profile-value">
            {user?.username ? `@${user.username}` : (user?.first_name ?? '—')}
          </span>
        </div>
        <div className="profile-row">
          <span className="muted">Telegram ID</span>
          <span className="profile-value">{user?.telegram_id ?? '—'}</span>
        </div>
        <div className="profile-row">
          <span className="muted">Referral</span>
          <span className="profile-value">{user?.referral_code ?? '—'}</span>
        </div>
      </div>

      <label className="field">
        {t('language')}
        <select
          value={locale}
          onChange={(e) => setLocale(e.target.value as 'ru' | 'en')}
        >
          <option value="ru">Русский</option>
          <option value="en">English</option>
        </select>
      </label>

      <div className="card notice-card">
        <div className="notice-title">{t('demoBanner')}</div>
        <p className="notice-text">{t('aggregator')}</p>
      </div>

      <div className="card security-card">
        <div className="notice-title">Security</div>
        <p className="notice-text">
          RootSwap never asks for seed phrases or private keys.
        </p>
      </div>
    </div>
  )
}
