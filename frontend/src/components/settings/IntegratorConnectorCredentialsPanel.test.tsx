import React from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type {
  IntegratorConnectorCredentialsRotationResponse,
  IntegratorConnectorProbeResponse,
} from '../../api/client'
import {
  EMPTY_CREDENTIAL_FORM,
  type CredentialFormValues,
} from './integratorCredentialsModel'
import type { ConnectorDraft } from './integratorConnectorModel'
import {
  IntegratorConnectorCredentialsPanel,
  type IntegratorConnectorCredentialsPanelProps,
} from './IntegratorConnectorCredentialsPanel'

vi.mock('../ui/Button', () => ({
  Button: ({
    children,
    loading: _loading,
    variant: _variant,
    size: _size,
    ...props
  }: React.ButtonHTMLAttributes<HTMLButtonElement> & {
    loading?: boolean
    variant?: string
    size?: string
  }) => (
    <button {...props}>{children}</button>
  ),
}))

const connector: ConnectorDraft = {
  id: 'connector-1',
  type: 'webhook',
  name: 'Ops Webhook',
  description: 'Operations webhook',
  enabled: true,
  approved: true,
  settings: {},
  settingsJson: '{}',
}

const credentialFormValues: CredentialFormValues = {
  ...EMPTY_CREDENTIAL_FORM,
  token: 'existing-token',
}

function createProps(overrides: Partial<IntegratorConnectorCredentialsPanelProps> = {}): IntegratorConnectorCredentialsPanelProps {
  return {
    connector,
    credentialMode: 'fields',
    credentialTemplateId: 'token',
    credentialFormValues,
    credentialPatchJson: '{\n  "token": ""\n}',
    rotationResult: null,
    probeResult: null,
    externalProbeEnabled: false,
    externalProbeTimeoutSeconds: 3,
    rotatingCredentials: false,
    probingConnector: false,
    onCredentialModeChange: vi.fn(),
    onCredentialTemplateChange: vi.fn(),
    onCredentialFieldChange: vi.fn(),
    onCredentialPatchJsonChange: vi.fn(),
    onExternalProbeEnabledChange: vi.fn(),
    onExternalProbeTimeoutSecondsChange: vi.fn(),
    onExternalProbeTimeoutBlur: vi.fn(),
    onRotateCredentials: vi.fn(),
    onProbeConnector: vi.fn(),
    ...overrides,
  }
}

describe('IntegratorConnectorCredentialsPanel', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders fields mode templates and forwards field, rotate, and probe actions', () => {
    const props = createProps()

    render(<IntegratorConnectorCredentialsPanel {...props} />)

    expect(screen.getByTestId('settings-integrator-credentials-panel')).toBeInTheDocument()
    expect(screen.getByText('Quick template')).toBeInTheDocument()
    expect(screen.getByTestId('settings-integrator-credential-template-token')).toHaveTextContent('Token')
    expect(screen.getByTestId('settings-integrator-credential-field-token')).toHaveValue('existing-token')

    fireEvent.click(screen.getByTestId('settings-integrator-credential-template-api_key'))
    expect(props.onCredentialTemplateChange).toHaveBeenCalledWith('api_key')

    fireEvent.change(screen.getByTestId('settings-integrator-credential-field-token'), {
      target: { value: 'next-token' },
    })
    expect(props.onCredentialFieldChange).toHaveBeenCalledWith('token', 'next-token')

    fireEvent.click(screen.getByTestId('settings-integrator-credential-mode-json'))
    expect(props.onCredentialModeChange).toHaveBeenCalledWith('json')

    const rotateButton = screen.getByTestId('settings-integrator-rotate')
    const probeButton = screen.getByTestId('settings-integrator-probe')
    expect(rotateButton).toHaveAttribute('data-connector-id', 'connector-1')
    expect(probeButton).toHaveAttribute('data-connector-id', 'connector-1')

    fireEvent.click(rotateButton)
    fireEvent.click(probeButton)

    expect(props.onRotateCredentials).toHaveBeenCalledTimes(1)
    expect(props.onProbeConnector).toHaveBeenCalledTimes(1)
  })

  it('renders json mode and forwards patch edits', () => {
    const props = createProps({
      credentialMode: 'json',
      credentialPatchJson: '{\n  "client_secret": ""\n}',
    })

    render(<IntegratorConnectorCredentialsPanel {...props} />)

    const textarea = screen.getByTestId('settings-integrator-credential-patch-json')
    expect(textarea).toHaveValue('{\n  "client_secret": ""\n}')

    fireEvent.change(textarea, {
      target: { value: '{ "client_secret": "next" }' },
    })

    expect(props.onCredentialPatchJsonChange).toHaveBeenCalledWith('{ "client_secret": "next" }')
  })

  it('forwards external probe checkbox, timeout changes, and timeout blur', () => {
    const props = createProps({
      externalProbeEnabled: true,
      externalProbeTimeoutSeconds: 2.5,
    })

    render(<IntegratorConnectorCredentialsPanel {...props} />)

    const checkbox = screen.getByTestId('settings-integrator-external-probe-enabled')
    const timeout = screen.getByTestId('settings-integrator-external-probe-timeout')

    expect(screen.getByTestId('settings-integrator-probe')).toHaveTextContent('External probe')

    fireEvent.click(checkbox)
    expect(props.onExternalProbeEnabledChange).toHaveBeenCalledWith(false)

    fireEvent.change(timeout, { target: { value: '4.2' } })
    expect(props.onExternalProbeTimeoutSecondsChange).toHaveBeenCalledWith(4.2)

    fireEvent.blur(timeout)
    expect(props.onExternalProbeTimeoutBlur).toHaveBeenCalledTimes(1)
  })

  it('renders rotation and probe results without leaking sensitive endpoint or response values', () => {
    const rotationResult: IntegratorConnectorCredentialsRotationResponse = {
      ok: true,
      status: 'rotated',
      connector,
      rotated_fields: ['token'],
      preserved_fields: ['url'],
      summary: {
        rotated_count: 1,
        preserved_count: 1,
      },
    }
    const probeResult: IntegratorConnectorProbeResponse = {
      ok: false,
      status: 'failed',
      dry_run: false,
      executed: true,
      connector,
      checks: [
        { name: 'endpoint', ok: true, severity: 'ok', message: 'Endpoint resolved' },
        { name: 'auth', ok: false, severity: 'error', message: 'Authorization failed' },
      ],
      probe: {
        mode: 'external',
        outbound_request_sent: true,
        timeout_seconds: 4,
        endpoint: {
          host: 'hooks.internal',
          url: 'https://secret.example/webhook',
          token: 'secret-token',
        },
        response: {
          status_code: 401,
          request_url: 'https://secret.example/response',
          authorization: 'Bearer secret-token',
        },
      },
      summary: {
        check_count: 2,
        failed_count: 1,
        blocking_failure_count: 1,
        warning_count: 0,
        probe_mode: 'external',
      },
    }

    const { container } = render(
      <IntegratorConnectorCredentialsPanel
        {...createProps({ rotationResult, probeResult })}
      />,
    )

    expect(screen.getByTestId('settings-integrator-rotation-result')).toHaveTextContent('Rotation rotated')
    expect(screen.getByTestId('settings-integrator-rotation-result')).toHaveTextContent('1 rotated / 1 preserved')
    expect(screen.getByText('token')).toBeInTheDocument()
    expect(screen.getByText('url')).toBeInTheDocument()

    expect(screen.getByTestId('settings-integrator-probe-result')).toHaveTextContent('External probe')
    expect(screen.getByTestId('settings-integrator-probe-mode')).toHaveTextContent('external')
    expect(screen.getByTestId('settings-integrator-probe-outbound')).toHaveTextContent('sent')
    expect(screen.getByTestId('settings-integrator-probe-timeout')).toHaveTextContent('4s')
    expect(screen.getByTestId('settings-integrator-probe-result')).toHaveTextContent('Checks: 2')
    expect(screen.getByTestId('settings-integrator-probe-result')).toHaveTextContent('Failures: 1')
    expect(screen.getByText('Endpoint resolved')).toBeInTheDocument()
    expect(screen.getByText('Authorization failed')).toBeInTheDocument()
    expect(screen.getByTestId('settings-integrator-probe-endpoint')).toHaveTextContent('host: hooks.internal')
    expect(screen.getByTestId('settings-integrator-probe-response')).toHaveTextContent('status_code: 401')

    expect(container).not.toHaveTextContent('https://secret.example/webhook')
    expect(container).not.toHaveTextContent('https://secret.example/response')
    expect(container).not.toHaveTextContent('secret-token')
    expect(container).not.toHaveTextContent('Bearer secret-token')
  })
})
