import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { saveConfig } from '../../api/client'
import { useTavilySettings } from './useTavilySettings'

vi.mock('../../api/client', () => ({
  saveConfig: vi.fn(),
}))

describe('useTavilySettings', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('saves a typed Tavily key, clears the input, and refreshes config', async () => {
    vi.mocked(saveConfig).mockResolvedValue(undefined)
    const onConfigSaved = vi.fn()
    const { result } = renderHook(() => useTavilySettings())

    act(() => {
      result.current.setTavilyKey('tvly-test-key')
    })
    await act(async () => {
      await result.current.saveTavilyKey(onConfigSaved)
    })

    expect(saveConfig).toHaveBeenCalledWith({ tavily_api_key: 'tvly-test-key' })
    expect(onConfigSaved).toHaveBeenCalledTimes(1)
    expect(result.current.tavilyKey).toBe('')
    expect(result.current.saveOk).toBe(true)
    expect(result.current.saving).toBe(false)
    expect(result.current.saveError).toBeNull()
  })

  it('uses undefined to keep the configured key when saving an empty input', async () => {
    vi.mocked(saveConfig).mockResolvedValue(undefined)
    const { result } = renderHook(() => useTavilySettings())

    await act(async () => {
      await result.current.saveTavilyKey(vi.fn())
    })

    expect(saveConfig).toHaveBeenCalledWith({ tavily_api_key: undefined })
  })

  it('uses an empty string when clearing the configured Tavily key', async () => {
    vi.mocked(saveConfig).mockResolvedValue(undefined)
    const onConfigSaved = vi.fn()
    const { result } = renderHook(() => useTavilySettings())

    await act(async () => {
      await result.current.clearTavilyKey(onConfigSaved)
    })

    expect(saveConfig).toHaveBeenCalledWith({ tavily_api_key: '' })
    expect(onConfigSaved).toHaveBeenCalledTimes(1)
  })

  it('keeps the refresh callback untouched and exposes save errors', async () => {
    vi.mocked(saveConfig).mockRejectedValue(new Error('Unable to save Tavily key'))
    const onConfigSaved = vi.fn()
    const { result } = renderHook(() => useTavilySettings())

    await act(async () => {
      await result.current.saveTavilyKey(onConfigSaved)
    })

    expect(onConfigSaved).not.toHaveBeenCalled()
    expect(result.current.saveError).toBe('Unable to save Tavily key')
    expect(result.current.saving).toBe(false)
  })
})
