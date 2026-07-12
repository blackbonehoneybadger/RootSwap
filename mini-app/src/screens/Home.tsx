import type { Direction } from '../lib/types'
import { openTelegramLink } from '../lib/telegram'

const SUPPORT_URL = 'https://t.me/RootSwapSupport'

interface HomeProps {
  onStart: (direction: Direction) => void
}

export function Home({ onStart }: HomeProps) {
  return (
    <div className="screen">
      <div className="demo-banner" role="status">
        DEMO MODE — no real money · демо-режим, без реальных денег
      </div>

      <header className="home-header">
        <h1 className="home-title">RootSwap</h1>
        <p className="home-subtitle">
          Агрегатор обменных сервисов · privacy-focused, non-custodial where
          possible
        </p>
      </header>

      <div className="home-actions">
        <button
          type="button"
          className="btn btn-primary btn-big"
          onClick={() => onStart('BUY')}
        >
          Купить
          <span className="btn-sub">RUB → USDT · BTC · XMR</span>
        </button>
        <button
          type="button"
          className="btn btn-secondary btn-big"
          onClick={() => onStart('SELL')}
        >
          Продать
          <span className="btn-sub">USDT · BTC · XMR → RUB</span>
        </button>
      </div>

      <div className="card notice-card">
        <div className="notice-title">Конфиденциальность</div>
        <p className="notice-text">
          RootSwap — privacy-focused сервис: мы запрашиваем минимум данных и
          работаем в режиме non-custodial where possible. Условия партнёров
          могут отличаться (partner requirements may vary), а фиатные платежи
          могут быть идентифицируемы (fiat payments may be identifiable).
        </p>
      </div>

      <div className="home-links">
        <button
          type="button"
          className="link-btn"
          onClick={() => openTelegramLink(SUPPORT_URL)}
        >
          Поддержка
        </button>
      </div>
    </div>
  )
}
