import { describe, expect, it } from 'vitest'
import { formatPeople, formatPeopleNeeded } from './format'

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

describe('formatPeopleNeeded', () => {
  it.each([
    [1, 'Для плана нужен ещё 1 человек.'],
    [2, 'Для плана нужны ещё 2 человека.'],
    [3, 'Для плана нужны ещё 3 человека.'],
    [4, 'Для плана нужны ещё 4 человека.'],
    [5, 'Для плана нужно ещё 5 человек.'],
    [11, 'Для плана нужно ещё 11 человек.'],
    [21, 'Для плана нужен ещё 21 человек.'],
    [22, 'Для плана нужны ещё 22 человека.'],
  ])('agrees with %i missing people', (count, expected) => {
    expect(formatPeopleNeeded(count)).toBe(expected)
  })
})
