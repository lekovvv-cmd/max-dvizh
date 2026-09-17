export type Screen = 'home' | 'signal' | 'autos' | 'plans' | 'group'

const items: Array<{ id: Exclude<Screen, 'signal'>; icon: string; label: string }> = [
  { id: 'home', icon: '⌂', label: 'Главная' },
  { id: 'autos', icon: '↻', label: 'Авто' },
  { id: 'plans', icon: '✓', label: 'Планы' },
  { id: 'group', icon: '◌', label: 'Компания' },
]

export function AppShell({ screen, name, children, onNavigate }: { screen: Screen; name: string; children: React.ReactNode; onNavigate: (screen: Screen) => void }) {
  return <main className="app-shell">
    <header className="topbar">
      <button className="brand" onClick={() => onNavigate('home')} aria-label="На главную ДВИЖ"><span>ϟ</span> ДВИЖ</button>
      <span className="topbar__user">{name}</span>
    </header>
    <div className="screen-content">{children}</div>
    {screen !== 'signal' ? <nav className="bottom-nav" aria-label="Основная навигация">
      {items.map(item => <button key={item.id} className={screen === item.id ? 'is-active' : ''} onClick={() => onNavigate(item.id)} aria-current={screen === item.id ? 'page' : undefined}>
        <span aria-hidden="true">{item.icon}</span>{item.label}
      </button>)}
    </nav> : null}
  </main>
}
