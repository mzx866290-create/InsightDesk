import { useCallback, useEffect, useMemo, useState } from 'react'
import { getProviderCatalog, saveCloudModelApiKey, deleteCloudModelApiKey } from '../../api/client'
import type { ProviderCatalogItem } from '../../api/types/index'
import { useChatStore } from '../../stores/chatStore'
import {
  buildProviderDisplayList,
  createBuiltinProviderConfig,
  createCustomProviderConfig,
  type ProviderApiKeyFeedback,
  type ProviderCatalogStatus,
  type ProviderDisplayItem,
} from './modelProviderModel'

export function useModelProviderController() {
  const providerConfigs = useChatStore((s) => s.providerConfigs)
  const saveProviderConfig = useChatStore((s) => s.saveProviderConfig)
  const deleteProviderConfig = useChatStore((s) => s.deleteProviderConfig)

  const [catalog, setCatalog] = useState<ProviderCatalogItem[]>([])
  const [catalogStatus, setCatalogStatus] = useState<ProviderCatalogStatus>('loading')
  const [catalogRequestVersion, setCatalogRequestVersion] = useState(0)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [apiKeyDraft, setApiKeyDraft] = useState('')
  const [apiKeySaving, setApiKeySaving] = useState(false)
  const [apiKeyClearing, setApiKeyClearing] = useState(false)
  const [apiKeyFeedback, setApiKeyFeedback] = useState<ProviderApiKeyFeedback>(null)
  const [showApiKey, setShowApiKey] = useState(false)
  const [addingCustom, setAddingCustom] = useState(false)
  const [customName, setCustomName] = useState('')
  const [customBaseUrl, setCustomBaseUrl] = useState('')
  const [healthChecking, setHealthChecking] = useState(false)
  const [healthResult, setHealthResult] = useState<'ok' | 'fail' | null>(null)

  useEffect(() => {
    let cancelled = false
    setCatalogStatus('loading')
    setCatalog([])
    getProviderCatalog()
      .then((res) => {
        if (cancelled) return
        setCatalog(res.providers)
        setCatalogStatus('ready')
      })
      .catch(() => {
        if (cancelled) return
        setCatalog([])
        setCatalogStatus('error')
      })
    return () => { cancelled = true }
  }, [catalogRequestVersion])

  const reloadCatalog = useCallback(() => {
    setCatalogRequestVersion((version) => version + 1)
  }, [])

  const displayList = useMemo(
    () => buildProviderDisplayList(catalog, providerConfigs),
    [catalog, providerConfigs],
  )

  const selected = useMemo<ProviderDisplayItem | null>(
    () => displayList.find((p) => p.id === selectedId) ?? displayList[0] ?? null,
    [displayList, selectedId],
  )

  useEffect(() => {
    if (!selectedId && displayList.length > 0) {
      setSelectedId(displayList[0].id)
    }
  }, [selectedId, displayList])

  useEffect(() => {
    setApiKeyDraft('')
    setApiKeyFeedback(null)
    setShowApiKey(false)
    setHealthResult(null)
  }, [selectedId])

  const updateApiKeyDraft = useCallback((value: string) => {
    setApiKeyDraft(value)
    setApiKeyFeedback(null)
  }, [])

  const toggleEnabled = useCallback(() => {
    if (!selected) return
    const existing = providerConfigs.find((c) => c.id === selected.id)
    if (existing) {
      saveProviderConfig({ ...existing, enabled: !existing.enabled, updatedAt: Date.now() })
    } else {
      const config = createBuiltinProviderConfig(selected.connectionType)
      saveProviderConfig({ ...config, id: selected.id, enabled: true })
    }
  }, [selected, providerConfigs, saveProviderConfig])

  const saveApiKey = useCallback(async () => {
    if (!selected || !apiKeyDraft.trim()) return
    setApiKeySaving(true)
    setApiKeyFeedback(null)
    try {
      const existing = providerConfigs.find((c) => c.id === selected.id)
      const existingRef = existing?.apiKeyRef || ''
      const result = await saveCloudModelApiKey({
        api_key: apiKeyDraft.trim(),
        api_key_ref: existingRef || undefined,
        base_url: selected.baseUrl,
      })
      const config = existing ?? createBuiltinProviderConfig(selected.connectionType)
      saveProviderConfig({
        ...config,
        id: selected.id,
        name: selected.name,
        apiKeyRef: result.api_key_ref,
        updatedAt: Date.now(),
      })
      setApiKeyDraft('')
      setApiKeyFeedback('saved')
    } catch {
      setApiKeyFeedback('save_error')
    } finally {
      setApiKeySaving(false)
    }
  }, [selected, apiKeyDraft, providerConfigs, saveProviderConfig])

  const clearApiKey = useCallback(async () => {
    if (!selected) return
    const existing = providerConfigs.find((c) => c.id === selected.id)
    if (!existing?.apiKeyRef) return
    setApiKeyClearing(true)
    setApiKeyFeedback(null)
    try {
      await deleteCloudModelApiKey(existing.apiKeyRef)
      saveProviderConfig({ ...existing, apiKeyRef: '', updatedAt: Date.now() })
      setApiKeyFeedback('cleared')
    } catch {
      setApiKeyFeedback('clear_error')
    } finally {
      setApiKeyClearing(false)
    }
  }, [selected, providerConfigs, saveProviderConfig])

  const addCustomProvider = useCallback(() => {
    if (!customName.trim()) return
    const config = createCustomProviderConfig(customName.trim(), customBaseUrl.trim())
    saveProviderConfig(config)
    setSelectedId(config.id)
    setAddingCustom(false)
    setCustomName('')
    setCustomBaseUrl('')
  }, [customName, customBaseUrl, saveProviderConfig])

  const deleteSelected = useCallback(async () => {
    if (!selected || selected.isBuiltin) return
    if (selected.apiKeyRef) {
      await deleteCloudModelApiKey(selected.apiKeyRef)
    }
    deleteProviderConfig(selected.id)
    setSelectedId(null)
  }, [selected, deleteProviderConfig])

  const runHealthCheck = useCallback(async () => {
    if (!selected) return
    setHealthChecking(true)
    setHealthResult(null)
    try {
      const baseUrl = selected.baseUrl || 'http://localhost:11434'
      const normalizedBaseUrl = baseUrl.replace(/\/+$/, '')
      const modelsUrl = normalizedBaseUrl.endsWith('/v1')
        ? `${normalizedBaseUrl}/models`
        : `${normalizedBaseUrl}/v1/models`
      const resp = await fetch(modelsUrl, { signal: AbortSignal.timeout(5000) })
      setHealthResult(resp.ok ? 'ok' : 'fail')
    } catch {
      setHealthResult('fail')
    } finally {
      setHealthChecking(false)
    }
  }, [selected])

  return {
    displayList,
    selected,
    selectedId,
    setSelectedId,
    apiKeyDraft,
    setApiKeyDraft: updateApiKeyDraft,
    apiKeySaving,
    apiKeyClearing,
    apiKeyFeedback,
    showApiKey,
    setShowApiKey,
    toggleEnabled,
    saveApiKey,
    clearApiKey,
    addingCustom,
    setAddingCustom,
    customName,
    setCustomName,
    customBaseUrl,
    setCustomBaseUrl,
    addCustomProvider,
    deleteSelected,
    healthChecking,
    healthResult,
    runHealthCheck,
    catalogStatus,
    reloadCatalog,
    catalogLoaded: catalogStatus !== 'loading',
  }
}
