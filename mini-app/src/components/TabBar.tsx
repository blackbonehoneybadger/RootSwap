import { useLocale } from '../lib/locale'
import type { MsgKey } from '../lib/i18n'

export type Tab = 'home' | 'history' | 'referral' | 'profile'

interface TabBarProps {
  active: Tab
  onSelect: (tab: Tab) => void
}

const TABS: { id: Tab; labelKey: MsgKey; icon: string }[] = [
  { id: 'home', labelKey: 'home', icon: '⇄' },
  { id: 'history', labelKey: 'history', icon: '≣' },
  { id: 'referral', labelKey: 'referral', icon: '⚭' },
  { id: 'profile', labelKey: 'profile', icon: '◉' },
]

export function TabBar({ active, onSelect }: TabBarProps) {
  const { t } = useLocale()
  return (
    <nav className="tab-bar" role="tablist">
      {TABS.map((tab) => (
        <button
          key={tab.id}
          type="button"
          role="tab"
          aria-selected={active === tab.id}
          className={`tab-item ${active === tab.id ? 'tab-item-active' : ''}`}
          onClick={() => onSelect(tab.id)}
        >
          <span className="tab-icon" aria-hidden="true">
            {tab.icon}
          </span>
          <span className="tab-label">{t(tab.labelKey)}</span>
        </button>
      ))}
    </nav>
  )
}
