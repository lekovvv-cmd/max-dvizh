import { Button } from '@maxhub/max-ui'
import { useEffect, useState } from 'react'
import { api, setDemoUser } from '../../app/api'
import type { Group, GroupCityUpdateResult, GroupMember, Location } from '../../app/api'
import groupIcon from '../../assets/figma-company/8deaf.svg'
import arrowIcon from '../../assets/figma-company/18d2d.svg'
import editIcon from '../../assets/figma-company/188ab.svg'
import avatarCircle from '../../assets/figma-company/5a81c.svg'
import { PlacePicker, type SelectedPlace } from '../../shared/ui/PlacePicker'
import { SectionHeader } from '../../shared/ui/SectionHeader'
import { CityPicker } from '../../shared/ui/CityPicker'
import { CompanyPopup } from './CompanyPopup'
import { CreateCompany } from './CreateCompany'

function formatMembers(count: number) {
  const lastTwo = count % 100
  const last = count % 10
  const word =
    lastTwo >= 11 && lastTwo <= 14
      ? 'участников'
      : last === 1
        ? 'участник'
        : last >= 2 && last <= 4
          ? 'участника'
          : 'участников'
  return `${count} ${word}`
}

export function Company({
  groups,
  active,
  locations,
  mode,
  onSelect,
  onNew,
  createOpen,
  chatAvailable,
  onCreateClose,
  onCreated,
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
  createOpen: boolean
  chatAvailable: boolean
  onCreateClose: () => void
  onCreated: (group: Group) => void
  onChangeCity: (groupId: string, city: string) => Promise<GroupCityUpdateResult>
  onAddPlace: (
    label: string,
    latitude: number,
    longitude: number,
    address?: string | null,
  ) => Promise<Location>
  onRenamePlace: (id: string, label: string) => Promise<void>
  onDefaultPlace: (id: string) => Promise<void>
  onDeletePlace: (id: string) => Promise<void>
}) {
  const [openGroupId, setOpenGroupId] = useState<string | null>(null)
  const [groupOpen, setGroupOpen] = useState(false)
  const [copied, setCopied] = useState(false)
  const [inviteOpen, setInviteOpen] = useState(false)
  const [person, setPerson] = useState('anton')
  const [label, setLabel] = useState('')
  const [selectedPlace, setSelectedPlace] = useState<SelectedPlace | null>(null)
  const [placeOpen, setPlaceOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [placeError, setPlaceError] = useState('')
  const [editingPlace, setEditingPlace] = useState<Location | null>(null)
  const [editPlaceOpen, setEditPlaceOpen] = useState(false)
  const [editingLabel, setEditingLabel] = useState('')
  const [cities, setCities] = useState<{ slug: string; name: string }[]>([])
  const [changeCityOpen, setChangeCityOpen] = useState(false)
  const [nextCity, setNextCity] = useState(active.city_slug)
  const [cityResult, setCityResult] = useState('')
  const [cityResultLeaving, setCityResultLeaving] = useState(false)
  const [createBusy, setCreateBusy] = useState(false)
  const [members, setMembers] = useState<GroupMember[]>([])
  const [membersStatus, setMembersStatus] = useState<'loading' | 'ready' | 'error'>('loading')

  useEffect(() => {
    void api
      .cities()
      .then(setCities)
      .catch(() => setError('Не удалось загрузить список городов'))
  }, [])
  useEffect(() => setNextCity(active.city_slug), [active.city_slug])
  useEffect(() => setCityResult(''), [active.id])
  useEffect(() => {
    if (!cityResult) return
    const leavingTimer = window.setTimeout(() => setCityResultLeaving(true), 2750)
    const removeTimer = window.setTimeout(() => setCityResult(''), 3000)
    return () => {
      window.clearTimeout(leavingTimer)
      window.clearTimeout(removeTimer)
    }
  }, [cityResult])
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
  const invite =
    active.invite_url ||
    (mode === 'development' && active.invite_token
      ? `${window.location.origin}/#startapp=${active.invite_token}`
      : null)

  async function shareInvite() {
    setError('')
    if (!invite) {
      setError('Приглашение в MAX пока не настроено. Нужен адрес бота.')
      return
    }
    try {
      if (window.WebApp?.shareMaxContent) {
        await window.WebApp.shareMaxContent({
          text: `Присоединяйся к «${active.name}» в ДВИЖе\n${invite}`,
        })
      } else {
        await navigator.clipboard.writeText(invite)
        setCopied(true)
      }
    } catch {
      setError('Не удалось поделиться. Скопируй приглашение вручную.')
    }
  }

  async function copyInvite() {
    if (!invite) {
      setError('Приглашение в MAX пока не настроено. Нужен адрес бота.')
      return
    }
    try {
      await navigator.clipboard.writeText(invite)
      setCopied(true)
    } catch {
      setError('Не удалось скопировать ссылку.')
    }
  }

  async function addPlace() {
    if (!selectedPlace) return
    setBusy(true)
    setPlaceError('')
    try {
      await onAddPlace(
        label.trim() || selectedPlace.title,
        selectedPlace.latitude,
        selectedPlace.longitude,
        selectedPlace.addressText,
      )
      setLabel('')
      setSelectedPlace(null)
      setPlaceOpen(false)
    } catch {
      setPlaceError('Не удалось сохранить место. Попробуй ещё раз.')
    } finally {
      setBusy(false)
    }
  }

  async function changePlace(action: () => Promise<void>) {
    setBusy(true)
    setError('')
    try {
      await action()
    } catch {
      setError('Не удалось изменить место. Попробуй ещё раз.')
    } finally {
      setBusy(false)
    }
  }

  async function changeCity() {
    setBusy(true)
    setError('')
    try {
      await onChangeCity(active.id, nextCity)
      setChangeCityOpen(false)
      setCityResultLeaving(false)
      setCityResult('Город изменён.')
    } catch {
      setError('Не удалось изменить город. Попробуй ещё раз.')
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
  const cityLocations = locations.filter(
    (item) => item.city_slug === active.city_slug && item.kind !== 'CURRENT',
  )
  const selectedGroup = groups.find((group) => group.id === openGroupId)

  return (
    <section className="page-stack company-page">
      <SectionHeader
        title="Компания"
        action={
          <button
            type="button"
            className="company-page__new"
            aria-label="Новая компания"
            onClick={onNew}
          >
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <rect width="24" height="24" rx="5" fill="currentColor" />
              <path d="M12 20V4M4 12h16" stroke="white" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </button>
        }
      />

      <section className="company-panel" aria-labelledby="company-list-title">
        <h2 id="company-list-title">Мои компании</h2>
        <div className="company-group-list">
          {groups.map((group) => (
            <div
              className={'company-group-card' + (active.id === group.id ? ' is-active' : '')}
              key={group.id}
            >
              <div className="company-group-card__header">
                <span className="company-group-card__icon" aria-hidden="true">
                  <img src={groupIcon} alt="" />
                </span>
                <span className="company-group-card__name">{group.name}</span>
                <span className="company-group-card__count">
                  {formatMembers(group.member_count)}
                </span>
                {active.id === group.id ? (
                  <span className="company-group-card__current">Текущая</span>
                ) : null}
                <button
                  type="button"
                  className="company-group-card__toggle"
                  aria-label={`Открыть компанию ${group.name}${active.id === group.id ? ', текущая' : ''}`}
                  onClick={() => {
                    setOpenGroupId(group.id)
                    onSelect(group)
                    setGroupOpen(true)
                  }}
                >
                  <img src={arrowIcon} alt="" />
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section
        className="company-panel company-panel--places"
        aria-labelledby="company-places-title"
      >
        <div className="company-panel__heading">
          <h2 id="company-places-title">Мои места</h2>
          <span className="company-panel__city">
            {cityName} · {active.name}
          </span>
          <p>
            {cityLocations.length
              ? 'Адрес виден только тебе'
              : 'Сохрани удобные точки — например, дом или работу — чтобы выбирать радиус поиска от них.'}
          </p>
        </div>
        {cityLocations.length ? (
          <div className="company-place-list">
            {cityLocations.map((place) => (
              <div className="company-place" key={place.id}>
                <div className="company-place__text">
                  <strong>{place.label}</strong>
                  {place.address_text ? <span>{place.address_text}</span> : null}
                </div>
                <button
                  type="button"
                  aria-label={`Изменить место ${place.label}`}
                  onClick={() => {
                    setEditingPlace(place)
                    setEditingLabel(place.label)
                    setError('')
                    setEditPlaceOpen(true)
                  }}
                >
                  <img src={editIcon} alt="" />
                </button>
              </div>
            ))}
          </div>
        ) : null}
        <button
          type="button"
          className="company-primary-button"
          onClick={() => {
            setPlaceError('')
            setPlaceOpen(true)
          }}
        >
          Добавить место
        </button>
      </section>

      {cityResult ? (
        <div
          className="company-toast"
          data-state={cityResultLeaving ? 'closing' : 'open'}
          role="status"
        >
          {cityResult}
        </div>
      ) : null}

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

      <CompanyPopup
        open={groupOpen}
        title={selectedGroup?.name || active.name}
        onClose={() => setGroupOpen(false)}
      >
        {selectedGroup ? (
          <>
            <button
              type="button"
              className="company-popup__city"
              aria-label={`Изменить город компании ${selectedGroup.name}`}
              onClick={() => {
                setGroupOpen(false)
                setError('')
                setNextCity(selectedGroup.city_slug)
                setChangeCityOpen(true)
              }}
            >
              <span>{cityName}</span>
              <img src={editIcon} alt="" />
            </button>
            <div className="company-group-card__members">
              <p>{formatMembers(selectedGroup.member_count)}</p>
              {active.id !== selectedGroup.id || membersStatus === 'loading' ? (
                <p role="status">Загружаем участников…</p>
              ) : null}
              {active.id === selectedGroup.id && membersStatus === 'error' ? (
                <p className="form-error" role="alert">
                  Не удалось загрузить участников.
                </p>
              ) : null}
              {active.id === selectedGroup.id && membersStatus === 'ready' ? (
                <ul>
                  {members.map((member) => (
                    <li key={member.id}>
                      <span className="company-group-card__person">
                        <span className="company-group-card__avatar" aria-hidden="true">
                          <img src={avatarCircle} alt="" />
                          <span>{member.display_name.trim().slice(0, 1).toUpperCase()}</span>
                        </span>
                        <span>{member.display_name}</span>
                      </span>
                      {member.is_me ? <small>Ты</small> : null}
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
            <button
              type="button"
              className="company-primary-button"
              onClick={() => {
                setGroupOpen(false)
                setError('')
                setCopied(false)
                setInviteOpen(true)
              }}
            >
              Пригласить друзей
            </button>
          </>
        ) : null}
      </CompanyPopup>

      <CompanyPopup
        open={createOpen}
        title="Создать компанию"
        description="Позови друзей, и ДВИЖ подберёт план, который подходит всем."
        className="company-create-popup"
        busy={createBusy}
        onClose={onCreateClose}
      >
        <CreateCompany
          inline
          chatAvailable={chatAvailable}
          onCreated={onCreated}
          onCancel={onCreateClose}
          onBusyChange={setCreateBusy}
        />
      </CompanyPopup>

      <CompanyPopup
        open={placeOpen}
        title="Добавить место?"
        busy={busy}
        onClose={() => setPlaceOpen(false)}
      >
        <label className="company-place-dialog__name">
          <span className="visually-hidden">Название</span>
          <input
            value={label}
            maxLength={80}
            placeholder="Название"
            onChange={(event) => setLabel(event.target.value)}
          />
        </label>
        <PlacePicker
          city={active.city_slug}
          value={selectedPlace}
          onSelect={setSelectedPlace}
          compact
        />
        {placeError ? (
          <p className="form-error" role="alert">
            {placeError}
          </p>
        ) : null}
        <button
          type="button"
          className="company-primary-button"
          disabled={busy || !selectedPlace}
          onClick={() => void addPlace()}
        >
          {busy ? 'Сохраняем…' : 'Сохранить'}
        </button>
      </CompanyPopup>

      <CompanyPopup
        open={editPlaceOpen}
        title="Изменить место"
        busy={busy}
        onClose={() => setEditPlaceOpen(false)}
      >
        {editingPlace ? (
          <>
            <label className="company-place-dialog__name">
              Название
              <input
                value={editingLabel}
                maxLength={80}
                onChange={(event) => setEditingLabel(event.target.value)}
              />
            </label>
            {editingPlace.address_text ? (
              <p className="company-place-dialog__address">{editingPlace.address_text}</p>
            ) : null}
            {editingPlace.is_default ? (
              <p className="company-place-dialog__address">По умолчанию</p>
            ) : null}
            {error ? (
              <p className="form-error" role="alert">
                {error}
              </p>
            ) : null}
            <button
              type="button"
              className="company-primary-button"
              disabled={busy || !editingLabel.trim()}
              onClick={() =>
                void changePlace(async () => {
                  await onRenamePlace(editingPlace.id, editingLabel.trim())
                  setEditPlaceOpen(false)
                })
              }
            >
              Сохранить
            </button>
            {!editingPlace.is_default ? (
              <button
                type="button"
                className="company-place-dialog__secondary"
                disabled={busy}
                onClick={() =>
                  void changePlace(async () => {
                    await onDefaultPlace(editingPlace.id)
                    setEditPlaceOpen(false)
                  })
                }
              >
                Сделать основным
              </button>
            ) : null}
            <button
              type="button"
              className="company-place-dialog__danger"
              disabled={busy}
              onClick={() =>
                void changePlace(async () => {
                  await onDeletePlace(editingPlace.id)
                  setEditPlaceOpen(false)
                })
              }
            >
              Удалить место
            </button>
          </>
        ) : null}
      </CompanyPopup>

      <CompanyPopup
        open={changeCityOpen}
        title="Сменить город компании?"
        description="Активные сигналы отменятся, а автосигналы этой компании будут поставлены на паузу."
        busy={busy}
        onClose={() => setChangeCityOpen(false)}
      >
        <CityPicker cities={cities} value={nextCity} onChange={setNextCity} />
        {error ? (
          <p className="form-error" role="alert">
            {error}
          </p>
        ) : null}
        <button
          type="button"
          className="company-primary-button"
          disabled={busy || nextCity === active.city_slug}
          onClick={() => void changeCity()}
        >
          {busy ? 'Меняем…' : 'Сменить город'}
        </button>
        <button
          type="button"
          className="company-place-dialog__secondary"
          disabled={busy}
          onClick={() => setChangeCityOpen(false)}
        >
          Отмена
        </button>
      </CompanyPopup>

      <CompanyPopup
        open={inviteOpen}
        title="Позвать друзей"
        description={`Приглашение в «${active.name}»`}
        onClose={() => setInviteOpen(false)}
      >
        {!invite ? (
          <p className="form-error" role="alert">
            Приглашение станет доступно после настройки адреса MAX-бота.
          </p>
        ) : null}
        {error ? (
          <p className="form-error" role="alert">
            {error}
          </p>
        ) : null}
        <button
          type="button"
          className="company-primary-button"
          disabled={!invite}
          onClick={() => void shareInvite()}
        >
          {window.WebApp?.shareMaxContent
            ? 'Поделиться в MAX'
            : copied
              ? 'Скопировано'
              : 'Скопировать ссылку'}
        </button>
        {window.WebApp?.shareMaxContent ? (
          <button
            type="button"
            className="company-place-dialog__secondary"
            onClick={() => void copyInvite()}
          >
            {copied ? 'Скопировано' : 'Скопировать ссылку'}
          </button>
        ) : null}
      </CompanyPopup>
    </section>
  )
}
