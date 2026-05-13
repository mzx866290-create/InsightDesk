import React from 'react'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { McpConnector } from '../../api/client'
import { McpMarketplaceConnectorGrid } from './McpMarketplaceConnectorGrid'

const connector = (patch: Partial<McpConnector>): McpConnector => ({
  name: 'filesystem',
  label: 'Filesystem',
  description: '',
  category: 'developer-tools',
  builtin: true,
  transport: 'stdio',
  source: '',
  ...patch,
})

describe('McpMarketplaceConnectorGrid', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders connector rows with stable test ids and connector data attributes', () => {
    render(
      <McpMarketplaceConnectorGrid
        connectors={[
          connector({
            name: 'filesystem',
            label: 'Filesystem',
            healthy: true,
            risk_level: 'low',
          }),
          connector({
            name: 'github',
            label: 'GitHub',
            category: 'code',
            enabled: true,
            status: 'Needs token',
            source: 'runtime',
          }),
        ]}
        fallbackSource="config"
      />,
    )

    const rows = screen.getAllByTestId('settings-mcp-marketplace-row')
    expect(rows).toHaveLength(2)
    expect(rows[0]).toHaveAttribute('data-connector-name', 'filesystem')
    expect(rows[1]).toHaveAttribute('data-connector-name', 'github')
    expect(within(rows[0]).getByText('Filesystem')).toBeInTheDocument()
    expect(within(rows[0]).getByText('Healthy')).toBeInTheDocument()
    expect(within(rows[0]).getByText('config')).toBeInTheDocument()
    expect(within(rows[1]).getByText('Needs token')).toBeInTheDocument()
    expect(within(rows[1]).getByText('runtime')).toBeInTheDocument()
  })

  it('falls back connector metadata when optional values are empty', () => {
    render(
      <McpMarketplaceConnectorGrid
        connectors={[
          connector({
            name: 'custom-connector',
            label: '',
            category: '',
            transport: '',
            risk_level: '',
            source: '',
            status: '',
          }),
        ]}
        fallbackSource={null}
      />,
    )

    const row = screen.getByTestId('settings-mcp-marketplace-row')
    expect(within(row).getByText('custom-connector')).toBeInTheDocument()
    expect(within(row).getByText('Disabled')).toBeInTheDocument()
    expect(within(row).getByText('custom')).toBeInTheDocument()
    expect(within(row).getByText('stdio')).toBeInTheDocument()
    expect(within(row).getByText('medium')).toBeInTheDocument()
    expect(within(row).getByText('-')).toBeInTheDocument()
  })

  it('dispatches template prefill actions for template connectors', () => {
    const onUseTemplate = vi.fn()
    const templateConnector = connector({
      name: 'fetch',
      label: 'Fetch',
      source: 'template',
      template: true,
    })

    render(
      <McpMarketplaceConnectorGrid
        connectors={[templateConnector]}
        fallbackSource="config"
        onUseTemplate={onUseTemplate}
      />,
    )

    fireEvent.click(screen.getByTestId('settings-mcp-use-template-fetch'))

    expect(onUseTemplate).toHaveBeenCalledWith(templateConnector)
    expect(within(screen.getByTestId('settings-mcp-marketplace-row')).getByText('Template')).toBeInTheDocument()
  })
})
