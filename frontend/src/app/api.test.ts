import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from './api'

afterEach(() => vi.unstubAllGlobals())

describe('API error messages', () => {
  it.each([
    [
      422,
      { detail: [{ loc: ['body', 'name'], msg: 'Field required', input: {} }] },
      'Проверь заполненные поля',
    ],
    [503, null, 'Сервис временно недоступен'],
    [409, { detail: 'Сначала убери расстояние из сигнала' }, 'Сначала убери расстояние из сигнала'],
  ])('handles HTTP %s without showing raw validation objects', async (status, body, message) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status, json: async () => body }))
    await expect(api.groups()).rejects.toThrow(message as string)
  })

  it('handles a non-JSON gateway error', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 502,
        json: async () => {
          throw new SyntaxError()
        },
      }),
    )
    await expect(api.groups()).rejects.toThrow('Сервис временно недоступен')
  })
})
