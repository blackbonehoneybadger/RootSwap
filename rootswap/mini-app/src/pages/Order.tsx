import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  FINAL_STATUSES,
  createDispute,
  getOrder,
  Order,
  simulatePayment,
} from '../api';
import { useLocale } from '../lib/locale';

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

function statusTone(status: string): string {
  if (status === 'COMPLETED') return 'ok';
  if (['FAILED', 'CANCELLED', 'EXPIRED', 'REFUND_FAILED'].includes(status)) return 'err';
  if (['AWAITING_PAYMENT', 'DISPUTED', 'REFUND_PENDING', 'EXPIRED'].includes(status)) return 'warn';
  return '';
}

function statusCopy(status: string, locale: 'ru' | 'en'): string {
  const map: Record<string, { ru: string; en: string }> = {
    CREATED: { ru: 'Заявка создана', en: 'Order created' },
    QUOTE_CONFIRMED: { ru: 'Котировка подтверждена', en: 'Quote confirmed' },
    AWAITING_PAYMENT: { ru: 'Ожидаем оплату', en: 'Awaiting payment' },
    PAYMENT_DETECTED: { ru: 'Платёж обнаружен', en: 'Payment detected' },
    PAYMENT_CONFIRMING: { ru: 'Подтверждение платежа', en: 'Confirming payment' },
    PROCESSING: { ru: 'Обработка', en: 'Processing' },
    PAYOUT_SENT: { ru: 'Выплата отправлена', en: 'Payout sent' },
    COMPLETED: { ru: 'Завершено', en: 'Completed' },
    FAILED: { ru: 'Ошибка', en: 'Failed' },
    CANCELLED: { ru: 'Отменено', en: 'Cancelled' },
    EXPIRED: { ru: 'Истекло', en: 'Expired' },
    DISPUTED: { ru: 'Спор', en: 'Disputed' },
    REFUND_PENDING: { ru: 'Возврат в обработке', en: 'Refund pending' },
    REFUNDED: { ru: 'Возвращено', en: 'Refunded' },
  };
  return map[status]?.[locale] || status;
}

export default function OrderPage() {
  const { id } = useParams<{ id: string }>();
  const nav = useNavigate();
  const { locale, t } = useLocale();
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
  if (!order) return <div className="loading">{t('loading')}</div>;

  const pi = order.payment_instructions;
  const statusIdx = TIMELINE.indexOf(order.status);
  const phone = pi?.sbp_phone || pi?.masked_phone;
  const account = pi?.account_number || pi?.masked_account;
  const card = pi?.card_number || pi?.masked_card;
  const deposit = pi?.deposit_address || pi?.deposit_address_masked;
  const recipient = pi?.recipient_name;
  const paymentExpired = pi?.expires_at ? Date.parse(pi.expires_at) < Date.now() : false;

  return (
    <div className="page">
      <header className="header">
        <button type="button" className="back" onClick={() => nav('/history')}>
          ←
        </button>
        <h1>{locale === 'ru' ? 'Заявка' : 'Order'}</h1>
      </header>

      {error && <div className="error">{error}</div>}
      {copied && <div className="toast">{locale === 'ru' ? 'Скопировано' : 'Copied'}: {copied}</div>}

      <div className={`status-badge ${statusTone(order.status)}`}>{order.status}</div>
      <p className="status-copy">{statusCopy(order.status, locale)}</p>

      {order.status === 'EXPIRED' || paymentExpired ? (
        <div className="notice">{locale === 'ru' ? 'Срок оплаты истёк' : 'Payment window expired'}</div>
      ) : null}

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
        <p>
          {order.from_asset} → {order.to_asset}
        </p>
        <p>
          In: {order.amount_in} · Out: {order.amount_out}
        </p>
        <p>Fee: {order.total_fee}</p>
        <p className="badge badge-mock">{order.quote_source_type}</p>
      </div>

      {pi && (
        <div className="card">
          <h3>{locale === 'ru' ? 'Инструкции по оплате' : 'Payment instructions'}</h3>
          <p>
            Expires: <Countdown expiresAt={pi.expires_at} />
          </p>
          <p>
            <strong>
              {locale === 'ru' ? 'К оплате' : 'Pay'}: {pi.amount} {pi.currency}
            </strong>{' '}
            <button type="button" onClick={() => copy(String(pi.amount), 'amount')}>
              Copy
            </button>
          </p>
          <p>
            Method: {pi.payment_method} · Bank: {pi.bank_name}
          </p>
          {recipient && <p>{locale === 'ru' ? 'Получатель' : 'Recipient'}: {recipient}</p>}
          {phone && (
            <p>
              SBP: {phone}{' '}
              <button type="button" onClick={() => copy(phone, 'phone')}>
                Copy
              </button>
            </p>
          )}
          {account && (
            <p>
              Account: {account}{' '}
              <button type="button" onClick={() => copy(account, 'account')}>
                Copy
              </button>
            </p>
          )}
          {card && (
            <p>
              Card: {card}{' '}
              <button type="button" onClick={() => copy(card, 'card')}>
                Copy
              </button>
            </p>
          )}
          {deposit && (
            <p>
              Deposit: {deposit}{' '}
              <button type="button" onClick={() => copy(deposit, 'deposit')}>
                Copy
              </button>
            </p>
          )}
          {pi.payment_comment && (
            <p>
              Comment: {pi.payment_comment}{' '}
              <button type="button" onClick={() => copy(pi.payment_comment!, 'comment')}>
                Copy
              </button>
            </p>
          )}
        </div>
      )}

      {!pi && order.status === 'AWAITING_PAYMENT' && (
        <div className="empty">{locale === 'ru' ? 'Инструкции ещё не готовы' : 'Instructions not ready'}</div>
      )}

      {order.status === 'AWAITING_PAYMENT' &&
        (order.quote_source_type === 'MOCK' || order.quote_source_type === 'SANDBOX') && (
          <button type="button" className="btn primary" onClick={() => void simulate()} disabled={busy}>
            {locale === 'ru' ? 'Я оплатил (DEMO)' : 'I paid (DEMO)'}
          </button>
        )}

      {!FINAL_STATUSES.has(order.status) && (
        <button type="button" className="btn danger" onClick={() => void dispute()} disabled={busy}>
          {locale === 'ru' ? 'Открыть спор' : 'Open dispute'}
        </button>
      )}
    </div>
  );
}
