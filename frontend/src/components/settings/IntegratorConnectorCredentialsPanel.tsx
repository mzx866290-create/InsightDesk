import React from 'react'
import { Activity, RotateCcw } from 'lucide-react'

import type {
  IntegratorConnectorCredentialsRotationResponse,
  IntegratorConnectorProbeResponse,
} from '../../api/client'
import { IntegratorCredentialEditor } from './IntegratorCredentialEditor'
import { IntegratorCredentialProbeControls } from './IntegratorCredentialProbeControls'
import { IntegratorCredentialResults } from './IntegratorCredentialResults'
import { connectorIdentifier } from './integratorConnectorModel'
import type {
  CredentialFormValues,
  CredentialInputKey,
  CredentialMode,
} from './integratorCredentialsModel'
import type { ConnectorDraft } from './integratorConnectorModel'
import { Button } from '../ui/Button'

export interface IntegratorConnectorCredentialsPanelProps {
  connector: ConnectorDraft
  credentialMode: CredentialMode
  credentialTemplateId: string
  credentialFormValues: CredentialFormValues
  credentialPatchJson: string
  rotationResult: IntegratorConnectorCredentialsRotationResponse | null
  probeResult: IntegratorConnectorProbeResponse | null
  externalProbeEnabled: boolean
  externalProbeTimeoutSeconds: number
  rotatingCredentials: boolean
  probingConnector: boolean
  onCredentialModeChange: (mode: CredentialMode) => void
  onCredentialTemplateChange: (templateId: string) => void
  onCredentialFieldChange: (field: CredentialInputKey, value: string) => void
  onCredentialPatchJsonChange: (value: string) => void
  onExternalProbeEnabledChange: (enabled: boolean) => void
  onExternalProbeTimeoutSecondsChange: (value: number) => void
  onExternalProbeTimeoutBlur: () => void
  onRotateCredentials: () => void
  onProbeConnector: () => void
}

export const IntegratorConnectorCredentialsPanel: React.FC<IntegratorConnectorCredentialsPanelProps> = ({
  connector,
  credentialMode,
  credentialTemplateId,
  credentialFormValues,
  credentialPatchJson,
  rotationResult,
  probeResult,
  externalProbeEnabled,
  externalProbeTimeoutSeconds,
  rotatingCredentials,
  probingConnector,
  onCredentialModeChange,
  onCredentialTemplateChange,
  onCredentialFieldChange,
  onCredentialPatchJsonChange,
  onExternalProbeEnabledChange,
  onExternalProbeTimeoutSecondsChange,
  onExternalProbeTimeoutBlur,
  onRotateCredentials,
  onProbeConnector,
}) => {
  const connectorId = connectorIdentifier(connector)

  return (
    <div
      className="space-y-3 border-t border-bg-border pt-3"
      data-testid="settings-integrator-credentials-panel"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h5 className="text-sm font-medium text-text-primary">Credentials</h5>
          <p className="mt-1 text-xs text-text-secondary">
            Rotate common credential fields directly, or switch to JSON patch for advanced changes.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => void onProbeConnector()}
            loading={probingConnector}
            data-testid="settings-integrator-probe"
            data-connector-id={connectorId}
          >
            <Activity size={12} />
            {externalProbeEnabled ? 'External probe' : 'Static probe'}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => void onRotateCredentials()}
            loading={rotatingCredentials}
            data-testid="settings-integrator-rotate"
            data-connector-id={connectorId}
          >
            <RotateCcw size={12} />
            Rotate
          </Button>
        </div>
      </div>

      <IntegratorCredentialProbeControls
        externalProbeEnabled={externalProbeEnabled}
        externalProbeTimeoutSeconds={externalProbeTimeoutSeconds}
        onExternalProbeEnabledChange={onExternalProbeEnabledChange}
        onExternalProbeTimeoutSecondsChange={onExternalProbeTimeoutSecondsChange}
        onExternalProbeTimeoutBlur={onExternalProbeTimeoutBlur}
      />

      <IntegratorCredentialEditor
        credentialMode={credentialMode}
        credentialTemplateId={credentialTemplateId}
        credentialFormValues={credentialFormValues}
        credentialPatchJson={credentialPatchJson}
        onCredentialModeChange={onCredentialModeChange}
        onCredentialTemplateChange={onCredentialTemplateChange}
        onCredentialFieldChange={onCredentialFieldChange}
        onCredentialPatchJsonChange={onCredentialPatchJsonChange}
      />

      <IntegratorCredentialResults
        rotationResult={rotationResult}
        probeResult={probeResult}
      />
    </div>
  )
}
