import type { AuthUser } from '../lib/types'

interface ProfileProps {
  user: AuthUser | null
}

export function Profile({ user }: ProfileProps) {
  return (
    <div className="screen">
      <h2 className="screen-title">Профиль</h2>

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
          <span className="muted">Реферальный код</span>
          <span className="profile-value">{user?.referral_code ?? '—'}</span>
        </div>
      </div>

      <div className="card notice-card">
        <div className="notice-title">Конфиденциальность</div>
        <p className="notice-text">
          RootSwap — privacy-focused агрегатор. Мы стремимся хранить минимум
          данных и работаем по принципу non-custodial where possible: где это
          возможно, средства не задерживаются на нашей стороне. Обратите
          внимание: требования партнёров могут отличаться
          (partner requirements may vary), а фиатные платежи могут быть идентифицируемы
          банками и платёжными системами (fiat payments may be identifiable).
        </p>
      </div>

      <div className="card security-card">
        <div className="notice-title">Безопасность</div>
        <p className="notice-text">
          RootSwap никогда не запрашивает seed-фразы или приватные ключи.
          Никогда не сообщайте их никому — ни в чатах, ни в «поддержке».
        </p>
      </div>

      <div className="demo-banner demo-banner-inline" role="status">
        DEMO MODE — no real money
      </div>
    </div>
  )
}
