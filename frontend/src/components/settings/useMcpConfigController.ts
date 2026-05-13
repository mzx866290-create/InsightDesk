import { useCallback, useEffect, useState, type Dispatch, type SetStateAction } from 'react'

import {
  getMcpConfig,
  saveMcpConfig,
  type McpConfigResponse,
  type McpRuntimeHealthResponse,
} from '../../api/client'
import {
  formatMcpConfigEditorValue,
  mcpErrorMessage,
  parseMcpConfigEditorValue,
} from './mcpApprovalsModel'

interface UseMcpConfigControllerOptions {
  loadState: () => Promise<void>
  loadRuntimeHealthHistory: () => Promise<void>
  setRuntimeHealth: Dispatch<SetStateAction<McpRuntimeHealthResponse | null>>
  setError: (message: string | null) => void
  setNotice: (message: string | null) => void
}

interface McpConfigController {
  mcpConfig: McpConfigResponse | null
  mcpConfigText: string
  setMcpConfigText: Dispatch<SetStateAction<string>>
  loadingConfig: boolean
  savingConfig: boolean
  loadConfig: () => Promise<void>
  handleSaveConfig: () => Promise<void>
}

export function useMcpConfigController({
  loadState,
  loadRuntimeHealthHistory,
  setRuntimeHealth,
  setError,
  setNotice,
}: UseMcpConfigControllerOptions): McpConfigController {
  const [mcpConfig, setMcpConfig] = useState<McpConfigResponse | null>(null)
  const [mcpConfigText, setMcpConfigText] = useState('')
  const [loadingConfig, setLoadingConfig] = useState(false)
  const [savingConfig, setSavingConfig] = useState(false)

  const loadConfig = useCallback(async () => {
    setLoadingConfig(true)
    setError(null)
    try {
      const payload = await getMcpConfig()
      setMcpConfig(payload)
      setMcpConfigText(formatMcpConfigEditorValue(payload))
    } catch (err) {
      setError(mcpErrorMessage(err, 'Failed to load MCP config'))
    } finally {
      setLoadingConfig(false)
    }
  }, [setError])

  useEffect(() => {
    void loadConfig()
  }, [loadConfig])

  const handleSaveConfig = useCallback(async () => {
    setSavingConfig(true)
    setError(null)
    setNotice(null)
    try {
      const payload = parseMcpConfigEditorValue(mcpConfigText)
      const saved = await saveMcpConfig(payload)
      setMcpConfig(saved)
      setMcpConfigText(formatMcpConfigEditorValue(saved))
      setRuntimeHealth(null)
      await Promise.all([loadState(), loadRuntimeHealthHistory()])
      setNotice('Config saved')
    } catch (err) {
      setError(mcpErrorMessage(err, 'Failed to save MCP config'))
    } finally {
      setSavingConfig(false)
    }
  }, [
    loadRuntimeHealthHistory,
    loadState,
    mcpConfigText,
    setError,
    setNotice,
    setRuntimeHealth,
  ])

  return {
    mcpConfig,
    mcpConfigText,
    setMcpConfigText,
    loadingConfig,
    savingConfig,
    loadConfig,
    handleSaveConfig,
  }
}
