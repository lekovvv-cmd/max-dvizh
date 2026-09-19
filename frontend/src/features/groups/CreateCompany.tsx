import { Button, Input } from '@maxhub/max-ui'
import { useEffect, useState } from 'react'
import { api, type Group } from '../../app/api'

export function CreateCompany({
  onCreated,
  onCancel,
  chatAvailable,
  joinState,
}: {
  onCreated: (group: Group) => void
  onCancel?: () => void
  chatAvailable: boolean
  joinState: string
}) {
  const [name, setName] = useState('Наша компания')
  const [city, setCity] = useState('')
  const [cities, setCities] = useState<{ slug: string; name: string }[]>([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    void api
      .cities()
      .then((items) => {
        setCities(items)
        setCity(items[0]?.slug || '')
      })
      .catch(() => setError('Не удалось загрузить города. Попробуй позже.'))
  }, [])
  async function submit(event: React.FormEvent, bindCurrentChat = false) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      onCreated(
        await api.createGroup({ name, city_slug: city, bind_current_chat: bindCurrentChat }),
      )
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Не удалось создать компанию')
    } finally {
      setBusy(false)
    }
  }
  return (
    <main className="start-screen">
      <section className="start-card">
        {joinState ? <p role="status">{joinState}</p> : null}
        <h1>Создать компанию</h1>
        <form onSubmit={(event) => void submit(event)}>
          <label>
            Название
            <Input value={name} onChange={(event) => setName(event.target.value)} required />
          </label>
          <label>
            Город
            <select value={city} onChange={(event) => setCity(event.target.value)} required>
              {cities.map((item) => (
                <option key={item.slug} value={item.slug}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
          {error ? (
            <p className="form-error" role="alert">
              {error}
            </p>
          ) : null}
          {error && !cities.length ? (
            <Button
              type="button"
              variant="secondary"
              onClick={() =>
                void api
                  .cities()
                  .then((items) => {
                    setCities(items)
                    setCity(items[0]?.slug || '')
                    setError('')
                  })
                  .catch(() => setError('Не удалось загрузить города. Попробуй позже.'))
              }
            >
              Повторить загрузку городов
            </Button>
          ) : null}
          {chatAvailable ? (
            <Button
              stretched
              variant="primary"
              type="button"
              loading={busy}
              disabled={busy || !city}
              onClick={(event) => void submit(event, true)}
            >
              Для этого чата MAX
            </Button>
          ) : null}
          <Button
            stretched
            variant={chatAvailable ? 'secondary' : 'primary'}
            type="submit"
            loading={busy}
            disabled={busy || !city}
          >
            Приватная компания
          </Button>
          {onCancel ? (
            <Button type="button" variant="secondary" onClick={onCancel}>
              Назад
            </Button>
          ) : null}
        </form>
      </section>
    </main>
  )
}
