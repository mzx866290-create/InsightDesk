import { useMemo } from 'react'

import type { IntegratorAuditPanelProps } from './IntegratorAuditPanel'
import type { IntegratorConnectorCredentialsPanelProps } from './IntegratorConnectorCredentialsPanel'
import type { IntegratorConnectorDetailsPanelProps } from './IntegratorConnectorDetailsPanel'
import type { IntegratorConnectorListPanelProps } from './IntegratorConnectorListPanel'
import type { IntegratorConnectorsToolbarPanelProps } from './IntegratorConnectorsToolbarPanel'
import type { IntegratorSchedulesPanelProps } from './IntegratorSchedulesPanel'
import {
  buildAuditPanelProps,
  buildConnectorDetailsProps,
  buildConnectorListProps,
  buildConnectorToolbarProps,
  buildCredentialPanelProps,
  buildMcpProductizationPanelProps,
  buildSchedulesPanelProps,
  type McpProductizationPanelProps,
} from './integratorConnectorsPanelProps'
import type { ConnectorDraft } from './integratorConnectorModel'
import type { UseIntegratorAuditResult } from './useIntegratorAudit'
import type { UseIntegratorConnectorCredentialsResult } from './useIntegratorConnectorCredentials'
import type { UseIntegratorConnectorsResult } from './useIntegratorConnectors'
import type { UseIntegratorConnectorsPanelActionsResult } from './useIntegratorConnectorsPanelActions'
import type { UseIntegratorSchedulesResult } from './useIntegratorSchedules'
import type { useMcpProductization } from './useMcpProductization'

type McpProductizationController = ReturnType<typeof useMcpProductization>

interface UseIntegratorConnectorsPanelPropsOptions {
  auditController: UseIntegratorAuditResult
  connectorController: UseIntegratorConnectorsResult
  credentialController: UseIntegratorConnectorCredentialsResult
  mcpProductization: McpProductizationController
  scheduleController: UseIntegratorSchedulesResult
  selectedConnector: ConnectorDraft | null
  actions: UseIntegratorConnectorsPanelActionsResult
}

export interface UseIntegratorConnectorsPanelPropsResult {
  mcpProductizationPanelProps: McpProductizationPanelProps
  connectorToolbarProps: IntegratorConnectorsToolbarPanelProps
  connectorListProps: IntegratorConnectorListPanelProps
  connectorDetailsProps: IntegratorConnectorDetailsPanelProps
  credentialPanelProps: IntegratorConnectorCredentialsPanelProps | null
  schedulesPanelProps: IntegratorSchedulesPanelProps
  auditPanelProps: IntegratorAuditPanelProps
}

export function useIntegratorConnectorsPanelProps({
  auditController,
  connectorController,
  credentialController,
  mcpProductization,
  scheduleController,
  selectedConnector,
  actions,
}: UseIntegratorConnectorsPanelPropsOptions): UseIntegratorConnectorsPanelPropsResult {
  const mcpProductizationPanelProps = useMemo<McpProductizationPanelProps>(() => (
    buildMcpProductizationPanelProps({
      mcpProductization,
      onRefresh: actions.handleMcpRefresh,
      onRuntimePing: actions.handleMcpRuntimePing,
      onHotUpdate: actions.handleMcpHotUpdate,
      onManifestInstall: actions.handleMcpManifestInstall,
    })
  ), [
    actions.handleMcpHotUpdate,
    actions.handleMcpManifestInstall,
    actions.handleMcpRefresh,
    actions.handleMcpRuntimePing,
    mcpProductization.mcpConfig,
    mcpProductization.mcpError,
    mcpProductization.mcpHotUpdating,
    mcpProductization.mcpInstalling,
    mcpProductization.mcpLoading,
    mcpProductization.mcpManifestText,
    mcpProductization.mcpMarketplaceCategories,
    mcpProductization.mcpMarketplaceCategoryId,
    mcpProductization.mcpMarketplaceSummary,
    mcpProductization.mcpNotice,
    mcpProductization.mcpPinging,
    mcpProductization.mcpRuntimeHealth,
    mcpProductization.handleMcpTemplateSelect,
    mcpProductization.setMcpManifestText,
    mcpProductization.setMcpMarketplaceCategoryId,
    mcpProductization.visibleMcpConnectors,
  ])

  const connectorToolbarProps = useMemo<IntegratorConnectorsToolbarPanelProps>(() => (
    buildConnectorToolbarProps({
      connectorController,
      selectedConnector,
      onRefresh: actions.handleConnectorRefresh,
      onSave: actions.handleConnectorSave,
      onTest: actions.handleConnectorTest,
    })
  ), [
    actions.handleConnectorRefresh,
    actions.handleConnectorSave,
    actions.handleConnectorTest,
    connectorController.connectorStats.approvedCount,
    connectorController.connectorStats.configuredCount,
    connectorController.connectors.length,
    connectorController.error,
    connectorController.loading,
    connectorController.notice,
    connectorController.persistence,
    connectorController.saving,
    connectorController.testing,
    selectedConnector,
  ])

  const connectorListProps = useMemo<IntegratorConnectorListPanelProps>(() => (
    buildConnectorListProps({ connectorController })
  ), [
    connectorController.addConnector,
    connectorController.connectors,
    connectorController.loading,
    connectorController.selectedIndex,
    connectorController.setSelectedIndex,
  ])

  const connectorDetailsProps = useMemo<IntegratorConnectorDetailsPanelProps>(() => (
    buildConnectorDetailsProps({
      connectorController,
      selectedConnector,
    })
  ), [
    connectorController.loading,
    connectorController.removeConnector,
    connectorController.selectedIndex,
    connectorController.supportedTypes,
    connectorController.updateConnector,
    selectedConnector,
  ])

  const credentialPanelProps = useMemo<IntegratorConnectorCredentialsPanelProps | null>(() => (
    buildCredentialPanelProps({
      selectedConnector,
      credentialController,
      onRotateCredentials: actions.handleRotateCredentials,
      onProbeConnector: actions.handleProbeConnector,
    })
  ), [
    actions.handleProbeConnector,
    actions.handleRotateCredentials,
    credentialController.clampExternalProbeTimeout,
    credentialController.credentialFormValues,
    credentialController.credentialMode,
    credentialController.credentialPatchJson,
    credentialController.credentialTemplateId,
    credentialController.externalProbeEnabled,
    credentialController.externalProbeTimeoutSeconds,
    credentialController.probeResult,
    credentialController.probingConnector,
    credentialController.rotationResult,
    credentialController.rotatingCredentials,
    credentialController.selectCredentialTemplate,
    credentialController.setCredentialMode,
    credentialController.setCredentialPatchJsonValue,
    credentialController.setExternalProbeEnabledValue,
    credentialController.setExternalProbeTimeoutSecondsValue,
    credentialController.updateCredentialField,
    selectedConnector,
  ])

  const schedulesPanelProps = useMemo<IntegratorSchedulesPanelProps>(() => (
    buildSchedulesPanelProps({
      connectors: connectorController.connectors,
      scheduleController,
      onRefreshSchedules: actions.handleRefreshSchedules,
      onDryRunScheduleTick: actions.handleDryRunScheduleTick,
      onSaveSchedules: actions.handleSaveSchedules,
      onTriggerSchedule: actions.handleTriggerSchedule,
    })
  ), [
    actions.handleDryRunScheduleTick,
    actions.handleRefreshSchedules,
    actions.handleSaveSchedules,
    actions.handleTriggerSchedule,
    connectorController.connectors,
    scheduleController.addSchedule,
    scheduleController.removeSchedule,
    scheduleController.scheduleError,
    scheduleController.scheduleLoading,
    scheduleController.scheduleNotice,
    scheduleController.scheduleRuntime,
    scheduleController.scheduleSaving,
    scheduleController.scheduleTickResult,
    scheduleController.scheduleTicking,
    scheduleController.scheduleValidationErrors,
    scheduleController.schedules,
    scheduleController.selectedSchedule,
    scheduleController.selectedScheduleIndex,
    scheduleController.setSelectedScheduleIndex,
    scheduleController.triggeringScheduleId,
    scheduleController.updateSchedule,
  ])

  const auditPanelProps = useMemo<IntegratorAuditPanelProps>(() => (
    buildAuditPanelProps({
      auditController,
      onRefreshAudit: actions.handleRefreshAudit,
    })
  ), [
    actions.handleRefreshAudit,
    auditController.auditError,
    auditController.auditEvents,
    auditController.auditLoading,
  ])

  return {
    mcpProductizationPanelProps,
    connectorToolbarProps,
    connectorListProps,
    connectorDetailsProps,
    credentialPanelProps,
    schedulesPanelProps,
    auditPanelProps,
  }
}
