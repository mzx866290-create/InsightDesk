import React from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { IntegratorAuditPanel } from './IntegratorAuditPanel'

vi.mock('../ui/Button', () => ({
  Button: ({ children, loading: _loading, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & { loading?: boolean }) => (
    <button {...props}>{children}</button>
  ),
}))

describe('IntegratorAuditPanel', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders audit rows and refresh action', () => {
    const onRefreshAudit = vi.fn()

    render(
      <IntegratorAuditPanel
        auditEvents={[
          {
            timestamp: 1_715_000_000,
            action: 'connector_test',
            result: 'success',
            connector_id: 'conn-1',
            connector_type: 'webhook',
            actor: 'system',
            request_id: 'req-1',
            details: {
              status: 'ok',
              url: 'https://example.com',
              secret: 'hidden',
            },
          },
        ]}
        auditError={null}
        auditLoading={false}
        onRefreshAudit={onRefreshAudit}
      />,
    )

    expect(screen.getByTestId('settings-integrator-audit-panel')).toBeInTheDocument()
    expect(screen.getByTestId('settings-integrator-audit-list')).toBeInTheDocument()
    expect(screen.getByTestId('settings-integrator-audit-row')).toBeInTheDocument()
    expect(screen.getByText('connector_test')).toBeInTheDocument()
    expect(screen.getByText('success')).toBeInTheDocument()
    expect(screen.getByText('status: ok')).toBeInTheDocument()
    expect(screen.queryByText('url: https://example.com')).not.toBeInTheDocument()

    fireEvent.click(screen.getByTestId('settings-integrator-audit-refresh'))
    expect(onRefreshAudit).toHaveBeenCalledTimes(1)
  })

  it('shows an error state', () => {
    render(
      <IntegratorAuditPanel
        auditEvents={[]}
        auditError="Mock audit failed"
        auditLoading={false}
        onRefreshAudit={vi.fn()}
      />,
    )

    expect(screen.getByTestId('settings-integrator-audit-error')).toHaveTextContent('Mock audit failed')
    expect(screen.queryByTestId('settings-integrator-audit-empty')).not.toBeInTheDocument()
  })

  it('shows an empty state when there are no audit records', () => {
    render(
      <IntegratorAuditPanel
        auditEvents={[]}
        auditError={null}
        auditLoading={false}
        onRefreshAudit={vi.fn()}
      />,
    )

    expect(screen.getByTestId('settings-integrator-audit-empty')).toHaveTextContent('No audit records yet.')
    expect(screen.queryByTestId('settings-integrator-audit-list')).not.toBeInTheDocument()
  })
})
