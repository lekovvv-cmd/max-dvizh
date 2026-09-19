import { describe, expect, it } from 'vitest'
import { formatPeople } from './format'

describe('formatPeople', () => {
  it.each([
    [1, '1 человек'],
    [2, '2 человека'],
    [5, '5 человек'],
    [11, '11 человек'],
    [22, '22 человека'],
  ])('uses a natural Russian form for %i', (count, expected) => {
    expect(formatPeople(count)).toBe(expected)
  })
})
