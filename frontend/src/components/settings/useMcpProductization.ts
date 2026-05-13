import { useCallback, useEffect, useMemo, useState } from 'react'

import {
  getMcpConfig,
  getMcpRuntimeHealth,
  installMcpConnectorManifest,
  saveMcpConfig,
} from '../../api/client'
import type {
  McpConfigResponse,
  McpConnector,
  McpConnectorManifest,
  McpRuntimeHealthResponse,
} from '../../api/client'
import * as mcpMarketplaceModel from './mcpMarketplaceModel'

export function useMcpProductization() {
  const [mcpConfig, setMcpConfig] = useState<McpConfigResponse | null>(null)
  const [mcpRuntimeHealth, setMcpRuntimeHealth] = useState<McpRuntimeHealthResponse | null>(null)
  const [mcpMarketplaceCategoryId, setMcpMarketplaceCategoryId] = useState('all')
  const [mcpLoading, setMcpLoading] = useState(false)
  const [mcpPinging, setMcpPinging] = useState(false)
  const [mcpHotUpdating, setMcpHotUpdating] = useState(false)
  const [mcpInstalling, setMcpInstalling] = useState(false)
  const [mcpManifestText, setMcpManifestText] = useState('')
  const [mcpError, setMcpError] = useState<string | null>(null)
  const [mcpNotice, setMcpNotice] = useState<string | null>(null)

  const mcpConnectors = mcpConfig?.connectors ?? []
  const mcpManifestValidation = useMemo(() => (
    mcpMarketplaceModel.validateMcpConnectorManifestText(mcpManifestText)
  ), [mcpManifestText])

  const mcpMarketplaceSummary = useMemo(() => {
    return mcpMarketplaceModel.mcpMarketplaceSummaryFromConfig(mcpConfig, mcpConnectors)
  }, [mcpConfig?.marketplace?.summary, mcpConnectors])

  const mcpMarketplaceCategories = useMemo(() => {
    return mcpMarketplaceModel.mcpMarketplaceCategoriesFromConfig(mcpConfig, mcpConnectors)
  }, [mcpConfig?.marketplace?.categories, mcpConnectors])

  const visibleMcpConnectors = useMemo(() => {
    return mcpMarketplaceModel.visibleMcpConnectors(
      mcpConfig,
      mcpConnectors,
      mcpMarketplaceCategoryId,
    )
  }, [mcpConnectors, mcpMarketplaceCategories, mcpMarketplaceCategoryId, mcpConfig])

  useEffect(() => {
    if (mcpMarketplaceCategoryId === 'all') return
    if (mcpMarketplaceCategories.some((category) => category.id === mcpMarketplaceCategoryId)) return
    setMcpMarketplaceCategoryId('all')
  }, [mcpMarketplaceCategories, mcpMarketplaceCategoryId])

  const loadMcpProductization = useCallback(async () => {
    setMcpLoading(true)
    setMcpError(null)
    setMcpNotice(null)
    try {
      const [configPayload, healthPayload] = await Promise.all([
        getMcpConfig(),
        getMcpRuntimeHealth(),
      ])
      setMcpConfig(configPayload)
      setMcpRuntimeHealth(healthPayload)
    } catch (err) {
      setMcpError(err instanceof Error ? err.message : String(err || 'Failed to load MCP connector status'))
    } finally {
      setMcpLoading(false)
    }
  }, [])

  const handleMcpRuntimePing = useCallback(async () => {
    setMcpPinging(true)
    setMcpError(null)
    setMcpNotice(null)
    try {
      const payload = await getMcpRuntimeHealth()
      setMcpRuntimeHealth(payload)
      setMcpNotice(`MCP runtime health ${payload.status}`)
    } catch (err) {
      setMcpError(err instanceof Error ? err.message : String(err || 'Failed to refresh MCP runtime health'))
    } finally {
      setMcpPinging(false)
    }
  }, [])

  const handleMcpHotUpdate = useCallback(async () => {
    if (!mcpConfig) return
    setMcpHotUpdating(true)
    setMcpError(null)
    setMcpNotice(null)
    try {
      const payload = await saveMcpConfig({ servers: mcpConfig.servers })
      setMcpConfig(payload)
      await handleMcpRuntimePing()
      setMcpNotice('MCP configuration hot update applied')
    } catch (err) {
      setMcpError(err instanceof Error ? err.message : String(err || 'Failed to hot update MCP configuration'))
    } finally {
      setMcpHotUpdating(false)
    }
  }, [handleMcpRuntimePing, mcpConfig])

  const handleMcpManifestInstall = useCallback(async () => {
    if (!mcpManifestValidation.valid || !mcpManifestValidation.parsed) {
      setMcpError(mcpManifestValidation.errors[0] || 'MCP connector manifest must be valid before install')
      setMcpNotice(null)
      return
    }

    const manifest: McpConnectorManifest = mcpManifestValidation.parsed
    setMcpInstalling(true)
    setMcpError(null)
    setMcpNotice(null)
    try {
      const payload = await installMcpConnectorManifest({ manifest })
      const connectorName = payload.installed?.name || manifest.name
      setMcpConfig(payload)
      setMcpManifestText('')
      setMcpNotice(`Installed MCP connector ${connectorName}; install commands were not executed`)
    } catch (err) {
      setMcpError(err instanceof Error ? err.message : String(err || 'Failed to install MCP connector manifest'))
    } finally {
      setMcpInstalling(false)
    }
  }, [mcpManifestValidation])

  const handleMcpTemplateSelect = useCallback((connector: McpConnector) => {
    setMcpManifestText(mcpMarketplaceModel.formatMcpConnectorManifestDraft(connector))
    setMcpError(null)
    setMcpNotice(`Loaded template for ${connector.label || connector.name}; fill command or URL before installing`)
  }, [])

  return {
    mcpConfig,
    mcpRuntimeHealth,
    mcpMarketplaceCategoryId,
    mcpMarketplaceSummary,
    mcpMarketplaceCategories,
    visibleMcpConnectors,
    mcpLoading,
    mcpPinging,
    mcpHotUpdating,
    mcpInstalling,
    mcpManifestText,
    mcpManifestValidation,
    mcpError,
    mcpNotice,
    loadMcpProductization,
    handleMcpRuntimePing,
    handleMcpHotUpdate,
    handleMcpManifestInstall,
    handleMcpTemplateSelect,
    setMcpManifestText,
    setMcpMarketplaceCategoryId,
  }
}
