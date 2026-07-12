import { useEffect, useState } from 'react'
import { authenticate, getCurrentUser } from './lib/api'
import { getInitData, initTelegram, isInsideTelegram } from './lib/telegram'
import type { AuthUser, Direction, Order } from './lib/types'
import { TabBar, type Tab } from './components/TabBar'
import { Home } from './screens/Home'
import { History } from './screens/History'
import { Referral } from './screens/Referral'
import { Profile } from './screens/Profile'
import { Wizard, type WizardPrefill } from './screens/Wizard'
import { OrderScreen } from './screens/OrderScreen'

type BootState = 'loading' | 'ready' | 'outside-telegram' | 'auth-error'

type View =
  | { kind: 'tabs' }
  | { kind: 'wizard'; direction: Direction; prefill: WizardPrefill | null }
  | { kind: 'order'; orderId: string; initialOrder: Order | null }

export default function App() {
  const [boot, setBoot] = useState<BootState>('loading')
  const [authError, setAuthError] = useState<string | null>(null)
  const [user, setUser] = useState<AuthUser | null>(null)
  const [tab, setTab] = useState<Tab>('home')
  const [historyRefreshKey, setHistoryRefreshKey] = useState(0)
  const [view, setView] = useState<View>({ kind: 'tabs' })

  useEffect(() => {
    initTelegram()
    if (!getInitData()) {
      // outside Telegram and not in DEV mode
      setBoot('outside-telegram')
      return
    }
    let cancelled = false
    authenticate()
      .then((u) => {
        if (!cancelled) {
          setUser(u)
          setBoot('ready')
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setAuthError(e instanceof Error ? e.message : 'Ошибка авторизации')
          setBoot('auth-error')
        }
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (boot === 'loading') {
    return (
      <div className="app">
        <div className="boot-screen">
          <div className="home-title">RootSwap</div>
          <div className="muted">Загрузка…</div>
        </div>
      </div>
    )
  }

  if (boot === 'outside-telegram') {
    return (
      <div className="app">
        <div className="boot-screen">
          <div className="home-title">RootSwap</div>
          <div className="card notice-card">
            <div className="notice-title">Откройте внутри Telegram</div>
            <p className="notice-text">
              Это мини-приложение работает внутри Telegram. Откройте бота и
              запустите приложение оттуда.
            </p>
            {isInsideTelegram() ? null : (
              <p className="muted">
                Данные Telegram (initData) недоступны в этом окружении.
              </p>
            )}
          </div>
        </div>
      </div>
    )
  }

  if (boot === 'auth-error') {
    return (
      <div className="app">
        <div className="boot-screen">
          <div className="home-title">RootSwap</div>
          <div className="error-box">
            Не удалось авторизоваться. {authError}
          </div>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => window.location.reload()}
          >
            Повторить
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
        {view.kind === 'tabs' && (
          <>
            {tab === 'home' && <Home onStart={(d) => openWizard(d)} />}
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
          onSelect={(t) => {
            setTab(t)
            setView({ kind: 'tabs' })
          }}
        />
      )}
    </div>
  )
}
