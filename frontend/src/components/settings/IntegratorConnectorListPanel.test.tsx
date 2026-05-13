import React from 'react'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { ConnectorDraft } from './integratorConnectorModel'
import {
  IntegratorConnectorListPanel,
  type IntegratorConnectorListPanelProps,
} from './IntegratorConnectorListPanel'

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

const connectorA: ConnectorDraft = {
  id: 'connector-1',
  type: 'webhook',
  name: 'Ops Webhook',
  description: '',
  enabled: true,
  approved: true,
  settings: {
    url: 'https://hooks.example/webhook',
  },
  settingsJson: '{}',
}

const connectorB: ConnectorDraft = {
  id: 'connector-2',
  type: 'email',
  name: 'Digest Email',
  description: '',
  enabled: true,
  approved: false,
  settings: {},
  settingsJson: '{}',
}

function createProps(overrides: Partial<IntegratorConnectorListPanelProps> = {}): IntegratorConnectorListPanelProps {
  return {
    connectors: [connectorA, connectorB],
    selectedIndex: 0,
    loading: false,
    onAddConnector: vi.fn(),
    onSelectConnector: vi.fn(),
    ...overrides,
  }
}

describe('IntegratorConnectorListPanel', () => {
  afterEach(() => {
    cleanup()
  })

  it('forwards the Add button callback', () => {
    const onAddConnector = vi.fn()

    render(<IntegratorConnectorListPanel {...createProps({ onAddConnector })} />)

    fireEvent.click(screen.getByTestId('settings-integrator-add'))
    expect(onAddConnector).toHaveBeenCalledTimes(1)
  })

  it('renders the empty state and forwards the add action', () => {
    const onAddConnector = vi.fn()

    render(
      <IntegratorConnectorListPanel
        {...createProps({
          connectors: [],
          onAddConnector,
        })}
      />,
    )

    const emptyState = screen.getByTestId('settings-integrator-empty')
    expect(emptyState).toHaveTextContent('Add the first webhook connector')

    fireEvent.click(emptyState)
    expect(onAddConnector).toHaveBeenCalledTimes(1)
  })

  it('does not render the empty state while loading', () => {
    render(
      <IntegratorConnectorListPanel
        {...createProps({
          connectors: [],
          loading: true,
        })}
      />,
    )

    expect(screen.queryByTestId('settings-integrator-empty')).not.toBeInTheDocument()
  })

  it('renders connector rows with status, metadata, selection, and click behavior', () => {
    const onSelectConnector = vi.fn()

    render(
      <IntegratorConnectorListPanel
        {...createProps({
          selectedIndex: 1,
          onSelectConnector,
        })}
      />,
    )

    const rows = screen.getAllByTestId('settings-integrator-connector-row')
    expect(rows).toHaveLength(2)

    expect(rows[0]).toHaveAttribute('data-connector-id', 'connector-1')
    expect(rows[0]).toHaveAttribute('data-connector-type', 'webhook')
    expect(rows[0]).toHaveClass('border-bg-border')
    expect(within(rows[0]).getByText('Ops Webhook')).toBeInTheDocument()
    expect(within(rows[0]).getByText('Approved')).toBeInTheDocument()
    expect(within(rows[0]).getByText('webhook')).toBeInTheDocument()
    expect(within(rows[0]).getByText('configured')).toBeInTheDocument()

    expect(rows[1]).toHaveAttribute('data-connector-id', 'connector-2')
    expect(rows[1]).toHaveAttribute('data-connector-type', 'email')
    expect(rows[1]).toHaveClass('border-accent-blue/50')
    expect(within(rows[1]).getByText('Digest Email')).toBeInTheDocument()
    expect(within(rows[1]).getByText('Needs approval')).toBeInTheDocument()
    expect(within(rows[1]).getByText('email')).toBeInTheDocument()
    expect(within(rows[1]).getByText('missing endpoint')).toBeInTheDocument()

    fireEvent.click(rows[0])
    expect(onSelectConnector).toHaveBeenCalledWith(0)
  })
})
