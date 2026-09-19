import { describe, expect, it } from 'vitest'

import {
  formatLocalDateTimeInput,
  groupSizeRange,
  initialGroupSize,
  parseExactPeople,
  parseOptionalInteger,
  parseOptionalRadius,
} from './signalForm'

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
    expect(groupSizeRange('exact', 2)).toEqual([2, 2])
    expect(groupSizeRange('exact', 5)).toEqual([5, 5])
    expect(groupSizeRange('exact', 9)).toEqual([9, 9])
    expect(groupSizeRange('exact')).toBeUndefined()
    expect(parseExactPeople('1')).toBeUndefined()
    expect(parseExactPeople('13')).toBeUndefined()
    expect(parseExactPeople('4.5')).toBeUndefined()
  })

  it('restores the real exact value while editing', () => {
    expect(initialGroupSize(7, 7)).toEqual({ choice: 'exact', exactPeople: '7' })
    expect(initialGroupSize(5, null)).toEqual({ choice: '5+', exactPeople: '5' })
  })
})
