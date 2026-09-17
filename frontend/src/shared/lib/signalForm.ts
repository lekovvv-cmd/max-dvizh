export type GroupSizeChoice = 'any' | '3+' | '5+' | 'exactly-5'

export const groupSizeRange = (choice: GroupSizeChoice): readonly [number, number] => {
  if (choice === '3+') return [3, 12]
  if (choice === '5+') return [5, 12]
  if (choice === 'exactly-5') return [5, 5]
  return [1, 12]
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
