import { useNavigate, useParams } from 'react-router-dom';
import { useLocale } from '../lib/locale';

const DOCS: Record<string, { titleKey: 'terms' | 'privacy' | 'risk'; body: { ru: string; en: string } }> = {
  terms: {
    titleKey: 'terms',
    body: {
      ru: 'RootSwap — агрегатор предложений партнёров (placeholder). Сервис не является лицензированной биржей. Условия исполнения зависят от выбранного партнёра. Реальные деньги в этой версии отключены.',
      en: 'RootSwap aggregates partner offers (placeholder). Not a licensed exchange. Execution terms depend on the selected partner. Real money is disabled in this build.',
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
      ru: 'Криптовалютные операции несут риск потери средств. Отправка в неправильную сеть необратима. KYC/AML может потребоваться партнёром. AML/юрисдикции — placeholder.',
      en: 'Crypto operations involve risk of loss. Wrong-network transfers are irreversible. Partners may require KYC/AML. Jurisdictions — placeholder.',
    },
  },
};

export default function Legal() {
  const nav = useNavigate();
  const { doc } = useParams();
  const { t, locale } = useLocale();
  const entry = doc ? DOCS[doc] : null;

  return (
    <div className="page">
      <header className="header">
        <button type="button" className="back" onClick={() => nav(doc ? '/legal' : '/')}>
          ←
        </button>
        <h1>{entry ? t(entry.titleKey) : t('legal')}</h1>
      </header>
      {!entry && (
        <nav className="menu">
          <button type="button" className="menu-item" onClick={() => nav('/legal/terms')}>
            {t('terms')}
          </button>
          <button type="button" className="menu-item" onClick={() => nav('/legal/privacy')}>
            {t('privacy')}
          </button>
          <button type="button" className="menu-item" onClick={() => nav('/legal/risk')}>
            {t('risk')}
          </button>
        </nav>
      )}
      {entry && (
        <div className="card">
          <p>{entry.body[locale]}</p>
          <p className="muted" style={{ marginTop: 12 }}>
            {t('aggregatorNotice')}
          </p>
        </div>
      )}
    </div>
  );
}
