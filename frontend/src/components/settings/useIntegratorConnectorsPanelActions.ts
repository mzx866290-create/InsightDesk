import { useCallback } from 'react'

import type { IntegratorSchedulesPanelProps } from './IntegratorSchedulesPanel'
import type { UseIntegratorAuditResult } from './useIntegratorAudit'
import type { UseIntegratorConnectorCredentialsResult } from './useIntegratorConnectorCredentials'
import type { UseIntegratorConnectorsResult } from './useIntegratorConnectors'
import type { UseIntegratorSchedulesResult } from './useIntegratorSchedules'
import type { useMcpProductization } from './useMcpProductization'

type McpProductizationController = Pick<
  ReturnType<typeof useMcpProductization>,
  | 'loadMcpProductization'
  | 'handleMcpRuntimePing'
  | 'handleMcpHotUpdate'
  | 'handleMcpManifestInstall'
  | 'handleMcpTemplateSelect'
>

type ConnectorActionController = Pick<
  UseIntegratorConnectorsResult,
  | 'loadConnectors'
  | 'handleSave'
  | 'handleTest'
>

type CredentialActionController = Pick<
  UseIntegratorConnectorCredentialsResult,
  | 'handleRotateCredentials'
  | 'handleProbeConnector'
>

type ScheduleActionController = Pick<
  UseIntegratorSchedulesResult,
  | 'loadSchedules'
  | 'handleDryRunScheduleTick'
  | 'handleSaveSchedules'
  | 'handleTriggerSchedule'
>

type AuditRefreshController = Pick<UseIntegratorAuditResult, 'loadAuditEvents'>

export interface UseIntegratorConnectorsPanelActionsParams {
  mcpProductization: McpProductizationController
  connectorController: ConnectorActionController
  credentialController: CredentialActionController
  scheduleController: ScheduleActionController
  onRefreshAudit: () => void
}

export interface UseIntegratorConnectorsPanelActionsResult {
  handleMcpRefresh: () => void
  handleMcpRuntimePing: () => void
  handleMcpHotUpdate: () => void
  handleMcpManifestInstall: () => void
  handleConnectorRefresh: () => void
  handleConnectorSave: () => void
  handleConnectorTest: () => void
  handleRotateCredentials: () => void
  handleProbeConnector: () => void
  handleRefreshSchedules: () => void
  handleDryRunScheduleTick: () => void
  handleSaveSchedules: () => void
  handleTriggerSchedule: IntegratorSchedulesPanelProps['onTriggerSchedule']
  handleRefreshAudit: () => void
}

export function useIntegratorAuditRefreshAction(auditController: AuditRefreshController): () => void {
  return useCallback(() => {
    void auditController.loadAuditEvents()
  }, [auditController.loadAuditEvents])
}

export function useIntegratorConnectorsPanelActions({
  mcpProductization,
  connectorController,
  credentialController,
  scheduleController,
  onRefreshAudit,
}: UseIntegratorConnectorsPanelActionsParams): UseIntegratorConnectorsPanelActionsResult {
  const handleMcpRefresh = useCallback(() => {
    void mcpProductization.loadMcpProductization()
  }, [mcpProductization.loadMcpProductization])

  const handleMcpRuntimePing = useCallback(() => {
    void mcpProductization.handleMcpRuntimePing()
  }, [mcpProductization.handleMcpRuntimePing])

  const handleMcpHotUpdate = useCallback(() => {
    void mcpProductization.handleMcpHotUpdate()
  }, [mcpProductization.handleMcpHotUpdate])

  const handleMcpManifestInstall = useCallback(() => {
    void mcpProductization.handleMcpManifestInstall()
  }, [mcpProductization.handleMcpManifestInstall])

  const handleConnectorRefresh = useCallback(() => {
    void connectorController.loadConnectors()
  }, [connectorController.loadConnectors])

  const handleConnectorSave = useCallback(() => {
    void connectorController.handleSave()
  }, [connectorController.handleSave])

  const handleConnectorTest = useCallback(() => {
    void connectorController.handleTest()
  }, [connectorController.handleTest])

  const handleRotateCredentials = useCallback(() => {
    void credentialController.handleRotateCredentials()
  }, [credentialController.handleRotateCredentials])

  const handleProbeConnector = useCallback(() => {
    void credentialController.handleProbeConnector()
  }, [credentialController.handleProbeConnector])

  const handleRefreshSchedules = useCallback(() => {
    void scheduleController.loadSchedules()
  }, [scheduleController.loadSchedules])

  const handleDryRunScheduleTick = useCallback(() => {
    void scheduleController.handleDryRunScheduleTick()
  }, [scheduleController.handleDryRunScheduleTick])

  const handleSaveSchedules = useCallback(() => {
    void scheduleController.handleSaveSchedules()
  }, [scheduleController.handleSaveSchedules])

  const handleTriggerSchedule = useCallback<IntegratorSchedulesPanelProps['onTriggerSchedule']>((schedule) => {
    void scheduleController.handleTriggerSchedule(schedule)
  }, [scheduleController.handleTriggerSchedule])

  return {
    handleMcpRefresh,
    handleMcpRuntimePing,
    handleMcpHotUpdate,
    handleMcpManifestInstall,
    handleConnectorRefresh,
    handleConnectorSave,
    handleConnectorTest,
    handleRotateCredentials,
    handleProbeConnector,
    handleRefreshSchedules,
    handleDryRunScheduleTick,
    handleSaveSchedules,
    handleTriggerSchedule,
    handleRefreshAudit: onRefreshAudit,
  }
}
