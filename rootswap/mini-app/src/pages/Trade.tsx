import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  badgeClass,
  createOrder,
  createQuote,
  fetchAssets,
  Quote,
  type AssetInfo,
} from '../api';
import { hapticError, hapticSuccess } from '../lib/telegram';
import { useLocale } from '../lib/locale';

interface Props {
  mode: 'BUY' | 'SELL';
}

interface RouteOpt {
  label: string;
  from: string;
  to: string;
  network?: string;
  fromNetwork?: string;
  status: string;
  enabled: boolean;
}

export default function Trade({ mode }: Props) {
  const nav = useNavigate();
  const { t } = useLocale();
  const [assets, setAssets] = useState<AssetInfo[]>([]);
  const [routeIdx, setRouteIdx] = useState(0);
  const [amount, setAmount] = useState('10000');
  const [paymentMethod, setPaymentMethod] = useState('SBP');
  const [bank, setBank] = useState('Sber');
  const [wallet, setWallet] = useState('');
  const [payoutAccount, setPayoutAccount] = useState('');
  const [memo, setMemo] = useState('');
  const [quotes, setQuotes] = useState<{
    best: Quote | null;
    fastest: Quote | null;
    lowest_fee: Quote | null;
    all: Quote[];
  } | null>(null);
  const [selected, setSelected] = useState<Quote | null>(null);
  const [confirm, setConfirm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [idempotencyKey, setIdempotencyKey] = useState(() => crypto.randomUUID());

  useEffect(() => {
    void fetchAssets()
      .then((data) => setAssets(data.assets))
      .catch(() => setAssets([]));
  }, []);

  const routes: RouteOpt[] = useMemo(() => {
    if (mode === 'BUY') {
      const cryptos = assets.filter(
        (a) => a.symbol !== 'RUB' && (a.status === 'sandbox' || a.status === 'planned' || a.status === 'supported'),
      );
      if (!cryptos.length) {
        return [
          { label: 'RUB → USDT TRC20', from: 'RUB', to: 'USDT', network: 'TRC20', status: 'sandbox', enabled: true },
          { label: 'RUB → BTC', from: 'RUB', to: 'BTC', network: 'BTC', status: 'sandbox', enabled: true },
          { label: 'RUB → XMR (sandbox)', from: 'RUB', to: 'XMR', network: 'XMR', status: 'sandbox', enabled: true },
        ];
      }
      return cryptos.map((a) => ({
        label: `RUB → ${a.symbol}${a.network ? ` ${a.network}` : ''}${a.status === 'planned' ? ` · ${t('comingSoon')}` : a.status === 'sandbox' ? ` · ${t('sandbox')}` : ''}`,
        from: 'RUB',
        to: a.symbol,
        network: a.network || undefined,
        status: a.status,
        enabled: a.enabled && a.status !== 'planned',
      }));
    }
    return [
      { label: 'USDT TRC20 → RUB', from: 'USDT', fromNetwork: 'TRC20', to: 'RUB', status: 'sandbox', enabled: true },
      { label: 'BTC → RUB', from: 'BTC', fromNetwork: 'BTC', to: 'RUB', status: 'sandbox', enabled: true },
      { label: 'XMR → RUB (sandbox)', from: 'XMR', fromNetwork: 'XMR', to: 'RUB', status: 'sandbox', enabled: true },
    ];
  }, [assets, mode, t]);

  const route = routes[Math.min(routeIdx, routes.length - 1)] || routes[0];
  const assetMeta = assets.find(
    (a) => a.symbol === (mode === 'BUY' ? route?.to : route?.from) && a.network === (mode === 'BUY' ? route?.network : route?.fromNetwork),
  );
  const walletOk = wallet.trim().length >= 11;
  const payoutOk = payoutAccount.trim().length >= 5;
  const routeEnabled = route?.enabled !== false;

  function quoteBadge(q: Quote): string | null {
    if (!quotes) return null;
    if (quotes.best?.id === q.id) return t('bestOverall');
    if (quotes.fastest?.id === q.id) return t('fastest');
    if (quotes.lowest_fee?.id === q.id) return t('lowestFee');
    return null;
  }

  async function fetchQuotes() {
    if (!routeEnabled) {
      setError(t('comingSoon'));
      return;
    }
    setLoading(true);
    setError(null);
    setQuotes(null);
    setSelected(null);
    setConfirm(false);
    setIdempotencyKey(crypto.randomUUID());
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
        body.to_network = route.network;
      } else {
        body.from_asset = route.from;
        body.from_network = route.fromNetwork;
        body.to_asset = route.to;
      }
      const res = await createQuote(body);
      if (!res.all.length) {
        setError(t('noQuotes'));
        return;
      }
      setQuotes(res);
      setSelected(res.best);
      hapticSuccess();
    } catch (e) {
      setError((e as Error).message);
      hapticError();
    } finally {
      setLoading(false);
    }
  }

  async function submitOrder() {
    if (!selected || submitting) return;
    if (mode === 'BUY' && !walletOk) {
      setError(t('wallet'));
      return;
    }
    if (mode === 'SELL' && !payoutOk) {
      setError('payout');
      return;
    }
    if (selected.expires_at && Date.parse(selected.expires_at) < Date.now()) {
      setError(t('quoteExpired'));
      setConfirm(false);
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const body: Record<string, unknown> = {
        quote_id: selected.id,
        idempotency_key: idempotencyKey,
        payment_method: paymentMethod,
        bank_name: bank,
      };
      if (mode === 'BUY') {
        body.wallet_address = wallet.trim();
        if (memo.trim() && assetMeta?.memo_required) {
          body.payout_details = { memo: memo.trim() };
        }
      }
      if (mode === 'SELL') {
        body.payout_details = {
          payment_method: paymentMethod,
          bank,
          account: payoutAccount.trim(),
        };
      }
      const order = await createOrder(body);
      hapticSuccess();
      nav(`/order/${order.id}`);
    } catch (e) {
      setError((e as Error).message);
      hapticError();
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="page">
      <header className="header">
        <button type="button" className="back" onClick={() => nav('/')}>←</button>
        <h1>{mode === 'BUY' ? t('buy') : t('sell')}</h1>
      </header>

      <div className="demo-banner demo-inline">{t('demoNotice')}</div>

      <label className="field">
        {mode === 'BUY' ? t('buy') : t('sell')}
        <select
          value={routeIdx}
          onChange={(e) => {
            setRouteIdx(Number(e.target.value));
            setQuotes(null);
            setSelected(null);
          }}
        >
          {routes.map((r, i) => (
            <option key={i} value={i} disabled={!r.enabled}>
              {r.label}
            </option>
          ))}
        </select>
      </label>

      {route && !routeEnabled && (
        <div className="notice">{route.to}/{route.network} — {t('comingSoon')}</div>
      )}

      <label className="field">
        {t('amount')}
        <input
          type="number"
          inputMode="decimal"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
        />
      </label>

      <label className="field">
        {t('paymentMethod')}
        <select value={paymentMethod} onChange={(e) => setPaymentMethod(e.target.value)}>
          <option value="SBP">SBP</option>
          <option value="bank_transfer">Bank transfer</option>
          <option value="card_transfer">Card</option>
        </select>
      </label>

      <label className="field">
        {t('bank')}
        <select value={bank} onChange={(e) => setBank(e.target.value)}>
          {['Sber', 'Tinkoff', 'Alfa', 'Raiffeisen', 'AnyBank'].map((b) => (
            <option key={b} value={b}>{b}</option>
          ))}
        </select>
      </label>

      {mode === 'BUY' && (
        <>
          <label className="field">
            {t('wallet')} ({route?.to} {route?.network || ''})
            <input
              value={wallet}
              onChange={(e) => setWallet(e.target.value)}
              placeholder={assetMeta?.address_hint || 'Wallet address'}
              autoComplete="off"
              spellCheck={false}
            />
          </label>
          {assetMeta?.memo_required && (
            <label className="field">
              Memo / Tag
              <input value={memo} onChange={(e) => setMemo(e.target.value)} placeholder="Required" />
            </label>
          )}
        </>
      )}

      {mode === 'SELL' && (
        <label className="field">
          Payout
          <input
            value={payoutAccount}
            onChange={(e) => setPayoutAccount(e.target.value)}
            placeholder="+79001234567"
            autoComplete="off"
          />
        </label>
      )}

      <button
        type="button"
        className="btn primary"
        onClick={() => void fetchQuotes()}
        disabled={loading || !routeEnabled}
      >
        {loading ? t('searching') : t('getQuotes')}
      </button>

      {error && <div className="error">{error}</div>}

      {quotes && (
        <div className="quotes">
          <h2>{t('quotes')}</h2>
          {quotes.all.map((q) => {
            const why = quoteBadge(q);
            return (
              <div
                key={q.id}
                className={`quote-card ${selected?.id === q.id ? 'selected' : ''}`}
                onClick={() => setSelected(q)}
                onKeyDown={() => setSelected(q)}
                role="button"
                tabIndex={0}
              >
                <div className="quote-header">
                  <span>{q.partner_code}</span>
                  <span className={badgeClass(q.quote_source_type)}>{q.quote_source_type}</span>
                </div>
                {why && <div className="quote-why">{why}</div>}
                <div>Out: {q.amount_out.toFixed(8)} {q.to_asset}</div>
                <div>{t('rootScore')}: {q.root_score.toFixed(2)}</div>
                <div>Fees: {q.total_fee.toFixed(2)}</div>
                <div className="muted">{t('expires')}: {new Date(q.expires_at).toLocaleTimeString()}</div>
                {q.kyc_required && <span className="kyc-label">KYC may be required</span>}
              </div>
            );
          })}
          {selected && (
            <button
              type="button"
              className="btn"
              onClick={() => setConfirm(true)}
              disabled={mode === 'BUY' ? !walletOk : !payoutOk}
            >
              {t('confirm')}
            </button>
          )}
        </div>
      )}

      {confirm && selected && (
        <div className="modal">
          <h3>{t('confirm')}</h3>
          <p>{selected.to_asset} / {selected.to_network}</p>
          <p>In: {selected.amount_in} · Out: {selected.amount_out}</p>
          <p>Fee: {selected.total_fee} · {selected.quote_source_type}</p>
          {mode === 'BUY' && (
            <>
              <p>{t('network')}: {selected.to_network}</p>
              <p>{t('wallet')}: {wallet.slice(0, 10)}…{wallet.slice(-6)}</p>
            </>
          )}
          <p className="notice">{t('wrongNetworkWarn')}</p>
          <p className="notice">{t('aggregatorNotice')}</p>
          {error && <div className="error">{error}</div>}
          <button type="button" className="btn primary" onClick={() => void submitOrder()} disabled={submitting}>
            {submitting ? t('creating') : t('createOrder')}
          </button>
          <button type="button" className="btn" onClick={() => setConfirm(false)} disabled={submitting}>
            {t('cancel')}
          </button>
        </div>
      )}
    </div>
  );
}
