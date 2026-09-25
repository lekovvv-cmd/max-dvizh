import { Button } from '@maxhub/max-ui'
import { useEffect, useState } from 'react'
import { api, type Group } from '../../app/api'
import { PulseMark } from '../../shared/ui/PulseMark'
import { CityPicker } from '../../shared/ui/CityPicker'

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
  const [name, setName] = useState('')
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
    if (!name.trim() || !city) return
    setBusy(true)
    setError('')
    try {
      onCreated(
        await api.createGroup({
          name: name.trim(),
          city_slug: city,
          bind_current_chat: bindCurrentChat,
        }),
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
        <PulseMark />
        <h1>Создать компанию</h1>
        <p>Позови друзей, и ДВИЖ подберёт план, который подходит всем.</p>
        <form onSubmit={(event) => void submit(event)}>
          <label>
            Название
            <input
              value={name}
              placeholder="Например, Наши друзья"
              maxLength={80}
              onChange={(event) => setName(event.target.value)}
              required
            />
          </label>
          <CityPicker cities={cities} value={city} onChange={setCity} />
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
              className="create-company__chat"
              variant="primary"
              type="button"
              loading={busy}
              disabled={busy || !city || !name.trim()}
              onClick={(event) => void submit(event, true)}
            >
              Для этого чата MAX
            </Button>
          ) : null}
          <Button
            stretched
            className="create-company__submit"
            variant={chatAvailable ? 'secondary' : 'primary'}
            type="submit"
            loading={busy}
            disabled={busy || !city || !name.trim()}
          >
            {chatAvailable ? 'Создать личную компанию' : 'Создать компанию'}
          </Button>
          {onCancel ? (
            <Button
              className="create-company__back"
              type="button"
              variant="secondary"
              onClick={onCancel}
            >
              Назад
            </Button>
          ) : null}
        </form>
      </section>
    </main>
  )
}
