import { Button, Input, Switch } from '@maxhub/max-ui'
import { useState } from 'react'

import { api } from '../../app/api'
import type { Group, Intent, Location } from '../../app/api'
import { activityLabel, weekDays } from '../../shared/lib/format'
import {
  groupSizeRange,
  initialGroupSize,
  parseExactPeople,
  parseOptionalInteger,
  parseOptionalRadius,
  type GroupSizeChoice,
} from '../../shared/lib/signalForm'
import { EmptyState } from '../../shared/ui/EmptyState'
import { Icon } from '../../shared/ui/Icon'
import { SectionHeader } from '../../shared/ui/SectionHeader'

const weekdays = [
  { value: 0, label: 'Пн' },
  { value: 1, label: 'Вт' },
  { value: 2, label: 'Ср' },
  { value: 3, label: 'Чт' },
  { value: 4, label: 'Пт' },
  { value: 5, label: 'Сб' },
  { value: 6, label: 'Вс' },
]

export function AutoSignals({
  group,
  groups,
  intents,
  locations,
  onChanged,
}: {
  group: Group
  groups: Group[]
  intents: Intent[]
  locations: Location[]
  onChanged: () => void
}) {
  const [creating, setCreating] = useState(false)
  const [editing, setEditing] = useState<Intent | null>(null)
  const [error, setError] = useState('')
  const autos = intents.filter(
    (intent) => intent.type === 'RECURRING' && intent.status !== 'CANCELLED',
  )
  async function toggle(intent: Intent) {
    setError('')
    try {
      await api.autoAction(intent.id, intent.status === 'ACTIVE' ? 'pause' : 'resume')
      onChanged()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Не удалось изменить автосигнал')
    }
  }
  async function remove(intent: Intent) {
    setError('')
    try {
      await api.autoAction(intent.id, 'cancel')
      onChanged()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Не удалось удалить автосигнал')
    }
  }
  if (creating || editing)
    return (
      <AutoSignalForm
        group={group}
        groups={groups}
        editing={editing}
        locations={locations}
        onDone={() => {
          setCreating(false)
          setEditing(null)
          onChanged()
        }}
        onCancel={() => {
          setCreating(false)
          setEditing(null)
        }}
      />
    )
  return (
    <section className="page-stack">
      <SectionHeader
        title="Автосигналы"
        action={
          <button
            type="button"
            className="icon-button"
            aria-label="Новый автосигнал"
            onClick={() => setCreating(true)}
          >
            <Icon name="plus" />
          </button>
        }
      />
      {error ? (
        <p className="form-error" role="alert">
          {error}
        </p>
      ) : null}
      {autos.length ? (
        <div className="autos-list">
          {autos.map((intent) => (
            <article className="autosignal-row" key={intent.id}>
              <button
                type="button"
                className="autosignal-row__main"
                onClick={() => setEditing(intent)}
                aria-label={`Изменить ${intent.name || 'автосигнал'}`}
              >
                <strong>{intent.name || 'Мой ДВИЖ'}</strong>
                <span>
                  {weekDays(intent.weekdays)}
                  {intent.local_start && intent.local_end
                    ? ` · ${intent.local_start}–${intent.local_end}`
                    : ''}
                </span>
                <span>
                  {(intent.activity_categories || [intent.activity_category])
                    .map(activityLabel)
                    .join(', ')}{' '}
                  · {intent.group_name || groups.find((item) => item.id === intent.group_id)?.name}
                </span>
                {intent.budget_max !== null || intent.radius_km !== null ? (
                  <span>
                    {intent.budget_max !== null ? `до ${intent.budget_max} ₽` : null}
                    {intent.budget_max !== null && intent.radius_km !== null ? ' · ' : null}
                    {intent.radius_km !== null ? `${intent.radius_km} км` : null}
                  </span>
                ) : null}
              </button>
              <label className="switch-control">
                <span className="sr-only">
                  {intent.status === 'ACTIVE' ? 'Поставить на паузу' : 'Возобновить'} {intent.name}
                </span>
                <Switch checked={intent.status === 'ACTIVE'} onChange={() => void toggle(intent)} />
              </label>
              <button
                type="button"
                className="text-action text-action--danger autosignal-row__delete"
                onClick={() => void remove(intent)}
              >
                Удалить
              </button>
            </article>
          ))}
        </div>
      ) : (
        <EmptyState title="Автосигналов пока нет">
          Создай правило — приглашение придёт, когда условия совпадут.
        </EmptyState>
      )}
      {!autos.length ? (
        <Button className="new-auto" variant="primary" onClick={() => setCreating(true)}>
          Создать автосигнал
        </Button>
      ) : null}
    </section>
  )
}

function AutoSignalForm({
  group,
  groups,
  editing,
  locations,
  onDone,
  onCancel,
}: {
  group: Group
  groups: Group[]
  editing: Intent | null
  locations: Location[]
  onDone: () => void
  onCancel: () => void
}) {
  const initialSize = initialGroupSize(editing?.min_people, editing?.max_people)
  const [name, setName] = useState(editing?.name || 'Пятничный ДВИЖ')
  const [selectedCategories, setSelectedCategories] = useState<string[]>(
    editing?.activity_categories || ['any'],
  )
  const [groupId, setGroupId] = useState(editing?.group_id || group.id)
  const [selectedWeekdays, setSelectedWeekdays] = useState<number[]>(editing?.weekdays || [4])
  const [localStart, setLocalStart] = useState(editing?.local_start || '18:00')
  const [localEnd, setLocalEnd] = useState(editing?.local_end || '23:00')
  const [people, setPeople] = useState<GroupSizeChoice>(initialSize.choice)
  const [exactPeople, setExactPeople] = useState(initialSize.exactPeople)
  const [budget, setBudget] = useState(editing?.budget_max?.toString() || '')
  const [locationId, setLocationId] = useState(editing?.origin_location_id || '')
  const [radius, setRadius] = useState(editing?.radius_km?.toString() || '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const budgetValue = parseOptionalInteger(budget, 0, 100_000)
  const radiusValue = parseOptionalRadius(radius)
  const exactPeopleValue = parseExactPeople(exactPeople)
  const range = groupSizeRange(people, exactPeopleValue)
  const currentGroup = groups.find((item) => item.id === groupId) || group
  const availableLocations = locations.filter((item) => item.city_slug === currentGroup.city_slug)
  const selectedLocationId = availableLocations.some((item) => item.id === locationId)
    ? locationId
    : availableLocations.find((item) => item.is_default)?.id || availableLocations[0]?.id || ''
  const hasLocationForRadius =
    radiusValue === null || (radiusValue !== undefined && Boolean(selectedLocationId))
  const canSubmit =
    selectedWeekdays.length > 0 &&
    /^\d{2}:\d{2}$/.test(localStart) &&
    /^\d{2}:\d{2}$/.test(localEnd) &&
    budgetValue !== undefined &&
    radiusValue !== undefined &&
    range !== undefined &&
    hasLocationForRadius

  function toggleWeekday(day: number) {
    setSelectedWeekdays((current) => {
      if (current.includes(day))
        return current.length === 1 ? current : current.filter((value) => value !== day)
      return [...current, day].sort((left, right) => left - right)
    })
  }
  function toggleCategory(category: string) {
    setSelectedCategories((current) =>
      category === 'any'
        ? ['any']
        : current.includes(category)
          ? current.filter((item) => item !== category).length
            ? current.filter((item) => item !== category)
            : ['any']
          : [...current.filter((item) => item !== 'any'), category],
    )
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (!canSubmit || budgetValue === undefined || radiusValue === undefined || range === undefined)
      return
    setBusy(true)
    setError('')
    try {
      const body = {
        group_id: groupId,
        name,
        activity_category: selectedCategories[0],
        activity_categories: selectedCategories,
        weekdays: selectedWeekdays,
        local_start: localStart,
        local_end: localEnd,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        budget_max: budgetValue,
        origin_location_id: radiusValue === null ? null : selectedLocationId,
        radius_km: radiusValue,
        min_people: range[0],
        max_people: range[1],
      }
      if (editing) await api.editAutosignal(editing.id, body)
      else await api.autosignal(body)
      onDone()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Не удалось сохранить автосигнал')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="auto-form">
      <button className="back-link" onClick={onCancel}>
        ← Назад
      </button>
      <h1>{editing ? 'Автосигнал' : 'Новый автосигнал'}</h1>
      <form onSubmit={submit}>
        <label>
          Название
          <Input value={name} onChange={(event) => setName(event.target.value)} required />
        </label>
        <label>
          Компания
          <select
            value={groupId}
            onChange={(event) => {
              setGroupId(event.target.value)
              setLocationId('')
              setRadius('')
            }}
          >
            {groups.map((item) => (
              <option value={item.id} key={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
        <div className="form-section">
          <h2>Что ок</h2>
          <div className="choices">
            {['any', 'games', 'sport', 'exhibition', 'concert', 'wellness'].map((category) => (
              <button
                type="button"
                key={category}
                className={`choice ${selectedCategories.includes(category) ? 'choice--selected' : ''}`}
                aria-pressed={selectedCategories.includes(category)}
                onClick={() => toggleCategory(category)}
              >
                {activityLabel(category)}
              </button>
            ))}
          </div>
        </div>
        <div className="form-section">
          <h2>Расписание</h2>
          <div className="choices choices--weekdays">
            {weekdays.map((day) => (
              <button
                key={day.value}
                type="button"
                className={`choice ${selectedWeekdays.includes(day.value) ? 'choice--selected' : ''}`}
                aria-pressed={selectedWeekdays.includes(day.value)}
                onClick={() => toggleWeekday(day.value)}
              >
                {day.label}
              </button>
            ))}
          </div>
        </div>
        <div className="form-row">
          <label>
            С{' '}
            <Input
              type="time"
              value={localStart}
              onChange={(event) => setLocalStart(event.target.value)}
              required
            />
          </label>
          <label>
            До{' '}
            <Input
              type="time"
              value={localEnd}
              onChange={(event) => setLocalEnd(event.target.value)}
              required
            />
          </label>
        </div>
        <div className="form-section">
          <h2>Условия</h2>
          <div className="form-row">
            <label>
              Бюджет, ₽{' '}
              <Input
                aria-label="Бюджет"
                type="number"
                min="0"
                max="100000"
                step="1"
                placeholder="Неважно"
                value={budget}
                onChange={(event) => setBudget(event.target.value)}
              />
            </label>
            <label>
              Радиус, км{' '}
              <Input
                aria-label="Радиус"
                type="number"
                min="0.1"
                max="100"
                step="0.1"
                placeholder="Неважно"
                value={radius}
                onChange={(event) => setRadius(event.target.value)}
              />
            </label>
          </div>
          <h3>Сколько человек</h3>
          <div className="choices">
            <button
              type="button"
              className={`choice ${people === 'any' ? 'choice--selected' : ''}`}
              aria-pressed={people === 'any'}
              onClick={() => setPeople('any')}
            >
              Неважно
            </button>
            <button
              type="button"
              className={`choice ${people === '3+' ? 'choice--selected' : ''}`}
              aria-pressed={people === '3+'}
              onClick={() => setPeople('3+')}
            >
              Хотя бы 3
            </button>
            <button
              type="button"
              className={`choice ${people === '5+' ? 'choice--selected' : ''}`}
              aria-pressed={people === '5+'}
              onClick={() => setPeople('5+')}
            >
              Хотя бы 5
            </button>
            <button
              type="button"
              className={`choice ${people === 'exact' ? 'choice--selected' : ''}`}
              aria-pressed={people === 'exact'}
              onClick={() => setPeople('exact')}
            >
              Ровно N
            </button>
          </div>
          {people === 'exact' ? (
            <label>
              Сколько человек?
              <Input
                aria-label="Сколько человек?"
                type="number"
                min="2"
                max="12"
                step="1"
                value={exactPeople}
                onChange={(event) => setExactPeople(event.target.value)}
              />
            </label>
          ) : null}
          {range === undefined ? (
            <p className="form-error">Укажи целое число участников от 2 до 12</p>
          ) : null}
        </div>
        {radiusValue !== null && radiusValue !== undefined ? (
          <label>
            Моё место
            <select
              value={selectedLocationId}
              required
              onChange={(event) => setLocationId(event.target.value)}
            >
              <option value="">Выбери место</option>
              {availableLocations.map((location) => (
                <option value={location.id} key={location.id}>
                  {location.label}
                  {location.address_text ? ` · ${location.address_text}` : ''}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        {!availableLocations.length ? (
          <p>Добавь место в «Компания», чтобы ограничивать расстояние.</p>
        ) : null}
        {budgetValue === undefined || radiusValue === undefined ? (
          <p className="form-error">Проверь введённые бюджет или радиус.</p>
        ) : null}
        {radiusValue !== null && radiusValue !== undefined && !selectedLocationId ? (
          <p className="form-error">Для радиуса выбери точку.</p>
        ) : null}
        {error ? (
          <p className="form-error" role="alert">
            {error}
          </p>
        ) : null}
        <div className="form-actions">
          <Button variant="secondary" type="button" onClick={onCancel}>
            Отмена
          </Button>
          <Button variant="primary" type="submit" loading={busy} disabled={busy || !canSubmit}>
            Сохранить
          </Button>
        </div>
      </form>
    </section>
  )
}
