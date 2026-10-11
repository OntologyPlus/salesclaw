import { describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { useFetch } from './useFetch'

describe('useFetch', () => {
  it('surfaces error for retryable failures', async () => {
    const fetcher = vi.fn().mockRejectedValue(new Error('network down'))
    const { result } = renderHook(() => useFetch(fetcher, ['error-case']))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.error?.message).toMatch(/network down/)
    expect(result.current.data).toBeNull()
  })

  it('returns data on success', async () => {
    const fetcher = vi.fn().mockResolvedValue({ ok: true })
    const { result } = renderHook(() => useFetch(fetcher, ['success-case']))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.data).toEqual({ ok: true })
    expect(result.current.error).toBeNull()
  })
})
