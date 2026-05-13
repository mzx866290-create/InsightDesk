import React from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  IntegratorConnectorsToolbarPanel,
  type IntegratorConnectorsToolbarPanelProps,
} from './IntegratorConnectorsToolbarPanel'

vi.mock('../ui/Button', () => ({
  Button: ({
    children,
    loading,
    disabled,
    variant: _variant,
    size: _size,
    ...props
  }: React.ButtonHTMLAttributes<HTMLButtonElement> & {
    loading?: boolean
    variant?: string
    size?: string
  }) => (
    <button {...props} disabled={disabled || loading} data-loading={loading ? 'true' : 'false'}>
      {children}
    </button>
  ),
}))

function createProps(overrides: Partial<IntegratorConnectorsToolbarPanelProps> = {}): IntegratorConnectorsToolbarPanelProps {
  return {
    totalCount: 4,
    configuredCount: 3,
    approvedCount: 2,
    storeLabel: 'integrator.connectors',
    selectedConnectorId: 'connector-1',
    notice: null,
    error: null,
    loading: false,
    saving: false,
    testing: false,
    testDisabled: false,
    onRefresh: vi.fn(),
    onSave: vi.fn(),
    onTest: vi.fn(),
    ...overrides,
  }
}

describe('IntegratorConnectorsToolbarPanel', () => {
  afterEach(() => {
    cleanup()
  })

  it('forwards refresh, save, and test actions', () => {
    const props = createProps()

    render(<IntegratorConnectorsToolbarPanel {...props} />)

    fireEvent.click(screen.getByTestId('settings-integrators-refresh'))
    fireEvent.click(screen.getByTestId('settings-integrators-save'))
    fireEvent.click(screen.getByTestId('settings-integrator-test'))

    expect(props.onRefresh).toHaveBeenCalledTimes(1)
    expect(props.onSave).toHaveBeenCalledTimes(1)
    expect(props.onTest).toHaveBeenCalledTimes(1)
  })

  it('keeps test disabled state and connector id attribute', () => {
    render(
      <IntegratorConnectorsToolbarPanel
        {...createProps({
          selectedConnectorId: 'connector-disabled',
          testDisabled: true,
        })}
      />,
    )

    const testButton = screen.getByTestId('settings-integrator-test')
    expect(testButton).toBeDisabled()
    expect(testButton).toHaveAttribute('data-connector-id', 'connector-disabled')
  })

  it('renders the connector summary', () => {
    render(
      <IntegratorConnectorsToolbarPanel
        {...createProps({
          totalCount: 8,
          configuredCount: 5,
          approvedCount: 4,
          storeLabel: '-',
        })}
      />,
    )

    expect(screen.getByText('Total:')).toHaveTextContent('Total: 8')
    expect(screen.getByText('Configured:')).toHaveTextContent('Configured: 5')
    expect(screen.getByText('Approved:')).toHaveTextContent('Approved: 4')
    expect(screen.getByText('Store:')).toHaveTextContent('Store: -')
  })

  it('renders notice and error messages', () => {
    render(
      <IntegratorConnectorsToolbarPanel
        {...createProps({
          notice: 'Integration connector configuration saved',
          error: 'Failed to save integration connectors',
        })}
      />,
    )

    expect(screen.getByText('Integration connector configuration saved')).toBeInTheDocument()
    expect(screen.getByTestId('settings-integrator-error')).toHaveTextContent('Failed to save integration connectors')
  })

  it('disables buttons while loading through the mocked Button', () => {
    render(
      <IntegratorConnectorsToolbarPanel
        {...createProps({
          loading: true,
          saving: true,
          testing: true,
        })}
      />,
    )

    expect(screen.getByTestId('settings-integrators-refresh')).toBeDisabled()
    expect(screen.getByTestId('settings-integrators-save')).toBeDisabled()
    expect(screen.getByTestId('settings-integrator-test')).toBeDisabled()
  })
})
