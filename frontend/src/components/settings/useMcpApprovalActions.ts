import { useCallback, useState, type Dispatch, type SetStateAction } from 'react'

import {
  approveMcpConnector,
  revokeMcpConnectorApproval,
  type McpConnectorApprovalsResponse,
  type McpRuntimeHealthResponse,
} from '../../api/client'
import {
  mcpErrorMessage,
  normalizeApprovalPayload,
} from './mcpApprovalsModel'

interface UseMcpApprovalActionsOptions {
  setApprovals: Dispatch<SetStateAction<McpConnectorApprovalsResponse>>
  setRuntimeHealth: Dispatch<SetStateAction<McpRuntimeHealthResponse | null>>
  setError: (message: string | null) => void
  setNotice: (message: string | null) => void
}

interface McpApprovalActions {
  actingName: string | null
  handleApprove: (name: string) => Promise<void>
  handleRevoke: (name: string) => Promise<void>
}

export function useMcpApprovalActions({
  setApprovals,
  setRuntimeHealth,
  setError,
  setNotice,
}: UseMcpApprovalActionsOptions): McpApprovalActions {
  const [actingName, setActingName] = useState<string | null>(null)

  const handleApprove = useCallback(async (name: string) => {
    setActingName(name)
    setError(null)
    setNotice(null)
    try {
      const payload = await approveMcpConnector(name)
      setApprovals(normalizeApprovalPayload(payload))
      setRuntimeHealth(null)
      setNotice(`Approved ${name}`)
    } catch (err) {
      setError(mcpErrorMessage(err, 'Failed to approve MCP connector'))
    } finally {
      setActingName(null)
    }
  }, [setApprovals, setError, setNotice, setRuntimeHealth])

  const handleRevoke = useCallback(async (name: string) => {
    setActingName(name)
    setError(null)
    setNotice(null)
    try {
      const payload = await revokeMcpConnectorApproval(name)
      setApprovals(normalizeApprovalPayload(payload))
      setRuntimeHealth(null)
      setNotice(`Revoked runtime approval for ${name}`)
    } catch (err) {
      setError(mcpErrorMessage(err, 'Failed to revoke MCP connector approval'))
    } finally {
      setActingName(null)
    }
  }, [setApprovals, setError, setNotice, setRuntimeHealth])

  return {
    actingName,
    handleApprove,
    handleRevoke,
  }
}
