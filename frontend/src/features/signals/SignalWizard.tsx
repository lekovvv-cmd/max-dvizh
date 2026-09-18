import { Button, Input } from '@maxhub/max-ui'
import { useState } from 'react'
import { api } from '../../app/api'
import type { Group, Intent, Location } from '../../app/api'
import { activityLabel } from '../../shared/lib/format'
import { formatLocalDateTimeInput, groupSizeRange, parseOptionalInteger, parseOptionalRadius, type GroupSizeChoice } from '../../shared/lib/signalForm'

type When = 'evening' | 'after20' | 'tomorrow' | 'weekend' | 'custom'
const categories = ['games', 'sport', 'exhibition', 'concert', 'wellness']
const initialWhen = (): When => new Date().getHours() >= 20 ? 'tomorrow' : new Date().getHours() >= 18 ? 'after20' : 'evening'

function rangeFor(when: When): [Date, Date] {
  const start = new Date()
  if (when === 'weekend') start.setDate(start.getDate() + ((6 - start.getDay() + 7) % 7))
  else if (when === 'tomorrow') start.setDate(start.getDate() + 1)
  start.setHours(when === 'after20' ? 20 : 18, 0, 0, 0)
  if (start <= new Date()) start.setDate(start.getDate() + 1)
  const end = new Date(start)
  end.setHours(23, 0, 0, 0)
  return [start, end]
}

function Choice({ selected, onClick, children, disabled = false }: { selected: boolean; onClick: () => void; children: React.ReactNode; disabled?: boolean }) {
  return <button type="button" className={`choice ${selected ? 'choice--selected' : ''}`} onClick={onClick} aria-pressed={selected} disabled={disabled}>{children}</button>
}

export function SignalWizard({ group, groups, locations, activeBatch, onAddPlace, onDone }: { group: Group; groups: Group[]; locations: Location[]; activeBatch?: Intent[]; onAddPlace: (city: string | null) => void; onDone: () => void }) {
  const existing = activeBatch?.[0]
  const [when, setWhen] = useState<When>(existing ? 'custom' : initialWhen())
  const [start, setStart] = useState(existing?.available_from ? formatLocalDateTimeInput(new Date(existing.available_from)) : formatLocalDateTimeInput(rangeFor(initialWhen())[0]))
  const [end, setEnd] = useState(existing?.available_to ? formatLocalDateTimeInput(new Date(existing.available_to)) : formatLocalDateTimeInput(rangeFor(initialWhen())[1]))
  const [selectedCategories, setSelectedCategories] = useState<string[]>(existing?.activity_categories || ['any'])
  const [groupIds, setGroupIds] = useState<string[]>(activeBatch?.map(intent => intent.group_id) || [group.id])
  const [conditionsOpen, setConditionsOpen] = useState(Boolean(existing?.budget_max || existing?.radius_km || existing?.max_people))
  const [budget, setBudget] = useState(existing?.budget_max?.toString() || '')
  const [radius, setRadius] = useState(existing?.radius_km?.toString() || '')
  const [locationId, setLocationId] = useState(existing?.origin_location_id || '')
  const [people, setPeople] = useState<GroupSizeChoice>(existing?.max_people === 5 && existing.min_people === 5 ? 'exactly-5' : existing?.min_people === 5 ? '5+' : existing?.min_people === 3 ? '3+' : 'any')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const budgetValue = parseOptionalInteger(budget, 0, 100_000)
  const radiusValue = parseOptionalRadius(radius)
  const selectedGroups = groups.filter(item => groupIds.includes(item.id))
  const cityMismatch = new Set(selectedGroups.map(item => item.city_slug)).size > 1
  const selectedCity = cityMismatch ? null : selectedGroups[0]?.city_slug
  const places = locations.filter(location => location.city_slug === selectedCity)
  const selectedLocationId = places.some(place => place.id === locationId) ? locationId : places.find(place => place.is_default)?.id || places[0]?.id || ''

  function chooseWhen(value: When) {
    setWhen(value)
    if (value !== 'custom') {
      const [from, to] = rangeFor(value)
      setStart(formatLocalDateTimeInput(from))
      setEnd(formatLocalDateTimeInput(to))
    }
  }
  function toggleCategory(value: string) {
    setSelectedCategories(current => value === 'any' ? ['any'] : current.includes(value) ? (current.filter(item => item !== value).length ? current.filter(item => item !== value) : ['any']) : [...current.filter(item => item !== 'any'), value])
  }
  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (cityMismatch || groupIds.length === 0 || budgetValue === undefined || radiusValue === undefined || (radiusValue !== null && !selectedLocationId)) return
    const from = new Date(start); const to = new Date(end)
    if (!Number.isFinite(from.getTime()) || !Number.isFinite(to.getTime()) || from >= to || to <= new Date()) { setError('Укажи время, которое ещё не прошло'); return }
    setBusy(true); setError('')
    const [minPeople, maxPeople] = groupSizeRange(people)
    const body = { group_ids: groupIds, activity_categories: selectedCategories, available_from: from.toISOString(), available_to: to.toISOString(), budget_max: budgetValue, origin_location_id: radiusValue === null ? null : selectedLocationId, radius_km: radiusValue, min_people: minPeople, max_people: maxPeople }
    try {
      if (existing?.signal_batch_id) await api.editSignalBatch(existing.signal_batch_id, body)
      else await api.signalBatch(body)
      onDone()
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Не удалось подать сигнал') } finally { setBusy(false) }
  }
  return <section className="wizard" aria-labelledby="signal-title">
    <button type="button" className="back-link" onClick={onDone}>‹ Назад</button>
    <h1 id="signal-title">{existing ? 'Изменить сигнал' : 'Когда свободен?'}</h1>
    <form onSubmit={event => void submit(event)}>
      <div className="wizard__block"><h2>Когда?</h2><div className="choices">
        <Choice selected={when === 'evening'} disabled={new Date().getHours() >= 18} onClick={() => chooseWhen('evening')}>Сегодня вечером</Choice>
        <Choice selected={when === 'after20'} disabled={new Date().getHours() >= 20} onClick={() => chooseWhen('after20')}>Сегодня после 20:00</Choice>
        <Choice selected={when === 'tomorrow'} onClick={() => chooseWhen('tomorrow')}>Завтра вечером</Choice>
        <Choice selected={when === 'weekend'} onClick={() => chooseWhen('weekend')}>На выходных</Choice>
        <Choice selected={when === 'custom'} onClick={() => chooseWhen('custom')}>Выбрать время</Choice>
      </div>{when === 'custom' ? <div className="form-row"><label>С<Input type="datetime-local" value={start} onChange={event => setStart(event.target.value)} /></label><label>До<Input type="datetime-local" value={end} onChange={event => setEnd(event.target.value)} /></label></div> : null}</div>
      <div className="wizard__block"><h2>Что ок?</h2><div className="choices"><Choice selected={selectedCategories.includes('any')} onClick={() => toggleCategory('any')}>Всё равно</Choice>{categories.map(category => <Choice key={category} selected={selectedCategories.includes(category)} onClick={() => toggleCategory(category)}>{activityLabel(category)}</Choice>)}</div></div>
      <div className="wizard__block"><h2>С кем?</h2><div className="choices">{groups.map(item => <Choice key={item.id} selected={groupIds.includes(item.id)} onClick={() => setGroupIds(current => current.includes(item.id) ? current.filter(id => id !== item.id) : [...current, item.id])}>{item.name}</Choice>)}</div>{cityMismatch ? <p className="form-error">Выбери компании из одного города</p> : null}</div>
      <details className="wizard__block" open={conditionsOpen} onToggle={event => setConditionsOpen(event.currentTarget.open)}><summary>Условия</summary>
        <label>Бюджет до, ₽<Input type="number" min="0" max="100000" placeholder="Неважно" value={budget} onChange={event => setBudget(event.target.value)} /></label>
        {places.length ? <><label>Расстояние до, км<Input type="number" min="0.1" max="100" step="0.1" placeholder="Неважно" value={radius} onChange={event => setRadius(event.target.value)} /></label>{radius ? <label>Откуда<select value={selectedLocationId} onChange={event => setLocationId(event.target.value)}>{places.map(place => <option key={place.id} value={place.id}>{place.label}{place.address_text ? ` · ${place.address_text}` : ''}</option>)}</select></label> : null}<p className="form-hint">≈ расстояние по прямой, не время в пути</p></> : <p>Добавь место в выбранном городе, чтобы ограничивать расстояние. <button type="button" className="back-link" onClick={() => onAddPlace(selectedCity || null)}>Добавить место</button></p>}
        <h3>Пойдёшь, если соберётся…</h3><div className="choices"><Choice selected={people === 'any'} onClick={() => setPeople('any')}>Неважно</Choice><Choice selected={people === '3+'} onClick={() => setPeople('3+')}>Хотя бы 3</Choice><Choice selected={people === '5+'} onClick={() => setPeople('5+')}>Хотя бы 5</Choice><Choice selected={people === 'exactly-5'} onClick={() => setPeople('exactly-5')}>Ровно 5</Choice></div>
      </details>
      {budgetValue === undefined || radiusValue === undefined ? <p className="form-error">Проверь условия</p> : null}
      {radiusValue !== null && radiusValue !== undefined && !selectedLocationId ? <p className="form-error">Для расстояния выбери место в городе выбранных компаний</p> : null}
      {error ? <p className="form-error" role="alert">{error}</p> : null}
      <div className="wizard__footer"><Button stretched variant="primary" type="submit" loading={busy} disabled={busy || cityMismatch || groupIds.length === 0 || budgetValue === undefined || radiusValue === undefined || (radiusValue !== null && !selectedLocationId)}>{existing ? 'Сохранить' : 'Подать сигнал ⚡'}</Button></div>
    </form>
  </section>
}
