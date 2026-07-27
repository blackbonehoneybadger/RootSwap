import { useEffect, useState } from 'react'
import { authenticate, getCurrentUser } from './lib/api'
import { createAuthOnce } from './lib/authBoot'
import { LocaleProvider, useLocale } from './lib/locale'
import {
  bindBackButton,
  getInitData,
  getLanguageCode,
  hideBackButton,
  initTelegram,
  isInsideTelegram,
  watchTelegramTheme,
} from './lib/telegram'
import type { AuthUser, Direction, Order } from './lib/types'
import { TabBar, type Tab } from './components/TabBar'
import { Home } from './screens/Home'
import { History } from './screens/History'
import { Referral } from './screens/Referral'
import { Profile } from './screens/Profile'
import { Wizard, type WizardPrefill } from './screens/Wizard'
import { OrderScreen } from './screens/OrderScreen'
import { Legal } from './screens/Legal'

type BootState = 'loading' | 'ready' | 'outside-telegram' | 'auth-error'

type View =
  | { kind: 'tabs' }
  | { kind: 'wizard'; direction: Direction; prefill: WizardPrefill | null }
  | { kind: 'order'; orderId: string; initialOrder: Order | null }
  | { kind: 'legal'; doc?: string }

/** Module-level: auth runs once per page load, never on locale/theme changes. */
const authOnce = createAuthOnce(() => authenticate())

function AppShell() {
  const { t } = useLocale()
  const [boot, setBoot] = useState<BootState>('loading')
  const [authError, setAuthError] = useState<string | null>(null)
  const [user, setUser] = useState<AuthUser | null>(null)
  const [tab, setTab] = useState<Tab>('home')
  const [historyRefreshKey, setHistoryRefreshKey] = useState(0)
  const [view, setView] = useState<View>({ kind: 'tabs' })

  // 1) Telegram theme / viewport — independent of auth
  useEffect(() => {
    initTelegram()
    return watchTelegramTheme()
  }, [])

  // 2) Authentication — empty deps; locale changes must NOT re-run this
  useEffect(() => {
    if (!getInitData()) {
      setBoot('outside-telegram')
      return
    }
    let cancelled = false
    authOnce
      .run()
      .then((u) => {
        if (!cancelled) {
          setUser(u as AuthUser)
          setBoot('ready')
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setAuthError(e instanceof Error ? e.message : t('authFailed'))
          setBoot('auth-error')
        }
      })
    return () => {
      cancelled = true
    }
    // intentionally omit locale / t — auth must not replay initData
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // 3) Telegram BackButton for nested views
  useEffect(() => {
    if (view.kind === 'tabs') {
      hideBackButton()
      return
    }
    return bindBackButton(() => setView({ kind: 'tabs' }))
  }, [view.kind])

  if (boot === 'loading') {
    return (
      <div className="app">
        <div className="boot-screen">
          <div className="home-title">{t('brand')}</div>
          <div className="muted">{t('loading')}</div>
        </div>
      </div>
    )
  }

  if (boot === 'outside-telegram') {
    return (
      <div className="app">
        <div className="boot-screen">
          <div className="home-title">{t('brand')}</div>
          <div className="card notice-card">
            <div className="notice-title">{t('openInTelegram')}</div>
            <p className="notice-text">{t('openInTelegramBody')}</p>
            {isInsideTelegram() ? null : <p className="muted">{t('noInitData')}</p>}
          </div>
        </div>
      </div>
    )
  }

  if (boot === 'auth-error') {
    return (
      <div className="app">
        <div className="boot-screen">
          <div className="home-title">{t('brand')}</div>
          <div className="error-box">
            {t('authFailed')} {authError}
          </div>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => window.location.reload()}
          >
            {t('retry')}
          </button>
        </div>
      </div>
    )
  }

  const openWizard = (direction: Direction, prefill: WizardPrefill | null = null) => {
    setView({ kind: 'wizard', direction, prefill })
  }

  const openOrder = (orderId: string, initialOrder: Order | null = null) => {
    setView({ kind: 'order', orderId, initialOrder })
  }

  const repeatOrder = (order: Order) => {
    const isBuy = order.direction === 'BUY'
    openWizard(order.direction, {
      direction: order.direction,
      asset: isBuy ? order.to_asset : order.from_asset,
      network: isBuy ? order.to_network : order.from_network,
      amountIn: order.amount_in,
    })
  }

  const backToTabs = () => setView({ kind: 'tabs' })

  return (
    <div className="app">
      <div className="demo-banner" role="status">
        {t('demoBanner')}
      </div>
      <main className="app-main">
        {view.kind === 'wizard' && (
          <Wizard
            key={`${view.direction}-${view.prefill ? 'prefill' : 'new'}`}
            initialDirection={view.direction}
            prefill={view.prefill}
            onClose={backToTabs}
            onOrderCreated={(order) => openOrder(order.id, order)}
          />
        )}
        {view.kind === 'order' && (
          <OrderScreen
            key={view.orderId}
            orderId={view.orderId}
            initialOrder={view.initialOrder}
            onBack={() => {
              setTab('history')
              setHistoryRefreshKey((k) => k + 1)
              backToTabs()
            }}
          />
        )}
        {view.kind === 'legal' && (
          <Legal doc={view.doc} onBack={backToTabs} />
        )}
        {view.kind === 'tabs' && (
          <>
            {tab === 'home' && (
              <Home
                onStart={(d) => openWizard(d)}
                onOpenLegal={(doc) => setView({ kind: 'legal', doc })}
              />
            )}
            {tab === 'history' && (
              <History
                refreshKey={historyRefreshKey}
                onOpenOrder={(id) => openOrder(id)}
                onRepeat={repeatOrder}
              />
            )}
            {tab === 'referral' && <Referral />}
            {tab === 'profile' && <Profile user={user ?? getCurrentUser()} />}
          </>
        )}
      </main>

      {view.kind === 'tabs' && (
        <TabBar
          active={tab}
          onSelect={(next) => {
            setTab(next)
            setView({ kind: 'tabs' })
          }}
        />
      )}
    </div>
  )
}

export default function App() {
  return (
    <LocaleProvider telegramLang={getLanguageCode()}>
      <AppShell />
    </LocaleProvider>
  )
}
