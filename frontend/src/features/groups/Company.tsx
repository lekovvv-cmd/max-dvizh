import { Button, Input } from '@maxhub/max-ui'
import { useState } from 'react'
import { setDemoUser } from '../../app/api'
import type { Group, Location } from '../../app/api'

export function Company({ groups, active, locations, mode, onSelect, onNew, onAddPlace }: { groups: Group[]; active: Group; locations: Location[]; mode: string; onSelect: (group: Group) => void; onNew: () => void; onAddPlace: (label: string) => Promise<Location> }) {
  const [copied, setCopied] = useState(false)
  const [person, setPerson] = useState('anton')
  const [label, setLabel] = useState('Дом')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
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
  return <section>
    <h1>Компании</h1>
    <div className="groups-list">{groups.map(group => <button key={group.id} className={`group-cell ${group.id === active.id ? 'group-cell--active' : ''}`} onClick={() => onSelect(group)}><span><strong>{group.name}</strong><small>{group.member_count} участника</small></span>{group.id === active.id ? <b>Текущая</b> : <span aria-hidden="true">›</span>}</button>)}</div>
    <Button variant="secondary" onClick={onNew}>+ Новая компания</Button>
    <section className="invite-card"><h2>Пригласить в «{active.name}»</h2><Button variant="primary" onClick={() => void shareInvite()}>{window.WebApp?.shareMaxContent ? 'Поделиться в MAX' : copied ? 'Ссылка скопирована' : 'Скопировать приглашение'}</Button></section>
    <section className="invite-card"><h2>Мои места</h2><p>Места видны только тебе. Для расстояния используются настоящие координаты устройства.</p>{locations.filter(item => item.city_slug === active.city_slug).map(place => <p key={place.id}>{place.label}</p>)}<label>Название места<Input value={label} maxLength={80} onChange={event => setLabel(event.target.value)} /></label><Button variant="secondary" loading={busy} disabled={busy || !label.trim()} onClick={() => void addPlace()}>Использовать мою геопозицию</Button></section>
    {error ? <p className="form-error" role="alert">{error}</p> : null}
    {mode === 'development' ? <section className="dev-tools"><p>Dev / demo tools</p><label>Демо-пользователь<input value={person} onChange={event => setPerson(event.target.value)} /></label><Button variant="secondary" onClick={() => { setDemoUser(person); window.location.reload() }}>Сменить пользователя</Button></section> : null}
  </section>
}
