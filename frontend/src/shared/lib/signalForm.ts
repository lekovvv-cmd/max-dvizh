export type GroupSizeChoice = 'any' | '3+' | '5+' | 'exact'

export const parseExactPeople = (raw: string, max = 12): number | undefined => {
  const value = parseOptionalInteger(raw, 2, max)
  return typeof value === 'number' ? value : undefined
}

export const initialGroupSize = (
  minPeople?: number,
  maxPeople?: number | null,
): { choice: GroupSizeChoice; exactPeople: string } => {
  if (minPeople !== undefined && maxPeople === minPeople)
    return { choice: 'exact', exactPeople: String(minPeople) }
  if (minPeople === 5) return { choice: '5+', exactPeople: '5' }
  if (minPeople === 3) return { choice: '3+', exactPeople: '5' }
  return { choice: 'any', exactPeople: '5' }
}

export const groupSizeRange = (
  choice: GroupSizeChoice,
  exactPeople?: number,
): readonly [number, number | null] | undefined => {
  if (choice === '3+') return [3, null]
  if (choice === '5+') return [5, null]
  if (choice === 'exact') return exactPeople === undefined ? undefined : [exactPeople, exactPeople]
  return [2, null]
}

export const parseOptionalInteger = (
  raw: string,
  min: number,
  max: number,
): number | null | undefined => {
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

export const formatRussianDateTimeInput = (date: Date): string => {
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${pad(date.getDate())}.${pad(date.getMonth() + 1)}.${date.getFullYear()} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

export const parseRussianDateTimeInput = (value: string): Date | null => {
  const match = /^(\d{2})\.(\d{2})\.(\d{4}) (\d{2}):(\d{2})$/.exec(value.trim())
  if (!match) return null
  const [, dayText, monthText, yearText, hourText, minuteText] = match
  const [day, month, year, hour, minute] = [dayText, monthText, yearText, hourText, minuteText].map(
    Number,
  )
  if (year < 1000 || month < 1 || month > 12 || hour > 23 || minute > 59) return null
  const date = new Date(year, month - 1, day, hour, minute)
  return date.getFullYear() === year &&
    date.getMonth() === month - 1 &&
    date.getDate() === day &&
    date.getHours() === hour &&
    date.getMinutes() === minute
    ? date
    : null
}

export const isLocalTimeInput = (value: string): boolean => {
  const match = /^(\d{2}):(\d{2})$/.exec(value)
  return Boolean(match && Number(match[1]) <= 23 && Number(match[2]) <= 59)
}

export const restoreRussianDateTimeInput = (value: unknown, fallback: string): string => {
  if (typeof value !== 'string') return fallback
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value)) {
    const date = new Date(value)
    return Number.isFinite(date.getTime()) ? formatRussianDateTimeInput(date) : fallback
  }
  return value
}
