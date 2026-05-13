import { useMemo, useState } from 'react'
import type { Dispatch, SetStateAction } from 'react'

import type {
  McpConfigResponse,
  McpConnector,
  McpConnectorApprovalsResponse,
  McpRuntimeHealthHistoryItem,
  McpRuntimeHealthResponse,
} from '../../api/client'
import { buildMcpApprovalsConnectorView } from './mcpApprovalsModel'
import { useMcpApprovalActions } from './useMcpApprovalActions'
import { useMcpApprovalCatalogController } from './useMcpApprovalCatalogController'
import { useMcpConfigController } from './useMcpConfigController'
import { useMcpRuntimeHealthController } from './useMcpRuntimeHealthController'

export interface UseMcpApprovalsResult {
  approvals: McpConnectorApprovalsResponse
  sortedConnectors: McpConnector[]
  unknownApprovedConnectors: string[]
  connectorLabelByName: Map<string, string>
  mcpConfig: McpConfigResponse | null
  mcpConfigText: string
  runtimeHealth: McpRuntimeHealthResponse | null
  runtimeHealthHistory: McpRuntimeHealthHistoryItem[]
  loading: boolean
  loadingConfig: boolean
  savingConfig: boolean
  checkingRuntime: boolean
  loadingRuntimeHistory: boolean
  actingName: string | null
  error: string | null
  runtimeHistoryError: string | null
  notice: string | null
  setMcpConfigText: Dispatch<SetStateAction<string>>
  loadState: () => Promise<void>
  loadConfig: () => Promise<void>
  loadRuntimeHealthHistory: () => Promise<void>
  handleRuntimeHealth: () => Promise<void>
  handleSaveConfig: () => Promise<void>
  handleApprove: (name: string) => Promise<void>
  handleRevoke: (name: string) => Promise<void>
}

export function useMcpApprovals(): UseMcpApprovalsResult {
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const {
    connectors,
    approvals,
    setApprovals,
    loading,
    loadState,
  } = useMcpApprovalCatalogController({ setError, setNotice })
  const {
    runtimeHealth,
    setRuntimeHealth,
    runtimeHealthHistory,
    checkingRuntime,
    loadingRuntimeHistory,
    runtimeHistoryError,
    loadRuntimeHealthHistory,
    handleRuntimeHealth,
  } = useMcpRuntimeHealthController({ setError, setNotice })
  const {
    mcpConfig,
    mcpConfigText,
    setMcpConfigText,
    loadingConfig,
    savingConfig,
    loadConfig,
    handleSaveConfig,
  } = useMcpConfigController({
    loadState,
    loadRuntimeHealthHistory,
    setRuntimeHealth,
    setError,
    setNotice,
  })
  const {
    actingName,
    handleApprove,
    handleRevoke,
  } = useMcpApprovalActions({
    setApprovals,
    setRuntimeHealth,
    setError,
    setNotice,
  })

  const connectorView = useMemo(
    () => buildMcpApprovalsConnectorView(connectors, approvals),
    [approvals, connectors],
  )

  return {
    approvals,
    sortedConnectors: connectorView.sortedConnectors,
    unknownApprovedConnectors: connectorView.unknownApprovedConnectors,
    connectorLabelByName: connectorView.connectorLabelByName,
    mcpConfig,
    mcpConfigText,
    runtimeHealth,
    runtimeHealthHistory,
    loading,
    loadingConfig,
    savingConfig,
    checkingRuntime,
    loadingRuntimeHistory,
    actingName,
    error,
    runtimeHistoryError,
    notice,
    setMcpConfigText,
    loadState,
    loadConfig,
    loadRuntimeHealthHistory,
    handleRuntimeHealth,
    handleSaveConfig,
    handleApprove,
    handleRevoke,
  }
}
