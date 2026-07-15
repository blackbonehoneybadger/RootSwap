import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  FINAL_STATUSES,
  createDispute,
  getOrder,
  Order,
  simulatePayment,
} from '../api';

function Countdown({ expiresAt }: { expiresAt: string }) {
  const [left, setLeft] = useState('');
  useEffect(() => {
    const tick = () => {
      const diff = new Date(expiresAt).getTime() - Date.now();
      if (diff <= 0) setLeft('Expired');
      else {
        const m = Math.floor(diff / 60000);
        const s = Math.floor((diff % 60000) / 1000);
        setLeft(`${m}:${s.toString().padStart(2, '0')}`);
      }
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [expiresAt]);
  return <span className="countdown">{left}</span>;
}

const TIMELINE = [
  'CREATED',
  'QUOTE_CONFIRMED',
  'AWAITING_PAYMENT',
  'PAYMENT_DETECTED',
  'PAYMENT_CONFIRMING',
  'PROCESSING',
  'PAYOUT_SENT',
  'COMPLETED',
];

export default function OrderPage() {
  const { id } = useParams<{ id: string }>();
  const nav = useNavigate();
  const [order, setOrder] = useState<Order | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    const load = async () => {
      try {
        const o = await getOrder(id);
        if (!cancelled) {
          setOrder(o);
          setError(null);
        }
        return o;
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Load failed');
        return null;
      }
    };
    void load();
    const interval = setInterval(() => {
      void (async () => {
        const o = await load();
        if (o && FINAL_STATUSES.has(o.status)) clearInterval(interval);
      })();
    }, 5000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [id]);

  async function dispute() {
    if (!id) return;
    setBusy(true);
    try {
      await createDispute(id, 'Payment issue reported by user');
      setOrder(await getOrder(id));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Dispute failed');
    } finally {
      setBusy(false);
    }
  }

  async function simulate() {
    if (!id) return;
    setBusy(true);
    try {
      setOrder(await simulatePayment(id));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Simulate failed');
    } finally {
      setBusy(false);
    }
  }

  function copy(text: string, label: string) {
    void navigator.clipboard.writeText(text).then(() => {
      setCopied(label);
      setTimeout(() => setCopied(null), 1500);
    });
  }

  if (error && !order) return <div className="error">{error}</div>;
  if (!order) return <div className="loading">Loading order...</div>;

  const pi = order.payment_instructions;
  const statusIdx = TIMELINE.indexOf(order.status);
  const phone = pi?.sbp_phone || pi?.masked_phone;
  const account = pi?.account_number || pi?.masked_account;
  const card = pi?.card_number || pi?.masked_card;
  const deposit = pi?.deposit_address || pi?.deposit_address_masked;
  const recipient = pi?.recipient_name;

  return (
    <div className="page">
      <header className="header">
        <button className="back" onClick={() => nav('/history')}>←</button>
        <h1>Заявка</h1>
      </header>

      {error && <div className="error">{error}</div>}
      {copied && <div className="toast">Скопировано: {copied}</div>}

      <div className="status-badge">{order.status}</div>
      <div className="timeline">
        {TIMELINE.map((s, i) => (
          <div
            key={s}
            className={`timeline-step ${
              order.status === s ? 'active' : statusIdx > i ? 'done' : ''
            }`}
          >
            {s}
          </div>
        ))}
      </div>

      <div className="card">
        <p>{order.from_asset} → {order.to_asset}</p>
        <p>In: {order.amount_in} · Out: {order.amount_out}</p>
        <p>Fee: {order.total_fee}</p>
        <p className="badge badge-mock">{order.quote_source_type}</p>
      </div>

      {pi && (
        <div className="card">
          <h3>Payment instructions</h3>
          <p>Expires: <Countdown expiresAt={pi.expires_at} /></p>
          <p>
            <strong>
              К оплате: {pi.amount} {pi.currency}
            </strong>{' '}
            <button type="button" onClick={() => copy(String(pi.amount), 'сумма')}>Copy</button>
          </p>
          <p>Method: {pi.payment_method} · Bank: {pi.bank_name}</p>
          {recipient && <p>Получатель: {recipient}</p>}
          {phone && (
            <p>
              SBP: {phone}{' '}
              <button type="button" onClick={() => copy(phone, 'телефон')}>Copy</button>
            </p>
          )}
          {account && (
            <p>
              Account: {account}{' '}
              <button type="button" onClick={() => copy(account, 'счёт')}>Copy</button>
            </p>
          )}
          {card && (
            <p>
              Card: {card}{' '}
              <button type="button" onClick={() => copy(card, 'карта')}>Copy</button>
            </p>
          )}
          {deposit && (
            <p>
              Deposit: {deposit}{' '}
              <button type="button" onClick={() => copy(deposit, 'депозит')}>Copy</button>
            </p>
          )}
          {pi.payment_comment && (
            <p>
              Comment: {pi.payment_comment}{' '}
              <button type="button" onClick={() => copy(pi.payment_comment!, 'комментарий')}>
                Copy
              </button>
            </p>
          )}
        </div>
      )}

      {order.status === 'AWAITING_PAYMENT' &&
        (order.quote_source_type === 'MOCK' || order.quote_source_type === 'SANDBOX') && (
          <button className="btn primary" disabled={busy} onClick={() => void simulate()}>
            {busy ? '…' : 'Я оплатил (DEMO)'}
          </button>
        )}

      {!FINAL_STATUSES.has(order.status) && order.status !== 'DISPUTED' && (
        <button className="btn danger" disabled={busy} onClick={() => void dispute()}>
          Открыть спор
        </button>
      )}
    </div>
  );
}
