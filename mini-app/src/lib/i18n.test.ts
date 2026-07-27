import { describe, expect, it } from 'vitest'

import { messages, t } from './i18n'
import { BANKS, PAYMENT_METHODS, bankLabel, paymentMethodLabel } from './routes'

describe('i18n', () => {
  it('has identical key sets for ru and en (no missing translations)', () => {
    const ru = Object.keys(messages.ru).sort()
    const en = Object.keys(messages.en).sort()
    expect(en).toEqual(ru)
  })

  it('has no empty strings in either locale', () => {
    for (const locale of ['ru', 'en'] as const) {
      for (const [key, value] of Object.entries(messages[locale])) {
        expect(value, `${locale}.${key}`).not.toBe('')
      }
    }
  })

  it('returns different text per locale', () => {
    expect(t('ru', 'confirmExchange')).not.toBe(t('en', 'confirmExchange'))
    expect(t('ru', 'confirmExchange')).toBe('Подтвердить обмен')
    expect(t('en', 'confirmExchange')).toBe('Confirm exchange')
  })

  it('interpolates named params', () => {
    expect(t('en', 'amountInAsset', { asset: 'BTC' })).toBe('Amount in BTC')
    expect(t('ru', 'amountInAsset', { asset: 'BTC' })).toBe('Сумма в BTC')
    expect(t('en', 'feesSummary', { total: '12.50' })).toBe('Fees: 12.50 total')
  })

  it('leaves unknown placeholders intact', () => {
    expect(t('en', 'amountInAsset')).toBe('Amount in {asset}')
  })
})

describe('domain labels (stable codes, localized display)', () => {
  it('localizes every bank code in both locales', () => {
    for (const code of BANKS) {
      expect(bankLabel('ru', code)).not.toBe('')
      expect(bankLabel('en', code)).not.toBe('')
    }
    expect(bankLabel('ru', 'Tinkoff')).toBe('Т-Банк (Тинькофф)')
    expect(bankLabel('en', 'Tinkoff')).toBe('T-Bank (Tinkoff)')
  })

  it('localizes every payment method in both locales', () => {
    for (const { value } of PAYMENT_METHODS) {
      expect(paymentMethodLabel('ru', value)).not.toBe('')
      expect(paymentMethodLabel('en', value)).not.toBe('')
    }
    expect(paymentMethodLabel('ru', 'SBP')).toBe('СБП')
    expect(paymentMethodLabel('en', 'bank_transfer')).toBe('Bank transfer')
  })

  it('falls back to the raw code for an unknown value', () => {
    expect(bankLabel('en', 'UNKNOWN')).toBe('UNKNOWN')
    expect(paymentMethodLabel('ru', 'nope')).toBe('nope')
  })
})
