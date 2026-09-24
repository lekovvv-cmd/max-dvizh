import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiTimeoutError, api } from './api'

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('API error messages', () => {
  it.each([
    [
      422,
      { detail: [{ loc: ['body', 'name'], msg: 'Field required', input: {} }] },
      'Проверь заполненные поля',
    ],
    [503, null, 'Сервис временно недоступен'],
    [409, { detail: 'internal conflict' }, 'Сервис временно недоступен'],
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

  it('times out a stalled submission with a recoverable message', async () => {
    vi.useFakeTimers()
    vi.stubGlobal(
      'fetch',
      (_url: string, init: RequestInit) =>
        new Promise((_resolve, reject) => {
          init.signal?.addEventListener('abort', () =>
            reject(new DOMException('Aborted', 'AbortError')),
          )
        }),
    )
    const result = api.signalBatch({})
    const assertion = expect(result).rejects.toBeInstanceOf(ApiTimeoutError)
    await vi.advanceTimersByTimeAsync(25_001)
    await assertion
    vi.useRealTimers()
  })
})
