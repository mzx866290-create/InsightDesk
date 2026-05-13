import React from 'react'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import type {
  IntegratorConnectorCredentialsRotationResponse,
  IntegratorConnectorProbeResponse,
} from '../../api/client'
import type { ConnectorDraft } from './integratorConnectorModel'
import { IntegratorCredentialResults } from './IntegratorCredentialResults'

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

describe('IntegratorCredentialResults', () => {
  afterEach(() => {
    cleanup()
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
      <IntegratorCredentialResults
        rotationResult={rotationResult}
        probeResult={probeResult}
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

  it('renders nothing when there are no results', () => {
    const { container } = render(
      <IntegratorCredentialResults
        rotationResult={null}
        probeResult={null}
      />,
    )

    expect(container).toBeEmptyDOMElement()
  })
})
