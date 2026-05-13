import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { McpConnector } from '../../api/client'
import { McpApprovalRow } from './McpApprovalRow'

const connector = (patch: Partial<McpConnector> = {}): McpConnector => ({
  name: 'kb',
  label: 'Knowledge Base',
  description: 'Local retrieval tools',
  category: 'core',
  builtin: true,
  transport: 'stdio',
  source: 'catalog',
  risk_level: 'high',
  requires_approval: true,
  enabled: true,
  ...patch,
})

function renderRow(overrides: Partial<React.ComponentProps<typeof McpApprovalRow>> = {}) {
  return render(
    <McpApprovalRow
      connector={connector()}
      approvedConnectors={[]}
      runtimeConnectors={[]}
      envConnectors={[]}
      sources={[]}
      actingName={null}
      loading={false}
      onApprove={vi.fn()}
      onRevoke={vi.fn()}
      {...overrides}
    />,
  )
}

describe('McpApprovalRow', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders pending approval and triggers approve', () => {
    const onApprove = vi.fn()

    renderRow({ onApprove })

    const row = screen.getByTestId('settings-mcp-approval-row')
    expect(within(row).getByText('Knowledge Base')).toBeInTheDocument()
    expect(within(row).getByText('high')).toHaveClass('text-amber-300')
    expect(within(row).getByText('pending')).toHaveClass('text-accent-red')

    fireEvent.click(screen.getByTestId('settings-mcp-approve-kb'))

    expect(onApprove).toHaveBeenCalledWith('kb')
  })

  it('renders approved runtime connector and triggers revoke', () => {
    const onRevoke = vi.fn()

    renderRow({
      approvedConnectors: ['kb'],
      runtimeConnectors: ['kb'],
      sources: ['runtime'],
      onRevoke,
    })

    const row = screen.getByTestId('settings-mcp-approval-row')
    expect(within(row).getByText('approved')).toHaveClass('text-accent-green')
    expect(within(row).getByText('runtime')).toBeInTheDocument()

    fireEvent.click(screen.getByTestId('settings-mcp-revoke-kb'))

    expect(onRevoke).toHaveBeenCalledWith('kb')
  })

  it('shows env-only approval source and disables already approved approve action', () => {
    renderRow({
      approvedConnectors: ['kb'],
      envConnectors: ['kb'],
      sources: ['env'],
    })

    expect(screen.getAllByText('env')).toHaveLength(2)
    expect(screen.getByTestId('settings-mcp-approve-kb')).toBeDisabled()
  })

  it('renders not-required connectors with neutral action', () => {
    renderRow({
      connector: connector({
        name: 'search',
        label: 'Search',
        requires_approval: false,
        risk_level: 'low',
      }),
    })

    const row = screen.getByTestId('settings-mcp-approval-row')
    expect(within(row).getByText('not required')).toHaveClass('text-text-secondary')
    expect(within(row).getByText('low')).toHaveClass('text-accent-green')
    expect(screen.getByTestId('settings-mcp-approve-search')).not.toBeDisabled()
  })

  it('disables other row actions while another connector is acting', () => {
    renderRow({ actingName: 'other' })

    expect(screen.getByTestId('settings-mcp-approve-kb')).toBeDisabled()
  })
})
