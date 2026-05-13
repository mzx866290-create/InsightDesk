import type { IntegratorConnectorDetailsPanelProps } from './IntegratorConnectorDetailsPanel'
import type { IntegratorConnectorListPanelProps } from './IntegratorConnectorListPanel'
import type { IntegratorConnectorsToolbarPanelProps } from './IntegratorConnectorsToolbarPanel'
import { connectorIdentifier } from './integratorConnectorModel'
import type { ConnectorDraft } from './integratorConnectorModel'
import type { UseIntegratorConnectorsResult } from './useIntegratorConnectors'

type ConnectorToolbarState = Pick<
  UseIntegratorConnectorsResult,
  | 'connectors'
  | 'connectorStats'
  | 'persistence'
  | 'notice'
  | 'error'
  | 'loading'
  | 'saving'
  | 'testing'
>

type ConnectorListState = Pick<
  UseIntegratorConnectorsResult,
  | 'connectors'
  | 'selectedIndex'
  | 'loading'
  | 'addConnector'
  | 'setSelectedIndex'
>

type ConnectorDetailsState = Pick<
  UseIntegratorConnectorsResult,
  | 'selectedIndex'
  | 'supportedTypes'
  | 'loading'
  | 'updateConnector'
  | 'removeConnector'
>

export interface BuildConnectorToolbarPropsParams {
  connectorController: ConnectorToolbarState
  selectedConnector: ConnectorDraft | null
  onRefresh: () => void
  onSave: () => void
  onTest: () => void
}

export function buildConnectorToolbarProps({
  connectorController,
  selectedConnector,
  onRefresh,
  onSave,
  onTest,
}: BuildConnectorToolbarPropsParams): IntegratorConnectorsToolbarPanelProps {
  return {
    totalCount: connectorController.connectors.length,
    configuredCount: connectorController.connectorStats.configuredCount,
    approvedCount: connectorController.connectorStats.approvedCount,
    storeLabel: connectorController.persistence?.enabled ? connectorController.persistence.config_key : '-',
    selectedConnectorId: selectedConnector ? connectorIdentifier(selectedConnector) : '',
    notice: connectorController.notice,
    error: connectorController.error,
    loading: connectorController.loading,
    saving: connectorController.saving,
    testing: connectorController.testing,
    testDisabled: !selectedConnector,
    onRefresh,
    onSave,
    onTest,
  }
}

export interface BuildConnectorListPropsParams {
  connectorController: ConnectorListState
}

export function buildConnectorListProps({
  connectorController,
}: BuildConnectorListPropsParams): IntegratorConnectorListPanelProps {
  return {
    connectors: connectorController.connectors,
    selectedIndex: connectorController.selectedIndex,
    loading: connectorController.loading,
    onAddConnector: connectorController.addConnector,
    onSelectConnector: connectorController.setSelectedIndex,
  }
}

export interface BuildConnectorDetailsPropsParams {
  connectorController: ConnectorDetailsState
  selectedConnector: ConnectorDraft | null
}

export function buildConnectorDetailsProps({
  connectorController,
  selectedConnector,
}: BuildConnectorDetailsPropsParams): IntegratorConnectorDetailsPanelProps {
  return {
    connector: selectedConnector,
    selectedIndex: connectorController.selectedIndex,
    supportedTypes: connectorController.supportedTypes,
    loading: connectorController.loading,
    onUpdateConnector: connectorController.updateConnector,
    onRemoveConnector: connectorController.removeConnector,
  }
}
