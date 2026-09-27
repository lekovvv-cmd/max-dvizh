import { StrictMode, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { MaxUI } from '@maxhub/max-ui'
import '@maxhub/max-ui/dist/styles.css'
import { App } from './app/App'
import './styles/global.css'

const rootElement = document.getElementById('root')

if (rootElement === null) {
  throw new Error('Root element not found')
}

function appTheme(): 'light' | 'dark' {
  const webApp = window.WebApp
  if (webApp?.colorScheme) return webApp.colorScheme
  if (webApp?.themeParams?.bg_color) {
    const color = webApp.themeParams.bg_color.replace('#', '')
    if (/^[0-9a-f]{6}$/i.test(color)) {
      const channels = [0, 2, 4].map((offset) => parseInt(color.slice(offset, offset + 2), 16))
      if ((channels[0] * 299 + channels[1] * 587 + channels[2] * 114) / 1000 < 128) return 'dark'
      return 'light'
    }
  }
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function ThemedApp() {
  const [scheme, setScheme] = useState(appTheme)
  useEffect(() => {
    const refresh = () => setScheme(appTheme())
    const media = window.matchMedia?.('(prefers-color-scheme: dark)')
    media?.addEventListener?.('change', refresh)
    window.WebApp?.onEvent?.('themeChanged', refresh)
    return () => {
      media?.removeEventListener?.('change', refresh)
      window.WebApp?.offEvent?.('themeChanged', refresh)
    }
  }, [])
  useEffect(() => {
    document.documentElement.dataset.theme = scheme
    document
      .querySelector('meta[name="theme-color"]')
      ?.setAttribute('content', scheme === 'dark' ? '#151323' : '#ffffff')
  }, [scheme])
  return (
    <MaxUI colorScheme={scheme}>
      <App />
    </MaxUI>
  )
}

createRoot(rootElement).render(
  <StrictMode>
    <ThemedApp />
  </StrictMode>,
)
