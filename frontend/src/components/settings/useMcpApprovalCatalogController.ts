import { useCallback, useEffect, useState, type Dispatch, type SetStateAction } from 'react'

import {
  getMcpConnectorApprovals,
  getMcpConnectors,
  type McpConnector,
  type McpConnectorApprovalsResponse,
} from '../../api/client'
import {
  emptyApprovalPayload,
  mcpErrorMessage,
  normalizeApprovalPayload,
} from './mcpApprovalsModel'

interface UseMcpApprovalCatalogControllerOptions {
  setError: (message: string | null) => void
  setNotice: (message: string | null) => void
}

interface McpApprovalCatalogController {
  connectors: McpConnector[]
  approvals: McpConnectorApprovalsResponse
  setApprovals: Dispatch<SetStateAction<McpConnectorApprovalsResponse>>
  loading: boolean
  loadState: () => Promise<void>
}

export function useMcpApprovalCatalogController({
  setError,
  setNotice,
}: UseMcpApprovalCatalogControllerOptions): McpApprovalCatalogController {
  const [connectors, setConnectors] = useState<McpConnector[]>([])
  const [approvals, setApprovals] = useState<McpConnectorApprovalsResponse>(() => emptyApprovalPayload())
  const [loading, setLoading] = useState(false)

  const loadState = useCallback(async () => {
    setLoading(true)
    setError(null)
    setNotice(null)
    try {
      const [catalogPayload, approvalsPayload] = await Promise.all([
        getMcpConnectors(),
        getMcpConnectorApprovals(),
      ])
      setConnectors(catalogPayload.connectors)
      setApprovals(normalizeApprovalPayload(approvalsPayload))
    } catch (err) {
      setError(mcpErrorMessage(err, 'Failed to load MCP approvals'))
    } finally {
      setLoading(false)
    }
  }, [setError, setNotice])

  useEffect(() => {
    void loadState()
  }, [loadState])

  return {
    connectors,
    approvals,
    setApprovals,
    loading,
    loadState,
  }
}
