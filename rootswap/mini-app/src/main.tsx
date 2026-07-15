import { StrictMode, useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { authDev, authTelegram, hasToken } from './api';
import Home from './pages/Home';
import Trade from './pages/Trade';
import OrderPage from './pages/Order';
import History from './pages/History';
import Referral from './pages/Referral';
import Profile from './pages/Profile';
import './styles.css';

declare global {
  interface Window {
    Telegram?: {
      WebApp?: {
        initData: string;
        initDataUnsafe?: { start_param?: string };
        ready: () => void;
        expand: () => void;
        themeParams?: Record<string, string>;
      };
    };
  }
}

function App() {
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [devMode, setDevMode] = useState(false);
  const allowDevAuth = import.meta.env.DEV && import.meta.env.VITE_ENABLE_DEV_AUTH !== 'false';

  useEffect(() => {
    const tg = window.Telegram?.WebApp;
    tg?.ready();
    tg?.expand();
    const initData = tg?.initData || '';
    const startParam = tg?.initDataUnsafe?.start_param;
    const referral = startParam?.startsWith('ref_') ? startParam.slice(4) : undefined;

    const boot = async () => {
      try {
        if (initData) {
          await authTelegram(initData, referral);
          setDevMode(false);
        } else if (allowDevAuth && !hasToken()) {
          await authDev();
          setDevMode(true);
        } else if (allowDevAuth && hasToken()) {
          setDevMode(true);
        } else if (!initData) {
          setError('Telegram auth required. Open inside Telegram Mini App.');
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Auth failed');
        if (allowDevAuth && !initData) {
          try {
            await authDev(900002);
            setDevMode(true);
            setError(null);
          } catch {
            /* keep error banner */
          }
        }
      } finally {
        setReady(true);
      }
    };
    void boot();
  }, [allowDevAuth]);

  if (!ready) return <div className="loading">Loading RootSwap...</div>;

  return (
    <BrowserRouter>
      {devMode && (
        <div className="demo-banner" role="status">
          DEMO MODE — browser auth · no real money
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
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
