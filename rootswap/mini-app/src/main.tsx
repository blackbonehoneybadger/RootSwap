import { StrictMode, useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { authDev, authTelegram, hasToken } from './api';
import {
  getInitData,
  getLanguageCode,
  getStartParam,
  initTelegramApp,
  isInsideTelegram,
  bindBackButton,
  hideBackButton,
  watchTelegramTheme,
} from './lib/telegram';
import { detectLocale, setLocale, t, type Locale } from './lib/i18n';
import { LocaleContext } from './lib/locale';
import Home from './pages/Home';
import Trade from './pages/Trade';
import OrderPage from './pages/Order';
import History from './pages/History';
import Referral from './pages/Referral';
import Profile from './pages/Profile';
import Legal from './pages/Legal';
import './styles.css';

function TelegramBackSync() {
  const nav = useNavigate();
  const loc = useLocation();
  useEffect(() => {
    if (loc.pathname === '/') {
      hideBackButton();
      return;
    }
    return bindBackButton(() => {
      if (window.history.length > 1) nav(-1);
      else nav('/');
    });
  }, [loc.pathname, nav]);
  return null;
}

function App() {
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [devMode, setDevMode] = useState(false);
  const [locale, setLocaleState] = useState<Locale>(() => detectLocale(getLanguageCode()));
  const allowDevAuth = import.meta.env.DEV && import.meta.env.VITE_ENABLE_DEV_AUTH !== 'false';

  const localeApi = useMemo(
    () => ({
      locale,
      setLocale: (l: Locale) => {
        setLocale(l);
        setLocaleState(l);
      },
      t: (key: Parameters<typeof t>[1]) => t(locale, key),
    }),
    [locale],
  );

  useEffect(() => {
    initTelegramApp();
    const stopThemeWatch = watchTelegramTheme();

    const boot = async () => {
      const initData = getInitData();
      const startParam = getStartParam();
      const referral = startParam?.startsWith('ref_') ? startParam.slice(4) : undefined;

      try {
        if (initData) {
          await authTelegram(initData, referral);
          setDevMode(false);
        } else if (allowDevAuth && !hasToken()) {
          await authDev();
          setDevMode(true);
        } else if (allowDevAuth && hasToken()) {
          setDevMode(true);
        } else if (!isInsideTelegram()) {
          setError(t(locale, 'authRequired'));
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : t(locale, 'authFailed'));
        if (allowDevAuth && !initData) {
          try {
            await authDev(900002);
            setDevMode(true);
            setError(null);
          } catch {
            /* keep */
          }
        }
      } finally {
        setReady(true);
      }
    };
    void boot();
    return () => stopThemeWatch();
  }, [allowDevAuth, locale]);

  if (!ready) return <div className="loading">{t(locale, 'loading')}</div>;

  return (
    <LocaleContext.Provider value={localeApi}>
      <BrowserRouter>
        <TelegramBackSync />
        {devMode && (
          <div className="demo-banner" role="status">
            {t(locale, 'demoNotice')}
          </div>
        )}
        {error && <div className="error">Auth: {error}</div>}
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/buy" element={<Trade mode="BUY" />} />
          <Route path="/sell" element={<Trade mode="SELL" />} />
          <Route path="/order/:id" element={<OrderPage />} />
          <Route path="/history" element={<History />} />
          <Route path="/referral" element={<Referral />} />
          <Route path="/profile" element={<Profile />} />
          <Route path="/legal/:doc?" element={<Legal />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </LocaleContext.Provider>
  );
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
