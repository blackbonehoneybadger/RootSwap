import { useMemo, useState } from 'react'
import { createOrder, fetchQuotes, uuidv4 } from '../lib/api'
import {
  BANKS,
  PAYMENT_METHODS,
  bankLabel,
  paymentMethodLabel,
  routesFor,
} from '../lib/routes'
import type {
  Direction,
  Order,
  PaymentMethod,
  Quote,
  QuoteRequest,
} from '../lib/types'
import {
  assetWithNetwork,
  fmtAmount,
  quoteLabelText,
} from '../lib/format'
import { Countdown } from '../components/Countdown'
import { SourceBadge } from '../components/SourceBadge'
import { hapticError, hapticSuccess } from '../lib/telegram'

export interface WizardPrefill {
  direction: Direction
  asset: string
  network: string | null
  amountIn: string
}

interface WizardProps {
  initialDirection: Direction
  prefill?: WizardPrefill | null
  onClose: () => void
  onOrderCreated: (order: Order) => void
}

type Step = 'route' | 'details' | 'quotes' | 'confirm'

export function Wizard({
  initialDirection,
  prefill,
  onClose,
  onOrderCreated,
}: WizardProps) {
  const [direction, setDirection] = useState<Direction>(
    prefill?.direction ?? initialDirection,
  )
  const routes = routesFor(direction)
  const prefillRouteIdx = prefill
    ? Math.max(
        0,
        routesFor(prefill.direction).findIndex(
          (r) => r.asset === prefill.asset && r.network === prefill.network,
        ),
      )
    : 0

  const [step, setStep] = useState<Step>('route')
  const [routeIdx, setRouteIdx] = useState<number>(prefillRouteIdx)
  const [amount, setAmount] = useState<string>(prefill?.amountIn ?? '')
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>('SBP')
  const [bank, setBank] = useState<string>(BANKS[0] ?? 'Sber')
  const [walletAddress, setWalletAddress] = useState('')
  const [payoutAccount, setPayoutAccount] = useState('')

  const [quotes, setQuotes] = useState<Quote[]>([])
  const [selectedQuote, setSelectedQuote] = useState<Quote | null>(null)
  const [checkedAddress, setCheckedAddress] = useState(false)
  const [checkedDemo, setCheckedDemo] = useState(false)

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const route = routes[routeIdx] ?? routes[0]

  const amountValid = useMemo(() => {
    const v = amount.trim()
    return /^\d+(\.\d+)?$/.test(v) && parseFloat(v) > 0
  }, [amount])

  const walletValid = walletAddress.trim().length > 10
  const payoutValid = payoutAccount.trim().length > 5

  const detailsValid =
    amountValid && (direction === 'BUY' ? walletValid : payoutValid)

  if (!route) return null

  const cryptoLabel = assetWithNetwork(route.asset, route.network)

  const buildQuoteRequest = (): QuoteRequest => {
    if (direction === 'BUY') {
      return {
        direction: 'BUY',
        from_asset: 'RUB',
        from_network: null,
        to_asset: route.asset,
        to_network: route.network,
        amount_in: amount.trim(),
        payment_method: paymentMethod,
        bank,
      }
    }
    return {
      direction: 'SELL',
      from_asset: route.asset,
      from_network: route.network,
      to_asset: 'RUB',
      to_network: null,
      amount_in: amount.trim(),
      payment_method: paymentMethod,
      bank,
    }
  }

  const loadQuotes = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetchQuotes(buildQuoteRequest())
      setQuotes(res.quotes)
      setStep('quotes')
    } catch (e: unknown) {
      hapticError()
      setError(e instanceof Error ? e.message : 'Не удалось получить котировки')
    } finally {
      setLoading(false)
    }
  }

  const submitOrder = async () => {
    if (!selectedQuote) return
    setLoading(true)
    setError(null)
    try {
      const order = await createOrder({
        quote_id: selectedQuote.quote_id,
        idempotency_key: uuidv4(),
        wallet_address: direction === 'BUY' ? walletAddress.trim() : null,
        payout_details:
          direction === 'SELL'
            ? {
                payment_method: paymentMethod,
                bank,
                account: payoutAccount.trim(),
              }
            : null,
      })
      hapticSuccess()
      onOrderCreated(order)
    } catch (e: unknown) {
      hapticError()
      setError(e instanceof Error ? e.message : 'Не удалось создать ордер')
    } finally {
      setLoading(false)
    }
  }

  const goBack = () => {
    setError(null)
    if (step === 'route') onClose()
    else if (step === 'details') setStep('route')
    else if (step === 'quotes') setStep('details')
    else {
      setSelectedQuote(null)
      setCheckedAddress(false)
      setCheckedDemo(false)
      setStep('quotes')
    }
  }

  const stepTitle: Record<Step, string> = {
    route: direction === 'BUY' ? 'Покупка криптовалюты' : 'Продажа криптовалюты',
    details: 'Детали обмена',
    quotes: 'Выбор предложения',
    confirm: 'Подтверждение',
  }

  return (
    <div className="screen wizard">
      <div className="wizard-header">
        <button type="button" className="back-btn" onClick={goBack}>
          ← Назад
        </button>
        <span className="wizard-title">{stepTitle[step]}</span>
      </div>

      <div className="demo-banner demo-banner-inline" role="status">
        DEMO MODE — no real money
      </div>

      {error && <div className="error-box">{error}</div>}

      {step === 'route' && (
        <div className="wizard-step">
          <div className="seg-control">
            <button
              type="button"
              className={`seg-item ${direction === 'BUY' ? 'seg-item-active' : ''}`}
              onClick={() => {
                setDirection('BUY')
                setRouteIdx(0)
              }}
            >
              Купить
            </button>
            <button
              type="button"
              className={`seg-item ${direction === 'SELL' ? 'seg-item-active' : ''}`}
              onClick={() => {
                setDirection('SELL')
                setRouteIdx(0)
              }}
            >
              Продать
            </button>
          </div>

          <div className="muted field-label">
            {direction === 'BUY'
              ? 'Вы платите RUB и получаете:'
              : 'Вы отправляете криптовалюту и получаете RUB:'}
          </div>

          <div className="route-list">
            {routes.map((r, i) => (
              <button
                key={`${r.asset}-${r.network ?? ''}`}
                type="button"
                className={`card route-item ${i === routeIdx ? 'route-item-active' : ''}`}
                onClick={() => setRouteIdx(i)}
              >
                <span className="route-label">{r.label}</span>
                <span className="muted">
                  {direction === 'BUY' ? `RUB → ${r.asset}` : `${r.asset} → RUB`}
                </span>
              </button>
            ))}
          </div>

          <button
            type="button"
            className="btn btn-primary"
            onClick={() => setStep('details')}
          >
            Далее
          </button>
        </div>
      )}

      {step === 'details' && (
        <div className="wizard-step">
          <label className="field">
            <span className="field-label">
              {direction === 'BUY'
                ? 'Сумма в RUB'
                : `Сумма в ${route.asset}`}
            </span>
            <input
              className="input"
              inputMode="decimal"
              placeholder={direction === 'BUY' ? 'например, 10000' : 'например, 100'}
              value={amount}
              onChange={(e) => setAmount(e.target.value.replace(',', '.'))}
            />
            {!amountValid && amount.trim() !== '' && (
              <span className="field-error">Введите положительное число</span>
            )}
          </label>

          <label className="field">
            <span className="field-label">
              {direction === 'BUY' ? 'Способ оплаты' : 'Способ получения RUB'}
            </span>
            <select
              className="input"
              value={paymentMethod}
              onChange={(e) => setPaymentMethod(e.target.value as PaymentMethod)}
            >
              {PAYMENT_METHODS.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span className="field-label">Банк</span>
            <select
              className="input"
              value={bank}
              onChange={(e) => setBank(e.target.value)}
            >
              {BANKS.map((b) => (
                <option key={b} value={b}>
                  {bankLabel(b)}
                </option>
              ))}
            </select>
          </label>

          {direction === 'BUY' ? (
            <label className="field">
              <span className="field-label">
                Адрес кошелька для получения {cryptoLabel}
              </span>
              <input
                className="input input-mono"
                placeholder={`Адрес в сети ${route.network ?? route.asset}`}
                value={walletAddress}
                onChange={(e) => setWalletAddress(e.target.value)}
                autoComplete="off"
                spellCheck={false}
              />
              {!walletValid && walletAddress.trim() !== '' && (
                <span className="field-error">
                  Адрес выглядит слишком коротким (мин. 11 символов)
                </span>
              )}
              <span className="field-hint muted">
                Внимательно проверьте адрес и сеть ({route.network ?? route.asset}).
              </span>
            </label>
          ) : (
            <label className="field">
              <span className="field-label">
                {paymentMethod === 'SBP'
                  ? 'Телефон для СБП'
                  : paymentMethod === 'card_transfer'
                    ? 'Номер карты'
                    : 'Номер счёта'}
              </span>
              <input
                className="input input-mono"
                placeholder={
                  paymentMethod === 'SBP' ? '+7 900 000-00-00' : 'Реквизиты для выплаты RUB'
                }
                value={payoutAccount}
                onChange={(e) => setPayoutAccount(e.target.value)}
                autoComplete="off"
              />
              {!payoutValid && payoutAccount.trim() !== '' && (
                <span className="field-error">Реквизиты слишком короткие</span>
              )}
            </label>
          )}

          <button
            type="button"
            className="btn btn-primary"
            disabled={!detailsValid || loading}
            onClick={() => void loadQuotes()}
          >
            {loading ? 'Ищем предложения…' : 'Получить котировки'}
          </button>
        </div>
      )}

      {step === 'quotes' && (
        <div className="wizard-step">
          {quotes.length === 0 ? (
            <div className="muted center-note">
              Нет доступных предложений. Попробуйте изменить сумму.
            </div>
          ) : (
            <ul className="quote-list">
              {quotes.map((q) => (
                <li key={q.quote_id} className="card quote-card">
                  <div className="quote-top">
                    <span className="quote-partner">{q.partner_name}</span>
                    <SourceBadge source={q.quote_source_type} />
                  </div>

                  <div className="quote-badges">
                    {q.labels.map((l) => (
                      <span key={l} className={`badge badge-label badge-label-${l}`}>
                        {quoteLabelText(l)}
                      </span>
                    ))}
                    {q.kyc_required && (
                      <span className="badge badge-kyc">KYC</span>
                    )}
                  </div>

                  <div className="quote-amount">
                    Вы получите:{' '}
                    <strong>
                      {fmtAmount(q.amount_out)}{' '}
                      {direction === 'BUY' ? route.asset : 'RUB'}
                    </strong>
                  </div>
                  <div className="muted quote-rate">
                    Курс: {fmtAmount(q.exchange_rate)} · ~
                    {q.estimated_time_minutes} мин · RootScore {q.root_score}
                  </div>

                  <details className="fees-details">
                    <summary>
                      Комиссии: {fmtAmount(q.total_fee)} всего
                    </summary>
                    <div className="fees-grid">
                      <span className="muted">Сервис</span>
                      <span>{fmtAmount(q.service_fee)}</span>
                      <span className="muted">Партнёр</span>
                      <span>{fmtAmount(q.partner_fee)}</span>
                      <span className="muted">Сеть</span>
                      <span>{fmtAmount(q.network_fee)}</span>
                      <span className="muted">Итого</span>
                      <span>{fmtAmount(q.total_fee)}</span>
                    </div>
                  </details>

                  <div className="quote-bottom">
                    <Countdown expiresAt={q.expires_at} prefix="Действует:" />
                    <button
                      type="button"
                      className="btn btn-primary btn-small"
                      onClick={() => {
                        setSelectedQuote(q)
                        setCheckedAddress(false)
                        setCheckedDemo(false)
                        setStep('confirm')
                      }}
                    >
                      Выбрать
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
          <button
            type="button"
            className="btn btn-secondary"
            disabled={loading}
            onClick={() => void loadQuotes()}
          >
            {loading ? 'Обновляем…' : 'Обновить котировки'}
          </button>
        </div>
      )}

      {step === 'confirm' && selectedQuote && (
        <div className="wizard-step">
          <div className="card confirm-card">
            <div className="confirm-row">
              <span className="muted">Направление</span>
              <span>{direction === 'BUY' ? 'Покупка' : 'Продажа'}</span>
            </div>
            <div className="confirm-row">
              <span className="muted">Актив</span>
              <span>{route.asset}</span>
            </div>
            <div className="confirm-row">
              <span className="muted">Сеть</span>
              <span>{route.network ?? '—'}</span>
            </div>
            <div className="confirm-row">
              <span className="muted">Вы отдаёте</span>
              <span>
                {fmtAmount(selectedQuote.amount_in)}{' '}
                {direction === 'BUY' ? 'RUB' : route.asset}
              </span>
            </div>
            <div className="confirm-row">
              <span className="muted">Вы получите</span>
              <span>
                {fmtAmount(selectedQuote.amount_out)}{' '}
                {direction === 'BUY' ? route.asset : 'RUB'}
              </span>
            </div>
            <div className="confirm-row">
              <span className="muted">Партнёр</span>
              <span>{selectedQuote.partner_name}</span>
            </div>
            <div className="confirm-row">
              <span className="muted">Комиссия сервиса</span>
              <span>{fmtAmount(selectedQuote.service_fee)}</span>
            </div>
            <div className="confirm-row">
              <span className="muted">Комиссия партнёра</span>
              <span>{fmtAmount(selectedQuote.partner_fee)}</span>
            </div>
            <div className="confirm-row">
              <span className="muted">Комиссия сети</span>
              <span>{fmtAmount(selectedQuote.network_fee)}</span>
            </div>
            <div className="confirm-row">
              <span className="muted">Комиссия итого</span>
              <span>{fmtAmount(selectedQuote.total_fee)}</span>
            </div>
            <div className="confirm-row">
              <span className="muted">Источник котировки</span>
              <SourceBadge source={selectedQuote.quote_source_type} />
            </div>
            {selectedQuote.kyc_required && (
              <div className="confirm-row">
                <span className="muted">KYC</span>
                <span>Партнёр может запросить верификацию</span>
              </div>
            )}
          </div>

          {direction === 'BUY' ? (
            <div className="card">
              <div className="notice-title">Адрес получения ({cryptoLabel})</div>
              <div className="mono-block">{walletAddress.trim()}</div>
            </div>
          ) : (
            <div className="card">
              <div className="notice-title">Реквизиты для выплаты RUB</div>
              <div className="profile-row">
                <span className="muted">Способ</span>
                <span>{paymentMethodLabel(paymentMethod)}</span>
              </div>
              <div className="profile-row">
                <span className="muted">Банк</span>
                <span>{bankLabel(bank)}</span>
              </div>
              <div className="mono-block">{payoutAccount.trim()}</div>
            </div>
          )}

          <Countdown
            expiresAt={selectedQuote.expires_at}
            prefix="Котировка действует:"
          />

          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={checkedAddress}
              onChange={(e) => setCheckedAddress(e.target.checked)}
            />
            <span>Я проверил адрес и сеть</span>
          </label>
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={checkedDemo}
              onChange={(e) => setCheckedDemo(e.target.checked)}
            />
            <span>Я понимаю, что это DEMO-режим без реальных денег</span>
          </label>

          <button
            type="button"
            className="btn btn-primary"
            disabled={!checkedAddress || !checkedDemo || loading}
            onClick={() => void submitOrder()}
          >
            {loading ? 'Создаём ордер…' : 'Подтвердить обмен'}
          </button>
        </div>
      )}
    </div>
  )
}
