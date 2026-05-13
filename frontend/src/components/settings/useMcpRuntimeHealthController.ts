import { useCallback, useEffect, useState, type Dispatch, type SetStateAction } from 'react'

import {
  getMcpRuntimeHealth,
  getMcpRuntimeHealthHistory,
  type McpRuntimeHealthHistoryItem,
  type McpRuntimeHealthResponse,
} from '../../api/client'
import {
  MCP_RUNTIME_HEALTH_HISTORY_LIMIT,
  mcpErrorMessage,
} from './mcpApprovalsModel'

interface UseMcpRuntimeHealthControllerOptions {
  setError: (message: string | null) => void
  setNotice: (message: string | null) => void
}

interface McpRuntimeHealthController {
  runtimeHealth: McpRuntimeHealthResponse | null
  setRuntimeHealth: Dispatch<SetStateAction<McpRuntimeHealthResponse | null>>
  runtimeHealthHistory: McpRuntimeHealthHistoryItem[]
  checkingRuntime: boolean
  loadingRuntimeHistory: boolean
  runtimeHistoryError: string | null
  loadRuntimeHealthHistory: () => Promise<void>
  handleRuntimeHealth: () => Promise<void>
}

export function useMcpRuntimeHealthController({
  setError,
  setNotice,
}: UseMcpRuntimeHealthControllerOptions): McpRuntimeHealthController {
  const [runtimeHealth, setRuntimeHealth] = useState<McpRuntimeHealthResponse | null>(null)
  const [runtimeHealthHistory, setRuntimeHealthHistory] = useState<McpRuntimeHealthHistoryItem[]>([])
  const [checkingRuntime, setCheckingRuntime] = useState(false)
  const [loadingRuntimeHistory, setLoadingRuntimeHistory] = useState(false)
  const [runtimeHistoryError, setRuntimeHistoryError] = useState<string | null>(null)

  const loadRuntimeHealthHistory = useCallback(async () => {
    setLoadingRuntimeHistory(true)
    setRuntimeHistoryError(null)
    try {
      const payload = await getMcpRuntimeHealthHistory(MCP_RUNTIME_HEALTH_HISTORY_LIMIT)
      setRuntimeHealthHistory(payload.history)
    } catch (err) {
      setRuntimeHistoryError(mcpErrorMessage(err, 'Failed to load MCP runtime history'))
    } finally {
      setLoadingRuntimeHistory(false)
    }
  }, [])

  useEffect(() => {
    void loadRuntimeHealthHistory()
  }, [loadRuntimeHealthHistory])

  const handleRuntimeHealth = useCallback(async () => {
    setCheckingRuntime(true)
    setError(null)
    setNotice(null)
    try {
      const payload = await getMcpRuntimeHealth()
      setRuntimeHealth(payload)
      void loadRuntimeHealthHistory()
      setNotice(`Runtime health: ${payload.status}`)
    } catch (err) {
      setError(mcpErrorMessage(err, 'Failed to check MCP runtime health'))
    } finally {
      setCheckingRuntime(false)
    }
  }, [loadRuntimeHealthHistory, setError, setNotice])

  return {
    runtimeHealth,
    setRuntimeHealth,
    runtimeHealthHistory,
    checkingRuntime,
    loadingRuntimeHistory,
    runtimeHistoryError,
    loadRuntimeHealthHistory,
    handleRuntimeHealth,
  }
}
