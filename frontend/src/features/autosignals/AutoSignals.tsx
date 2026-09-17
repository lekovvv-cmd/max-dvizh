import { Button, Input, Switch } from '@maxhub/max-ui'
import { useState } from 'react'

import { api } from '../../app/api'
import type { Group, Intent, Location } from '../../app/api'
import { activityLabel, weekDays } from '../../shared/lib/format'
import { groupSizeRange, parseOptionalInteger, parseOptionalRadius, type GroupSizeChoice } from '../../shared/lib/signalForm'
import { EmptyState } from '../../shared/ui/EmptyState'

const weekdays = [
  { value: 0, label: 'Пн' }, { value: 1, label: 'Вт' }, { value: 2, label: 'Ср' },
  { value: 3, label: 'Чт' }, { value: 4, label: 'Пт' }, { value: 5, label: 'Сб' }, { value: 6, label: 'Вс' },
]

export function AutoSignals({ group, intents, locations, onChanged }: { group: Group; intents: Intent[]; locations: Location[]; onChanged: () => void }) {
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')
  const autos = intents.filter(intent => intent.type === 'RECURRING' && intent.status !== 'CANCELLED')
  async function toggle(intent: Intent) { setError(''); try { await api.autoAction(intent.id, intent.status === 'ACTIVE' ? 'pause' : 'resume'); onChanged() } catch (reason) { setError(reason instanceof Error ? reason.message : 'Не удалось изменить автосигнал') } }
  if (creating) return <AutoSignalForm group={group} locations={locations} onDone={() => { setCreating(false); onChanged() }} onCancel={() => setCreating(false)} />
  return <section><p className="section-kicker">Автосигналы</p><h1>Позови меня, если…</h1><p className="screen-intro">Автосигнал приглашает, но никогда не записывает тебя сам.</p>{error ? <p className="form-error" role="alert">{error}</p> : null}
    {autos.length ? <div className="autos-list">{autos.map(intent => <article className="autosignal-card" key={intent.id}><div><h2>⚡ {intent.name || 'Мой ДВИЖ'}</h2><p>{weekDays(intent.weekdays)}{intent.local_start && intent.local_end ? ` · ${intent.local_start}–${intent.local_end}` : ''}</p><p>{group.name}</p><p>{activityLabel(intent.activity_category)}{intent.budget_max !== null ? ` · до ${intent.budget_max} ₽` : ''}{intent.radius_km !== null ? ` · до ${intent.radius_km} км` : ''}</p></div><label className="switch-control"><span className="sr-only">{intent.status === 'ACTIVE' ? 'Поставить на паузу' : 'Возобновить'} {intent.name}</span><Switch checked={intent.status === 'ACTIVE'} onChange={() => void toggle(intent)} /></label></article>)}</div> : <EmptyState title="Автосигналов пока нет">Настрой один раз — и ДВИЖ позовёт, когда условия совпадут.</EmptyState>}
    <Button className="new-auto" variant="secondary" stretched onClick={() => setCreating(true)}>+ Новый автосигнал</Button>
  </section>
}

function AutoSignalForm({ group, locations, onDone, onCancel }: { group: Group; locations: Location[]; onDone: () => void; onCancel: () => void }) {
  const [name, setName] = useState('Пятничный ДВИЖ')
  const [category, setCategory] = useState('other')
  const [selectedWeekdays, setSelectedWeekdays] = useState<number[]>([4])
  const [localStart, setLocalStart] = useState('18:00')
  const [localEnd, setLocalEnd] = useState('23:00')
  const [people, setPeople] = useState<GroupSizeChoice>('3+')
  const [budget, setBudget] = useState('')
  const [locationId, setLocationId] = useState('')
  const [radius, setRadius] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const budgetValue = parseOptionalInteger(budget, 0, 100_000)
  const radiusValue = parseOptionalRadius(radius)
  const range = groupSizeRange(people)
  const hasLocationForRadius = radiusValue === null || (radiusValue !== undefined && Boolean(locationId))
  const canSubmit = selectedWeekdays.length > 0 && /^\d{2}:\d{2}$/.test(localStart) && /^\d{2}:\d{2}$/.test(localEnd) && budgetValue !== undefined && radiusValue !== undefined && hasLocationForRadius

  function toggleWeekday(day: number) {
    setSelectedWeekdays(current => {
      if (current.includes(day)) return current.length === 1 ? current : current.filter(value => value !== day)
      return [...current, day].sort((left, right) => left - right)
    })
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (!canSubmit || budgetValue === undefined || radiusValue === undefined) return
    setBusy(true)
    setError('')
    try {
      await api.autosignal({
        group_id: group.id,
        city_slug: group.city_slug,
        name,
        activity_category: category,
        weekdays: selectedWeekdays,
        local_start: localStart,
        local_end: localEnd,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        budget_max: budgetValue,
        origin_location_id: radiusValue === null ? null : locationId,
        radius_km: radiusValue,
        min_people: range[0],
        max_people: range[1],
      })
      onDone()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Не удалось сохранить автосигнал')
    } finally {
      setBusy(false)
    }
  }

  return <section className="auto-form"><button className="back-link" onClick={onCancel}>‹ Назад</button><p className="section-kicker">Новый автосигнал</p><h1>Когда тебя звать?</h1><p className="screen-intro">Можно изменить условия позже.</p><form onSubmit={submit}>
    <label>Название<Input value={name} onChange={event => setName(event.target.value)} required /></label>
    <label>Активность<select value={category} onChange={event => setCategory(event.target.value)}><option value="other">Всё равно</option><option value="games">🎮 Игры</option><option value="sport">🎳 Активности</option><option value="exhibition">🎭 Культура</option><option value="concert">🎵 Музыка</option></select></label>
    <div className="wizard__block"><h2>Дни недели</h2><div className="choices">{weekdays.map(day => <button key={day.value} type="button" className={`choice ${selectedWeekdays.includes(day.value) ? 'choice--selected' : ''}`} aria-pressed={selectedWeekdays.includes(day.value)} onClick={() => toggleWeekday(day.value)}>{day.label}</button>)}</div></div>
    <div className="form-row"><label>С <Input type="time" value={localStart} onChange={event => setLocalStart(event.target.value)} required /></label><label>До <Input type="time" value={localEnd} onChange={event => setLocalEnd(event.target.value)} required /></label></div>
    <div className="wizard__block"><h2>Размер компании</h2><div className="choices"><button type="button" className={`choice ${people === 'any' ? 'choice--selected' : ''}`} onClick={() => setPeople('any')}>Неважно</button><button type="button" className={`choice ${people === '3+' ? 'choice--selected' : ''}`} onClick={() => setPeople('3+')}>3+</button><button type="button" className={`choice ${people === '5+' ? 'choice--selected' : ''}`} onClick={() => setPeople('5+')}>5+</button><button type="button" className={`choice ${people === 'exactly-5' ? 'choice--selected' : ''}`} onClick={() => setPeople('exactly-5')}>Ровно 5</button></div></div>
    <div className="form-row"><label>Бюджет, ₽ <Input aria-label="Бюджет" type="number" min="0" max="100000" step="1" placeholder="Неважно" value={budget} onChange={event => setBudget(event.target.value)} /></label><label>Радиус, км <Input aria-label="Радиус" type="number" min="0.1" max="100" step="0.1" placeholder="Неважно" value={radius} onChange={event => setRadius(event.target.value)} /></label></div>
    {radiusValue !== null && radiusValue !== undefined ? <label>Точка отправления<select value={locationId} required onChange={event => setLocationId(event.target.value)}><option value="">Выбери точку</option>{locations.map(location => <option value={location.id} key={location.id}>{location.label}</option>)}</select></label> : null}
    {budgetValue === undefined || radiusValue === undefined ? <p className="form-error">Проверь введённые бюджет или радиус.</p> : null}{radiusValue !== null && radiusValue !== undefined && !locationId ? <p className="form-error">Для радиуса выбери точку.</p> : null}{error ? <p className="form-error" role="alert">{error}</p> : null}
    <div className="form-actions"><Button variant="secondary" type="button" onClick={onCancel}>Отмена</Button><Button variant="primary" type="submit" loading={busy} disabled={busy || !canSubmit}>Сохранить</Button></div>
  </form></section>
}
