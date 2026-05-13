import React from 'react'
import { IntegratorConnectorListPanel } from './IntegratorConnectorListPanel'
import { IntegratorConnectorDetailsPanel } from './IntegratorConnectorDetailsPanel'
import { IntegratorConnectorsToolbarPanel } from './IntegratorConnectorsToolbarPanel'
import { IntegratorConnectorCredentialsPanel } from './IntegratorConnectorCredentialsPanel'
import { IntegratorConnectorTestResultPanel } from './IntegratorConnectorTestResultPanel'
import { IntegratorAuditPanel } from './IntegratorAuditPanel'
import { IntegratorSchedulesPanel } from './IntegratorSchedulesPanel'
import { McpProductizationPanel } from './McpProductizationPanel'
import { useIntegratorConnectorsPanel } from './useIntegratorConnectorsPanel'

export const IntegratorConnectorsPanel: React.FC = () => {
  const {
    mcpProductizationPanelProps,
    connectorToolbarProps,
    connectorListProps,
    connectorDetailsProps,
    credentialPanelProps,
    connectorTestResult,
    schedulesPanelProps,
    auditPanelProps,
  } = useIntegratorConnectorsPanel()

  return (
    <div className="space-y-4" data-testid="settings-integrators-panel">
      <McpProductizationPanel {...mcpProductizationPanelProps} />

      <IntegratorConnectorsToolbarPanel {...connectorToolbarProps} />

      <div className="grid gap-3 lg:grid-cols-[minmax(0,0.95fr)_minmax(0,1.35fr)]">
        <IntegratorConnectorListPanel {...connectorListProps} />

        <IntegratorConnectorDetailsPanel {...connectorDetailsProps}>
          {credentialPanelProps ? (
            <>
              <IntegratorConnectorCredentialsPanel {...credentialPanelProps} />

              {connectorTestResult && <IntegratorConnectorTestResultPanel testResult={connectorTestResult} />}
            </>
          ) : null}
        </IntegratorConnectorDetailsPanel>
      </div>

      <IntegratorSchedulesPanel {...schedulesPanelProps} />

      <IntegratorAuditPanel {...auditPanelProps} />
    </div>
  )
}
