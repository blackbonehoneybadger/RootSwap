import { useState } from 'react'
import { useLocale } from '../lib/locale'
import type { MsgKey } from '../lib/i18n'

const DOCS: Record<
  string,
  { titleKey: MsgKey; body: { ru: string; en: string } }
> = {
  terms: {
    titleKey: 'terms',
    body: {
      ru: 'RootSwap — агрегатор предложений партнёров (placeholder, не финальный юридический документ). Сервис не является лицензированной биржей. Условия исполнения зависят от выбранного партнёра. Sandbox не двигает реальные средства.',
      en: 'RootSwap aggregates partner offers (placeholder, not a final legal document). Not a licensed exchange. Execution terms depend on the selected partner. Sandbox does not move real funds.',
    },
  },
  privacy: {
    titleKey: 'privacy',
    body: {
      ru: 'Мы обрабатываем Telegram user id, котировки и ордера. Платёжные реквизиты шифруются. Seed-фразы и приватные ключи никогда не запрашиваются. Полная политика — placeholder.',
      en: 'We process Telegram user id, quotes and orders. Payment details are encrypted. Seed phrases and private keys are never requested. Full policy — placeholder.',
    },
  },
  risk: {
    titleKey: 'risk',
    body: {
      ru: 'Криптовалютные операции несут риск потери средств. Неверная сеть необратима. RootSwap не обещает анонимность. KYC может требоваться партнёром. Planned-монеты недоступны.',
      en: 'Crypto operations involve risk of loss. Wrong-network transfers are irreversible. RootSwap does not promise anonymity. Partners may require KYC. Planned assets are unavailable.',
    },
  },
  partners: {
    titleKey: 'partners',
    body: {
      ru: 'Обмен может исполняться партнёром. Комиссии и KYC зависят от партнёра и показываются до подтверждения. Live BestChange и другие провайдеры не подключены без официального доступа.',
      en: 'Exchange may be executed by a partner. Fees and KYC depend on the partner and are shown before confirmation. Live BestChange and other providers are not connected without official access.',
    },
  },
  aml: {
    titleKey: 'aml',
    body: {
      ru: 'AML/KYC notice (placeholder). RootSwap не обходит требования партнёров, платёжных систем или Telegram. Юрисдикции — уточняются отдельно.',
      en: 'AML/KYC notice (placeholder). RootSwap does not bypass partner, payment-system, or Telegram requirements. Jurisdictions to be confirmed separately.',
    },
  },
}

interface LegalProps {
  doc?: string
  onBack: () => void
}

export function Legal({ doc: initialDoc, onBack }: LegalProps) {
  const { t, locale } = useLocale()
  const [doc, setDoc] = useState<string | undefined>(initialDoc)
  const entry = doc ? DOCS[doc] : null

  return (
    <div className="screen">
      <header className="screen-header">
        <button
          type="button"
          className="btn-text"
          onClick={() => {
            if (entry) setDoc(undefined)
            else onBack()
          }}
        >
          ← {t('back')}
        </button>
        <h1>{entry ? t(entry.titleKey) : t('legal')}</h1>
      </header>
      {!entry && (
        <nav className="stack">
          {Object.entries(DOCS).map(([key, item]) => (
            <button
              key={key}
              type="button"
              className="card card-button"
              onClick={() => setDoc(key)}
            >
              {t(item.titleKey)}
            </button>
          ))}
        </nav>
      )}
      {entry && (
        <div className="card">
          <p>{entry.body[locale]}</p>
          <p className="muted" style={{ marginTop: 12 }}>
            {t('aggregator')}
          </p>
        </div>
      )}
    </div>
  )
}
