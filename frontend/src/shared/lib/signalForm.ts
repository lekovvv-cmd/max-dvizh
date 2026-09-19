export type GroupSizeChoice = 'any' | '3+' | '5+' | 'exact'

export const parseExactPeople = (raw: string, max = 12): number | undefined => {
  const value = parseOptionalInteger(raw, 2, max)
  return typeof value === 'number' ? value : undefined
}

export const initialGroupSize = (minPeople?: number, maxPeople?: number | null): { choice: GroupSizeChoice; exactPeople: string } => {
  if (minPeople !== undefined && maxPeople === minPeople) return { choice: 'exact', exactPeople: String(minPeople) }
  if (minPeople === 5) return { choice: '5+', exactPeople: '5' }
  if (minPeople === 3) return { choice: '3+', exactPeople: '5' }
  return { choice: 'any', exactPeople: '5' }
}

export const groupSizeRange = (choice: GroupSizeChoice, exactPeople?: number): readonly [number, number | null] | undefined => {
  if (choice === '3+') return [3, null]
  if (choice === '5+') return [5, null]
  if (choice === 'exact') return exactPeople === undefined ? undefined : [exactPeople, exactPeople]
  return [2, null]
}

export const parseOptionalInteger = (raw: string, min: number, max: number): number | null | undefined => {
  if (raw.trim() === '') return null
  const value = Number(raw)
  if (!Number.isInteger(value) || value < min || value > max) return undefined
  return value
}

export const parseOptionalRadius = (raw: string): number | null | undefined => {
  if (raw.trim() === '') return null
  const value = Number(raw)
  if (!Number.isFinite(value) || value <= 0 || value > 100) return undefined
  return value
}

export const formatLocalDateTimeInput = (date: Date): string => {
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}
