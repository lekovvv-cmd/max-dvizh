import { Button } from '@maxhub/max-ui'
import { useEffect, useState } from 'react'
import { api, setDemoUser } from '../../app/api'
import type { Group, GroupCityUpdateResult, GroupMember, Location } from '../../app/api'
import { ConfirmDialog } from '../../shared/ui/ConfirmDialog'
import { Icon } from '../../shared/ui/Icon'
import { formatPeople } from '../../shared/lib/format'
import { SectionHeader } from '../../shared/ui/SectionHeader'
import { CityPicker } from '../../shared/ui/CityPicker'

export function Company({
  groups,
  active,
  locations,
  mode,
  onSelect,
  onNew,
  onChangeCity,
  onAddPlace,
  onRenamePlace,
  onDefaultPlace,
  onDeletePlace,
}: {
  groups: Group[]
  active: Group
  locations: Location[]
  mode: string
  onSelect: (group: Group) => void
  onNew: () => void
  onChangeCity: (groupId: string, city: string) => Promise<GroupCityUpdateResult>
  onAddPlace: (label: string) => Promise<Location>
  onRenamePlace: (id: string, label: string) => Promise<void>
  onDefaultPlace: (id: string) => Promise<void>
  onDeletePlace: (id: string) => Promise<void>
}) {
  const [copied, setCopied] = useState(false)
  const [inviteOpen, setInviteOpen] = useState(false)
  const [person, setPerson] = useState('anton')
  const [label, setLabel] = useState('')
  const [placeOpen, setPlaceOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [placeError, setPlaceError] = useState('')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editingLabel, setEditingLabel] = useState('')
  const [placeMenuId, setPlaceMenuId] = useState<string | null>(null)
  const [cities, setCities] = useState<{ slug: string; name: string }[]>([])
  const [changeCityOpen, setChangeCityOpen] = useState(false)
  const [nextCity, setNextCity] = useState(active.city_slug)
  const [cityResult, setCityResult] = useState('')
  const [members, setMembers] = useState<GroupMember[]>([])
  const [membersStatus, setMembersStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  useEffect(() => {
    void api
      .cities()
      .then(setCities)
      .catch(() => setError('Не удалось загрузить список городов'))
  }, [])
  useEffect(() => {
    setNextCity(active.city_slug)
  }, [active.city_slug])
  useEffect(() => {
    setCityResult('')
  }, [active.id])
  useEffect(() => {
    let current = true
    setMembers([])
    setMembersStatus('loading')
    void api.groupMembers(active.id).then(
      (items) => {
        if (current) {
          setMembers(items)
          setMembersStatus('ready')
        }
      },
      () => {
        if (current) setMembersStatus('error')
      },
    )
    return () => {
      current = false
    }
  }, [active.id])
  const invite = active.invite_url || `${window.location.origin}#startapp=${active.invite_token}`
  async function shareInvite() {
    setError('')
    try {
      if (window.WebApp?.shareMaxContent)
        window.WebApp.shareMaxContent({
          text: `Присоединяйся к «${active.name}» в ДВИЖе`,
          link: invite,
        })
      else {
        await navigator.clipboard.writeText(invite)
        setCopied(true)
      }
    } catch {
      setError('Не удалось поделиться. Скопируй приглашение вручную.')
    }
  }
  async function copyInvite() {
    try {
      await navigator.clipboard.writeText(invite)
      setCopied(true)
    } catch {
      setError('Не удалось скопировать ссылку.')
    }
  }
  async function addPlace() {
    setBusy(true)
    setPlaceError('')
    try {
      await onAddPlace(label.trim())
      setLabel('')
      setPlaceOpen(false)
    } catch (reason) {
      setPlaceError(
        reason instanceof Error
          ? reason.message
          : 'Геопозиция недоступна. Расстояние останется выключенным.',
      )
    } finally {
      setBusy(false)
    }
  }
  async function changePlace(action: () => Promise<void>) {
    setBusy(true)
    setError('')
    try {
      await action()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Не удалось изменить место')
    } finally {
      setBusy(false)
    }
  }
  async function changeCity() {
    setBusy(true)
    setError('')
    try {
      const result = await onChangeCity(active.id, nextCity)
      setChangeCityOpen(false)
      setCityResult(
        `Город изменён. Отменено сигналов: ${result.cancelled_signals}. Автосигналов на паузе: ${result.paused_autosignals}. Закрыто вариантов: ${result.cancelled_plans}.`,
      )
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Не удалось изменить город')
    } finally {
      setBusy(false)
    }
  }
  const cityName =
    cities.find((city) => city.slug === active.city_slug)?.name ||
    ({ ekb: 'Екатеринбург', msk: 'Москва', spb: 'Санкт-Петербург' } as Record<string, string>)[
      active.city_slug
    ] ||
    'Твой город'
  const cityLocations = locations.filter((item) => item.city_slug === active.city_slug)
  return (
    <section className="page-stack company-page">
      <SectionHeader
        title="Компания"
        action={
          <button type="button" className="icon-button" aria-label="Новая компания" onClick={onNew}>
            <Icon name="plus" />
          </button>
        }
      />
      <div className="company-overview">
        <span className="company-overview__icon" aria-hidden="true">
          <Icon name="users" size={30} />
        </span>
        <strong>{active.name}</strong>
        <span>
          {cityName} · {formatPeople(active.member_count)}
        </span>
        <Button variant="primary" stretched onClick={() => setInviteOpen(true)}>
          Пригласить друзей
        </Button>
      </div>
      {groups.length > 1 ? (
        <section className="settings-section">
          <h2>Мои компании</h2>
          <div className="groups-list">
            {groups.map((group) => (
              <button
                key={group.id}
                className={`group-cell ${group.id === active.id ? 'group-cell--active' : ''}`}
                onClick={() => onSelect(group)}
              >
                <span>
                  <strong>{group.name}</strong>
                  <small>{formatPeople(group.member_count)}</small>
                </span>
                {group.id === active.id ? <b>Текущая</b> : <Icon name="chevron" size={18} />}
              </button>
            ))}
          </div>
        </section>
      ) : null}
      <section className="settings-section company-members" aria-labelledby="company-members-title">
        <div className="settings-section__head">
          <div>
            <h2 id="company-members-title">Кто в компании</h2>
            <p>{formatPeople(active.member_count)}</p>
          </div>
        </div>
        {membersStatus === 'loading' ? <p className="text-muted">Загружаем участников…</p> : null}
        {membersStatus === 'error' ? (
          <p className="form-error" role="alert">
            Не удалось загрузить участников.
          </p>
        ) : null}
        {membersStatus === 'ready' ? (
          <ul className="company-members__list">
            {members.map((person) => (
              <li key={person.id}>
                <span className="company-members__avatar" aria-hidden="true">
                  {person.display_name.trim().slice(0, 1).toUpperCase()}
                </span>
                <span>{person.display_name}</span>
                {person.is_me ? <small>Ты</small> : null}
              </li>
            ))}
          </ul>
        ) : null}
      </section>
      <section className="settings-section">
        <div className="settings-section__head">
          <div>
            <h2>Мои места</h2>
            <p>Эти точки видны только тебе.</p>
          </div>
        </div>
        {cityLocations.length ? (
          <div className="saved-places">
            {cityLocations.map((place) => (
              <div className="saved-place" key={place.id}>
                <div className="saved-place__content">
                  {editingId === place.id ? (
                    <label>
                      Название места
                      <input
                        value={editingLabel}
                        maxLength={80}
                        onChange={(event) => setEditingLabel(event.target.value)}
                      />
                    </label>
                  ) : (
                    <>
                      <strong>{place.label}</strong>
                      {place.is_default ? <span className="quiet-label">По умолчанию</span> : null}
                      {place.address_text ? <p>{place.address_text}</p> : null}
                    </>
                  )}
                </div>
                {editingId === place.id ? (
                  <div className="saved-place__actions">
                    <Button
                      variant="primary"
                      disabled={busy || !editingLabel.trim()}
                      onClick={() =>
                        void changePlace(async () => {
                          await onRenamePlace(place.id, editingLabel.trim())
                          setEditingId(null)
                        })
                      }
                    >
                      Сохранить
                    </Button>
                    <Button variant="secondary" disabled={busy} onClick={() => setEditingId(null)}>
                      Отмена
                    </Button>
                  </div>
                ) : (
                  <>
                    <button
                      type="button"
                      className="icon-button icon-button--quiet"
                      aria-label={`Действия с местом ${place.label}`}
                      aria-expanded={placeMenuId === place.id}
                      onClick={() =>
                        setPlaceMenuId((current) => (current === place.id ? null : place.id))
                      }
                    >
                      <Icon name="more" />
                    </button>
                    {placeMenuId === place.id ? (
                      <div className="row-menu">
                        <button
                          type="button"
                          onClick={() => {
                            setEditingId(place.id)
                            setEditingLabel(place.label)
                            setPlaceMenuId(null)
                          }}
                        >
                          Переименовать
                        </button>
                        {!place.is_default ? (
                          <button
                            type="button"
                            onClick={() =>
                              void changePlace(async () => {
                                await onDefaultPlace(place.id)
                                setPlaceMenuId(null)
                              })
                            }
                          >
                            Сделать основным
                          </button>
                        ) : null}
                        <button
                          type="button"
                          className="danger"
                          onClick={() =>
                            void changePlace(async () => {
                              await onDeletePlace(place.id)
                              setPlaceMenuId(null)
                            })
                          }
                        >
                          Удалить
                        </button>
                      </div>
                    ) : null}
                  </>
                )}
              </div>
            ))}
          </div>
        ) : (
          <p className="empty-copy">
            Сохранённых мест пока нет. Без них расстояние в сигнале недоступно.
          </p>
        )}
        <div className={'add-place' + (placeOpen ? ' is-open' : '')}>
          <button
            type="button"
            className="add-place__trigger"
            aria-expanded={placeOpen}
            onClick={() => {
              setPlaceOpen((current) => !current)
              setPlaceMenuId(null)
              setPlaceError('')
            }}
          >
            <span className="add-place__icon" aria-hidden="true">
              <Icon name="pin" size={20} />
            </span>
            <span>Добавить место</span>
            <span className="add-place__toggle" aria-hidden="true">
              <span className="add-place__plus">
                <Icon name="plus" size={21} />
              </span>
              <span className="add-place__minus">
                <Icon name="minus" size={21} />
              </span>
            </span>
          </button>
          {placeOpen ? (
            <div className="add-place__form">
              <label>
                Название
                <input
                  value={label}
                  maxLength={80}
                  placeholder="Например, Дом"
                  onChange={(event) => setLabel(event.target.value)}
                />
              </label>
              <p className="form-hint">Нужна геопозиция. Точка будет видна только тебе.</p>
              {placeError ? (
                <p className="form-error" role="alert">
                  {placeError}
                </p>
              ) : null}
              <Button
                variant="primary"
                loading={busy}
                disabled={busy || !label.trim()}
                onClick={() => void addPlace()}
              >
                Сохранить текущее место
              </Button>
            </div>
          ) : null}
        </div>
      </section>
      <section className="settings-section">
        <div className="settings-section__head">
          <div>
            <h2>Город компании</h2>
            <p>{cityName}</p>
          </div>
          <Button
            variant="secondary"
            disabled={!cities.length || busy}
            onClick={() => {
              setNextCity(active.city_slug)
              setChangeCityOpen(true)
            }}
          >
            Изменить
          </Button>
        </div>
        {cityResult ? (
          <p className="inline-notice" role="status">
            {cityResult}
          </p>
        ) : null}
      </section>
      {error ? (
        <p className="form-error" role="alert">
          {error}
        </p>
      ) : null}
      {mode === 'development' && new URLSearchParams(window.location.search).has('dev') ? (
        <section className="dev-tools">
          <p>Dev / demo tools</p>
          <label>
            Демо-пользователь
            <input value={person} onChange={(event) => setPerson(event.target.value)} />
          </label>
          <Button
            variant="secondary"
            onClick={() => {
              setDemoUser(person)
              window.location.reload()
            }}
          >
            Сменить пользователя
          </Button>
        </section>
      ) : null}
      {changeCityOpen ? (
        <ConfirmDialog
          title="Сменить город компании?"
          description="Активные сигналы отменятся, а автосигналы этой компании будут поставлены на паузу."
          confirmLabel="Сменить город"
          cancelLabel="Отмена"
          busy={busy}
          confirmDisabled={nextCity === active.city_slug}
          onConfirm={() => void changeCity()}
          onCancel={() => setChangeCityOpen(false)}
        >
          <CityPicker cities={cities} value={nextCity} onChange={setNextCity} />
        </ConfirmDialog>
      ) : null}
      {inviteOpen ? (
        <ConfirmDialog
          title="Позвать друзей"
          description={'Приглашение в «' + active.name + '»'}
          confirmLabel={window.WebApp?.shareMaxContent ? 'Поделиться в MAX' : 'Скопировать ссылку'}
          cancelLabel="Закрыть"
          onConfirm={() => void shareInvite()}
          onCancel={() => setInviteOpen(false)}
        >
          {window.WebApp?.shareMaxContent ? (
            <button type="button" className="secondary-button" onClick={() => void copyInvite()}>
              {copied ? 'Скопировано' : 'Скопировать ссылку'}
            </button>
          ) : null}
        </ConfirmDialog>
      ) : null}
    </section>
  )
}
