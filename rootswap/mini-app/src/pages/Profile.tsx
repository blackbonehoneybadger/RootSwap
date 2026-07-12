import { useNavigate } from 'react-router-dom';

export default function Profile() {
  const nav = useNavigate();

  return (
    <div className="page">
      <header className="header">
        <button className="back" onClick={() => nav('/')}>←</button>
        <h1>Профиль</h1>
      </header>
      <div className="card">
        <h3>Privacy notice</h3>
        <p>RootSwap is privacy-focused and non-custodial where possible. Partner requirements may vary.</p>
        <p>Fiat payments may be identifiable depending on partner and payment method.</p>
      </div>
      <div className="card">
        <h3>Security notice</h3>
        <p>RootSwap never asks for seed phrases or private keys.</p>
        <p>Do not share your wallet credentials with anyone claiming to be RootSwap support.</p>
      </div>
      <div className="notice">
        Mock/Sandbox mode. Real money is disabled in this version.
      </div>
    </div>
  );
}
