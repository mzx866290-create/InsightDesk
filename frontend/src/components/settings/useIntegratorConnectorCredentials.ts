import { useCallback, useState } from 'react'

import {
  probeIntegratorConnector,
  rotateIntegratorConnectorCredentials,
} from '../../api/client'
import type {
  IntegratorConnectorCredentialsRotationResponse,
  IntegratorConnectorProbeResponse,
} from '../../api/client'
import {
  connectorIdentifier,
  toDraft,
} from './integratorConnectorModel'
import {
  buildCredentialPatchFromFields,
  clampExternalProbeTimeout as clampProbeTimeout,
  credentialTemplateById,
  parseCredentialsPatchJson,
} from './integratorCredentialsModel'
import { useIntegratorCredentialFormState } from './useIntegratorCredentialFormState'
import type { ConnectorDraft } from './integratorConnectorModel'
import type {
  CredentialFormValues,
  CredentialInputKey,
  CredentialMode,
} from './integratorCredentialsModel'

export interface UseIntegratorConnectorCredentialsOptions {
  selectedConnector: ConnectorDraft | null
  resetKey: unknown
  onConnectorUpdated: (connector: ConnectorDraft) => void
  onError: (message: string | null) => void
  onNotice: (message: string | null) => void
  onAuditRefresh?: () => void
}

export interface UseIntegratorConnectorCredentialsResult {
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
  setCredentialMode: (mode: CredentialMode) => void
  selectCredentialTemplate: (templateId: string) => void
  updateCredentialField: (field: CredentialInputKey, value: string) => void
  setCredentialPatchJsonValue: (value: string) => void
  setExternalProbeEnabledValue: (enabled: boolean) => void
  setExternalProbeTimeoutSecondsValue: (value: number) => void
  clampExternalProbeTimeout: () => void
  handleRotateCredentials: () => Promise<void>
  handleProbeConnector: () => Promise<void>
}

export function useIntegratorConnectorCredentials({
  selectedConnector,
  resetKey,
  onConnectorUpdated,
  onError,
  onNotice,
  onAuditRefresh,
}: UseIntegratorConnectorCredentialsOptions): UseIntegratorConnectorCredentialsResult {
  const [rotatingCredentials, setRotatingCredentials] = useState(false)
  const [probingConnector, setProbingConnector] = useState(false)
  const {
    credentialMode,
    credentialTemplateId,
    credentialFormValues,
    credentialPatchJson,
    rotationResult,
    probeResult,
    externalProbeEnabled,
    externalProbeTimeoutSeconds,
    setCredentialMode,
    selectCredentialTemplate,
    updateCredentialField,
    setCredentialPatchJsonValue,
    setExternalProbeEnabledValue,
    setExternalProbeTimeoutSecondsValue,
    clampExternalProbeTimeout,
    resetCredentialInputs,
    setRotationResult,
    setProbeResult,
  } = useIntegratorCredentialFormState({ resetKey })

  const handleRotateCredentials = useCallback(async () => {
    if (!selectedConnector) return
    setRotatingCredentials(true)
    onError(null)
    onNotice(null)
    setRotationResult(null)
    try {
      const selectedCredentialTemplate = credentialTemplateById(credentialTemplateId)
      const settings = credentialMode === 'fields'
        ? buildCredentialPatchFromFields(credentialFormValues, selectedCredentialTemplate.fields)
        : parseCredentialsPatchJson(credentialPatchJson)
      const payload = await rotateIntegratorConnectorCredentials(
        connectorIdentifier(selectedConnector),
        { settings },
      )
      setRotationResult(payload)
      onConnectorUpdated(toDraft(payload.connector))
      resetCredentialInputs()
      onNotice(`Connector credentials ${payload.status}`)
      onAuditRefresh?.()
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err || 'Failed to rotate connector credentials'))
    } finally {
      setRotatingCredentials(false)
    }
  }, [
    credentialFormValues,
    credentialMode,
    credentialPatchJson,
    credentialTemplateId,
    onAuditRefresh,
    onConnectorUpdated,
    onError,
    onNotice,
    resetCredentialInputs,
    selectedConnector,
    setRotationResult,
  ])

  const handleProbeConnector = useCallback(async () => {
    if (!selectedConnector) return
    setProbingConnector(true)
    onError(null)
    onNotice(null)
    setProbeResult(null)
    try {
      const mode = externalProbeEnabled ? 'external' : 'static'
      const payload = await probeIntegratorConnector(connectorIdentifier(selectedConnector), {
        mode,
        ...(mode === 'external'
          ? { timeout_seconds: clampProbeTimeout(externalProbeTimeoutSeconds) }
          : {}),
      })
      setProbeResult(payload)
      onConnectorUpdated(toDraft(payload.connector))
      onNotice(`Connector probe ${payload.status}`)
      onAuditRefresh?.()
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err || 'Failed to probe integration connector'))
    } finally {
      setProbingConnector(false)
    }
  }, [
    externalProbeEnabled,
    externalProbeTimeoutSeconds,
    onAuditRefresh,
    onConnectorUpdated,
    onError,
    onNotice,
    selectedConnector,
    setProbeResult,
  ])

  return {
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
    setCredentialMode,
    selectCredentialTemplate,
    updateCredentialField,
    setCredentialPatchJsonValue,
    setExternalProbeEnabledValue,
    setExternalProbeTimeoutSecondsValue,
    clampExternalProbeTimeout,
    handleRotateCredentials,
    handleProbeConnector,
  }
}
