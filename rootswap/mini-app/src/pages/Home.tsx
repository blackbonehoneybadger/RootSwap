import { Link } from 'react-router-dom';

export default function Home() {
  return (
    <div className="page">
      <header className="header">
        <h1>RootSwap</h1>
        <p className="subtitle">Privacy-focused · Non-custodial where possible</p>
      </header>
      <div className="notice">
        Mock/Sandbox only. Real money is disabled. Partner requirements may vary.
      </div>
      <nav className="menu">
        <Link to="/buy" className="menu-item primary">Купить крипто</Link>
        <Link to="/sell" className="menu-item primary">Продать крипто</Link>
        <Link to="/history" className="menu-item">История</Link>
        <Link to="/referral" className="menu-item">Рефералы</Link>
        <Link to="/profile" className="menu-item">Профиль</Link>
        <a href="https://t.me/RootSwapSupport" className="menu-item" target="_blank" rel="noreferrer">Поддержка</a>
      </nav>
    </div>
  );
}
