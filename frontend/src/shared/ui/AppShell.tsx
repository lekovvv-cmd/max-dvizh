import { Icon, type IconName } from './Icon'
import companyHomeIcon from '../../assets/figma-company/33510.svg'
import companyDvizhIcon from '../../assets/figma-company/d6545.svg'
import companyUsersIcon from '../../assets/figma-company/690e2.svg'

export type Screen = 'home' | 'signal' | 'dvizhi' | 'group'

const items: Array<{
  id: Exclude<Screen, 'signal'>
  icon: IconName
  label: string
}> = [
  { id: 'home', icon: 'home', label: 'Главная' },
  { id: 'dvizhi', icon: 'list', label: 'Движи' },
  { id: 'group', icon: 'users', label: 'Компания' },
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
        <nav
          className={`bottom-nav${screen === 'group' ? ' bottom-nav--company' : ''}`}
          aria-label="Основная навигация"
        >
          {items.map((item) => (
            <button
              key={item.id}
              className={screen === item.id ? 'is-active' : ''}
              onClick={() => onNavigate(item.id)}
              aria-current={screen === item.id ? 'page' : undefined}
            >
              <span className="bottom-nav__icon">
                {screen === 'group' ? (
                  <img
                    src={
                      item.id === 'home'
                        ? companyHomeIcon
                        : item.id === 'dvizhi'
                          ? companyDvizhIcon
                          : companyUsersIcon
                    }
                    alt=""
                  />
                ) : (
                  <Icon name={item.icon} />
                )}
              </span>
              {screen === 'group' && item.id === 'dvizhi' ? 'Движ' : item.label}
            </button>
          ))}
        </nav>
      ) : null}
    </main>
  )
}
