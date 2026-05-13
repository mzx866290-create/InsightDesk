import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import type { IntegratorConnectorTestResult } from '../../api/client'
import { IntegratorConnectorTestResultPanel } from './IntegratorConnectorTestResultPanel'

const createTestResult = (
  patch: Partial<IntegratorConnectorTestResult> = {},
): IntegratorConnectorTestResult => ({
  ok: true,
  status: 'passed',
  dry_run: true,
  executed: false,
  connector: {
    id: 'connector-1',
    type: 'webhook',
    name: 'Webhook connector',
    enabled: true,
    approved: true,
    settings: {},
  },
  checks: [
    {
      name: 'payload',
      ok: true,
      severity: 'blocking',
      message: 'Payload is valid',
    },
  ],
  summary: {
    check_count: 1,
    failed_count: 0,
    blocking_failure_count: 0,
    warning_count: 0,
  },
  ...patch,
})

describe('IntegratorConnectorTestResultPanel', () => {
  afterEach(() => {
    cleanup()
  })

  it('shows a successful dry-run result without outbound requests', () => {
    render(<IntegratorConnectorTestResultPanel testResult={createTestResult()} />)

    const panel = screen.getByTestId('settings-integrator-test-result')
    expect(panel).toBeInTheDocument()
    expect(within(panel).getByText('Dry-run test')).toBeInTheDocument()
    expect(within(panel).getByText('passed')).toHaveClass('text-accent-green')
    expect(within(panel).getByText('OK')).toHaveClass('text-accent-green')
    expect(within(panel).getByText('Payload is valid')).toBeInTheDocument()
    expect(within(panel).getByText('No outbound request was sent.')).toBeInTheDocument()
  })

  it('shows a failed dry-run result with failure styling and status', () => {
    render(
      <IntegratorConnectorTestResultPanel
        testResult={createTestResult({
          ok: false,
          status: 'failed',
          checks: [
            {
              name: 'approval',
              ok: false,
              severity: 'blocking',
              message: 'Connector is not approved',
            },
          ],
          summary: {
            check_count: 1,
            failed_count: 1,
            blocking_failure_count: 1,
            warning_count: 0,
          },
        })}
      />,
    )

    const panel = screen.getByTestId('settings-integrator-test-result')
    expect(within(panel).getByText('failed')).toHaveClass('text-accent-red')
    expect(within(panel).getByText('FAIL')).toHaveClass('text-accent-red')
    expect(within(panel).getByText('Connector is not approved')).toBeInTheDocument()
  })
})
