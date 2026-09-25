import { useCallback, useEffect, useMemo, useState } from 'react'

import { DvizhFlow } from '../features/dvizhi/DvizhFlow'
import { Company } from '../features/groups/Company'
import { CreateCompany } from '../features/groups/CreateCompany'
import { HomeIntro } from '../features/signals/HomeIntro'
import { SignalComposer } from '../features/signals/SignalComposer'
import { setActivityTaxonomy } from '../shared/lib/activityCatalog'
import { activityLabel, formatSignalWindow } from '../shared/lib/format'
import { AppShell, type Screen } from '../shared/ui/AppShell'
import { CoachMark, type CoachStep } from '../shared/ui/CoachMark'
import {
  api,
  type Dvizh,
  type Group,
  type GroupCityUpdateResult,
  type Intent,
  type Location,
} from './api'

function initialDeepLink() {
  const hash = new URLSearchParams(window.location.hash.slice(1))
  const token =
    window.WebApp?.initDataUnsafe?.start_param ||
    new URLSearchParams(window.WebApp?.initData || '').get('start_param') ||
    hash.get('WebAppStartParam') ||
    hash.get('startapp') ||
    new URLSearchParams(window.location.search).get('startapp')
  return token || ''
}

function priority(dvizh: Dvizh) {
  if (
    dvizh.status === 'AWAITING_CONFIRMATION' &&
    dvizh.candidates.some(
      (candidate) =>
        candidate.id === dvizh.active_candidate_id && candidate.my_reaction === 'WOULD_GO',
    ) &&
    !dvizh.my_confirmation
  )
    return 0
  if (dvizh.status === 'CHOOSING_CANDIDATES') return 1
  if (
    dvizh.status === 'COLLECTING_REACTIONS' &&
    !dvizh.is_initiator &&
    dvizh.candidates.some((candidate) => !candidate.my_reaction)
  )
    return 2
  if (dvizh.status === 'PROVIDER_UNAVAILABLE' || dvizh.status === 'NO_SOURCE') return 3
  if (dvizh.status === 'COLLECTING_REACTIONS' || dvizh.status === 'AWAITING_CONFIRMATION') return 4
  if (dvizh.status === 'GATHERED') return 5
  return 9
}

function DvizhList({
  items,
  onOpen,
  onSignal,
  recurring,
  onRepeat,
  onCancelRepeat,
}: {
  items: Dvizh[]
  onOpen: (id: string) => void
  onSignal: () => void
  recurring?: Intent
  onRepeat: () => void
  onCancelRepeat: () => void
}) {
  const collecting = items.filter(
    (item) => !['GATHERED', 'EXPIRED', 'CANCELLED', 'NO_MATCH'].includes(item.status),
  )
  const gathered = items.filter((item) => item.status === 'GATHERED')
  return (
    <section className="page-stack dvizh-list">
      <h1>Движи</h1>
      {collecting.length ? (
        <section>
          <h2>Собираются</h2>
          {collecting.map((item) => (
            <button className="dvizh-list__item" key={item.id} onClick={() => onOpen(item.id)}>
              <strong>{item.activity_ids.map(activityLabel).join(' или ')}</strong>
              <span>
                {item.group_name} · {formatSignalWindow(item.available_from, item.available_to)}
              </span>
              <small>
                {item.status === 'CHOOSING_CANDIDATES'
                  ? 'Выбери место'
                  : item.status === 'AWAITING_CONFIRMATION'
                    ? 'Нужно подтвердить'
                    : item.status === 'NO_SOURCE' || item.status === 'PROVIDER_UNAVAILABLE'
                      ? 'Нужен новый поиск'
                      : 'Собирается'}
              </small>
            </button>
          ))}
        </section>
      ) : null}
      {gathered.length ? (
        <section>
          <h2>Собрались</h2>
          {gathered.map((item) => (
            <button className="dvizh-list__item" key={item.id} onClick={() => onOpen(item.id)}>
              <strong>
                {item.candidates.find((candidate) => candidate.id === item.active_candidate_id)
                  ?.title || item.activity_ids.map(activityLabel).join(' или ')}
              </strong>
              <span>
                {item.group_name} · {formatSignalWindow(item.available_from, item.available_to)}
              </span>
              <small>Собрался · {item.participants.length} участников</small>
            </button>
          ))}
        </section>
      ) : null}
      {recurring ? (
        <section className="dvizh-result">
          <h2>Регулярный сигнал</h2>
          <p>
            {recurring.group_name} ·{' '}
            {recurring.weekdays
              ?.map((day) => ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'][day])
              .join(', ')}{' '}
            · {recurring.local_start}–{recurring.local_end}
          </p>
          <div className="inline-actions">
            <button className="text-action" onClick={onRepeat}>
              Изменить
            </button>
            <button className="text-action" onClick={onCancelRepeat}>
              Отключить
            </button>
          </div>
        </section>
      ) : null}
      {!collecting.length && !gathered.length ? (
        <div className="dvizh-result">
          <h2>Пока нет движей</h2>
          <p>Подай сигнал, выбери место, и мы спросим компанию.</p>
          <button className="primary-button" onClick={onSignal}>
            Подать сигнал
          </button>
        </div>
      ) : null}
    </section>
  )
}

export function App() {
  const [screen, setScreen] = useState<Screen>('home')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [groups, setGroups] = useState<Group[]>([])
  const [groupId, setGroupId] = useState<string | null>(null)
  const [locations, setLocations] = useState<Location[]>([])
  const [intents, setIntents] = useState<Intent[]>([])
  const [dvizhi, setDvizhi] = useState<Dvizh[]>([])
  const [mode, setMode] = useState('MAX')
  const [chatAvailable, setChatAvailable] = useState(false)
  const [creatingGroup, setCreatingGroup] = useState(false)
  const [joinState, setJoinState] = useState('')
  const [targetId, setTargetId] = useState<string | null>(() => {
    const token = initialDeepLink()
    return token.startsWith('dvizh_') ? token.slice(6) : null
  })
  const [editingBatch, setEditingBatch] = useState<string | null>(null)
  const [repeat, setRepeat] = useState(false)
  const [coachEpoch, setCoachEpoch] = useState(0)

  const load = useCallback(async () => {
    setError('')
    try {
      const [session, nextGroups, nextLocations, nextIntents, nextDvizhi, taxonomy] =
        await Promise.all([
          api.session(),
          api.groups(),
          api.locations(),
          api.intents(),
          api.dvizhi(),
          api.taxonomy(),
        ])
      setActivityTaxonomy(taxonomy)
      setMode(session.max_mode)
      setChatAvailable(Boolean(session.max_chat_id))
      setGroups(nextGroups)
      setLocations(nextLocations)
      setIntents(nextIntents)
      setDvizhi(nextDvizhi)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Не получилось загрузить данные')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])
  useEffect(() => {
    if (!loading && targetId && !dvizhi.some((item) => item.id === targetId)) {
      void api
        .dvizh(targetId)
        .then((item) =>
          setDvizhi((current) =>
            current.some((value) => value.id === item.id) ? current : [item, ...current],
          ),
        )
        .catch(() => setTargetId(null))
    }
  }, [loading, targetId, dvizhi])
  useEffect(() => {
    const token = initialDeepLink()
    if (!token || token.startsWith('dvizh_')) return
    void api
      .join(token)
      .then((result) => {
        setJoinState(result.already_member ? 'Ты уже участник' : 'Ты в компании')
        setGroupId(result.group.id)
        void load()
      })
      .catch((reason) =>
        setJoinState(reason instanceof Error ? reason.message : 'Приглашение недействительно'),
      )
  }, [load])
  useEffect(() => {
    const timer = window.setInterval(() => {
      if (
        dvizhi.some((item) =>
          ['COLLECTING_REACTIONS', 'AWAITING_CONFIRMATION'].includes(item.status),
        )
      ) {
        void api
          .dvizhi()
          .then(setDvizhi)
          .catch(() => undefined)
      }
    }, 15000)
    return () => window.clearInterval(timer)
  }, [dvizhi])

  const group = groups.find((item) => item.id === groupId) || groups[0] || null
  const recurring = intents.find(
    (item) => item.type === 'RECURRING' && item.status === 'ACTIVE' && item.group_id === group?.id,
  )
  const focused = dvizhi.find((item) => item.id === targetId)
  const homeDvizh = useMemo(() => {
    if (focused) return focused
    return [...dvizhi]
      .filter(
        (item) =>
          item.group_id === group?.id &&
          !['CANCELLED', 'EXPIRED', 'NO_MATCH'].includes(item.status),
      )
      .sort((a, b) => priority(a) - priority(b))[0]
  }, [focused, dvizhi, group?.id])
  const selected = screen === 'dvizhi' ? focused : homeDvizh
  const coachStep: CoachStep | null = (() => {
    void coachEpoch
    const done = (step: CoachStep) => localStorage.getItem(`dvizh-onboarding-v1-${step}`) === 'done'
    if (screen === 'home' && !selected && !done('signal')) return 'signal'
    if (
      (screen === 'home' || screen === 'dvizhi') &&
      selected &&
      (selected.status === 'CHOOSING_CANDIDATES' ||
        (selected.status === 'COLLECTING_REACTIONS' && !selected.is_initiator)) &&
      selected.candidates.some((candidate) => !candidate.my_reaction) &&
      !done('choice')
    )
      return 'choice'
    if (
      screen !== 'signal' &&
      selected &&
      ['COLLECTING_REACTIONS', 'AWAITING_CONFIRMATION', 'GATHERED'].includes(selected.status) &&
      !done('dvizhi')
    )
      return 'dvizhi'
    return null
  })()
  const finishCoach = (step: CoachStep) => {
    localStorage.setItem(`dvizh-onboarding-v1-${step}`, 'done')
    setCoachEpoch((value) => value + 1)
  }
  const updateDvizh = (value: Dvizh) =>
    setDvizhi((items) => items.map((item) => (item.id === value.id ? value : item)))
  const openSignal = (batch: string | null = null, recurring = false) => {
    setEditingBatch(batch)
    setRepeat(recurring)
    setScreen('signal')
  }
  const editDvizh = (item: Dvizh) => openSignal(item.signal_batch_id)

  if (loading)
    return (
      <main className="system-state" aria-live="polite">
        <span className="loading-indicator" aria-hidden="true" />
        <p>Загружаем…</p>
      </main>
    )
  if (error && !groups.length)
    return (
      <main className="system-state">
        <section className="system-card" role="alert">
          <h1>Не получилось загрузить</h1>
          <p>{error}</p>
          <button className="primary-button" onClick={() => void load()}>
            Повторить
          </button>
        </section>
      </main>
    )
  if (!group || creatingGroup)
    return (
      <CreateCompany
        chatAvailable={chatAvailable}
        joinState={joinState}
        onCreated={(created) => {
          setGroupId(created.id)
          setCreatingGroup(false)
          void load()
        }}
        onCancel={group ? () => setCreatingGroup(false) : undefined}
      />
    )

  const changeGroupCity = async (id: string, city: string): Promise<GroupCityUpdateResult> => {
    const result = await api.updateGroupCity(id, city)
    setGroups((items) => items.map((item) => (item.id === id ? result.group : item)))
    await load()
    return result
  }
  const createLocationAt = async (
    label: string,
    latitude: number,
    longitude: number,
    city: string,
    kind: 'SAVED' | 'CURRENT' = 'SAVED',
  ) => {
    const location = await api.createLocation({
      label,
      latitude,
      longitude,
      city_slug: city,
      kind,
      is_ephemeral: false,
    })
    setLocations((items) => [location, ...items])
    return location
  }
  const addLocation = async (label: string) => {
    if (!navigator.geolocation) throw new Error('Геопозиция недоступна')
    const position = await new Promise<GeolocationPosition>((resolve, reject) =>
      navigator.geolocation.getCurrentPosition(resolve, reject, {
        enableHighAccuracy: true,
        timeout: 15000,
      }),
    )
    return createLocationAt(
      label,
      position.coords.latitude,
      position.coords.longitude,
      group.city_slug,
    )
  }
  const batch = intents.filter(
    (item) => item.signal_batch_id === editingBatch && item.status === 'ACTIVE',
  )
  const content =
    screen === 'signal' ? (
      <SignalComposer
        key={editingBatch || String(repeat)}
        group={group}
        groups={groups}
        locations={locations}
        activeBatch={batch.length ? batch : undefined}
        activeRecurring={repeat ? recurring : undefined}
        adjustment={repeat ? 'repeat' : null}
        onCreateLocation={createLocationAt}
        onBack={() => setScreen('home')}
        onDone={async () => {
          await load()
          setTargetId(null)
          setScreen('home')
        }}
      />
    ) : screen === 'group' ? (
      <Company
        groups={groups}
        active={group}
        locations={locations}
        mode={mode}
        onChangeCity={changeGroupCity}
        onAddPlace={addLocation}
        onRenamePlace={async (id, label) => {
          const value = await api.renameLocation(id, label)
          setLocations((items) => items.map((item) => (item.id === id ? value : item)))
        }}
        onDefaultPlace={async (id) => {
          const value = await api.defaultLocation(id)
          setLocations((items) =>
            items.map((item) =>
              item.city_slug === value.city_slug ? { ...item, is_default: item.id === id } : item,
            ),
          )
        }}
        onDeletePlace={async (id) => {
          await api.deleteLocation(id)
          setLocations(await api.locations())
        }}
        onNew={() => setCreatingGroup(true)}
        onSelect={(value) => {
          setGroupId(value.id)
          setTargetId(null)
        }}
      />
    ) : screen === 'dvizhi' && !selected ? (
      <DvizhList
        items={dvizhi}
        onOpen={setTargetId}
        onSignal={() => openSignal()}
        recurring={recurring}
        onRepeat={() => openSignal(null, true)}
        onCancelRepeat={() => {
          if (recurring)
            void api
              .cancelRecurringSignal(recurring.id)
              .then(() => load())
              .catch((reason) =>
                setError(reason instanceof Error ? reason.message : 'Не удалось отключить сигнал'),
              )
        }}
      />
    ) : selected ? (
      <div className="page-stack home-page">
        {screen === 'dvizhi' ? (
          <button type="button" className="text-action" onClick={() => setTargetId(null)}>
            ← Все движи
          </button>
        ) : null}
        <DvizhFlow
          key={selected.id}
          dvizh={selected}
          onUpdate={updateDvizh}
          onEdit={() => editDvizh(selected)}
          onNew={() => openSignal()}
        />
        {screen === 'home' ? (
          <button className="text-action" onClick={() => setScreen('dvizhi')}>
            Все движи
          </button>
        ) : null}
      </div>
    ) : (
      <div className="page-stack home-page">
        <HomeIntro
          onSignal={() => openSignal()}
          onRepeat={() => openSignal(null, true)}
          hasRepeat={Boolean(recurring)}
        />
        {joinState ? <p className="inline-notice">{joinState}</p> : null}
      </div>
    )

  return (
    <>
      <AppShell
        screen={screen}
        onNavigate={(value) => {
          setTargetId(null)
          setScreen(value)
        }}
      >
        {error ? (
          <p className="inline-notice" role="alert">
            {error}
          </p>
        ) : null}
        {content}
      </AppShell>
      {coachStep ? (
        <CoachMark
          step={coachStep}
          onDone={() => finishCoach(coachStep)}
          onSkip={() => {
            ;(['signal', 'choice', 'dvizhi'] as CoachStep[]).forEach((step) =>
              localStorage.setItem(`dvizh-onboarding-v1-${step}`, 'done'),
            )
            setCoachEpoch((value) => value + 1)
          }}
        />
      ) : null}
    </>
  )
}
