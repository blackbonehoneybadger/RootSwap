export type Tab = 'home' | 'history' | 'referral' | 'profile'

interface TabBarProps {
  active: Tab
  onSelect: (tab: Tab) => void
}

const TABS: { id: Tab; label: string; icon: string }[] = [
  { id: 'home', label: 'Главная', icon: '⇄' },
  { id: 'history', label: 'История', icon: '≣' },
  { id: 'referral', label: 'Рефералы', icon: '⚭' },
  { id: 'profile', label: 'Профиль', icon: '◉' },
]

export function TabBar({ active, onSelect }: TabBarProps) {
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
          <span className="tab-label">{tab.label}</span>
        </button>
      ))}
    </nav>
  )
}
