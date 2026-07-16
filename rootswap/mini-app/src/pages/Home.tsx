import { Link } from 'react-router-dom';
import { useLocale } from '../lib/locale';

export default function Home() {
  const { t, locale, setLocale } = useLocale();

  return (
    <div className="page">
      <header className="header">
        <h1>{t('brand')}</h1>
        <p className="subtitle">{t('subtitle')}</p>
      </header>
      <div className="notice">{t('demoNotice')}</div>
      <div className="notice subtle">{t('aggregatorNotice')}</div>
      <nav className="menu">
        <Link to="/buy" className="menu-item primary">{t('buy')}</Link>
        <Link to="/sell" className="menu-item primary">{t('sell')}</Link>
        <Link to="/history" className="menu-item">{t('history')}</Link>
        <Link to="/referral" className="menu-item">{t('referral')}</Link>
        <Link to="/profile" className="menu-item">{t('profile')}</Link>
        <Link to="/legal" className="menu-item">{t('legal')}</Link>
        <a href="https://t.me/RootSwapSupport" className="menu-item" target="_blank" rel="noreferrer">
          {t('support')}
        </a>
      </nav>
      <label className="field lang-switch">
        {t('language')}
        <select
          value={locale}
          onChange={(e) => setLocale(e.target.value as 'ru' | 'en')}
        >
          <option value="ru">Русский</option>
          <option value="en">English</option>
        </select>
      </label>
    </div>
  );
}
