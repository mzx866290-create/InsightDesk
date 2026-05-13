import type { IntegratorConnectorCredentialsPanelProps } from './IntegratorConnectorCredentialsPanel'
import type { ConnectorDraft } from './integratorConnectorModel'
import type { UseIntegratorConnectorCredentialsResult } from './useIntegratorConnectorCredentials'

type CredentialPanelState = Pick<
  UseIntegratorConnectorCredentialsResult,
  | 'credentialMode'
  | 'credentialTemplateId'
  | 'credentialFormValues'
  | 'credentialPatchJson'
  | 'rotationResult'
  | 'probeResult'
  | 'externalProbeEnabled'
  | 'externalProbeTimeoutSeconds'
  | 'rotatingCredentials'
  | 'probingConnector'
  | 'setCredentialMode'
  | 'selectCredentialTemplate'
  | 'updateCredentialField'
  | 'setCredentialPatchJsonValue'
  | 'setExternalProbeEnabledValue'
  | 'setExternalProbeTimeoutSecondsValue'
  | 'clampExternalProbeTimeout'
>

export interface BuildCredentialPanelPropsParams {
  selectedConnector: ConnectorDraft | null
  credentialController: CredentialPanelState
  onRotateCredentials: () => void
  onProbeConnector: () => void
}

export function buildCredentialPanelProps({
  selectedConnector,
  credentialController,
  onRotateCredentials,
  onProbeConnector,
}: BuildCredentialPanelPropsParams): IntegratorConnectorCredentialsPanelProps | null {
  if (!selectedConnector) return null

  return {
    connector: selectedConnector,
    credentialMode: credentialController.credentialMode,
    credentialTemplateId: credentialController.credentialTemplateId,
    credentialFormValues: credentialController.credentialFormValues,
    credentialPatchJson: credentialController.credentialPatchJson,
    rotationResult: credentialController.rotationResult,
    probeResult: credentialController.probeResult,
    externalProbeEnabled: credentialController.externalProbeEnabled,
    externalProbeTimeoutSeconds: credentialController.externalProbeTimeoutSeconds,
    rotatingCredentials: credentialController.rotatingCredentials,
    probingConnector: credentialController.probingConnector,
    onCredentialModeChange: credentialController.setCredentialMode,
    onCredentialTemplateChange: credentialController.selectCredentialTemplate,
    onCredentialFieldChange: credentialController.updateCredentialField,
    onCredentialPatchJsonChange: credentialController.setCredentialPatchJsonValue,
    onExternalProbeEnabledChange: credentialController.setExternalProbeEnabledValue,
    onExternalProbeTimeoutSecondsChange: credentialController.setExternalProbeTimeoutSecondsValue,
    onExternalProbeTimeoutBlur: credentialController.clampExternalProbeTimeout,
    onRotateCredentials,
    onProbeConnector,
  }
}
