import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { ProviderCatalogResponse } from '../../api/types/index'
import { useChatStore } from '../../stores/chatStore'
import { createBuiltinProviderConfig, createCustomProviderConfig } from './modelProviderModel'
import { useModelProviderController } from './useModelProviderController'

const mocks = vi.hoisted(() => ({
  deleteCloudModelApiKey: vi.fn(),
  getProviderCatalog: vi.fn(),
  saveCloudModelApiKey: vi.fn(),
}))

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client')
  return {
    ...actual,
    deleteCloudModelApiKey: mocks.deleteCloudModelApiKey,
    getProviderCatalog: mocks.getProviderCatalog,
    saveCloudModelApiKey: mocks.saveCloudModelApiKey,
  }
})

const catalogResponse: ProviderCatalogResponse = {
  providers: [
    {
      id: 'openai-compatible',
      connection_type: 'openai_compatible',
      aliases: ['cloud'],
      capabilities: ['chat'],
      default_base_url: 'https://openrouter.ai/api/v1',
      default_model: 'gpt-4o-mini',
      base_url_env_keys: [],
      model_env_keys: [],
    },
  ],
  default_provider: 'openai_compatible',
  total: 1,
}

describe('useModelProviderController', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useChatStore.setState({ providerConfigs: [] })
    mocks.getProviderCatalog.mockResolvedValue(catalogResponse)
  })

  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  it('surfaces catalog failures and retries explicitly', async () => {
    mocks.getProviderCatalog
      .mockRejectedValueOnce(new Error('catalog unavailable'))
      .mockResolvedValueOnce(catalogResponse)
    const { result } = renderHook(() => useModelProviderController())

    await waitFor(() => expect(result.current.catalogStatus).toBe('error'))

    act(() => result.current.reloadCatalog())

    await waitFor(() => expect(result.current.catalogStatus).toBe('ready'))
    expect(result.current.displayList).toHaveLength(1)
    expect(result.current.displayList[0].apiKeyUrl).toBe('https://openrouter.ai/settings/keys')
    expect(mocks.getProviderCatalog).toHaveBeenCalledTimes(2)
  })

  it('exposes save failures and success instead of swallowing them', async () => {
    mocks.saveCloudModelApiKey
      .mockRejectedValueOnce(new Error('save failed'))
      .mockResolvedValueOnce({ api_key_ref: 'managed-key', api_key_set: true })
    const { result } = renderHook(() => useModelProviderController())
    await waitFor(() => expect(result.current.selected).not.toBeNull())

    act(() => result.current.setApiKeyDraft('secret'))
    await act(async () => result.current.saveApiKey())
    expect(result.current.apiKeyFeedback).toBe('save_error')
    expect(result.current.apiKeySaving).toBe(false)

    act(() => result.current.setApiKeyDraft('secret'))
    await act(async () => result.current.saveApiKey())
    expect(result.current.apiKeyFeedback).toBe('saved')
    expect(result.current.apiKeyDraft).toBe('')
    expect(mocks.saveCloudModelApiKey).toHaveBeenLastCalledWith({
      api_key: 'secret',
      api_key_ref: undefined,
      base_url: 'https://openrouter.ai/api/v1',
    })
  })

  it('exposes clear failures and success instead of swallowing them', async () => {
    useChatStore.setState({
      providerConfigs: [
        {
          ...createBuiltinProviderConfig('openai_compatible'),
          apiKeyRef: 'managed-key',
        },
      ],
    })
    mocks.deleteCloudModelApiKey
      .mockRejectedValueOnce(new Error('clear failed'))
      .mockResolvedValueOnce(undefined)
    const { result } = renderHook(() => useModelProviderController())
    await waitFor(() => expect(result.current.selected?.apiKeyRef).toBe('managed-key'))

    await act(async () => result.current.clearApiKey())
    expect(result.current.apiKeyFeedback).toBe('clear_error')
    expect(result.current.apiKeyClearing).toBe(false)

    await act(async () => result.current.clearApiKey())
    expect(result.current.apiKeyFeedback).toBe('cleared')
    expect(result.current.apiKeyClearing).toBe(false)
  })

  it('reports failed and successful health checks', async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce({ ok: true })
    vi.stubGlobal('fetch', fetchMock)
    const { result } = renderHook(() => useModelProviderController())
    await waitFor(() => expect(result.current.selected).not.toBeNull())

    await act(async () => result.current.runHealthCheck())
    expect(result.current.healthResult).toBe('fail')

    await act(async () => result.current.runHealthCheck())
    expect(result.current.healthResult).toBe('ok')
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fetchMock).toHaveBeenLastCalledWith(
      'https://openrouter.ai/api/v1/models',
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
  })

  it('keeps a custom provider when managed key deletion fails and removes it after success', async () => {
    const customProvider = {
      ...createCustomProviderConfig('Custom Provider', 'https://custom.example/v1'),
      id: 'custom-provider',
      apiKeyRef: 'managed-custom-key',
    }
    useChatStore.setState({ providerConfigs: [customProvider] })
    mocks.deleteCloudModelApiKey
      .mockRejectedValueOnce(new Error('managed key delete failed'))
      .mockResolvedValueOnce(undefined)
    const { result } = renderHook(() => useModelProviderController())
    await waitFor(() => expect(result.current.catalogStatus).toBe('ready'))

    act(() => result.current.setSelectedId(customProvider.id))
    await waitFor(() => expect(result.current.selected?.id).toBe(customProvider.id))

    await act(async () => {
      await expect(result.current.deleteSelected()).rejects.toThrow('managed key delete failed')
    })
    expect(useChatStore.getState().providerConfigs).toContainEqual(customProvider)

    await act(async () => {
      await result.current.deleteSelected()
    })
    expect(mocks.deleteCloudModelApiKey).toHaveBeenCalledTimes(2)
    expect(mocks.deleteCloudModelApiKey).toHaveBeenCalledWith('managed-custom-key')
    expect(useChatStore.getState().providerConfigs).not.toContainEqual(customProvider)
  })
})
