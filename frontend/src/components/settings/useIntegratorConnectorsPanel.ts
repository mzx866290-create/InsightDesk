import { useEffect } from 'react'

import type { IntegratorConnectorTestResult } from '../../api/client'
import type { IntegratorAuditPanelProps } from './IntegratorAuditPanel'
import type { IntegratorConnectorCredentialsPanelProps } from './IntegratorConnectorCredentialsPanel'
import type { IntegratorConnectorDetailsPanelProps } from './IntegratorConnectorDetailsPanel'
import type { IntegratorConnectorListPanelProps } from './IntegratorConnectorListPanel'
import type { IntegratorConnectorsToolbarPanelProps } from './IntegratorConnectorsToolbarPanel'
import type { IntegratorSchedulesPanelProps } from './IntegratorSchedulesPanel'
import type { McpProductizationPanelProps } from './integratorConnectorsPanelProps'
import { useIntegratorAudit } from './useIntegratorAudit'
import { useIntegratorConnectorCredentials } from './useIntegratorConnectorCredentials'
import { useIntegratorConnectors } from './useIntegratorConnectors'
import {
  useIntegratorAuditRefreshAction,
  useIntegratorConnectorsPanelActions,
} from './useIntegratorConnectorsPanelActions'
import { useIntegratorConnectorsPanelProps } from './useIntegratorConnectorsPanelProps'
import { useIntegratorSchedules } from './useIntegratorSchedules'
import { useMcpProductization } from './useMcpProductization'

export interface UseIntegratorConnectorsPanelResult {
  mcpProductizationPanelProps: McpProductizationPanelProps
  connectorToolbarProps: IntegratorConnectorsToolbarPanelProps
  connectorListProps: IntegratorConnectorListPanelProps
  connectorDetailsProps: IntegratorConnectorDetailsPanelProps
  credentialPanelProps: IntegratorConnectorCredentialsPanelProps | null
  connectorTestResult: IntegratorConnectorTestResult | null
  schedulesPanelProps: IntegratorSchedulesPanelProps
  auditPanelProps: IntegratorAuditPanelProps
}

export function useIntegratorConnectorsPanel(): UseIntegratorConnectorsPanelResult {
  const auditController = useIntegratorAudit()
  const refreshAudit = useIntegratorAuditRefreshAction(auditController)

  const connectorController = useIntegratorConnectors({ onAuditRefresh: refreshAudit })
  const selectedConnector = connectorController.selectedConnector
  const credentialController = useIntegratorConnectorCredentials({
    selectedConnector,
    resetKey: connectorController.selectedIndex,
    onConnectorUpdated: connectorController.updateSelectedConnector,
    onError: connectorController.setError,
    onNotice: connectorController.setNotice,
    onAuditRefresh: refreshAudit,
  })
  const mcpProductization = useMcpProductization()
  const scheduleController = useIntegratorSchedules(connectorController.connectors)

  useEffect(() => {
    void mcpProductization.loadMcpProductization()
    void connectorController.loadConnectors()
    void auditController.loadAuditEvents()
    void scheduleController.loadSchedules()
  }, [
    auditController.loadAuditEvents,
    connectorController.loadConnectors,
    mcpProductization.loadMcpProductization,
    scheduleController.loadSchedules,
  ])

  const actions = useIntegratorConnectorsPanelActions({
    mcpProductization,
    connectorController,
    credentialController,
    scheduleController,
    onRefreshAudit: refreshAudit,
  })
  const panelProps = useIntegratorConnectorsPanelProps({
    auditController,
    connectorController,
    credentialController,
    mcpProductization,
    scheduleController,
    selectedConnector,
    actions,
  })

  return {
    ...panelProps,
    connectorTestResult: connectorController.testResult,
  }
}
