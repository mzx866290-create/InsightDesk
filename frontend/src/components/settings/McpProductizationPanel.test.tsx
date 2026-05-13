import React from 'react'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { McpConnector, McpMarketplaceCategory, McpRuntimeHealthResponse } from '../../api/client'
import type { McpMarketplaceSummaryView } from './mcpMarketplaceModel'
import { McpProductizationPanel } from './McpProductizationPanel'

vi.mock('../ui/Button', () => ({
  Button: ({
    children,
    loading: _loading,
    ...props
  }: React.ButtonHTMLAttributes<HTMLButtonElement> & { loading?: boolean }) => (
    <button {...props}>{children}</button>
  ),
}))

const marketplaceSummary: McpMarketplaceSummaryView = {
  total: 2,
  enabled: 1,
  healthy: 1,
  approval: 1,
  builtin: 1,
  custom: 1,
  categories: 1,
}

const marketplaceCategory: McpMarketplaceCategory = {
  id: 'developer-tools',
  label: 'Developer Tools',
  total: 2,
  enabled: 1,
  healthy: 1,
  requires_approval: 1,
  connectors: ['filesystem', 'github'],
}

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

const runtimeHealth = (patch: Partial<McpRuntimeHealthResponse> = {}): McpRuntimeHealthResponse => ({
  status: 'degraded',
  servers: [],
  history: [],
  history_limit: 10,
  summary: {
    total: 2,
    healthy: 1,
    unhealthy: 1,
    tool_count: 8,
    status_counts: { healthy: 1, degraded: 1 },
    alert_count: 1,
    unhealthy_connectors: ['github'],
    slow_connectors: [],
  },
  ...patch,
})

describe('McpProductizationPanel', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders marketplace summary, runtime health, alerts, and connector rows', () => {
    render(
      <McpProductizationPanel
        marketplaceSummary={marketplaceSummary}
        marketplaceCategories={[marketplaceCategory]}
        marketplaceCategoryId="all"
        visibleConnectors={[
          connector({ name: 'filesystem', label: 'Filesystem', healthy: true }),
          connector({ name: 'github', label: 'GitHub', enabled: false, source: 'runtime' }),
        ]}
        fallbackSource="config"
        runtimeHealth={runtimeHealth()}
        notice="MCP runtime health degraded"
        error={null}
        manifestText=""
        loading={false}
        pinging={false}
        hotUpdating={false}
        installing={false}
        hotUpdateDisabled={false}
        installDisabled
        onRefresh={vi.fn()}
        onRuntimePing={vi.fn()}
        onHotUpdate={vi.fn()}
        onManifestInstall={vi.fn()}
        onManifestTextChange={vi.fn()}
        onTemplateSelect={vi.fn()}
        onMarketplaceCategoryChange={vi.fn()}
      />,
    )

    expect(screen.getByTestId('settings-mcp-productization-panel')).toBeInTheDocument()
    expect(screen.getByTestId('settings-mcp-runtime-status')).toHaveTextContent('degraded')
    expect(screen.getByTestId('settings-mcp-runtime-summary')).toHaveTextContent('Tools: 8')
    expect(screen.getByTestId('settings-mcp-runtime-alert')).toHaveTextContent('github')
    expect(screen.getByTestId('settings-mcp-notice')).toHaveTextContent('MCP runtime health degraded')

    const rows = screen.getAllByTestId('settings-mcp-marketplace-row')
    expect(rows).toHaveLength(2)
    expect(within(rows[0]).getByText('Filesystem')).toBeInTheDocument()
    expect(within(rows[0]).getByText('config')).toBeInTheDocument()
    expect(within(rows[1]).getByText('GitHub')).toBeInTheDocument()
    expect(within(rows[1]).getByText('runtime')).toBeInTheDocument()
  })

  it('dispatches toolbar and category actions', () => {
    const onRefresh = vi.fn()
    const onRuntimePing = vi.fn()
    const onHotUpdate = vi.fn()
    const onManifestInstall = vi.fn()
    const onManifestTextChange = vi.fn()
    const onTemplateSelect = vi.fn()
    const onMarketplaceCategoryChange = vi.fn()

    render(
      <McpProductizationPanel
        marketplaceSummary={marketplaceSummary}
        marketplaceCategories={[marketplaceCategory]}
        marketplaceCategoryId="developer-tools"
        visibleConnectors={[connector({ name: 'filesystem', label: 'Filesystem', source: 'template', template: true })]}
        fallbackSource={null}
        runtimeHealth={null}
        notice={null}
        error="MCP failed"
        manifestText='{"name":"github"}'
        loading={false}
        pinging={false}
        hotUpdating={false}
        installing={false}
        hotUpdateDisabled={false}
        installDisabled={false}
        onRefresh={onRefresh}
        onRuntimePing={onRuntimePing}
        onHotUpdate={onHotUpdate}
        onManifestInstall={onManifestInstall}
        onManifestTextChange={onManifestTextChange}
        onTemplateSelect={onTemplateSelect}
        onMarketplaceCategoryChange={onMarketplaceCategoryChange}
      />,
    )

    expect(screen.getByTestId('settings-mcp-error')).toHaveTextContent('MCP failed')

    fireEvent.click(screen.getByTestId('settings-mcp-refresh'))
    fireEvent.click(screen.getByTestId('settings-mcp-runtime-ping'))
    fireEvent.click(screen.getByTestId('settings-mcp-hot-update'))
    fireEvent.change(screen.getByTestId('settings-mcp-manifest-text'), {
      target: { value: '{"name":"slack"}' },
    })
    fireEvent.click(screen.getByTestId('settings-mcp-manifest-install'))
    fireEvent.click(screen.getByTestId('settings-mcp-use-template-filesystem'))
    fireEvent.click(screen.getByTestId('settings-mcp-marketplace-category-all'))
    fireEvent.click(screen.getByTestId('settings-mcp-marketplace-category-developer-tools'))

    expect(onRefresh).toHaveBeenCalledTimes(1)
    expect(onRuntimePing).toHaveBeenCalledTimes(1)
    expect(onHotUpdate).toHaveBeenCalledTimes(1)
    expect(onManifestTextChange).toHaveBeenCalledWith('{"name":"slack"}')
    expect(onManifestInstall).toHaveBeenCalledTimes(1)
    expect(onTemplateSelect).toHaveBeenCalledWith(expect.objectContaining({ name: 'filesystem' }))
    expect(onMarketplaceCategoryChange).toHaveBeenNthCalledWith(1, 'all')
    expect(onMarketplaceCategoryChange).toHaveBeenNthCalledWith(2, 'developer-tools')
  })

  it('disables hot update when config is unavailable', () => {
    render(
      <McpProductizationPanel
        marketplaceSummary={marketplaceSummary}
        marketplaceCategories={[]}
        marketplaceCategoryId="all"
        visibleConnectors={[]}
        fallbackSource={null}
        runtimeHealth={null}
        notice={null}
        error={null}
        manifestText=""
        loading={false}
        pinging={false}
        hotUpdating={false}
        installing={false}
        hotUpdateDisabled
        installDisabled
        onRefresh={vi.fn()}
        onRuntimePing={vi.fn()}
        onHotUpdate={vi.fn()}
        onManifestInstall={vi.fn()}
        onManifestTextChange={vi.fn()}
        onTemplateSelect={vi.fn()}
        onMarketplaceCategoryChange={vi.fn()}
      />,
    )

    expect(screen.getByTestId('settings-mcp-hot-update')).toBeDisabled()
  })

  it('renders manifest validation hints', () => {
    render(
      <McpProductizationPanel
        marketplaceSummary={marketplaceSummary}
        marketplaceCategories={[]}
        marketplaceCategoryId="all"
        visibleConnectors={[]}
        fallbackSource={null}
        runtimeHealth={null}
        notice={null}
        error={null}
        manifestText='{"name":"fetch"}'
        manifestValidation={{
          valid: false,
          errors: ['command: required by connector manifest'],
          requiredFields: ['name', 'command'],
          sensitiveFields: ['env'],
        }}
        loading={false}
        pinging={false}
        hotUpdating={false}
        installing={false}
        hotUpdateDisabled
        installDisabled
        onRefresh={vi.fn()}
        onRuntimePing={vi.fn()}
        onHotUpdate={vi.fn()}
        onManifestInstall={vi.fn()}
        onManifestTextChange={vi.fn()}
        onTemplateSelect={vi.fn()}
        onMarketplaceCategoryChange={vi.fn()}
      />,
    )

    expect(screen.getByTestId('settings-mcp-manifest-hints')).toHaveTextContent('Required: name, command')
    expect(screen.getByTestId('settings-mcp-manifest-hints')).toHaveTextContent('env')
    expect(screen.getByTestId('settings-mcp-manifest-hints')).toHaveTextContent('command: required by connector manifest')
  })
})
