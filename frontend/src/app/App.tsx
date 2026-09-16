import { useCallback, useEffect, useState } from 'react'

type HealthResponse = {
  status: string
  service: string
  version: string
}

type HealthState =
  | { kind: 'loading' }
  | { kind: 'success'; data: HealthResponse }
  | { kind: 'error' }

const healthUrl = '/api/v1/health'

export function App() {
  const [health, setHealth] = useState<HealthState>({ kind: 'loading' })

  const checkHealth = useCallback(async () => {
    setHealth({ kind: 'loading' })

    try {
      const response = await fetch(healthUrl)
      if (!response.ok) {
        throw new Error(`Health check failed with ${response.status}`)
      }
      const data = (await response.json()) as HealthResponse
      setHealth({ kind: 'success', data })
    } catch {
      setHealth({ kind: 'error' })
    }
  }, [])

  useEffect(() => {
    void checkHealth()
  }, [checkHealth])

  return (
    <main className="app-shell">
      <section aria-labelledby="bootstrap-title" className="bootstrap-card">
        <p className="product-name">MAX ДВИЖ</p>
        <h1 id="bootstrap-title">Технический каркас готов</h1>
        <p>
          M0: frontend подключён к backend healthcheck. Продуктовые сценарии будут
          добавляться следующими вертикальными срезами.
        </p>
        <HealthPanel health={health} onRetry={checkHealth} />
      </section>
    </main>
  )
}

function HealthPanel({ health, onRetry }: { health: HealthState; onRetry: () => Promise<void> }) {
  if (health.kind === 'loading') {
    return <p aria-live="polite">Проверяем backend…</p>
  }

  if (health.kind === 'error') {
    return (
      <div role="alert">
        <p>Backend пока недоступен.</p>
        <button type="button" onClick={() => void onRetry()}>
          Повторить проверку
        </button>
      </div>
    )
  }

  return (
    <p aria-live="polite">
      Backend: {health.data.status} · {health.data.service} v{health.data.version}
    </p>
  )
}
