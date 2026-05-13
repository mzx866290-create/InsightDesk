import React from 'react'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { ConnectorDraft } from './integratorConnectorModel'
import {
  IntegratorConnectorDetailsPanel,
  type IntegratorConnectorDetailsPanelProps,
} from './IntegratorConnectorDetailsPanel'

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
  }) => <button {...props}>{children}</button>,
}))

const connector: ConnectorDraft = {
  id: 'connector-1',
  type: 'webhook',
  name: 'Ops Webhook',
  description: 'Operations webhook',
  enabled: true,
  approved: false,
  settings: {
    url: 'https://example.invalid/webhook',
  },
  settingsJson: '{\n  "url": "https://example.invalid/webhook"\n}',
}

function createProps(overrides: Partial<IntegratorConnectorDetailsPanelProps> = {}): IntegratorConnectorDetailsPanelProps {
  return {
    connector,
    selectedIndex: 2,
    supportedTypes: ['webhook', 'slack', 'mcp'],
    loading: false,
    children: null,
    onUpdateConnector: vi.fn(),
    onRemoveConnector: vi.fn(),
    ...overrides,
  }
}

describe('IntegratorConnectorDetailsPanel', () => {
  afterEach(() => {
    cleanup()
  })

  it('shows the loading and empty states', () => {
    render(<IntegratorConnectorDetailsPanel {...createProps({ connector: null, loading: true })} />)
    expect(screen.getByText('Loading connectors...')).toBeInTheDocument()

    cleanup()

    render(<IntegratorConnectorDetailsPanel {...createProps({ connector: null, loading: false })} />)
    expect(screen.getByText('No connector selected')).toBeInTheDocument()
  })

  it('renders connector fields and forwards updates', () => {
    const props = createProps()

    render(<IntegratorConnectorDetailsPanel {...props} />)

    const panel = screen.getByTestId('settings-integrator-connector-details')
    expect(panel).toHaveAttribute('data-connector-id', 'connector-1')
    expect(within(panel).getByTestId('settings-integrator-name')).toHaveValue('Ops Webhook')
    expect(within(panel).getByTestId('settings-integrator-type')).toHaveValue('webhook')
    expect(within(panel).getByTestId('settings-integrator-enabled')).toBeChecked()
    expect(within(panel).getByTestId('settings-integrator-approved')).not.toBeChecked()
    expect(within(panel).getByTestId('settings-integrator-settings-json')).toHaveValue(
      '{\n  "url": "https://example.invalid/webhook"\n}',
    )

    fireEvent.change(within(panel).getByTestId('settings-integrator-name'), {
      target: { value: 'New name' },
    })
    expect(props.onUpdateConnector).toHaveBeenCalledWith(2, { name: 'New name' })

    fireEvent.change(within(panel).getByTestId('settings-integrator-type'), {
      target: { value: 'slack' },
    })
    expect(props.onUpdateConnector).toHaveBeenCalledWith(2, { type: 'slack' })

    fireEvent.change(within(panel).getByLabelText('Description'), {
      target: { value: 'New description' },
    })
    expect(props.onUpdateConnector).toHaveBeenCalledWith(2, { description: 'New description' })

    fireEvent.click(within(panel).getByTestId('settings-integrator-enabled'))
    expect(props.onUpdateConnector).toHaveBeenCalledWith(2, { enabled: false })

    fireEvent.click(within(panel).getByTestId('settings-integrator-approved'))
    expect(props.onUpdateConnector).toHaveBeenCalledWith(2, { approved: true })

    fireEvent.change(within(panel).getByTestId('settings-integrator-settings-json'), {
      target: { value: '{ "url": "https://example.invalid/next" }' },
    })
    expect(props.onUpdateConnector).toHaveBeenCalledWith(2, {
      settingsJson: '{ "url": "https://example.invalid/next" }',
    })
  })

  it('forwards remove actions', () => {
    const props = createProps()

    render(<IntegratorConnectorDetailsPanel {...props} />)

    fireEvent.click(screen.getByTestId('settings-integrator-remove'))
    expect(props.onRemoveConnector).toHaveBeenCalledWith(2)
    expect(screen.getByTestId('settings-integrator-remove')).toHaveAttribute('data-connector-id', 'connector-1')
  })

  it('renders children after the settings JSON block', () => {
    render(
      <IntegratorConnectorDetailsPanel
        {...createProps({
          children: (
            <>
              <div data-testid="child-credentials">Credentials panel</div>
              <div data-testid="child-result">Test result panel</div>
            </>
          ),
        })}
      />,
    )

    const panel = screen.getByTestId('settings-integrator-connector-details')
    const jsonIndex = panel.textContent?.indexOf('https://example.invalid/webhook') ?? -1
    const childCredentialsIndex = panel.textContent?.indexOf('Credentials panel') ?? -1
    const childResultIndex = panel.textContent?.indexOf('Test result panel') ?? -1

    expect(jsonIndex).toBeGreaterThanOrEqual(0)
    expect(childCredentialsIndex).toBeGreaterThan(jsonIndex)
    expect(childResultIndex).toBeGreaterThan(childCredentialsIndex)
    expect(screen.getByTestId('child-credentials')).toBeInTheDocument()
    expect(screen.getByTestId('child-result')).toBeInTheDocument()
  })
})
