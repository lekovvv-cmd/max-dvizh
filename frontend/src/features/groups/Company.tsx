import { Button } from '@maxhub/max-ui'
import { useState } from 'react'
import { setDemoUser } from '../../app/api'
import type { Group } from '../../app/api'

export function Company({ groups, active, onSelect }: { groups: Group[]; active: Group; onSelect: (group: Group) => void }) {
  const [copied, setCopied] = useState(false); const [person, setPerson] = useState('anton')
  const invite = active.invite_url || `${window.location.origin}#startapp=${active.invite_token}`
  async function copyInvite() { await navigator.clipboard?.writeText(invite); setCopied(true) }
  return <section><p className="section-kicker">Компании</p><h1>Свои люди</h1><p className="screen-intro">Офферы и условия остаются только внутри выбранной компании.</p><div className="groups-list">{groups.map(group => <button key={group.id} className={`group-cell ${group.id === active.id ? 'group-cell--active' : ''}`} onClick={() => onSelect(group)}><span><strong>{group.name}</strong><small>{group.member_count} участника</small></span>{group.id === active.id ? <b>Текущая</b> : <span aria-hidden="true">›</span>}</button>)}</div><section className="invite-card"><h2>Пригласить в «{active.name}»</h2><p>Отправь приглашение прямо в MAX — ссылка не раскрывает условия участников.</p><Button variant="primary" onClick={() => void copyInvite()}>{copied ? 'Ссылка скопирована' : 'Пригласить'}</Button></section><section className="dev-tools"><p>Dev / demo tools</p><label>Демо-пользователь<input value={person} onChange={event => setPerson(event.target.value)} /></label><Button variant="secondary" onClick={() => { setDemoUser(person); window.location.reload() }}>Сменить пользователя</Button></section></section>
}
