import type { Direction } from '../lib/types'
import { openTelegramLink } from '../lib/telegram'
import { useLocale } from '../lib/locale'

const SUPPORT_URL = 'https://t.me/RootSwapSupport'

interface HomeProps {
  onStart: (direction: Direction) => void
  onOpenLegal?: (doc?: string) => void
}

export function Home({ onStart, onOpenLegal }: HomeProps) {
  const { t } = useLocale()

  return (
    <div className="screen">
      <header className="home-header">
        <h1 className="home-title">{t('brand')}</h1>
        <p className="home-subtitle">{t('aggregator')}</p>
      </header>

      <div className="home-actions">
        <button
          type="button"
          className="btn btn-primary btn-big"
          onClick={() => onStart('BUY')}
        >
          {t('buy')}
          <span className="btn-sub">RUB → USDT · BTC · XMR</span>
        </button>
        <button
          type="button"
          className="btn btn-secondary btn-big"
          onClick={() => onStart('SELL')}
        >
          {t('sell')}
          <span className="btn-sub">USDT · BTC · XMR → RUB</span>
        </button>
      </div>

      <div className="card notice-card">
        <div className="notice-title">{t('demoBanner')}</div>
        <p className="notice-text">{t('aggregator')}</p>
      </div>

      <div className="home-links">
        <button
          type="button"
          className="link-btn"
          onClick={() => onOpenLegal?.()}
        >
          {t('legal')}
        </button>
        <button
          type="button"
          className="link-btn"
          onClick={() => openTelegramLink(SUPPORT_URL)}
        >
          {t('support')}
        </button>
      </div>
    </div>
  )
}
