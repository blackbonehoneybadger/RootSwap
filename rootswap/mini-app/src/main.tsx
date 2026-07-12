import { StrictMode, useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { authTelegram } from './api';
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

  useEffect(() => {
    const tg = window.Telegram?.WebApp;
    tg?.ready();
    tg?.expand();
    const initData = tg?.initData || '';
    const startParam = tg?.initDataUnsafe?.start_param;
    const referral = startParam?.startsWith('ref_') ? startParam.slice(4) : undefined;

    if (initData) {
      authTelegram(initData, referral)
        .then(() => setReady(true))
        .catch((e) => {
          setError(e.message);
          setReady(true);
        });
    } else {
      setReady(true);
    }
  }, []);

  if (!ready) return <div className="loading">Loading RootSwap...</div>;
  if (error) return <div className="error">Auth: {error}. Dev mode without Telegram.</div>;

  return (
    <BrowserRouter>
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
