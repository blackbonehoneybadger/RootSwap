import { useMemo, useRef, useState } from 'react'
import { createOrder, fetchQuotes, uuidv4 } from '../lib/api'
import {
  BANKS,
  PAYMENT_METHODS,
  bankLabel,
  isPositiveDecimalString,
  paymentMethodLabel,
  routesFor,
} from '../lib/routes'
import { useLocale } from '../lib/locale'
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
  const { t, locale } = useLocale()
  const [direction, setDirection] = useState<Direction>(
    prefill?.direction ?? initialDirection,
  )
  const routes = routesFor(direction)
  const idempotencyKeyRef = useRef(uuidv4())
  const submittingRef = useRef(false)
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

  const amountValid = useMemo(() => isPositiveDecimalString(amount), [amount])

  const walletValid = walletAddress.trim().length > 10
  const payoutValid = payoutAccount.trim().length > 5
  const routeEnabled = route?.enabled !== false

  const detailsValid =
    amountValid &&
    routeEnabled &&
    (direction === 'BUY' ? walletValid : payoutValid)

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
    if (!routeEnabled) {
      setError(t('comingSoon'))
      return
    }
    if (selectedQuote?.expires_at && Date.parse(selectedQuote.expires_at) < Date.now()) {
      setError(t('quoteExpired'))
    }
    setLoading(true)
    setError(null)
    idempotencyKeyRef.current = uuidv4()
    try {
      const res = await fetchQuotes(buildQuoteRequest())
      setQuotes(res.quotes)
      setStep('quotes')
    } catch (e: unknown) {
      hapticError()
      setError(e instanceof Error ? e.message : t('failedQuotes'))
    } finally {
      setLoading(false)
    }
  }

  const submitOrder = async () => {
    if (!selectedQuote || submittingRef.current || loading) return
    if (selectedQuote.expires_at && Date.parse(selectedQuote.expires_at) < Date.now()) {
      setError(t('quoteExpired'))
      return
    }
    submittingRef.current = true
    setLoading(true)
    setError(null)
    try {
      const order = await createOrder({
        quote_id: selectedQuote.quote_id,
        idempotency_key: idempotencyKeyRef.current,
        wallet_address: direction === 'BUY' ? walletAddress.trim() : null,
        payout_details:
          direction === 'SELL'
            ? {
                payment_method: paymentMethod,
                bank,
                account: payoutAccount.trim(),
              }
            : null,
        payment_method: direction === 'BUY' ? paymentMethod : null,
        bank: direction === 'BUY' ? bank : null,
      })
      hapticSuccess()
      onOrderCreated(order)
    } catch (e: unknown) {
      hapticError()
      setError(e instanceof Error ? e.message : t('failedOrder'))
    } finally {
      submittingRef.current = false
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
    route: direction === 'BUY' ? t('wizardBuyTitle') : t('wizardSellTitle'),
    details: t('wizardDetailsTitle'),
    quotes: t('wizardQuotesTitle'),
    confirm: t('wizardConfirmTitle'),
  }

  return (
    <div className="screen wizard">
      <div className="wizard-header">
        <button type="button" className="back-btn" onClick={goBack}>
          ← {t('back')}
        </button>
        <span className="wizard-title">{stepTitle[step]}</span>
      </div>

      <div className="demo-banner demo-banner-inline" role="status">
        {t('demoModeInline')}
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
              {t('buyShort')}
            </button>
            <button
              type="button"
              className={`seg-item ${direction === 'SELL' ? 'seg-item-active' : ''}`}
              onClick={() => {
                setDirection('SELL')
                setRouteIdx(0)
              }}
            >
              {t('sellShort')}
            </button>
          </div>

          <div className="muted field-label">
            {direction === 'BUY' ? t('payRubGet') : t('sendCryptoGetRub')}
          </div>

          <div className="route-list">
            {routes.map((r, i) => (
              <button
                key={`${r.asset}-${r.network ?? ''}`}
                type="button"
                className={`card route-item ${i === routeIdx ? 'route-item-active' : ''}`}
                disabled={!r.enabled}
                onClick={() => r.enabled && setRouteIdx(i)}
              >
                <span className="route-label">
                  {r.label}
                  {r.status === 'planned' ? ` · ${t('comingSoon')}` : ''}
                  {r.status === 'sandbox' ? ` · ${t('sandbox')}` : ''}
                </span>
                <span className="muted">
                  {direction === 'BUY' ? `RUB → ${r.asset}` : `${r.asset} → RUB`}
                </span>
              </button>
            ))}
          </div>

          <button
            type="button"
            className="btn btn-primary"
            disabled={!routeEnabled}
            onClick={() => setStep('details')}
          >
            {t('next')}
          </button>
        </div>
      )}

      {step === 'details' && (
        <div className="wizard-step">
          <label className="field">
            <span className="field-label">
              {direction === 'BUY'
                ? t('amountInRub')
                : t('amountInAsset', { asset: route.asset })}
            </span>
            <input
              className="input"
              inputMode="decimal"
              placeholder={direction === 'BUY' ? t('egAmountBuy') : t('egAmountSell')}
              value={amount}
              onChange={(e) => setAmount(e.target.value.replace(',', '.'))}
            />
            {!amountValid && amount.trim() !== '' && (
              <span className="field-error">{t('enterPositive')}</span>
            )}
          </label>

          <label className="field">
            <span className="field-label">
              {direction === 'BUY' ? t('paymentMethod') : t('payoutMethod')}
            </span>
            <select
              className="input"
              value={paymentMethod}
              onChange={(e) => setPaymentMethod(e.target.value as PaymentMethod)}
            >
              {PAYMENT_METHODS.map((m) => (
                <option key={m.value} value={m.value}>
                  {paymentMethodLabel(locale, m.value)}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span className="field-label">{t('bank')}</span>
            <select
              className="input"
              value={bank}
              onChange={(e) => setBank(e.target.value)}
            >
              {BANKS.map((b) => (
                <option key={b} value={b}>
                  {bankLabel(locale, b)}
                </option>
              ))}
            </select>
          </label>

          {direction === 'BUY' ? (
            <label className="field">
              <span className="field-label">
                {t('walletForAsset', { asset: cryptoLabel })}
              </span>
              <input
                className="input input-mono"
                placeholder={t('addressInNetwork', {
                  network: route.network ?? route.asset,
                })}
                value={walletAddress}
                onChange={(e) => setWalletAddress(e.target.value)}
                autoComplete="off"
                spellCheck={false}
              />
              {!walletValid && walletAddress.trim() !== '' && (
                <span className="field-error">{t('addressTooShort')}</span>
              )}
              <span className="field-hint muted">
                {t('checkAddressNetwork', { network: route.network ?? route.asset })}
              </span>
            </label>
          ) : (
            <label className="field">
              <span className="field-label">
                {paymentMethod === 'SBP'
                  ? t('phoneForSbp')
                  : paymentMethod === 'card_transfer'
                    ? t('cardNumber')
                    : t('accountNumber')}
              </span>
              <input
                className="input input-mono"
                placeholder={
                  paymentMethod === 'SBP' ? '+7 900 000-00-00' : t('payoutPlaceholder')
                }
                value={payoutAccount}
                onChange={(e) => setPayoutAccount(e.target.value)}
                autoComplete="off"
              />
              {!payoutValid && payoutAccount.trim() !== '' && (
                <span className="field-error">{t('detailsTooShort')}</span>
              )}
            </label>
          )}

          <button
            type="button"
            className="btn btn-primary"
            disabled={!detailsValid || loading}
            onClick={() => void loadQuotes()}
          >
            {loading ? t('searchingOffers') : t('getQuotes')}
          </button>
        </div>
      )}

      {step === 'quotes' && (
        <div className="wizard-step">
          {quotes.length === 0 ? (
            <div className="muted center-note">{t('noOffers')}</div>
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
                    {t('youReceiveColon')}{' '}
                    <strong>
                      {fmtAmount(q.amount_out)}{' '}
                      {direction === 'BUY' ? route.asset : 'RUB'}
                    </strong>
                  </div>
                  <div className="muted quote-rate">
                    {t('rate')}: {fmtAmount(q.exchange_rate)} · ~
                    {q.estimated_time_minutes} {t('minutesShort')} · {t('rootScore')}{' '}
                    {q.root_score}
                  </div>

                  <details className="fees-details">
                    <summary>
                      {t('feesSummary', { total: fmtAmount(q.total_fee) })}
                    </summary>
                    <div className="fees-grid">
                      <span className="muted">{t('feeService')}</span>
                      <span>{fmtAmount(q.service_fee)}</span>
                      <span className="muted">{t('feePartner')}</span>
                      <span>{fmtAmount(q.partner_fee)}</span>
                      <span className="muted">{t('feeNetwork')}</span>
                      <span>{fmtAmount(q.network_fee)}</span>
                      <span className="muted">{t('feeTotal')}</span>
                      <span>{fmtAmount(q.total_fee)}</span>
                    </div>
                  </details>

                  <div className="quote-bottom">
                    <Countdown expiresAt={q.expires_at} prefix={t('validFor')} />
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
                      {t('choose')}
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
            {loading ? t('updating') : t('refreshQuotes')}
          </button>
        </div>
      )}

      {step === 'confirm' && selectedQuote && (
        <div className="wizard-step">
          <div className="card confirm-card">
            <div className="confirm-row">
              <span className="muted">{t('directionLabel')}</span>
              <span>{direction === 'BUY' ? t('purchase') : t('sale')}</span>
            </div>
            <div className="confirm-row">
              <span className="muted">{t('asset')}</span>
              <span>{route.asset}</span>
            </div>
            <div className="confirm-row">
              <span className="muted">{t('network')}</span>
              <span>{route.network ?? '—'}</span>
            </div>
            <div className="confirm-row">
              <span className="muted">{t('youGive')}</span>
              <span>
                {fmtAmount(selectedQuote.amount_in)}{' '}
                {direction === 'BUY' ? 'RUB' : route.asset}
              </span>
            </div>
            <div className="confirm-row">
              <span className="muted">{t('youReceive')}</span>
              <span>
                {fmtAmount(selectedQuote.amount_out)}{' '}
                {direction === 'BUY' ? route.asset : 'RUB'}
              </span>
            </div>
            <div className="confirm-row">
              <span className="muted">{t('partner')}</span>
              <span>{selectedQuote.partner_name}</span>
            </div>
            <div className="confirm-row">
              <span className="muted">{t('serviceFee')}</span>
              <span>{fmtAmount(selectedQuote.service_fee)}</span>
            </div>
            <div className="confirm-row">
              <span className="muted">{t('partnerFee')}</span>
              <span>{fmtAmount(selectedQuote.partner_fee)}</span>
            </div>
            <div className="confirm-row">
              <span className="muted">{t('networkFee')}</span>
              <span>{fmtAmount(selectedQuote.network_fee)}</span>
            </div>
            <div className="confirm-row">
              <span className="muted">{t('totalFee')}</span>
              <span>{fmtAmount(selectedQuote.total_fee)}</span>
            </div>
            <div className="confirm-row">
              <span className="muted">{t('quoteSource')}</span>
              <SourceBadge source={selectedQuote.quote_source_type} />
            </div>
            {selectedQuote.kyc_required && (
              <div className="confirm-row">
                <span className="muted">KYC</span>
                <span>{t('kycMayRequire')}</span>
              </div>
            )}
            {direction === 'BUY' && (
              <div className="confirm-row">
                <span className="muted">{t('wallet')}</span>
                <span>
                  {walletAddress.slice(0, 8)}…{walletAddress.slice(-6)}
                </span>
              </div>
            )}
          </div>
          <div className="card notice-card">
            <p className="notice-text">{t('wrongNetwork')}</p>
          </div>

          {direction === 'BUY' ? (
            <div className="card">
              <div className="notice-title">
                {t('receivingAddressFor', { asset: cryptoLabel })}
              </div>
              <div className="mono-block">{walletAddress.trim()}</div>
            </div>
          ) : (
            <div className="card">
              <div className="notice-title">{t('payoutRequisites')}</div>
              <div className="profile-row">
                <span className="muted">{t('method')}</span>
                <span>{paymentMethodLabel(locale, paymentMethod)}</span>
              </div>
              <div className="profile-row">
                <span className="muted">{t('bank')}</span>
                <span>{bankLabel(locale, bank)}</span>
              </div>
              <div className="mono-block">{payoutAccount.trim()}</div>
            </div>
          )}

          <Countdown
            expiresAt={selectedQuote.expires_at}
            prefix={t('quoteValidFor')}
          />

          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={checkedAddress}
              onChange={(e) => setCheckedAddress(e.target.checked)}
            />
            <span>{t('confirmedAddress')}</span>
          </label>
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={checkedDemo}
              onChange={(e) => setCheckedDemo(e.target.checked)}
            />
            <span>{t('understandDemo')}</span>
          </label>

          <button
            type="button"
            className="btn btn-primary"
            disabled={!checkedAddress || !checkedDemo || loading}
            onClick={() => void submitOrder()}
          >
            {loading ? t('creatingOrder') : t('confirmExchange')}
          </button>
        </div>
      )}
    </div>
  )
}
