import { Button, Input } from '@maxhub/max-ui'
import { useEffect, useState } from 'react'
import { api, setDemoUser } from '../../app/api'
import type { Group, GroupCityUpdateResult, Location } from '../../app/api'
import { ConfirmDialog } from '../../shared/ui/ConfirmDialog'
import { Icon } from '../../shared/ui/Icon'
import { formatPeople } from '../../shared/lib/format'
import { SectionHeader } from '../../shared/ui/SectionHeader'

export function Company({ groups, active, locations, mode, onSelect, onNew, onChangeCity, onAddPlace, onRenamePlace, onDefaultPlace, onDeletePlace }: { groups: Group[]; active: Group; locations: Location[]; mode: string; onSelect: (group: Group) => void; onNew: () => void; onChangeCity: (groupId: string, city: string) => Promise<GroupCityUpdateResult>; onAddPlace: (label: string) => Promise<Location>; onRenamePlace: (id: string, label: string) => Promise<void>; onDefaultPlace: (id: string) => Promise<void>; onDeletePlace: (id: string) => Promise<void> }) {
  const [copied, setCopied] = useState(false)
  const [person, setPerson] = useState('anton')
  const [label, setLabel] = useState('Дом')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editingLabel, setEditingLabel] = useState('')
  const [placeMenuId, setPlaceMenuId] = useState<string | null>(null)
  const [cities, setCities] = useState<{ slug: string; name: string }[]>([])
  const [changeCityOpen, setChangeCityOpen] = useState(false)
  const [nextCity, setNextCity] = useState(active.city_slug)
  const [cityResult, setCityResult] = useState('')
  useEffect(() => { void api.cities().then(setCities).catch(() => setError('Не удалось загрузить список городов')) }, [])
  useEffect(() => { setNextCity(active.city_slug) }, [active.city_slug])
  useEffect(() => { setCityResult('') }, [active.id])
  const invite = active.invite_url || `${window.location.origin}#startapp=${active.invite_token}`
  async function shareInvite() {
    setError('')
    try {
      if (window.WebApp?.shareMaxContent) window.WebApp.shareMaxContent({ text: `Присоединяйся к «${active.name}» в ДВИЖе`, link: invite })
      else { await navigator.clipboard.writeText(invite); setCopied(true) }
    } catch { setError('Не удалось поделиться. Скопируй приглашение вручную.') }
  }
  async function addPlace() {
    setBusy(true); setError('')
    try { await onAddPlace(label) } catch (reason) { setError(reason instanceof Error ? reason.message : 'Геопозиция недоступна. Расстояние останется выключенным.') } finally { setBusy(false) }
  }
  async function changePlace(action: () => Promise<void>) {
    setBusy(true); setError('')
    try { await action() } catch (reason) { setError(reason instanceof Error ? reason.message : 'Не удалось изменить место') } finally { setBusy(false) }
  }
  async function changeCity() {
    setBusy(true); setError('')
    try {
      const result = await onChangeCity(active.id, nextCity)
      setChangeCityOpen(false)
      setCityResult(`Город изменён. Отменено сигналов: ${result.cancelled_signals}. Автосигналов на паузе: ${result.paused_autosignals}. Закрыто вариантов: ${result.cancelled_plans}.`)
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Не удалось изменить город') } finally { setBusy(false) }
  }
  const cityName = cities.find(city => city.slug === active.city_slug)?.name || active.city_slug
  const cityLocations = locations.filter(item => item.city_slug === active.city_slug)
  return <section className="page-stack company-page">
    <SectionHeader title="Компания" action={<button type="button" className="icon-button" aria-label="Новая компания" onClick={onNew}><Icon name="plus" /></button>} />
    <div className="company-overview"><strong>{active.name}</strong><span>{formatPeople(active.member_count)} · {cityName}</span></div>
    {groups.length > 1 ? <section className="settings-section"><h2>Мои компании</h2><div className="groups-list">{groups.map(group => <button key={group.id} className={`group-cell ${group.id === active.id ? 'group-cell--active' : ''}`} onClick={() => onSelect(group)}><span><strong>{group.name}</strong><small>{formatPeople(group.member_count)}</small></span>{group.id === active.id ? <b>Текущая</b> : <Icon name="chevron" size={18} />}</button>)}</div></section> : null}
    <section className="settings-section"><div className="settings-section__head"><div><h2>Участники и приглашение</h2><p>Добавь друзей в «{active.name}».</p></div><button type="button" className="text-action" onClick={() => void shareInvite()}>{window.WebApp?.shareMaxContent ? 'Поделиться' : copied ? 'Скопировано' : 'Пригласить'}</button></div></section>
    <section className="settings-section"><div className="settings-section__head"><div><h2>Мои места</h2><p>Видны только тебе.</p></div></div>
      {cityLocations.length ? <div className="saved-places">{cityLocations.map(place => <div className="saved-place" key={place.id}>
        <div className="saved-place__content">{editingId === place.id ? <label>Название места<Input value={editingLabel} maxLength={80} onChange={event => setEditingLabel(event.target.value)} /></label> : <><strong>{place.label}</strong>{place.is_default ? <span className="quiet-label">По умолчанию</span> : null}{place.address_text ? <p>{place.address_text}</p> : null}</>}</div>
        {editingId === place.id ? <div className="saved-place__actions"><Button variant="primary" disabled={busy || !editingLabel.trim()} onClick={() => void changePlace(async () => { await onRenamePlace(place.id, editingLabel.trim()); setEditingId(null) })}>Сохранить</Button><Button variant="secondary" disabled={busy} onClick={() => setEditingId(null)}>Отмена</Button></div> : <><button type="button" className="icon-button icon-button--quiet" aria-label={`Действия с местом ${place.label}`} aria-expanded={placeMenuId === place.id} onClick={() => setPlaceMenuId(current => current === place.id ? null : place.id)}><Icon name="more" /></button>{placeMenuId === place.id ? <div className="row-menu"><button type="button" onClick={() => { setEditingId(place.id); setEditingLabel(place.label); setPlaceMenuId(null) }}>Переименовать</button>{!place.is_default ? <button type="button" onClick={() => void changePlace(async () => { await onDefaultPlace(place.id); setPlaceMenuId(null) })}>Сделать основным</button> : null}<button type="button" className="danger" onClick={() => void changePlace(async () => { await onDeletePlace(place.id); setPlaceMenuId(null) })}>Удалить</button></div> : null}</>}
      </div>)}</div> : <p className="empty-copy">Сохранённых мест пока нет. Без них расстояние в сигнале недоступно.</p>}
      <details className="add-place"><summary>+ Добавить место</summary><div className="add-place__form"><label>Название<Input value={label} maxLength={80} onChange={event => setLabel(event.target.value)} /></label><Button variant="secondary" loading={busy} disabled={busy || !label.trim()} onClick={() => void addPlace()}>Использовать геопозицию</Button></div></details>
    </section>
    <section className="settings-section"><div className="settings-section__head"><div><h2>Город компании</h2><p>{cityName}</p></div><Button variant="secondary" disabled={!cities.length || busy} onClick={() => { setNextCity(active.city_slug); setChangeCityOpen(true) }}>Изменить</Button></div>{cityResult ? <p className="inline-notice" role="status">{cityResult}</p> : null}</section>
    {error ? <p className="form-error" role="alert">{error}</p> : null}
    {mode === 'development' ? <section className="dev-tools"><p>Dev / demo tools</p><label>Демо-пользователь<input value={person} onChange={event => setPerson(event.target.value)} /></label><Button variant="secondary" onClick={() => { setDemoUser(person); window.location.reload() }}>Сменить пользователя</Button></section> : null}
    {changeCityOpen ? <ConfirmDialog title="Сменить город компании?" description="Активные сигналы отменятся, а автосигналы этой компании будут поставлены на паузу." confirmLabel="Сменить город" cancelLabel="Отмена" busy={busy} confirmDisabled={nextCity === active.city_slug} onConfirm={() => void changeCity()} onCancel={() => setChangeCityOpen(false)}><label>Город<select value={nextCity} onChange={event => setNextCity(event.target.value)}>{cities.map(city => <option key={city.slug} value={city.slug}>{city.name}</option>)}</select></label></ConfirmDialog> : null}
  </section>
}
