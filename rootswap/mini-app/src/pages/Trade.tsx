import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { badgeClass, createOrder, createQuote, Quote } from '../api';

const ROUTES = {
  BUY: [
    { label: 'RUB → USDT TRC20', from: 'RUB', to: 'USDT', network: 'TRC20' },
    { label: 'RUB → BTC', from: 'RUB', to: 'BTC', network: 'BTC' },
    { label: 'RUB → XMR', from: 'RUB', to: 'XMR', network: 'XMR' },
  ],
  SELL: [
    { label: 'USDT TRC20 → RUB', from: 'USDT', fromNetwork: 'TRC20', to: 'RUB' },
    { label: 'BTC → RUB', from: 'BTC', fromNetwork: 'BTC', to: 'RUB' },
    { label: 'XMR → RUB', from: 'XMR', fromNetwork: 'XMR', to: 'RUB' },
  ],
};

interface Props {
  mode: 'BUY' | 'SELL';
}

export default function Trade({ mode }: Props) {
  const nav = useNavigate();
  const [routeIdx, setRouteIdx] = useState(0);
  const [amount, setAmount] = useState('10000');
  const [paymentMethod, setPaymentMethod] = useState('SBP');
  const [bank, setBank] = useState('Sber');
  const [wallet, setWallet] = useState('');
  const [payoutAccount, setPayoutAccount] = useState('');
  const [quotes, setQuotes] = useState<{ best: Quote | null; all: Quote[] } | null>(null);
  const [selected, setSelected] = useState<Quote | null>(null);
  const [confirm, setConfirm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const route = ROUTES[mode][routeIdx];
  const walletOk = wallet.trim().length >= 11;
  const payoutOk = payoutAccount.trim().length >= 5;

  async function fetchQuotes() {
    setLoading(true);
    setError(null);
    try {
      const body: Record<string, unknown> = {
        direction: mode,
        amount_in: parseFloat(amount),
        payment_method: paymentMethod,
        bank_name: bank,
      };
      if (mode === 'BUY') {
        body.from_asset = route.from;
        body.to_asset = route.to;
        body.to_network = 'network' in route ? route.network : undefined;
      } else {
        body.from_asset = route.from;
        body.from_network = 'fromNetwork' in route ? route.fromNetwork : undefined;
        body.to_asset = route.to;
      }
      const res = await createQuote(body);
      if (!res.all.length) {
        setError('Нет доступных котировок. Попробуйте другую сумму.');
        setQuotes(null);
        return;
      }
      setQuotes({ best: res.best, all: res.all });
      setSelected(res.best);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function submitOrder() {
    if (!selected) return;
    if (mode === 'BUY' && !walletOk) {
      setError('Укажите адрес кошелька для получения криптовалюты');
      return;
    }
    if (mode === 'SELL' && !payoutOk) {
      setError('Укажите реквизиты для выплаты RUB');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const body: Record<string, unknown> = {
        quote_id: selected.id,
        idempotency_key: crypto.randomUUID(),
        payment_method: paymentMethod,
        bank_name: bank,
      };
      if (mode === 'BUY') body.wallet_address = wallet.trim();
      if (mode === 'SELL') {
        body.payout_details = {
          payment_method: paymentMethod,
          bank,
          account: payoutAccount.trim(),
        };
      }
      const order = await createOrder(body);
      nav(`/order/${order.id}`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page">
      <header className="header">
        <button className="back" onClick={() => nav('/')}>←</button>
        <h1>{mode === 'BUY' ? 'Купить' : 'Продать'}</h1>
      </header>

      <div className="demo-banner demo-inline">DEMO MODE — no real money</div>

      <label className="field">
        Направление
        <select value={routeIdx} onChange={(e) => setRouteIdx(Number(e.target.value))}>
          {ROUTES[mode].map((r, i) => (
            <option key={i} value={i}>{r.label}</option>
          ))}
        </select>
      </label>

      <label className="field">
        Сумма
        <input type="number" value={amount} onChange={(e) => setAmount(e.target.value)} />
      </label>

      <label className="field">
        Способ оплаты
        <select value={paymentMethod} onChange={(e) => setPaymentMethod(e.target.value)}>
          <option value="SBP">SBP</option>
          <option value="bank_transfer">Банковский перевод</option>
          <option value="card_transfer">Перевод на карту</option>
        </select>
      </label>

      <label className="field">
        Банк
        <select value={bank} onChange={(e) => setBank(e.target.value)}>
          {['Sber', 'Tinkoff', 'Alfa', 'Raiffeisen', 'AnyBank'].map((b) => (
            <option key={b} value={b}>{b}</option>
          ))}
        </select>
      </label>

      {mode === 'BUY' && (
        <label className="field">
          Адрес кошелька ({route.to} {'network' in route ? route.network : ''})
          <input
            value={wallet}
            onChange={(e) => setWallet(e.target.value)}
            placeholder="Wallet address"
            autoComplete="off"
            spellCheck={false}
          />
          {!walletOk && wallet.trim() !== '' && (
            <span className="field-error">Адрес слишком короткий</span>
          )}
        </label>
      )}

      {mode === 'SELL' && (
        <label className="field">
          {paymentMethod === 'SBP' ? 'Телефон СБП' : paymentMethod === 'card_transfer' ? 'Номер карты' : 'Счёт'}
          <input
            value={payoutAccount}
            onChange={(e) => setPayoutAccount(e.target.value)}
            placeholder={paymentMethod === 'SBP' ? '+79001234567' : 'Реквизиты выплаты'}
            autoComplete="off"
          />
        </label>
      )}

      <button className="btn primary" onClick={() => void fetchQuotes()} disabled={loading}>
        {loading ? 'Ищем…' : 'Получить котировку'}
      </button>

      {error && <div className="error">{error}</div>}

      {quotes && (
        <div className="quotes">
          <h2>Котировки</h2>
          {quotes.all.map((q) => (
            <div
              key={q.id}
              className={`quote-card ${selected?.id === q.id ? 'selected' : ''}`}
              onClick={() => setSelected(q)}
            >
              <div className="quote-header">
                <span>{q.partner_code}</span>
                <span className={badgeClass(q.quote_source_type)}>{q.quote_source_type}</span>
              </div>
              <div>Out: {q.amount_out.toFixed(8)} {q.to_asset}</div>
              <div>RootScore: {q.root_score.toFixed(2)}</div>
              <div>Fees: {q.total_fee.toFixed(2)}</div>
              {q.kyc_required && <span className="kyc-label">KYC may be required</span>}
            </div>
          ))}
          {selected && (
            <button
              className="btn"
              onClick={() => setConfirm(true)}
              disabled={mode === 'BUY' ? !walletOk : !payoutOk}
            >
              Подтвердить
            </button>
          )}
        </div>
      )}

      {confirm && selected && (
        <div className="modal">
          <h3>Подтверждение</h3>
          <p>Asset: {selected.to_asset} / {selected.to_network}</p>
          <p>Amount in: {selected.amount_in}</p>
          <p>Amount out: {selected.amount_out}</p>
          <p>Fee: {selected.total_fee}</p>
          <p>Source: {selected.quote_source_type}</p>
          {mode === 'BUY' && wallet && (
            <p>Wallet: {wallet.slice(0, 8)}...{wallet.slice(-6)}</p>
          )}
          {mode === 'SELL' && <p>Payout: {payoutAccount}</p>}
          <p className="notice">Partner requirements may vary. Fiat payments may be identifiable.</p>
          <p className="notice">Это DEMO-режим без реальных денег.</p>
          <button className="btn primary" onClick={() => void submitOrder()} disabled={loading}>
            {loading ? 'Создаём…' : 'Создать заявку'}
          </button>
          <button className="btn" onClick={() => setConfirm(false)}>Отмена</button>
        </div>
      )}
    </div>
  );
}
