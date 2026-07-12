import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getReferralStats } from '../api';

export default function Referral() {
  const nav = useNavigate();
  const [stats, setStats] = useState<Awaited<ReturnType<typeof getReferralStats>> | null>(null);

  useEffect(() => {
    getReferralStats().then(setStats).catch(() => {});
  }, []);

  function copyLink() {
    if (stats) navigator.clipboard.writeText(stats.referral_link);
  }

  return (
    <div className="page">
      <header className="header">
        <button className="back" onClick={() => nav('/')}>←</button>
        <h1>Рефералы</h1>
      </header>
      {stats && (
        <>
          <div className="card">
            <p>Code: {stats.referral_code}</p>
            <button className="btn" onClick={copyLink}>Copy link</button>
            <p>Referred: {stats.referred_count}</p>
            <p>Total rewards: {stats.total_rewards.toFixed(4)} RUB</p>
          </div>
          <h3>Rewards</h3>
          {stats.rewards.map((r) => (
            <div key={r.order_id} className="card">
              {r.amount} RUB · {r.status}
            </div>
          ))}
        </>
      )}
    </div>
  );
}
