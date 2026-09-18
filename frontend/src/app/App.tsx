import { Button, Input } from '@maxhub/max-ui'
import { useCallback, useEffect, useRef, useState } from 'react'

import { AutoSignals } from '../features/autosignals/AutoSignals'
import { Company } from '../features/groups/Company'
import { OfferPool } from '../features/offers/OfferPool'
import { Plans } from '../features/plans/Plans'
import { SignalWizard } from '../features/signals/SignalWizard'
import { AppShell } from '../shared/ui/AppShell'
import type { Screen } from '../shared/ui/AppShell'
import { api } from './api'
import type { Group, Intent, Location, Offer, Plan } from './api'
import { activityLabel } from '../shared/lib/format'

export function App() {
  const [screen, setScreen] = useState<Screen>('home')
  const [loading, setLoading] = useState(true); const [error, setError] = useState('')
  const [group, setGroup] = useState<Group | null>(null); const [groups, setGroups] = useState<Group[]>([])
  const [selectedGroupId, setSelectedGroupId] = useState<string | null>(null)
  const [locations, setLocations] = useState<Location[]>([]); const [intents, setIntents] = useState<Intent[]>([])
  const [offers, setOffers] = useState<Offer[]>([]); const [plans, setPlans] = useState<Plan[]>([]); const [name, setName] = useState('')
  const [mode, setMode] = useState('MAX')
  const [chatAvailable, setChatAvailable] = useState(false)
  const [editingBatch, setEditingBatch] = useState<string | null>(null)
  const [creatingGroup, setCreatingGroup] = useState(false)
  const [joinState, setJoinState] = useState('')
  const handledJoinToken = useRef<string | null>(null)
  const [targetId, setTargetId] = useState('')
  const load = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const [session, nextGroups] = await Promise.all([api.session(), api.groups()])
      const selected = nextGroups.find(item => item.id === selectedGroupId) ?? nextGroups[0] ?? null
      const [nextLocations, nextOffers, nextPlans, nextIntents] = await Promise.all([api.locations(), api.offers(), api.plans(), api.intents()])
      setName(session.display_name); setMode(session.max_mode); setChatAvailable(Boolean(session.max_chat_id)); setGroups(nextGroups); setGroup(selected); setLocations(nextLocations); setOffers(nextOffers); setPlans(nextPlans); setIntents(nextIntents)
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Сервис временно недоступен') } finally { setLoading(false) }
  }, [selectedGroupId])
  useEffect(() => { void load() }, [load])
  useEffect(() => {
    const token = new URLSearchParams(window.location.hash.slice(1)).get('startapp') || new URLSearchParams(window.WebApp?.initData || '').get('start_param')
    if (token?.startsWith('offer_')) { setScreen('home'); setTargetId(`offer-${token.slice(6)}`); return }
    if (token?.startsWith('plan_')) { setScreen('plans'); setTargetId(`plan-${token.slice(5)}`); return }
    if (token && handledJoinToken.current !== token) {
      handledJoinToken.current = token
      setJoinState('Вступаем…')
      void api.join(token).then(result => { setJoinState(result.already_member ? 'Ты уже участник' : 'Ты в компании'); setSelectedGroupId(result.group.id) }).catch(reason => setJoinState(reason instanceof Error ? reason.message : 'Приглашение недействительно'))
    }
  }, [])
  useEffect(() => { if (targetId && !loading) document.getElementById(targetId)?.scrollIntoView({ behavior: 'smooth', block: 'center' }) }, [targetId, loading, offers, plans])
  if (loading) return <main className="system-state" aria-live="polite"><span className="loading-bolt">ϟ</span><p>Открываем ДВИЖ…</p></main>
  if (error) return <main className="system-state"><section className="system-card" role="alert"><span className="loading-bolt">!</span><h1>Не получилось загрузить</h1><p>{error}</p><Button variant="primary" onClick={() => void load()}>Повторить</Button></section></main>
  if (!group || creatingGroup) return <Start chatAvailable={chatAvailable} joinState={joinState} onCreated={created => { setSelectedGroupId(created.id); setCreatingGroup(false) }} onCancel={group ? () => setCreatingGroup(false) : undefined} />
  const refresh = () => void load()
  const addLocation = async (label: string) => {
    if (!navigator.geolocation) throw new Error('Геопозиция недоступна. Расстояние останется выключенным.')
    const position = await new Promise<GeolocationPosition>((resolve, reject) => navigator.geolocation.getCurrentPosition(resolve, reject, { enableHighAccuracy: true, timeout: 15000 }))
    const location = await api.createLocation({ label, latitude: position.coords.latitude, longitude: position.coords.longitude, city_slug: group.city_slug, kind: 'SAVED', is_ephemeral: false })
    setLocations(current => [location, ...current]); return location
  }
  const activeBatches = (() => {
    const batches = new Map<string, Intent[]>()
    for (const intent of intents) if (intent.type === 'ONE_TIME' && intent.status === 'ACTIVE' && intent.signal_batch_id && (!intent.expires_at || new Date(intent.expires_at) > new Date())) batches.set(intent.signal_batch_id, [...(batches.get(intent.signal_batch_id) || []), intent])
    return [...batches.values()]
  })()
  const providerStates = activeBatches.flat().map(intent => intent.provider_state)
  const providerState = ['PROVIDER_UNAVAILABLE', 'NO_FEASIBLE_PLAN', 'NO_SOURCE'].find(state => providerStates.includes(state))
  const content = screen === 'home' ? <><section className="home-summary">{joinState ? <p role="status">{joinState}</p> : null}{activeBatches.map(batch => <article className="company-choice" key={batch[0].signal_batch_id}><strong>⚡ Сигнал активен</strong><p>{batch[0].available_from ? new Date(batch[0].available_from).toLocaleString('ru-RU') : ''} · {batch[0].activity_categories.map(activityLabel).join(', ')}</p><p>{batch.map(item => item.group_name || groups.find(groupItem => groupItem.id === item.group_id)?.name).join(' + ')}</p><Button variant="secondary" onClick={() => { setEditingBatch(batch[0].signal_batch_id); setScreen('signal') }}>Изменить</Button><Button variant="secondary" onClick={() => { if (batch[0].signal_batch_id) void api.cancelSignalBatch(batch[0].signal_batch_id).then(refresh).catch(reason => setError(reason instanceof Error ? reason.message : 'Не удалось отменить сигнал')) }}>Отменить</Button></article>)}{plans.filter(plan => plan.status === 'COLLECTING').length ? <section><h2>Собираем</h2><Plans plans={plans.filter(plan => plan.status === 'COLLECTING')} onChanged={refresh} /></section> : null}</section><OfferPool offers={offers} hasActiveSignal={activeBatches.length > 0} providerState={providerState} onRetry={activeBatches.length ? () => { void Promise.all(activeBatches.map(batch => batch[0].signal_batch_id ? api.refreshSignalBatch(batch[0].signal_batch_id) : Promise.resolve())).then(refresh).catch(reason => setError(reason instanceof Error ? reason.message : 'Не удалось повторить поиск')) } : undefined} onSignal={() => { setEditingBatch(null); setScreen('signal') }} onChanged={refresh} /></>
    : screen === 'signal' ? <SignalWizard group={group} groups={groups} locations={locations} activeBatch={activeBatches.find(batch => batch[0].signal_batch_id === editingBatch)} onAddPlace={() => setScreen('group')} onDone={() => { setScreen('home'); setEditingBatch(null); refresh() }} />
      : screen === 'autos' ? <AutoSignals group={group} groups={groups} locations={locations} intents={intents} onChanged={refresh} />
        : screen === 'plans' ? <Plans plans={plans} onChanged={refresh} />
          : <Company groups={groups} active={group} locations={locations} mode={mode} onAddPlace={addLocation} onNew={() => setCreatingGroup(true)} onSelect={selected => { setSelectedGroupId(selected.id); setScreen('home') }} />
  return <AppShell screen={screen} name={name} onNavigate={setScreen}>{content}</AppShell>
}

function Start({ onCreated, onCancel, chatAvailable, joinState }: { onCreated: (group: Group) => void; onCancel?: () => void; chatAvailable: boolean; joinState: string }) {
  const [name, setName] = useState('Наша компания'); const [city, setCity] = useState(''); const [cities, setCities] = useState<{ slug: string; name: string }[]>([]); const [error, setError] = useState(''); const [busy, setBusy] = useState(false)
  useEffect(() => { void api.cities().then(items => { setCities(items); setCity(items[0]?.slug || '') }).catch(() => setError('Не удалось загрузить города. Попробуй позже.')) }, [])
  async function submit(event: React.FormEvent, bindCurrentChat = false) { event.preventDefault(); setBusy(true); setError(''); try { onCreated(await api.createGroup({ name, city_slug: city, bind_current_chat: bindCurrentChat })) } catch (reason) { setError(reason instanceof Error ? reason.message : 'Не удалось создать компанию') } finally { setBusy(false) } }
  return <main className="start-screen"><section className="start-card"><span className="start-card__bolt">ϟ</span>{joinState ? <p role="status">{joinState}</p> : null}<h1>Новая компания</h1><form onSubmit={event => void submit(event)}><label>Название компании<Input value={name} onChange={event => setName(event.target.value)} required /></label><label>Город<select value={city} onChange={event => setCity(event.target.value)} required>{cities.map(item => <option key={item.slug} value={item.slug}>{item.name}</option>)}</select></label>{error ? <p className="form-error" role="alert">{error}</p> : null}{error && !cities.length ? <Button type="button" variant="secondary" onClick={() => void api.cities().then(items => { setCities(items); setCity(items[0]?.slug || ''); setError('') }).catch(() => setError('Не удалось загрузить города. Попробуй позже.'))}>Повторить загрузку городов</Button> : null}{chatAvailable ? <Button stretched variant="primary" type="button" loading={busy} disabled={busy || !city} onClick={event => void submit(event, true)}>Создать ДВИЖ для этого чата</Button> : null}<Button stretched variant={chatAvailable ? 'secondary' : 'primary'} type="submit" loading={busy} disabled={busy || !city}>Создать приватную компанию</Button>{onCancel ? <Button type="button" variant="secondary" onClick={onCancel}>Назад</Button> : null}</form></section></main>
}
