import { Icon, type IconName } from './Icon'

export type Screen = 'home' | 'signal' | 'plans' | 'group'

const items: Array<{
  id: Exclude<Screen, 'signal'>
  icon: IconName
  activeIcon: IconName
  label: string
}> = [
  { id: 'home', icon: 'home', activeIcon: 'homeSolid', label: 'Главная' },
  { id: 'plans', icon: 'list', activeIcon: 'listSolid', label: 'Планы' },
  { id: 'group', icon: 'users', activeIcon: 'usersSolid', label: 'Компания' },
]

export function AppShell({
  screen,
  children,
  onNavigate,
}: {
  screen: Screen
  children: React.ReactNode
  onNavigate: (screen: Screen) => void
}) {
  return (
    <main className="app-shell">
      {screen === 'home' ? (
        <header className="topbar">
          <span className="brand">ДВИЖ</span>
        </header>
      ) : null}
      <div className="screen-content">{children}</div>
      {screen !== 'signal' ? (
        <nav className="bottom-nav" aria-label="Основная навигация">
          {items.map((item) => (
            <button
              key={item.id}
              className={screen === item.id ? 'is-active' : ''}
              onClick={() => onNavigate(item.id)}
              aria-current={screen === item.id ? 'page' : undefined}
            >
              <Icon name={screen === item.id ? item.activeIcon : item.icon} />
              {item.label}
            </button>
          ))}
        </nav>
      ) : null}
    </main>
  )
}
