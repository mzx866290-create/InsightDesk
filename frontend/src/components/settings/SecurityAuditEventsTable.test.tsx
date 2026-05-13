import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { SecurityAuditEvent } from '../../api/client'
import { SecurityAuditEventsTable } from './SecurityAuditEventsTable'

const event = (patch: Partial<SecurityAuditEvent> = {}): SecurityAuditEvent => ({
  timestamp: 1_715_000_000,
  action: 'remote_auth_guard',
  result: 'blocked',
  user_id: 'user-1',
  user_role: 'admin',
  auth_mode: 'token',
  auth_source: 'header',
  is_local: false,
  request_id: 'req-1',
  ip: '203.0.113.10',
  details: { reason: 'missing_token' },
  ...patch,
})

describe('SecurityAuditEventsTable', () => {
  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('renders loading and empty states', () => {
    const { rerender } = render(<SecurityAuditEventsTable events={[]} loading />)

    expect(screen.queryByTestId('settings-security-audit-empty')).not.toBeInTheDocument()
    expect(document.querySelector('.animate-spin')).toBeInTheDocument()

    rerender(<SecurityAuditEventsTable events={[]} loading={false} />)

    expect(screen.getByTestId('settings-security-audit-empty')).toHaveTextContent('No audit events.')
  })

  it('renders event rows with metadata and red result tone', () => {
    vi.spyOn(Date.prototype, 'toLocaleString').mockReturnValue('2024-05-06 12:00:00')

    render(<SecurityAuditEventsTable events={[event()]} loading={false} />)

    const row = screen.getByTestId('settings-security-audit-event-row')
    expect(within(row).getByText('2024-05-06 12:00:00')).toBeInTheDocument()
    expect(within(row).getByText('req-1 | 203.0.113.10')).toBeInTheDocument()
    expect(within(row).getByText('remote_auth_guard')).toBeInTheDocument()
    expect(within(row).getByText('token / header')).toBeInTheDocument()
    expect(within(row).getByText('blocked')).toHaveClass('bg-accent-red/15')
    expect(within(row).getByText('admin: user-1')).toBeInTheDocument()
    expect(within(row).getByText('reason=missing_token')).toBeInTheDocument()
  })

  it('clamps long detail text', () => {
    const longText = 'x'.repeat(180)

    render(<SecurityAuditEventsTable events={[event({ details: { note: longText } })]} loading={false} />)

    const row = screen.getByTestId('settings-security-audit-event-row')
    const detail = within(row).getByTitle(`note=${longText}`)
    expect(detail.textContent).toHaveLength(142)
    expect(detail.textContent?.endsWith('...')).toBe(true)
  })
})
