import type { Taxonomy } from '../../app/api'

// Populated only from GET /leisure/taxonomy. The backend owns available activities.
let taxonomy: Taxonomy = { directions: [], activities: [] }

export function setActivityTaxonomy(value: Taxonomy) {
  taxonomy = value
}

export function getActivityTaxonomy() {
  return taxonomy
}

export function activityCategoryLabel(id: string) {
  if (id.endsWith('/*'))
    return taxonomy.directions.find((item) => item.id === id.slice(0, -2))?.label ?? 'Досуг'
  return taxonomy.activities.find((item) => item.id === id)?.label ?? 'Досуг'
}

export function searchActivities(query: string) {
  const words = query.trim().toLocaleLowerCase('ru-RU').split(/\s+/).filter(Boolean)
  if (!words.length) return taxonomy.activities
  return taxonomy.activities.filter((item) =>
    words.every((word) => item.label.toLocaleLowerCase('ru-RU').includes(word)),
  )
}
