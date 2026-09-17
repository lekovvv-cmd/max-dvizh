import { Button, Input } from '@maxhub/max-ui'
import { useCallback, useEffect, useState } from 'react'

import { AutoSignals } from '../features/autosignals/AutoSignals'
import { Company } from '../features/groups/Company'
import { OfferPool } from '../features/offers/OfferPool'
import { Plans } from '../features/plans/Plans'
import { SignalWizard } from '../features/signals/SignalWizard'
import { AppShell } from '../shared/ui/AppShell'
import type { Screen } from '../shared/ui/AppShell'
import { api } from './api'
import type { Group, Intent, Location, Offer, Plan } from './api'

export function App() {
  const [screen, setScreen] = useState<Screen>('home')
  const [loading, setLoading] = useState(true); const [error, setError] = useState('')
  const [group, setGroup] = useState<Group | null>(null); const [groups, setGroups] = useState<Group[]>([])
  const [locations, setLocations] = useState<Location[]>([]); const [intents, setIntents] = useState<Intent[]>([])
  const [offers, setOffers] = useState<Offer[]>([]); const [plans, setPlans] = useState<Plan[]>([]); const [name, setName] = useState('')
  const load = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const [session, nextGroups] = await Promise.all([api.session(), api.groups()])
      const selected = group && nextGroups.some(item => item.id === group.id) ? group : nextGroups[0] ?? null
      const [nextLocations, nextOffers, nextPlans, nextIntents] = await Promise.all([api.locations(), api.offers(), api.plans(), selected ? api.intents(selected.id) : Promise.resolve([])])
      setName(session.display_name); setGroups(nextGroups); setGroup(selected); setLocations(nextLocations); setOffers(nextOffers); setPlans(nextPlans); setIntents(nextIntents)
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Сервис временно недоступен') } finally { setLoading(false) }
  }, [group])
  useEffect(() => { void load() }, [load])
  useEffect(() => {
    const token = new URLSearchParams(window.location.hash.slice(1)).get('startapp') || new URLSearchParams(window.WebApp?.initData || '').get('start_param')
    if (token) void api.join(token).then(result => { setGroup(result.group); void load() }).catch(() => undefined)
  }, [load])
  if (loading) return <main className="system-state" aria-live="polite"><span className="loading-bolt">ϟ</span><p>Открываем ДВИЖ…</p></main>
  if (error) return <main className="system-state"><section className="system-card" role="alert"><span className="loading-bolt">!</span><h1>Не получилось загрузить</h1><p>{error}</p><Button variant="primary" onClick={() => void load()}>Повторить</Button></section></main>
  if (!group) return <Start onCreated={created => { setGroup(created); void load() }} />
  const refresh = () => void load()
  const addLocation = async () => { const location = await api.createLocation(defaultLocation(group.city_slug)); setLocations(current => [location, ...current]); return location }
  const content = screen === 'home' ? <OfferPool offers={offers} onSignal={() => setScreen('signal')} onChanged={refresh} />
    : screen === 'signal' ? <SignalWizard group={group} locations={locations} addLocation={addLocation} onDone={() => { setScreen('home'); refresh() }} />
      : screen === 'autos' ? <AutoSignals group={group} locations={locations} intents={intents} onChanged={refresh} />
        : screen === 'plans' ? <Plans plans={plans} />
          : <Company groups={groups} active={group} onSelect={selected => { setGroup(selected); setScreen('home'); refresh() }} />
  return <AppShell screen={screen} name={name} onNavigate={setScreen}>{content}</AppShell>
}

function Start({ onCreated }: { onCreated: (group: Group) => void }) {
  const [name, setName] = useState('Наша компания'); const [city, setCity] = useState('ekb'); const [error, setError] = useState(''); const [busy, setBusy] = useState(false)
  async function submit(event: React.FormEvent) { event.preventDefault(); setBusy(true); setError(''); try { onCreated(await api.createGroup({ name, city_slug: city })) } catch (reason) { setError(reason instanceof Error ? reason.message : 'Не удалось создать компанию') } finally { setBusy(false) } }
  return <main className="start-screen"><section className="start-card"><span className="start-card__bolt">ϟ</span><p className="section-kicker">MAX ДВИЖ</p><h1>С кем собираем ДВИЖ?</h1><p>Создай приватную компанию. Условия и точки участников не видны друг другу.</p><form onSubmit={submit}><label>Название компании<Input value={name} onChange={event => setName(event.target.value)} required /></label><label>Город <Input value={city} onChange={event => setCity(event.target.value)} required /></label>{error ? <p className="form-error" role="alert">{error}</p> : null}<Button stretched variant="primary" type="submit" loading={busy} disabled={busy}>Создать компанию</Button></form></section></main>
}

function defaultLocation(city: string) { const points: Record<string, [number, number]> = { ekb: [56.8389, 60.6057], msk: [55.7558, 37.6176], spb: [59.9343, 30.3351] }; const [latitude, longitude] = points[city] || [55.7558, 37.6176]; return { label: 'Моя точка', latitude, longitude, city_slug: city, kind: 'SAVED', is_ephemeral: false } }
