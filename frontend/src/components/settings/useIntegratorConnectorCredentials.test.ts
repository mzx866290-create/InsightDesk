import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type {
  IntegratorConnector,
  IntegratorConnectorCredentialsRotationResponse,
  IntegratorConnectorProbeResponse,
} from '../../api/client'
import type { ConnectorDraft } from './integratorConnectorModel'
import { useIntegratorConnectorCredentials } from './useIntegratorConnectorCredentials'

const mocks = vi.hoisted(() => ({
  rotateIntegratorConnectorCredentials: vi.fn(),
  probeIntegratorConnector: vi.fn(),
}))

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client')
  return {
    ...actual,
    rotateIntegratorConnectorCredentials: mocks.rotateIntegratorConnectorCredentials,
    probeIntegratorConnector: mocks.probeIntegratorConnector,
  }
})

const connectorPayload: IntegratorConnector = {
  id: 'connector-1',
  type: 'webhook',
  name: 'Ops Webhook',
  description: '',
  enabled: true,
  approved: true,
  settings: {
    url: 'https://example.invalid/hooks/ops',
  },
}

const connectorDraft: ConnectorDraft = {
  ...connectorPayload,
  settingsJson: JSON.stringify(connectorPayload.settings, null, 2),
}

const rotationResponse = (
  patch: Partial<IntegratorConnectorCredentialsRotationResponse> = {},
): IntegratorConnectorCredentialsRotationResponse => ({
  ok: true,
  status: 'rotated',
  connector: {
    ...connectorPayload,
    settings: {
      url: 'https://example.invalid/hooks/ops',
      token: '***redacted***',
    },
  },
  rotated_fields: ['token'],
  preserved_fields: ['url'],
  summary: {
    rotated_count: 1,
    preserved_count: 1,
  },
  ...patch,
})

const probeResponse = (
  patch: Partial<IntegratorConnectorProbeResponse> = {},
): IntegratorConnectorProbeResponse => ({
  ok: true,
  status: 'passed',
  dry_run: true,
  executed: false,
  connector: connectorPayload,
  checks: [],
  probe: {
    mode: 'static',
    outbound_request_sent: false,
  },
  summary: {
    check_count: 0,
    failed_count: 0,
    blocking_failure_count: 0,
    warning_count: 0,
  },
  ...patch,
})

function renderCredentialsHook(
  overrides: Partial<Parameters<typeof useIntegratorConnectorCredentials>[0]> = {},
) {
  const onConnectorUpdated = vi.fn()
  const onError = vi.fn()
  const onNotice = vi.fn()
  const onAuditRefresh = vi.fn()
  const utils = renderHook(
    (props: Parameters<typeof useIntegratorConnectorCredentials>[0]) =>
      useIntegratorConnectorCredentials(props),
    {
      initialProps: {
        selectedConnector: connectorDraft,
        resetKey: 0,
        onConnectorUpdated,
        onError,
        onNotice,
        onAuditRefresh,
        ...overrides,
      },
    },
  )

  return {
    ...utils,
    onConnectorUpdated,
    onError,
    onNotice,
    onAuditRefresh,
  }
}

describe('useIntegratorConnectorCredentials', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  it('resets credential state when resetKey changes', () => {
    const { result, rerender } = renderCredentialsHook()

    act(() => {
      result.current.updateCredentialField('token', 'secret-token')
      result.current.setCredentialMode('json')
      result.current.setCredentialPatchJsonValue('{ "token": "next" }')
      result.current.setExternalProbeEnabledValue(true)
      result.current.setExternalProbeTimeoutSecondsValue(20)
    })

    expect(result.current.credentialMode).toBe('json')
    expect(result.current.credentialFormValues.token).toBe('secret-token')
    expect(result.current.externalProbeEnabled).toBe(true)
    expect(result.current.externalProbeTimeoutSeconds).toBe(20)

    rerender({
      selectedConnector: connectorDraft,
      resetKey: 1,
      onConnectorUpdated: vi.fn(),
      onError: vi.fn(),
      onNotice: vi.fn(),
      onAuditRefresh: vi.fn(),
    })

    expect(result.current.credentialMode).toBe('fields')
    expect(result.current.credentialTemplateId).toBe('token')
    expect(result.current.credentialFormValues.token).toBe('')
    expect(result.current.credentialPatchJson).toBe('{\n  "token": ""\n}')
    expect(result.current.externalProbeEnabled).toBe(false)
    expect(result.current.externalProbeTimeoutSeconds).toBe(3)
  })

  it('preserves matching fields while switching templates', () => {
    const { result } = renderCredentialsHook()

    act(() => {
      result.current.updateCredentialField('client_id', 'client-1')
      result.current.updateCredentialField('client_secret', 'secret-1')
      result.current.selectCredentialTemplate('oauth_client')
    })

    expect(result.current.credentialTemplateId).toBe('oauth_client')
    expect(result.current.credentialFormValues.client_id).toBe('client-1')
    expect(result.current.credentialFormValues.client_secret).toBe('secret-1')

    act(() => {
      result.current.selectCredentialTemplate('token')
    })

    expect(result.current.credentialTemplateId).toBe('token')
    expect(result.current.credentialFormValues.client_id).toBe('')
    expect(result.current.credentialFormValues.client_secret).toBe('')
  })

  it('rotates credentials from fields and updates connector state', async () => {
    mocks.rotateIntegratorConnectorCredentials.mockResolvedValue(rotationResponse())
    const { result, onConnectorUpdated, onError, onNotice, onAuditRefresh } = renderCredentialsHook()

    act(() => {
      result.current.updateCredentialField('token', ' secret-token ')
    })

    await act(async () => {
      await result.current.handleRotateCredentials()
    })

    expect(mocks.rotateIntegratorConnectorCredentials).toHaveBeenCalledWith('connector-1', {
      settings: {
        token: 'secret-token',
      },
    })
    expect(result.current.rotationResult?.status).toBe('rotated')
    expect(result.current.credentialFormValues.token).toBe('')
    expect(result.current.credentialPatchJson).toBe('{\n  "token": ""\n}')
    expect(result.current.rotatingCredentials).toBe(false)
    expect(onConnectorUpdated).toHaveBeenCalledWith(expect.objectContaining({ id: 'connector-1' }))
    expect(onNotice).toHaveBeenCalledWith('Connector credentials rotated')
    expect(onAuditRefresh).toHaveBeenCalledTimes(1)
    expect(onError).toHaveBeenCalledWith(null)
  })

  it('rotates credentials from JSON and surfaces validation failures', async () => {
    const { result, onError } = renderCredentialsHook()

    act(() => {
      result.current.setCredentialMode('json')
      result.current.setCredentialPatchJsonValue('{ "api_key": "key-1" }')
    })

    mocks.rotateIntegratorConnectorCredentials.mockResolvedValue(rotationResponse({
      rotated_fields: ['api_key'],
    }))

    await act(async () => {
      await result.current.handleRotateCredentials()
    })

    expect(mocks.rotateIntegratorConnectorCredentials).toHaveBeenCalledWith('connector-1', {
      settings: {
        api_key: 'key-1',
      },
    })

    act(() => {
      result.current.setCredentialPatchJsonValue('[]')
    })

    await act(async () => {
      await result.current.handleRotateCredentials()
    })

    expect(onError).toHaveBeenLastCalledWith('Credential patch must be a JSON object.')
    expect(result.current.rotatingCredentials).toBe(false)
  })

  it('probes static and external connector health with clamped timeout', async () => {
    mocks.probeIntegratorConnector.mockResolvedValueOnce(probeResponse())
    mocks.probeIntegratorConnector.mockResolvedValueOnce(probeResponse({
      status: 'failed',
      dry_run: false,
      executed: true,
      probe: {
        mode: 'external',
        outbound_request_sent: true,
        timeout_seconds: 10,
      },
    }))
    const { result, onConnectorUpdated, onNotice, onAuditRefresh } = renderCredentialsHook()

    await act(async () => {
      await result.current.handleProbeConnector()
    })

    expect(mocks.probeIntegratorConnector).toHaveBeenCalledWith('connector-1', {
      mode: 'static',
    })
    expect(result.current.probeResult?.probe.mode).toBe('static')
    expect(onNotice).toHaveBeenCalledWith('Connector probe passed')

    act(() => {
      result.current.setExternalProbeEnabledValue(true)
      result.current.setExternalProbeTimeoutSecondsValue(20)
      result.current.clampExternalProbeTimeout()
    })

    expect(result.current.externalProbeTimeoutSeconds).toBe(10)

    await act(async () => {
      await result.current.handleProbeConnector()
    })

    expect(mocks.probeIntegratorConnector).toHaveBeenLastCalledWith('connector-1', {
      mode: 'external',
      timeout_seconds: 10,
    })
    expect(result.current.probeResult?.probe.mode).toBe('external')
    expect(result.current.probingConnector).toBe(false)
    expect(onConnectorUpdated).toHaveBeenCalledTimes(2)
    expect(onAuditRefresh).toHaveBeenCalledTimes(2)
  })

  it('reports probe API errors and ignores empty selection', async () => {
    mocks.probeIntegratorConnector.mockRejectedValue(new Error('probe failed'))
    const { result, onError } = renderCredentialsHook()

    await act(async () => {
      await result.current.handleProbeConnector()
    })

    expect(onError).toHaveBeenLastCalledWith('probe failed')
    expect(result.current.probingConnector).toBe(false)

    const emptyHook = renderCredentialsHook({ selectedConnector: null })

    await act(async () => {
      await emptyHook.result.current.handleProbeConnector()
      await emptyHook.result.current.handleRotateCredentials()
    })

    expect(mocks.probeIntegratorConnector).toHaveBeenCalledTimes(1)
    expect(mocks.rotateIntegratorConnectorCredentials).toHaveBeenCalledTimes(0)
  })
})
