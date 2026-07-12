import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { createDispute, getOrder, Order } from '../api';

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

export default function OrderPage() {
  const { id } = useParams<{ id: string }>();
  const nav = useNavigate();
  const [order, setOrder] = useState<Order | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    getOrder(id).then(setOrder).catch((e) => setError(e.message));
    const interval = setInterval(() => getOrder(id).then(setOrder).catch(() => {}), 5000);
    return () => clearInterval(interval);
  }, [id]);

  async function dispute() {
    if (!id) return;
    await createDispute(id, 'Payment issue reported by user');
    getOrder(id).then(setOrder);
  }

  function copy(text: string) {
    navigator.clipboard.writeText(text);
  }

  if (error) return <div className="error">{error}</div>;
  if (!order) return <div className="loading">Loading order...</div>;

  const pi = order.payment_instructions;

  return (
    <div className="page">
      <header className="header">
        <button className="back" onClick={() => nav('/history')}>←</button>
        <h1>Заявка</h1>
      </header>

      <div className="status-badge">{order.status}</div>
      <div className="timeline">
        {['CREATED', 'AWAITING_PAYMENT', 'PAYMENT_DETECTED', 'PROCESSING', 'COMPLETED'].map((s) => (
          <div key={s} className={`timeline-step ${order.status === s ? 'active' : ''}`}>{s}</div>
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
          <p>Method: {pi.payment_method} · Bank: {pi.bank_name}</p>
          {pi.masked_phone && <p>SBP: {pi.masked_phone} <button onClick={() => copy(pi.masked_phone!)}>Copy</button></p>}
          {pi.masked_account && <p>Account: {pi.masked_account}</p>}
          {pi.masked_card && <p>Card: {pi.masked_card}</p>}
          {pi.deposit_address_masked && (
            <p>Deposit: {pi.deposit_address_masked} <button onClick={() => copy(pi.deposit_address_masked!)}>Copy</button></p>
          )}
          {pi.payment_comment && <p>Comment: {pi.payment_comment}</p>}
        </div>
      )}

      {!['COMPLETED', 'CANCELLED', 'EXPIRED'].includes(order.status) && (
        <button className="btn danger" onClick={dispute}>Открыть спор</button>
      )}
    </div>
  );
}
