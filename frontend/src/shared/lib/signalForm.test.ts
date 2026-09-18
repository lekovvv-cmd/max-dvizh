import { describe, expect, it } from 'vitest'

import { formatLocalDateTimeInput, groupSizeRange, parseOptionalInteger, parseOptionalRadius } from './signalForm'

describe('signal form values', () => {
  it('formats datetime-local values from local calendar fields', () => {
    expect(formatLocalDateTimeInput(new Date(2026, 8, 17, 9, 5))).toBe('2026-09-17T09:05')
  })

  it('preserves a zero budget and rejects invalid numeric input', () => {
    expect(parseOptionalInteger('', 0, 100_000)).toBeNull()
    expect(parseOptionalInteger('0', 0, 100_000)).toBe(0)
    expect(parseOptionalInteger('-1', 0, 100_000)).toBeUndefined()
    expect(parseOptionalInteger('100001', 0, 100_000)).toBeUndefined()
    expect(parseOptionalInteger('NaN', 0, 100_000)).toBeUndefined()
    expect(parseOptionalRadius('')).toBeNull()
    expect(parseOptionalRadius('0')).toBeUndefined()
    expect(parseOptionalRadius('101')).toBeUndefined()
  })

  it('maps every group-size choice to the backend range', () => {
    expect(groupSizeRange('any')).toEqual([2, null])
    expect(groupSizeRange('3+')).toEqual([3, null])
    expect(groupSizeRange('5+')).toEqual([5, null])
    expect(groupSizeRange('exactly-5')).toEqual([5, 5])
  })
})
