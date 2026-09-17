import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { MaxUI } from '@maxhub/max-ui'
import '@maxhub/max-ui/dist/styles.css'
import { App } from './app/App'
import './styles/global.css'

const rootElement = document.getElementById('root')

if (rootElement === null) {
  throw new Error('Root element not found')
}

createRoot(rootElement).render(
  <StrictMode>
    <MaxUI>
      <App />
    </MaxUI>
  </StrictMode>,
)
