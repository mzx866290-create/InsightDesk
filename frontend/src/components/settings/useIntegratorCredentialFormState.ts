import { useCallback, useEffect, useState } from 'react'

import type { IntegratorConnectorCredentialsRotationResponse, IntegratorConnectorProbeResponse } from '../../api/client'
import {
  clampExternalProbeTimeout as clampProbeTimeout,
  CREDENTIAL_TEMPLATES,
  credentialTemplateById,
  DEFAULT_CREDENTIAL_PATCH_JSON,
  DEFAULT_EXTERNAL_PROBE_TIMEOUT_SECONDS,
  EMPTY_CREDENTIAL_FORM,
} from './integratorCredentialsModel'
import type {
  CredentialFormValues,
  CredentialInputKey,
  CredentialMode,
} from './integratorCredentialsModel'

interface UseIntegratorCredentialFormStateOptions {
  resetKey: unknown
}

export interface IntegratorCredentialFormState {
  credentialMode: CredentialMode
  credentialTemplateId: string
  credentialFormValues: CredentialFormValues
  credentialPatchJson: string
  rotationResult: IntegratorConnectorCredentialsRotationResponse | null
  probeResult: IntegratorConnectorProbeResponse | null
  externalProbeEnabled: boolean
  externalProbeTimeoutSeconds: number
  setCredentialMode: (mode: CredentialMode) => void
  selectCredentialTemplate: (templateId: string) => void
  updateCredentialField: (field: CredentialInputKey, value: string) => void
  setCredentialPatchJsonValue: (value: string) => void
  setExternalProbeEnabledValue: (enabled: boolean) => void
  setExternalProbeTimeoutSecondsValue: (value: number) => void
  clampExternalProbeTimeout: () => void
  resetCredentialInputs: () => void
  setRotationResult: (result: IntegratorConnectorCredentialsRotationResponse | null) => void
  setProbeResult: (result: IntegratorConnectorProbeResponse | null) => void
}

const DEFAULT_CREDENTIAL_TEMPLATE_ID = CREDENTIAL_TEMPLATES[0].id

function emptyCredentialForm(): CredentialFormValues {
  return { ...EMPTY_CREDENTIAL_FORM }
}

export function useIntegratorCredentialFormState({
  resetKey,
}: UseIntegratorCredentialFormStateOptions): IntegratorCredentialFormState {
  const [credentialMode, setCredentialModeState] = useState<CredentialMode>('fields')
  const [credentialTemplateId, setCredentialTemplateId] = useState(DEFAULT_CREDENTIAL_TEMPLATE_ID)
  const [credentialFormValues, setCredentialFormValues] = useState<CredentialFormValues>(emptyCredentialForm)
  const [credentialPatchJson, setCredentialPatchJson] = useState(DEFAULT_CREDENTIAL_PATCH_JSON)
  const [rotationResult, setRotationResult] = useState<IntegratorConnectorCredentialsRotationResponse | null>(null)
  const [probeResult, setProbeResult] = useState<IntegratorConnectorProbeResponse | null>(null)
  const [externalProbeEnabled, setExternalProbeEnabled] = useState(false)
  const [externalProbeTimeoutSeconds, setExternalProbeTimeoutSeconds] = useState(
    DEFAULT_EXTERNAL_PROBE_TIMEOUT_SECONDS,
  )

  const resetCredentialInputs = useCallback(() => {
    setCredentialFormValues(emptyCredentialForm())
    setCredentialPatchJson(DEFAULT_CREDENTIAL_PATCH_JSON)
  }, [])

  useEffect(() => {
    setCredentialModeState('fields')
    setCredentialTemplateId(DEFAULT_CREDENTIAL_TEMPLATE_ID)
    resetCredentialInputs()
    setRotationResult(null)
    setProbeResult(null)
    setExternalProbeEnabled(false)
    setExternalProbeTimeoutSeconds(DEFAULT_EXTERNAL_PROBE_TIMEOUT_SECONDS)
  }, [resetCredentialInputs, resetKey])

  const setCredentialMode = useCallback((mode: CredentialMode) => {
    setCredentialModeState(mode)
    setRotationResult(null)
  }, [])

  const selectCredentialTemplate = useCallback((templateId: string) => {
    const template = credentialTemplateById(templateId)
    setCredentialFormValues((current) => {
      const nextValues = emptyCredentialForm()
      for (const field of template.fields) {
        nextValues[field] = current[field]
      }
      return nextValues
    })
    setCredentialTemplateId(template.id)
    setRotationResult(null)
  }, [])

  const updateCredentialField = useCallback((field: CredentialInputKey, value: string) => {
    setRotationResult(null)
    setCredentialFormValues((current) => ({
      ...current,
      [field]: value,
    }))
  }, [])

  const setCredentialPatchJsonValue = useCallback((value: string) => {
    setCredentialPatchJson(value)
    setRotationResult(null)
  }, [])

  const setExternalProbeEnabledValue = useCallback((enabled: boolean) => {
    setExternalProbeEnabled(enabled)
    setProbeResult(null)
  }, [])

  const setExternalProbeTimeoutSecondsValue = useCallback((value: number) => {
    setExternalProbeTimeoutSeconds(value)
    setProbeResult(null)
  }, [])

  const clampExternalProbeTimeout = useCallback(() => {
    setExternalProbeTimeoutSeconds((value) => clampProbeTimeout(value))
  }, [])

  return {
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
  }
}
