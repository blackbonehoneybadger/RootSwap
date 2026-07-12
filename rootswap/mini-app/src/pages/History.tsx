import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { getOrders, Order } from '../api';

export default function History() {
  const [orders, setOrders] = useState<Order[]>([]);
  const nav = useNavigate();

  useEffect(() => {
    getOrders().then(setOrders).catch(() => setOrders([]));
  }, []);

  return (
    <div className="page">
      <header className="header">
        <button className="back" onClick={() => nav('/')}>←</button>
        <h1>История</h1>
      </header>
      {orders.length === 0 && <p className="empty">No orders yet</p>}
      {orders.map((o) => (
        <div key={o.id} className="card order-row" onClick={() => nav(`/order/${o.id}`)}>
          <div>{o.from_asset} → {o.to_asset}</div>
          <div className="status-badge small">{o.status}</div>
          <div>{o.amount_in} · {new Date(o.created_at).toLocaleDateString()}</div>
          <Link to={o.direction === 'BUY' ? '/buy' : '/sell'} onClick={(e) => e.stopPropagation()} className="repeat">Repeat</Link>
        </div>
      ))}
    </div>
  );
}
