import { useCallback, useMemo, useState } from 'react'

import type {
  IntegratorConnectorTestResult,
  IntegratorConnectorsResponse,
} from '../../api/client'
import {
  connectorStats as deriveConnectorStats,
  DEFAULT_CONNECTOR,
  toDraft,
} from './integratorConnectorModel'
import type { ConnectorDraft, ConnectorStats } from './integratorConnectorModel'
import {
  loadIntegratorConnectorCatalog,
  saveIntegratorConnectorDrafts,
  testIntegratorConnectorDraft,
} from './integratorConnectorActions'
import {
  clampConnectorSelectionIndex,
  connectorActionErrorMessage,
  DEFAULT_SUPPORTED_CONNECTOR_TYPES,
  supportedConnectorTypesOrDefault,
} from './integratorConnectorHookModel'

export interface UseIntegratorConnectorsOptions {
  onAuditRefresh?: () => void
}

export interface UseIntegratorConnectorsResult {
  connectors: ConnectorDraft[]
  supportedTypes: string[]
  persistence: IntegratorConnectorsResponse['persistence'] | null
  selectedIndex: number
  selectedConnector: ConnectorDraft | null
  connectorStats: ConnectorStats
  loading: boolean
  saving: boolean
  testing: boolean
  testResult: IntegratorConnectorTestResult | null
  error: string | null
  notice: string | null
  setConnectors: React.Dispatch<React.SetStateAction<ConnectorDraft[]>>
  setSelectedIndex: React.Dispatch<React.SetStateAction<number>>
  setError: React.Dispatch<React.SetStateAction<string | null>>
  setNotice: React.Dispatch<React.SetStateAction<string | null>>
  setTestResult: React.Dispatch<React.SetStateAction<IntegratorConnectorTestResult | null>>
  loadConnectors: () => Promise<void>
  updateConnector: (index: number, patch: Partial<ConnectorDraft>) => void
  addConnector: () => void
  removeConnector: (index: number) => void
  updateSelectedConnector: (connector: ConnectorDraft) => void
  handleSave: () => Promise<void>
  handleTest: () => Promise<void>
}

export function useIntegratorConnectors(
  options: UseIntegratorConnectorsOptions = {},
): UseIntegratorConnectorsResult {
  const { onAuditRefresh } = options
  const [connectors, setConnectors] = useState<ConnectorDraft[]>([])
  const [supportedTypes, setSupportedTypes] = useState<string[]>(DEFAULT_SUPPORTED_CONNECTOR_TYPES)
  const [persistence, setPersistence] = useState<IntegratorConnectorsResponse['persistence'] | null>(null)
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<IntegratorConnectorTestResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const selectedConnector = connectors[selectedIndex] ?? null
  const connectorStats = useMemo(
    () => deriveConnectorStats(connectors),
    [connectors],
  )

  const refreshAudit = useCallback(() => {
    onAuditRefresh?.()
  }, [onAuditRefresh])

  const loadConnectors = useCallback(async () => {
    setLoading(true)
    setError(null)
    setNotice(null)
    try {
      const payload = await loadIntegratorConnectorCatalog()
      setConnectors(payload.connectors.map(toDraft))
      setSupportedTypes(supportedConnectorTypesOrDefault(payload.supported_types))
      setPersistence(payload.persistence)
      setTestResult(null)
      setSelectedIndex(0)
    } catch (err) {
      setError(connectorActionErrorMessage(err, 'Failed to load integration connectors'))
    } finally {
      setLoading(false)
    }
  }, [])

  const updateConnector = useCallback((index: number, patch: Partial<ConnectorDraft>) => {
    setConnectors((current) =>
      current.map((connector, itemIndex) =>
        itemIndex === index ? { ...connector, ...patch } : connector,
      ),
    )
  }, [])

  const updateSelectedConnector = useCallback((connector: ConnectorDraft) => {
    setConnectors((current) =>
      current.map((item, index) => (index === selectedIndex ? connector : item)),
    )
  }, [selectedIndex])

  const addConnector = useCallback(() => {
    setConnectors((current) => {
      const next = [
        ...current,
        { ...DEFAULT_CONNECTOR, name: `Webhook ${current.length + 1}` },
      ]
      setSelectedIndex(next.length - 1)
      return next
    })
    setNotice(null)
    setError(null)
    setTestResult(null)
  }, [])

  const removeConnector = useCallback((index: number) => {
    setConnectors((current) => current.filter((_, itemIndex) => itemIndex !== index))
    setSelectedIndex((current) => clampConnectorSelectionIndex(current, connectors.length - 1))
    setNotice(null)
    setTestResult(null)
  }, [connectors.length])

  const handleSave = useCallback(async () => {
    setSaving(true)
    setError(null)
    setNotice(null)
    try {
      const payload = await saveIntegratorConnectorDrafts(connectors)
      setConnectors(payload.connectors.map(toDraft))
      setSupportedTypes(supportedConnectorTypesOrDefault(payload.supported_types.length > 0 ? payload.supported_types : supportedTypes))
      setPersistence(payload.persistence)
      setSelectedIndex((index) => clampConnectorSelectionIndex(index, payload.connectors.length))
      setTestResult(null)
      setNotice('Integration connector configuration saved')
      refreshAudit()
    } catch (err) {
      setError(connectorActionErrorMessage(err, 'Failed to save integration connectors'))
    } finally {
      setSaving(false)
    }
  }, [connectors, refreshAudit, supportedTypes])

  const handleTest = useCallback(async () => {
    if (!selectedConnector) return
    setTesting(true)
    setError(null)
    setNotice(null)
    setTestResult(null)
    try {
      const payload = await testIntegratorConnectorDraft(selectedConnector)
      setTestResult(payload)
      setNotice(`Connector test ${payload.status}`)
      refreshAudit()
    } catch (err) {
      setError(connectorActionErrorMessage(err, 'Failed to test integration connector'))
    } finally {
      setTesting(false)
    }
  }, [refreshAudit, selectedConnector])

  return {
    connectors,
    supportedTypes,
    persistence,
    selectedIndex,
    selectedConnector,
    connectorStats,
    loading,
    saving,
    testing,
    testResult,
    error,
    notice,
    setConnectors,
    setSelectedIndex,
    setError,
    setNotice,
    setTestResult,
    loadConnectors,
    updateConnector,
    addConnector,
    removeConnector,
    updateSelectedConnector,
    handleSave,
    handleTest,
  }
}
