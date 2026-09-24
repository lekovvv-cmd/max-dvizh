import { useEffect, useRef, useState } from 'react'
import { ApiTimeoutError, api } from '../../app/api'
import type { Group, Intent, Location } from '../../app/api'
import { activityCatalog, searchActivities } from '../../shared/lib/activityCatalog'
import { activityLabel, formatPeople, formatSignalWindow, weekDays } from '../../shared/lib/format'
import {
  formatLocalDateTimeInput,
  groupSizeRange,
  initialGroupSize,
  parseExactPeople,
  parseOptionalInteger,
  parseOptionalRadius,
  type GroupSizeChoice,
} from '../../shared/lib/signalForm'
import { ConfirmDialog } from '../../shared/ui/ConfirmDialog'
import { Icon } from '../../shared/ui/Icon'
import { PulseMark } from '../../shared/ui/PulseMark'

type When = 'today' | 'tomorrow' | 'weekend' | 'custom'
export type SignalAdjustment = 'tomorrow' | 'any' | 'radius' | 'budget' | 'repeat' | null
type Form = {
  when: When
  start: string
  end: string
  categories: string[]
  groupIds: string[]
  budget: string
  radius: string
  locationId: string
  people: GroupSizeChoice
  exactPeople: string
  repeat: boolean
  weekdays: number[]
  localStart: string
  localEnd: string
}

const quickCategories = ['any', 'games', 'sport', 'concert']
const weekdays = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
const budgetOptions = ['', '500', '1000', '2000', 'custom']
const radiusOptions = ['', '2', '5', '10']

function rangeFor(when: Exclude<When, 'custom'>): [Date, Date] {
  const start = new Date()
  if (when === 'tomorrow') start.setDate(start.getDate() + 1)
  if (when === 'weekend') {
    const days = (6 - start.getDay() + 7) % 7
    start.setDate(start.getDate() + days)
  }
  start.setHours(when === 'today' ? 20 : 18, 0, 0, 0)
  if (start <= new Date()) start.setDate(start.getDate() + (when === 'weekend' ? 7 : 1))
  const end = new Date(start)
  end.setHours(23, 0, 0, 0)
  return [start, end]
}

function weekdayFrom(date: Date) {
  return (date.getDay() + 6) % 7
}

function initialForm(groups: Group[], group: Group, existing?: Intent): Form {
  const size = initialGroupSize(existing?.min_people, existing?.max_people)
  const [defaultStart, defaultEnd] = rangeFor(new Date().getHours() < 20 ? 'today' : 'tomorrow')
  const start = existing?.available_from ? new Date(existing.available_from) : defaultStart
  const end = existing?.available_to ? new Date(existing.available_to) : defaultEnd
  const repeat = existing?.type === 'RECURRING'
  const selected =
    existing?.group_id && groups.some((item) => item.id === existing.group_id)
      ? existing.group_id
      : group.id
  return {
    when: existing?.available_from ? 'custom' : new Date().getHours() < 20 ? 'today' : 'tomorrow',
    start: formatLocalDateTimeInput(start),
    end: formatLocalDateTimeInput(end),
    categories: existing?.activity_categories?.length ? existing.activity_categories : ['any'],
    groupIds: [selected],
    budget: existing?.budget_max?.toString() ?? '',
    radius: existing?.radius_km?.toString() ?? '',
    locationId: existing?.origin_location_id ?? '',
    people: size.choice,
    exactPeople: size.exactPeople,
    repeat,
    weekdays: existing?.weekdays?.length ? existing.weekdays : [weekdayFrom(start)],
    localStart: existing?.local_start ?? '18:00',
    localEnd: existing?.local_end ?? '23:00',
  }
}

function readDraft(key: string, fallback: Form): Form {
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return fallback
    const saved: Partial<Form> = JSON.parse(raw)
    if (!Array.isArray(saved.categories) || !Array.isArray(saved.groupIds)) return fallback
    return { ...fallback, ...saved }
  } catch {
    return fallback
  }
}

function adjusted(form: Form, adjustment: SignalAdjustment): Form {
  if (adjustment === 'repeat') return { ...form, repeat: true }
  if (adjustment === 'any') return { ...form, categories: ['any'] }
  if (adjustment === 'radius') return { ...form, radius: '10' }
  if (adjustment === 'budget') return { ...form, budget: String((Number(form.budget) || 0) + 200) }
  if (adjustment === 'tomorrow') {
    const end = new Date(form.end)
    if (!Number.isFinite(end.getTime())) return form
    end.setDate(end.getDate() + 1)
    return { ...form, when: 'custom', end: formatLocalDateTimeInput(end) }
  }
  return form
}

function Choice({
  active,
  onClick,
  children,
  className = '',
  disabled = false,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
  className?: string
  disabled?: boolean
}) {
  return (
    <button
      type="button"
      className={'choice ' + (active ? 'choice--selected ' : '') + className}
      aria-pressed={active}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  )
}

export function SignalComposer({
  group,
  groups,
  locations,
  activeBatch,
  activeRecurring,
  adjustment,
  onCreateLocation,
  onDone,
  onBack,
}: {
  group: Group
  groups: Group[]
  locations: Location[]
  activeBatch?: Intent[]
  activeRecurring?: Intent
  adjustment: SignalAdjustment
  onCreateLocation: (
    label: string,
    latitude: number,
    longitude: number,
    city: string,
    kind?: 'SAVED' | 'CURRENT',
  ) => Promise<Location>
  onDone: () => void | Promise<void>
  onBack: () => void
}) {
  const existing = activeRecurring ?? activeBatch?.[0]
  const key = 'dvizh-signal-draft-v2:' + (existing?.id ?? 'new')
  const initial = useRef<Form>(initialForm(groups, group, existing))
  const [form, setForm] = useState<Form>(() =>
    adjusted(readDraft(key, initial.current), adjustment),
  )
  const [conditionsOpen, setConditionsOpen] = useState(
    Boolean(
      (existing?.budget_max !== null && existing?.budget_max !== undefined) ||
        existing?.radius_km ||
        (existing?.min_people && existing.min_people > 2),
    ),
  )
  const [busy, setBusy] = useState(false)
  const busyRef = useRef(false)
  const [error, setError] = useState('')
  const [timeError, setTimeError] = useState('')
  const [exitOpen, setExitOpen] = useState(false)
  const [placeOpen, setPlaceOpen] = useState(false)
  const [placeLabel, setPlaceLabel] = useState('Дом')
  const [coords, setCoords] = useState<{ latitude: number; longitude: number } | null>(null)
  const [placeBusy, setPlaceBusy] = useState(false)
  const [placeError, setPlaceError] = useState('')
  const [checking, setChecking] = useState(false)
  const [locatingCurrent, setLocatingCurrent] = useState(false)
  const [catalogOpen, setCatalogOpen] = useState(false)
  const [categorySearch, setCategorySearch] = useState('')
  const visibleActivities = searchActivities(categorySearch)

  useEffect(() => {
    localStorage.setItem(key, JSON.stringify(form))
  }, [form, key])

  const update = (change: Partial<Form>) => setForm((current) => ({ ...current, ...change }))
  const selectedGroups = groups.filter((item) => form.groupIds.includes(item.id))
  const cityMismatch = new Set(selectedGroups.map((item) => item.city_slug)).size > 1
  const city = cityMismatch ? '' : (selectedGroups[0]?.city_slug ?? group.city_slug)
  const places = locations.filter((item) => item.city_slug === city)
  const budget = parseOptionalInteger(form.budget, 0, 100000)
  const radius = parseOptionalRadius(form.radius)
  const people = groupSizeRange(form.people, parseExactPeople(form.exactPeople))
  const selectedPlace = places.find((item) => item.id === form.locationId)
  const valid = Boolean(
    form.groupIds.length &&
      !cityMismatch &&
      budget !== undefined &&
      radius !== undefined &&
      people &&
      (radius === null || selectedPlace) &&
      (!form.repeat || form.weekdays.length),
  )
  const dirty = JSON.stringify(form) !== JSON.stringify(initial.current)
  const budgetChoice = budgetOptions.includes(form.budget) ? form.budget : 'custom'
  const whenLabel = form.repeat
    ? 'Каждую неделю · ' + weekDays(form.weekdays)
    : form.when === 'today'
      ? 'Сегодня после 20:00'
      : form.when === 'tomorrow'
        ? 'Завтра · 18:00–23:00'
        : form.when === 'weekend'
          ? 'В субботу · 18:00–23:00'
          : Number.isFinite(new Date(form.start).getTime()) &&
              Number.isFinite(new Date(form.end).getTime())
            ? formatSignalWindow(
                new Date(form.start).toISOString(),
                new Date(form.end).toISOString(),
              )
            : 'Выбери время'
  const selectedActivitySummary = form.categories.includes('any')
    ? 'Любой вариант'
    : form.categories.length > 3
      ? form.categories.slice(0, 2).map(activityLabel).join(', ') +
        ` и ещё ${form.categories.length - 2}`
      : form.categories.map(activityLabel).join(', ')
  const summary = [
    whenLabel,
    selectedActivitySummary,
    selectedGroups.map((item) => item.name).join(' + '),
  ]
    .filter(Boolean)
    .join(' · ')

  function chooseWhen(value: When) {
    if (value === 'custom') return update({ when: value })
    const [start, end] = rangeFor(value)
    update({
      when: value,
      start: formatLocalDateTimeInput(start),
      end: formatLocalDateTimeInput(end),
      weekdays: [weekdayFrom(start)],
      localStart: formatLocalDateTimeInput(start).slice(11),
      localEnd: formatLocalDateTimeInput(end).slice(11),
    })
    setTimeError('')
  }

  function toggleCategory(value: string) {
    setForm((current) => {
      if (value === 'any') return { ...current, categories: ['any'] }
      const next = current.categories.includes(value)
        ? current.categories.filter((item) => item !== value)
        : [...current.categories.filter((item) => item !== 'any'), value]
      return { ...current, categories: next.length ? next : ['any'] }
    })
  }

  function leave() {
    if (dirty) setExitOpen(true)
    else onBack()
  }

  async function checkTimedOutSubmission(from: string) {
    setChecking(true)
    try {
      const intents = await api.intents()
      const saved = intents.some(
        (intent) =>
          intent.status === 'ACTIVE' &&
          (form.repeat
            ? intent.type === 'RECURRING' &&
              intent.group_id === form.groupIds[0] &&
              intent.local_start === form.localStart &&
              intent.local_end === form.localEnd
            : intent.type === 'ONE_TIME' &&
              intent.available_from === from &&
              form.groupIds.includes(intent.group_id)),
      )
      if (saved) {
        localStorage.removeItem(key)
        await onDone()
      } else {
        setError('Не удалось подтвердить сохранение. Проверь связь и попробуй ещё раз.')
      }
    } catch {
      setError('Связь пропала. Проверяем, сохранился ли сигнал.')
    } finally {
      setChecking(false)
    }
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (busyRef.current || !valid || budget === undefined || radius === undefined || !people) return
    const from = new Date(form.start)
    const to = new Date(form.end)
    if (!form.repeat && (!Number.isFinite(from.getTime()) || from <= new Date())) {
      setTimeError('Выбери время начала в будущем.')
      return
    }
    if (!form.repeat && (!Number.isFinite(to.getTime()) || to <= from)) {
      setTimeError('Время окончания должно быть позже начала.')
      return
    }
    if (form.repeat && form.localEnd <= form.localStart) {
      setTimeError('Время окончания должно быть позже начала.')
      return
    }
    setTimeError('')
    setError('')
    setBusy(true)
    busyRef.current = true
    const common = {
      activity_categories: form.categories,
      budget_max: budget,
      origin_location_id: radius === null ? null : form.locationId,
      radius_km: radius,
      min_people: people[0],
      max_people: people[1],
    }
    try {
      if (form.repeat) {
        const body = {
          ...common,
          group_id: form.groupIds[0],
          name: 'Мой ДВИЖ',
          activity_category: form.categories[0],
          weekdays: form.weekdays,
          local_start: form.localStart,
          local_end: form.localEnd,
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        }
        if (activeRecurring) await api.editAutosignal(activeRecurring.id, body)
        else {
          const created = await api.autosignal(body)
          if (activeBatch?.[0]?.signal_batch_id) {
            try {
              await api.cancelSignalBatch(activeBatch[0].signal_batch_id)
            } catch (reason) {
              await api.autoAction(created.id, 'cancel').catch(() => undefined)
              throw reason
            }
          }
        }
      } else {
        const body = {
          ...common,
          group_ids: form.groupIds,
          available_from: from.toISOString(),
          available_to: to.toISOString(),
        }
        if (activeBatch?.[0]?.signal_batch_id)
          await api.editSignalBatch(activeBatch[0].signal_batch_id, body)
        else {
          const created = await api.signalBatch(body)
          if (activeRecurring) {
            try {
              await api.autoAction(activeRecurring.id, 'cancel')
            } catch (reason) {
              await api.cancelSignalBatch(created.signal_batch_id).catch(() => undefined)
              throw reason
            }
          }
        }
      }
      localStorage.removeItem(key)
      await onDone()
    } catch (reason) {
      if (reason instanceof ApiTimeoutError) {
        setError(reason.message)
        await checkTimedOutSubmission(Number.isFinite(from.getTime()) ? from.toISOString() : '')
      } else
        setError(
          reason instanceof Error
            ? reason.message
            : 'Не удалось начать поиск. Попробовать ещё раз?',
        )
    } finally {
      setBusy(false)
      busyRef.current = false
    }
  }

  function locate() {
    setPlaceError('')
    if (!navigator.geolocation) {
      setPlaceError('Не получилось определить геопозицию.')
      return
    }
    setPlaceBusy(true)
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setCoords({ latitude: position.coords.latitude, longitude: position.coords.longitude })
        setPlaceBusy(false)
      },
      () => {
        setPlaceError('Не получилось определить геопозицию.')
        setPlaceBusy(false)
      },
      { enableHighAccuracy: true, timeout: 15000 },
    )
  }

  function useCurrentLocation() {
    if (!navigator.geolocation) {
      setPlaceError('Не получилось определить геопозицию.')
      return
    }
    setLocatingCurrent(true)
    setPlaceError('')
    navigator.geolocation.getCurrentPosition(
      (position) => {
        void onCreateLocation(
          'Текущее местоположение',
          position.coords.latitude,
          position.coords.longitude,
          city,
          'CURRENT',
        )
          .then((place) => update({ locationId: place.id }))
          .catch(() => setPlaceError('Не получилось сохранить геопозицию.'))
          .finally(() => setLocatingCurrent(false))
      },
      () => {
        setPlaceError('Не получилось определить геопозицию.')
        setLocatingCurrent(false)
      },
      { enableHighAccuracy: true, timeout: 15000 },
    )
  }

  async function savePlace() {
    if (!coords || !placeLabel.trim() || placeBusy) return
    setPlaceBusy(true)
    setPlaceError('')
    try {
      const place = await onCreateLocation(
        placeLabel.trim(),
        coords.latitude,
        coords.longitude,
        city,
      )
      update({ locationId: place.id })
      setPlaceOpen(false)
      setCoords(null)
    } catch {
      setPlaceError('Не удалось сохранить место. Попробуй ещё раз.')
    } finally {
      setPlaceBusy(false)
    }
  }

  if (busy || checking)
    return (
      <section className="search-saving" aria-live="polite">
        <PulseMark />
        <h1>{checking ? 'Проверяем сохранение' : 'Ищем подходящий план'}</h1>
        <p>Проверяем события, места и условия друзей.</p>
        <p className="search-saving__summary">{summary}</p>
        <ol className="search-steps">
          <li className="is-active">Сохраняем сигнал</li>
          <li>Ищем варианты</li>
          <li>Проверяем компанию</li>
        </ol>
        <p className="text-muted">Можно закрыть приложение — мы пришлём приглашение в MAX.</p>
      </section>
    )

  return (
    <section
      className={'signal-composer' + (catalogOpen ? ' signal-composer--catalog-open' : '')}
      aria-labelledby="signal-title"
    >
      <button
        type="button"
        className="signal-composer__close"
        aria-label="Закрыть форму"
        onClick={leave}
      >
        <Icon name="close" size={22} />
      </button>
      <h1 id="signal-title">{existing ? 'Изменить условия' : 'Когда двигаемся?'}</h1>
      <form onSubmit={(event) => void submit(event)}>
        <section className="form-section" aria-labelledby="when-title">
          <h2 id="when-title">Когда</h2>
          {form.repeat ? (
            <>
              <p className="form-hint">Выбери дни и время для повторения.</p>
              <div className="choices choices--weekdays" role="group" aria-label="Дни недели">
                {weekdays.map((label, day) => (
                  <Choice
                    key={label}
                    active={form.weekdays.includes(day)}
                    onClick={() => {
                      const next = form.weekdays.includes(day)
                        ? form.weekdays.filter((item) => item !== day)
                        : [...form.weekdays, day].sort()
                      update({ weekdays: next })
                    }}
                  >
                    {label}
                  </Choice>
                ))}
              </div>
              <div className="form-row">
                <label>
                  С{' '}
                  <input
                    type="time"
                    value={form.localStart}
                    onChange={(event) => update({ localStart: event.target.value })}
                  />
                </label>
                <label>
                  До{' '}
                  <input
                    type="time"
                    value={form.localEnd}
                    onChange={(event) => update({ localEnd: event.target.value })}
                  />
                </label>
              </div>
            </>
          ) : (
            <>
              <div className="choices choices--when" role="group" aria-label="Когда удобно">
                {new Date().getHours() < 20 ? (
                  <Choice active={form.when === 'today'} onClick={() => chooseWhen('today')}>
                    Сегодня после 20:00
                  </Choice>
                ) : null}
                <Choice active={form.when === 'tomorrow'} onClick={() => chooseWhen('tomorrow')}>
                  <span>Завтра вечером</span>
                  <small>18:00–23:00</small>
                </Choice>
                <Choice active={form.when === 'weekend'} onClick={() => chooseWhen('weekend')}>
                  <span>На выходных</span>
                  <small>Сб · 18:00–23:00</small>
                </Choice>
                <Choice active={form.when === 'custom'} onClick={() => chooseWhen('custom')}>
                  Выбрать время
                </Choice>
              </div>
              {form.when === 'custom' ? (
                <div className="form-row">
                  <label>
                    С{' '}
                    <input
                      type="datetime-local"
                      value={form.start}
                      onChange={(event) => update({ start: event.target.value })}
                    />
                  </label>
                  <label>
                    До{' '}
                    <input
                      type="datetime-local"
                      value={form.end}
                      onChange={(event) => update({ end: event.target.value })}
                    />
                  </label>
                </div>
              ) : null}
            </>
          )}
          {timeError ? (
            <p className="form-error" role="alert">
              {timeError}
            </p>
          ) : null}
        </section>
        <section className="form-section" aria-labelledby="category-title">
          <h2 id="category-title">Что подходит</h2>
          <p className="form-hint">Выбери несколько направлений или найди занятие в каталоге.</p>
          <div className="choices activity-quick" role="group" aria-label="Что подходит">
            {quickCategories.map((category) => (
              <Choice
                key={category}
                active={form.categories.includes(category)}
                onClick={() => toggleCategory(category)}
              >
                {category === 'any' ? 'Любой вариант' : activityLabel(category)}
              </Choice>
            ))}
            <button
              type="button"
              className={'activity-search-trigger' + (catalogOpen ? ' is-open' : '')}
              aria-expanded={catalogOpen}
              aria-controls="activity-catalog"
              onClick={() => setCatalogOpen((value) => !value)}
            >
              <Icon name="search" size={20} />
              <span>Все занятия</span>
              <span className="activity-search-trigger__count">{activityCatalog.length}</span>
            </button>
          </div>
          {catalogOpen ? (
            <div className="activity-catalog" id="activity-catalog">
              <label className="activity-catalog__search">
                <Icon name="search" size={20} />
                <span className="sr-only">Поиск занятия</span>
                <input
                  type="search"
                  value={categorySearch}
                  placeholder="Квесты, музеи, театр…"
                  onChange={(event) => setCategorySearch(event.target.value)}
                />
              </label>
              <div className="activity-catalog__list" role="group" aria-label="Все занятия">
                {visibleActivities.map((category) => (
                  <button
                    type="button"
                    key={category.id}
                    className={
                      'activity-catalog__item' +
                      (form.categories.includes(category.id) ? ' is-selected' : '')
                    }
                    aria-pressed={form.categories.includes(category.id)}
                    onClick={() => toggleCategory(category.id)}
                  >
                    <span>
                      <strong>{category.label}</strong>
                      <small>{category.detail}</small>
                    </span>
                    <span className="activity-catalog__check" aria-hidden="true">
                      {form.categories.includes(category.id) ? (
                        <Icon name="check" size={17} />
                      ) : null}
                    </span>
                  </button>
                ))}
                {visibleActivities.length === 0 ? (
                  <p className="activity-catalog__empty">
                    Ничего не нашли. Выбери «Любой вариант», чтобы видеть весь доступный досуг.
                  </p>
                ) : null}
              </div>
            </div>
          ) : null}
          {!form.categories.includes('any') ? (
            <p className="activity-selection">
              Выбрано: {form.categories.map(activityLabel).join(', ')}
            </p>
          ) : null}
        </section>
        <section className="form-section" aria-labelledby="company-title">
          <h2 id="company-title">С кем</h2>
          <div className="company-options">
            {groups.map((item) => {
              const selected = form.groupIds.includes(item.id)
              return (
                <button
                  type="button"
                  key={item.id}
                  className={'company-option ' + (selected ? 'is-selected' : '')}
                  aria-pressed={selected}
                  onClick={() => {
                    const next = selected
                      ? form.groupIds.filter((id) => id !== item.id)
                      : [...form.groupIds, item.id]
                    update({ groupIds: form.repeat ? [item.id] : next, locationId: '', radius: '' })
                  }}
                >
                  <span className="company-option__identity">
                    <span className="company-option__icon" aria-hidden="true">
                      <Icon name="users" size={23} />
                    </span>
                    <span className="company-option__text">
                      <strong>{item.name}</strong>
                      <small>
                        {item.member_count > 1
                          ? `Ты и ещё ${formatPeople(item.member_count - 1)}`
                          : 'Пока только ты'}
                      </small>
                    </span>
                  </span>
                  <span className="company-option__check" aria-hidden="true">
                    {selected ? <Icon name="check" size={17} /> : null}
                  </span>
                </button>
              )
            })}
          </div>
          {cityMismatch ? <p className="form-error">Выбери компании из одного города.</p> : null}
        </section>
        <details
          className="conditions"
          open={conditionsOpen}
          onToggle={(event) => setConditionsOpen(event.currentTarget.open)}
        >
          <summary>
            <strong>Бюджет, расстояние и компания</strong>
            <span>Необязательно</span>
          </summary>
          <div className="conditions__content">
            <section className="subsection">
              <h3>Бюджет</h3>
              <div className="choices" role="group" aria-label="Бюджет">
                {budgetOptions.map((option) => (
                  <Choice
                    key={option}
                    active={budgetChoice === option}
                    onClick={() =>
                      update({
                        budget:
                          option === 'custom'
                            ? budgetChoice === 'custom'
                              ? form.budget
                              : '1500'
                            : option,
                      })
                    }
                  >
                    {option === ''
                      ? 'Неважно'
                      : option === 'custom'
                        ? 'Своя сумма'
                        : 'До ' + Number(option).toLocaleString('ru-RU') + ' ₽'}
                  </Choice>
                ))}
              </div>
              {budgetChoice === 'custom' ? (
                <label>
                  Сумма, ₽{' '}
                  <input
                    type="number"
                    min="0"
                    max="100000"
                    value={form.budget}
                    onChange={(event) => update({ budget: event.target.value })}
                  />
                </label>
              ) : null}
              {budget === undefined ? (
                <p className="form-error">Укажи сумму от 0 до 100 000 ₽.</p>
              ) : null}
            </section>
            <section className="subsection">
              <h3>Расстояние</h3>
              <p className="form-hint">Сначала выбери точку.</p>
              <div className="choices" role="group" aria-label="Точка отсчёта">
                {places.map((place) => (
                  <Choice
                    key={place.id}
                    active={form.locationId === place.id}
                    onClick={() => update({ locationId: place.id })}
                  >
                    {place.label}
                  </Choice>
                ))}
                <button
                  type="button"
                  className="choice"
                  onClick={useCurrentLocation}
                  disabled={locatingCurrent}
                >
                  {locatingCurrent ? 'Определяем…' : 'Текущее местоположение'}
                </button>
                <button type="button" className="choice" onClick={() => setPlaceOpen(true)}>
                  + Добавить место
                </button>
              </div>
              {placeError && !placeOpen ? (
                <p className="form-error" role="alert">
                  {placeError}
                </p>
              ) : null}
              <div className="choices" role="group" aria-label="Радиус">
                {radiusOptions.map((option) => (
                  <Choice
                    key={option}
                    active={form.radius === option}
                    onClick={() => update({ radius: option })}
                    disabled={!selectedPlace && Boolean(option)}
                  >
                    {option ? 'До ' + option + ' км' : 'Неважно'}
                  </Choice>
                ))}
              </div>
              {!selectedPlace ? (
                <p className="form-hint">Выбери точку, чтобы задать расстояние.</p>
              ) : null}
              {radius === undefined ? (
                <p className="form-error">Укажи расстояние до 100 км.</p>
              ) : null}
            </section>
            <section className="subsection">
              <h3>Количество участников</h3>
              <div className="choices" role="group" aria-label="Количество участников">
                {(['any', '3+', '5+', 'exact'] as GroupSizeChoice[]).map((option) => (
                  <Choice
                    key={option}
                    active={form.people === option}
                    onClick={() => update({ people: option })}
                  >
                    {option === 'any'
                      ? 'Неважно'
                      : option === '3+'
                        ? 'Хотя бы 3'
                        : option === '5+'
                          ? 'Хотя бы 5'
                          : 'Ровно…'}
                  </Choice>
                ))}
              </div>
              {form.people === 'exact' ? (
                <label>
                  Сколько человек?{' '}
                  <input
                    type="number"
                    min="2"
                    max="12"
                    value={form.exactPeople}
                    onChange={(event) => update({ exactPeople: event.target.value })}
                  />
                </label>
              ) : null}
              <p className="form-hint">
                Сигнал сработает, когда наберётся указанное количество участников.
              </p>
              {!people ? <p className="form-error">Укажи от 2 до 12 человек.</p> : null}
            </section>
          </div>
        </details>
        <label className="repeat-control">
          <span>Повторять каждую неделю</span>
          <input
            type="checkbox"
            checked={form.repeat}
            onChange={(event) =>
              update({
                repeat: event.target.checked,
                groupIds: event.target.checked ? form.groupIds.slice(0, 1) : form.groupIds,
              })
            }
          />
        </label>
        {error ? (
          <p className="form-error" role="alert">
            {error}
          </p>
        ) : null}
        <div className="wizard__footer">
          <p className="wizard__summary">{summary}</p>
          <button className="primary-button" type="submit" disabled={!valid || busy}>
            {existing ? 'Сохранить условия' : 'Начать поиск'}
          </button>
        </div>
      </form>
      {exitOpen ? (
        <ConfirmDialog
          title="Выйти без сохранения?"
          description="Изменения в форме будут удалены."
          confirmLabel="Выйти"
          cancelLabel="Остаться"
          onConfirm={() => {
            localStorage.removeItem(key)
            onBack()
          }}
          onCancel={() => setExitOpen(false)}
        />
      ) : null}
      {placeOpen ? (
        <ConfirmDialog
          title="Новое место"
          description="Это место видно только тебе."
          confirmLabel="Сохранить место"
          cancelLabel="Закрыть"
          confirmDisabled={!coords || !placeLabel.trim()}
          busy={placeBusy}
          onConfirm={() => void savePlace()}
          onCancel={() => {
            setPlaceOpen(false)
            setPlaceError('')
          }}
        >
          <label>
            Название{' '}
            <input
              value={placeLabel}
              maxLength={80}
              onChange={(event) => setPlaceLabel(event.target.value)}
            />
          </label>
          <button type="button" className="secondary-button" onClick={locate} disabled={placeBusy}>
            Использовать мою геопозицию
          </button>
          {coords ? <p role="status">Точка получена. Можно сохранить место.</p> : null}
          {placeError ? (
            <p className="form-error" role="alert">
              {placeError}
            </p>
          ) : null}
        </ConfirmDialog>
      ) : null}
    </section>
  )
}
