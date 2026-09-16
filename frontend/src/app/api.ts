export type Group = { id: string; name: string; city_slug: string; member_count: number; invite_token?: string | null; invite_url?: string | null }
export type Location = { id: string; label: string; city_slug: string; kind: string }
export type Intent = { id: string; type: string; status: string; name: string | null; city_slug: string; activity_category: string; budget_max: number; min_people: number; max_people: number; expires_at: string | null }
export type Offer = { id: string; status: string; is_near: boolean; title: string; venue_name: string | null; starts_at: string; ends_at: string; price_text: string | null; price_min: number | null; is_demo: boolean; source_url: string | null; source_fetched_at: string; distance_km: number; potential_count: number; required_min_people: number; required_max_people: number; expires_at: string; budget_delta: number | null }
export type Plan = { id: string; status: string; title: string; venue_name: string | null; starts_at: string; ends_at: string; price_text: string | null; source_url: string | null; participant_count: number; required_min_people: number; required_max_people: number; share_text: string }

declare global {
  interface Window { WebApp?: { initData?: string; shareMaxContent?: (params: { text?: string; link?: string }) => void; openMaxLink?: (url: string) => void } }
}

let demoUser = localStorage.getItem('dvizh-demo-user') || 'anton'
export function setDemoUser(value: string) { demoUser = value; localStorage.setItem('dvizh-demo-user', value) }

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  headers.set('Content-Type', 'application/json')
  if (window.WebApp?.initData) headers.set('X-MAX-Init-Data', window.WebApp.initData)
  else headers.set('X-Demo-User', demoUser)
  const response = await fetch(`/api/v1${path}`, { ...init, headers })
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: 'Сервис временно недоступен' })) as { detail?: string }
    throw new Error(body.detail || `Ошибка ${response.status}`)
  }
  return response.json() as Promise<T>
}

export const api = {
  session: () => request<{ id: string; display_name: string }>('/session'),
  groups: () => request<Group[]>('/groups'),
  createGroup: (body: { name: string; city_slug: string }) => request<Group>('/groups', { method: 'POST', body: JSON.stringify(body) }),
  join: (token: string) => request<{ group: Group }>(`/groups/join/${token}`, { method: 'POST' }),
  locations: () => request<Location[]>('/locations'),
  createLocation: (body: object) => request<Location>('/locations', { method: 'POST', body: JSON.stringify(body) }),
  intents: (groupId: string) => request<Intent[]>(`/intents?group_id=${encodeURIComponent(groupId)}`),
  signal: (body: object) => request<Intent>('/intents', { method: 'POST', body: JSON.stringify(body) }),
  autosignal: (body: object) => request<Intent>('/autosignals', { method: 'POST', body: JSON.stringify(body) }),
  autoAction: (id: string, action: string) => request<Intent>(`/autosignals/${id}/${action}`, { method: 'POST' }),
  offers: () => request<Offer[]>('/offers'),
  accept: (id: string, near: boolean) => request<Offer>(`/offers/${id}/accept`, { method: 'POST', body: JSON.stringify({ confirm_near_exception: near }) }),
  reject: (id: string) => request<Offer>(`/offers/${id}/reject`, { method: 'POST' }),
  plans: () => request<Plan[]>('/plans'),
  seedDemo: (groupId: string) => request<{ status: string }>(`/development/seed-demo/${groupId}`, { method: 'POST' }),
}
