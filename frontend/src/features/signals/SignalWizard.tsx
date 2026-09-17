import { Button, Input } from '@maxhub/max-ui'
import { useState } from 'react'

import { api } from '../../app/api'
import type { Group, Location } from '../../app/api'
import { formatLocalDateTimeInput, groupSizeRange, parseOptionalInteger, parseOptionalRadius, type GroupSizeChoice } from '../../shared/lib/signalForm'

type Step = 1 | 2 | 3
type Budget = 'any' | '500' | '1000' | 'custom'
type Radius = 'any' | '3' | '5' | '10' | 'custom'

function Choice({ selected, onClick, children }: { selected: boolean; onClick: () => void; children: React.ReactNode }) {
  return <button type="button" className={`choice ${selected ? 'choice--selected' : ''}`} onClick={onClick} aria-pressed={selected}>{children}</button>
}

export function SignalWizard({ group, locations, addLocation, onDone }: { group: Group; locations: Location[]; addLocation: () => Promise<Location>; onDone: () => void }) {
  const [step, setStep] = useState<Step>(1)
  const [category, setCategory] = useState('other')
  const [budget, setBudget] = useState<Budget>('any')
  const [customBudget, setCustomBudget] = useState('')
  const [radius, setRadius] = useState<Radius>('any')
  const [customRadius, setCustomRadius] = useState('')
  const [locationId, setLocationId] = useState(locations[0]?.id ?? '')
  const [start, setStart] = useState(formatLocalDateTimeInput(new Date(Date.now() + 7_200_000)))
  const [end, setEnd] = useState(formatLocalDateTimeInput(new Date(Date.now() + 18_000_000)))
  const [people, setPeople] = useState<GroupSizeChoice>('3+')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const budgetValue = budget === 'custom' ? parseOptionalInteger(customBudget, 0, 100_000) : budget === 'any' ? null : Number(budget)
  const radiusValue = radius === 'custom' ? parseOptionalRadius(customRadius) : radius === 'any' ? null : Number(radius)
  const validStepOne = Boolean(start && end && new Date(start) < new Date(end))
  const validStepTwo = budgetValue !== undefined && radiusValue !== undefined && (radiusValue === null || Boolean(locationId))

  async function ensureLocation() {
    if (radiusValue === null || radiusValue === undefined || locationId) return
    const location = await addLocation()
    setLocationId(location.id)
  }

  async function submit() {
    if (!validStepOne || !validStepTwo || budgetValue === undefined || radiusValue === undefined) return
    setBusy(true); setError('')
    const groupSize = groupSizeRange(people)
    try {
      await api.signal({ group_id: group.id, city_slug: group.city_slug, activity_category: category, available_from: new Date(start).toISOString(), available_to: new Date(end).toISOString(), budget_max: budgetValue, origin_location_id: radiusValue === null ? null : locationId, radius_km: radiusValue, min_people: groupSize[0], max_people: groupSize[1], expires_at: new Date(Date.now() + 86_400_000).toISOString() })
      onDone()
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Не удалось подать сигнал') } finally { setBusy(false) }
  }

  return <section className="wizard" aria-labelledby="signal-title">
    <button className="back-link" onClick={onDone}>‹ Назад</button>
    <div className="wizard__progress" aria-label={`Шаг ${step} из 3`}><span>Шаг {step} из 3</span><div><i className={step >= 1 ? 'is-done' : ''} /><i className={step >= 2 ? 'is-done' : ''} /><i className={step >= 3 ? 'is-done' : ''} /></div></div>
    {step === 1 ? <>
      <p className="section-kicker">Новый сигнал</p><h1 id="signal-title">Когда и что?</h1><p className="screen-intro">Расскажи, для какого ДВИЖа ты открыт.</p>
      <div className="wizard__block"><label>Когда двигаемся?<Input type="datetime-local" value={start} onChange={event => setStart(event.target.value)} /></label><label>До<Input type="datetime-local" value={end} onChange={event => setEnd(event.target.value)} /></label></div>
      <div className="wizard__block"><h2>Что хочется?</h2><div className="choices"><Choice selected={category === 'other'} onClick={() => setCategory('other')}>Всё равно</Choice><Choice selected={category === 'games'} onClick={() => setCategory('games')}>🎮 Игры</Choice><Choice selected={category === 'sport'} onClick={() => setCategory('sport')}>🎳 Активности</Choice><Choice selected={category === 'exhibition'} onClick={() => setCategory('exhibition')}>🎭 Культура</Choice><Choice selected={category === 'concert'} onClick={() => setCategory('concert')}>🎵 Музыка</Choice></div></div>
      {!validStepOne ? <p className="form-error">Укажи корректное окно времени.</p> : null}
      <div className="wizard__footer"><Button stretched variant="primary" disabled={!validStepOne} onClick={() => setStep(2)}>Дальше</Button></div>
    </> : null}
    {step === 2 ? <>
      <p className="section-kicker">Что важно</p><h1 id="signal-title">Условия</h1><p className="screen-intro">Ограничения необязательны — выбирай только важное.</p>
      <div className="wizard__block"><h2>Бюджет</h2><div className="choices"><Choice selected={budget === 'any'} onClick={() => setBudget('any')}>Неважно</Choice><Choice selected={budget === '500'} onClick={() => setBudget('500')}>До 500 ₽</Choice><Choice selected={budget === '1000'} onClick={() => setBudget('1000')}>До 1000 ₽</Choice><Choice selected={budget === 'custom'} onClick={() => setBudget('custom')}>Свой</Choice></div>{budget === 'custom' ? <Input aria-label="Свой бюджет" type="number" min="0" max="100000" step="1" placeholder="Сумма в рублях" value={customBudget} onChange={event => setCustomBudget(event.target.value)} /> : null}</div>
      <div className="wizard__block"><h2>Расстояние</h2><div className="choices"><Choice selected={radius === 'any'} onClick={() => setRadius('any')}>Неважно</Choice><Choice selected={radius === '3'} onClick={() => setRadius('3')}>До 3 км</Choice><Choice selected={radius === '5'} onClick={() => setRadius('5')}>До 5 км</Choice><Choice selected={radius === '10'} onClick={() => setRadius('10')}>До 10 км</Choice><Choice selected={radius === 'custom'} onClick={() => setRadius('custom')}>Свой</Choice></div>{radius === 'custom' ? <Input aria-label="Свой радиус" type="number" min="0.1" max="100" step="0.1" placeholder="Километры" value={customRadius} onChange={event => setCustomRadius(event.target.value)} /> : null}</div>
      {radiusValue !== null && radiusValue !== undefined ? <div className="wizard__block"><h2>Откуда считаем расстояние?</h2>{locations.length ? <label>Твоя точка<select value={locationId} onChange={event => setLocationId(event.target.value)}><option value="">Выбери точку</option>{locations.map(location => <option key={location.id} value={location.id}>{location.label}</option>)}</select></label> : <Button variant="secondary" onClick={() => void ensureLocation()}>Добавить мою точку</Button>}</div> : null}
      {radiusValue !== null && radiusValue !== undefined && !locationId ? <p className="form-error">Для радиуса выбери точку.</p> : null}
      {budgetValue === undefined || radiusValue === undefined ? <p className="form-error">Проверь введённые бюджет или радиус.</p> : null}
      <div className="wizard__footer wizard__footer--two"><Button variant="secondary" onClick={() => setStep(1)}>Назад</Button><Button variant="primary" disabled={!validStepTwo} onClick={() => setStep(3)}>Дальше</Button></div>
    </> : null}
    {step === 3 ? <>
      <p className="section-kicker">Компания</p><h1 id="signal-title">С кем собираемся?</h1><p className="screen-intro">Сигнал увидит только твоя компания.</p>
      <div className="company-choice"><strong>{group.name}</strong><span>{group.member_count} участника</span></div>
      <div className="wizard__block"><h2>Размер компании</h2><div className="choices"><Choice selected={people === 'any'} onClick={() => setPeople('any')}>Неважно</Choice><Choice selected={people === '3+'} onClick={() => setPeople('3+')}>3+</Choice><Choice selected={people === '5+'} onClick={() => setPeople('5+')}>5+</Choice><Choice selected={people === 'exactly-5'} onClick={() => setPeople('exactly-5')}>Ровно 5</Choice></div></div>
      {error ? <p className="form-error" role="alert">{error}</p> : null}
      <div className="wizard__footer wizard__footer--two"><Button variant="secondary" disabled={busy} onClick={() => setStep(2)}>Назад</Button><Button variant="primary" loading={busy} disabled={busy} onClick={() => void submit()}>Подать сигнал ⚡</Button></div>
    </> : null}
  </section>
}
