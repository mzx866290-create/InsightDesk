import React from 'react'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  getAgentCatalog,
  installAgentPluginManifest,
  uninstallAgentPluginManifest,
} from '../../api/client'
import { AgentCatalogPanel } from './AgentCatalogPanel'

vi.mock('../../api/client', () => ({
  getAgentCatalog: vi.fn(),
  installAgentPluginManifest: vi.fn(),
  uninstallAgentPluginManifest: vi.fn(),
}))

describe('AgentCatalogPanel', () => {
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('renders the catalog summary, rows, and refresh action', async () => {
    vi.mocked(getAgentCatalog).mockResolvedValue({
      agents: [
        {
          name: 'research',
          description: 'Research agent',
          capabilities: ['research'],
          metadata: {},
        },
        {
          name: 'support_triage',
          description: 'Support plugin',
          capabilities: ['support_triage', 'customer_support'],
          metadata: {
            plugin: true,
            version: '1.0.0',
            risk_level: 'high',
            requires_approval: true,
          },
        },
      ],
      summary: { total: 2, builtin: 1, plugin: 1 },
      plugin_manifests: { enabled: true, directory_count: 1 },
    })

    render(<AgentCatalogPanel />)

    await waitFor(() => {
      expect(screen.getByTestId('settings-agent-catalog-summary')).toBeInTheDocument()
    })
    expect(screen.getAllByText('research')[0]).toBeInTheDocument()
    expect(screen.getAllByText('support_triage')[0]).toBeInTheDocument()
    expect(screen.getByText('Built-in')).toBeInTheDocument()
    expect(screen.getAllByText('Plugin')[0]).toBeInTheDocument()
    expect(screen.getByText('risk_level:', { exact: false })).toBeInTheDocument()
    expect(screen.getByText('requires_approval:', { exact: false })).toBeInTheDocument()

    fireEvent.click(screen.getByTestId('settings-agent-catalog-refresh'))
    expect(getAgentCatalog).toHaveBeenCalledTimes(2)
  })

  it('surfaces loader errors', async () => {
    vi.mocked(getAgentCatalog).mockRejectedValue(new Error('catalog unavailable'))

    render(<AgentCatalogPanel />)

    await waitFor(() => {
      expect(screen.getByTestId('settings-agent-catalog-error')).toHaveTextContent('catalog unavailable')
    })
  })

  it('shows manifest validation issues from the catalog response', async () => {
    vi.mocked(getAgentCatalog).mockResolvedValue({
      agents: [],
      summary: { total: 0, builtin: 0, plugin: 0 },
      plugin_manifests: {
        enabled: true,
        directory_count: 1,
        scanned_count: 1,
        loaded_count: 0,
        issue_count: 1,
        issues: [
          {
            file: 'config/agent_plugins/bad.json',
            code: 'invalid_manifest',
            message: 'capabilities cannot be empty',
          },
        ],
      },
    })

    render(<AgentCatalogPanel />)

    await waitFor(() => {
      expect(screen.getByTestId('settings-agent-catalog-manifest-issues')).toHaveTextContent('invalid_manifest')
    })
    expect(screen.getByText('config/agent_plugins/bad.json')).toBeInTheDocument()
  })

  it('filters marketplace templates by search query and category', async () => {
    vi.mocked(getAgentCatalog).mockResolvedValue({
      agents: [],
      summary: { total: 0, builtin: 0, plugin: 0 },
      plugin_manifests: {
        enabled: true,
        directory_count: 1,
        scanned_count: 0,
        loaded_count: 0,
        issue_count: 0,
        issues: [],
      },
      marketplace: {
        templates: [
          {
            name: 'market_research',
            description: 'Market research plugin',
            capabilities: ['market_research'],
            category: 'research',
            risk_level: 'medium',
            requires_approval: false,
            approval_reason: '',
            source: 'builtin',
            installed: false,
            template: true,
            manifest: {
              enabled: true,
              name: 'market_research',
              description: 'Market research plugin',
              capabilities: ['market_research'],
            },
          },
          {
            name: 'sales_enablement',
            description: 'Sales enablement plugin',
            capabilities: ['sales_brief'],
            category: 'sales',
            risk_level: 'low',
            requires_approval: false,
            approval_reason: '',
            source: 'builtin',
            installed: false,
            template: true,
            manifest: {
              enabled: true,
              name: 'sales_enablement',
              description: 'Sales enablement plugin',
              capabilities: ['sales_brief'],
            },
          },
        ],
        summary: { total: 2, installed: 0, available: 2, categories: 2, issue_count: 0 },
        issues: [],
      },
    })

    render(<AgentCatalogPanel />)

    await waitFor(() => {
      expect(screen.getAllByTestId('settings-agent-plugin-marketplace-row')).toHaveLength(2)
    })

    fireEvent.change(screen.getByTestId('settings-agent-plugin-marketplace-query'), {
      target: { value: 'sales' },
    })
    expect(screen.getByText('sales_enablement')).toBeInTheDocument()
    expect(screen.queryByText('market_research')).not.toBeInTheDocument()

    fireEvent.change(screen.getByTestId('settings-agent-plugin-marketplace-category'), {
      target: { value: 'research' },
    })
    expect(screen.getByTestId('settings-agent-plugin-marketplace-empty')).toBeInTheDocument()

    fireEvent.change(screen.getByTestId('settings-agent-plugin-marketplace-query'), {
      target: { value: '' },
    })
    expect(screen.getAllByText('market_research').length).toBeGreaterThan(0)
  })

  it('installs marketplace Agent plugin templates directly', async () => {
    const marketplaceManifest = {
      enabled: true,
      name: 'market_research',
      description: 'Market research plugin',
      capabilities: ['market_research'],
      risk_level: 'medium',
    }
    vi.mocked(getAgentCatalog).mockResolvedValue({
      agents: [],
      summary: { total: 0, builtin: 0, plugin: 0 },
      plugin_manifests: {
        enabled: true,
        directory_count: 1,
        scanned_count: 0,
        loaded_count: 0,
        issue_count: 0,
        issues: [],
      },
      marketplace: {
        templates: [
          {
            name: 'market_research',
            description: 'Market research plugin',
            capabilities: ['market_research'],
            category: 'research',
            risk_level: 'medium',
            requires_approval: false,
            approval_reason: '',
            source: 'builtin',
            installed: false,
            template: true,
            manifest: marketplaceManifest,
          },
        ],
        summary: { total: 1, installed: 0, available: 1, categories: 1, issue_count: 0 },
        issues: [],
      },
    })
    vi.mocked(installAgentPluginManifest).mockResolvedValue({
      agents: [
        {
          name: 'market_research',
          description: 'Market research plugin',
          capabilities: ['market_research'],
          metadata: { plugin: true, source: 'plugin_manifest' },
        },
      ],
      summary: { total: 1, builtin: 0, plugin: 1 },
      plugin_manifests: {
        enabled: true,
        directory_count: 1,
        scanned_count: 1,
        loaded_count: 1,
        issue_count: 0,
        issues: [],
      },
      marketplace: {
        templates: [
          {
            name: 'market_research',
            description: 'Market research plugin',
            capabilities: ['market_research'],
            category: 'research',
            risk_level: 'medium',
            requires_approval: false,
            approval_reason: '',
            source: 'builtin',
            installed: true,
            template: true,
            manifest: marketplaceManifest,
          },
        ],
        summary: { total: 1, installed: 1, available: 0, categories: 1, issue_count: 0 },
        issues: [],
      },
      installed: {
        name: 'market_research',
        manifest_path: 'config/agent_plugins/market_research.json',
        executed_entrypoint: false,
      },
    })

    render(<AgentCatalogPanel />)

    await waitFor(() => {
      expect(screen.getByTestId('settings-agent-plugin-marketplace')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByTestId('settings-agent-plugin-template-use-market_research'))
    expect(screen.getByTestId('settings-agent-plugin-manifest-input')).toHaveValue(
      JSON.stringify(marketplaceManifest, null, 2),
    )

    fireEvent.click(screen.getByTestId('settings-agent-plugin-template-install-market_research'))

    await waitFor(() => {
      expect(installAgentPluginManifest).toHaveBeenCalledWith({ manifest: marketplaceManifest })
    })
    expect(await screen.findByTestId('settings-agent-plugin-install-success')).toHaveTextContent(
      'Installed market_research; entrypoint execution: no.',
    )
  })

  it('shows workflow runtime metadata for plugin templates and installed agents', async () => {
    vi.mocked(getAgentCatalog).mockResolvedValue({
      agents: [
        {
          name: 'customer_health_workflow',
          description: 'Customer health workflow plugin',
          capabilities: ['customer_health'],
          metadata: { plugin: true, source: 'plugin_manifest', runtime: 'workflow_manifest' },
        },
      ],
      summary: { total: 1, builtin: 0, plugin: 1 },
      plugin_manifests: {
        enabled: true,
        directory_count: 1,
        scanned_count: 1,
        loaded_count: 1,
        issue_count: 0,
        issues: [],
      },
      marketplace: {
        templates: [
          {
            name: 'customer_health_workflow',
            description: 'Customer health workflow plugin',
            capabilities: ['customer_health'],
            category: 'operations',
            risk_level: 'medium',
            requires_approval: true,
            approval_reason: 'Reviews customer context.',
            source: 'builtin',
            installed: true,
            template: true,
            manifest: {
              enabled: true,
              name: 'customer_health_workflow',
              runtime: 'workflow_manifest',
              description: 'Customer health workflow plugin',
              capabilities: ['customer_health'],
              workflow: [
                {
                  id: 'signals',
                  title: 'Collect signals',
                  prompt: 'Review signals for {description}.',
                  artifact_type: 'analysis_note',
                },
              ],
            },
          },
        ],
        summary: { total: 1, installed: 1, available: 0, categories: 1, issue_count: 0 },
        issues: [],
      },
    })

    render(<AgentCatalogPanel />)

    await waitFor(() => {
      expect(screen.getAllByText('workflow_manifest').length).toBeGreaterThan(0)
    })
    expect(screen.getByText('Workflow steps:', { exact: false })).toBeInTheDocument()
    expect(screen.getAllByText('customer_health_workflow').length).toBeGreaterThan(0)
  })

  it('installs declarative Agent plugin manifests without entrypoint execution', async () => {
    vi.mocked(getAgentCatalog).mockResolvedValue({
      agents: [],
      summary: { total: 0, builtin: 0, plugin: 0 },
      plugin_manifests: {
        enabled: true,
        directory_count: 1,
        scanned_count: 0,
        loaded_count: 0,
        issue_count: 0,
        issues: [],
      },
    })
    vi.mocked(installAgentPluginManifest).mockResolvedValue({
      agents: [
        {
          name: 'support_triage',
          description: 'Support triage plugin',
          capabilities: ['support_triage'],
          metadata: { plugin: true, source: 'plugin_manifest' },
        },
      ],
      summary: { total: 1, builtin: 0, plugin: 1 },
      plugin_manifests: {
        enabled: true,
        directory_count: 1,
        scanned_count: 1,
        loaded_count: 1,
        issue_count: 0,
        issues: [],
      },
      installed: {
        name: 'support_triage',
        manifest_path: 'config/agent_plugins/support_triage.json',
        executed_entrypoint: false,
      },
    })

    render(<AgentCatalogPanel />)

    await waitFor(() => {
      expect(screen.getByTestId('settings-agent-plugin-install-panel')).toBeInTheDocument()
    })

    fireEvent.change(screen.getByTestId('settings-agent-plugin-manifest-input'), {
      target: {
        value: JSON.stringify({
          name: 'support_triage',
          description: 'Support triage plugin',
          capabilities: ['support_triage'],
          metadata: { owner: 'ops', entrypoint: 'not-executed' },
        }),
      },
    })
    fireEvent.click(screen.getByTestId('settings-agent-plugin-install-submit'))

    await waitFor(() => {
      expect(installAgentPluginManifest).toHaveBeenCalledWith({
        manifest: {
          name: 'support_triage',
          description: 'Support triage plugin',
          capabilities: ['support_triage'],
          metadata: { owner: 'ops', entrypoint: 'not-executed' },
        },
      })
    })
    expect(await screen.findByTestId('settings-agent-plugin-install-success')).toHaveTextContent(
      'Installed support_triage; entrypoint execution: no.',
    )
    expect(screen.getAllByText('support_triage').length).toBeGreaterThan(0)
  })

  it('uninstalls installed marketplace Agent plugin manifests', async () => {
    const marketplaceManifest = {
      enabled: true,
      name: 'support_triage',
      description: 'Support triage plugin',
      capabilities: ['support_triage'],
      risk_level: 'medium',
    }
    vi.mocked(getAgentCatalog).mockResolvedValue({
      agents: [
        {
          name: 'support_triage',
          description: 'Support triage plugin',
          capabilities: ['support_triage'],
          metadata: { plugin: true, source: 'plugin_manifest' },
        },
      ],
      summary: { total: 1, builtin: 0, plugin: 1 },
      plugin_manifests: {
        enabled: true,
        directory_count: 1,
        scanned_count: 1,
        loaded_count: 1,
        issue_count: 0,
        issues: [],
      },
      marketplace: {
        templates: [
          {
            name: 'support_triage',
            description: 'Support triage plugin',
            capabilities: ['support_triage'],
            category: 'operations',
            risk_level: 'medium',
            requires_approval: true,
            approval_reason: 'Routes support tasks.',
            source: 'builtin',
            installed: true,
            template: true,
            manifest: marketplaceManifest,
          },
        ],
        summary: { total: 1, installed: 1, available: 0, categories: 1, issue_count: 0 },
        issues: [],
      },
    })
    vi.mocked(uninstallAgentPluginManifest).mockResolvedValue({
      agents: [],
      summary: { total: 0, builtin: 0, plugin: 0 },
      plugin_manifests: {
        enabled: true,
        directory_count: 1,
        scanned_count: 1,
        loaded_count: 0,
        issue_count: 0,
        issues: [],
      },
      marketplace: {
        templates: [
          {
            name: 'support_triage',
            description: 'Support triage plugin',
            capabilities: ['support_triage'],
            category: 'operations',
            risk_level: 'medium',
            requires_approval: true,
            approval_reason: 'Routes support tasks.',
            source: 'builtin',
            installed: false,
            template: true,
            manifest: marketplaceManifest,
          },
        ],
        summary: { total: 1, installed: 0, available: 1, categories: 1, issue_count: 0 },
        issues: [],
      },
      uninstalled: {
        name: 'support_triage',
        manifest_path: 'config/agent_plugins/support_triage.json',
        deleted_manifest: true,
        existed: true,
      },
    })

    render(<AgentCatalogPanel />)

    await waitFor(() => {
      expect(screen.getByTestId('settings-agent-plugin-template-uninstall-support_triage')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByTestId('settings-agent-plugin-template-uninstall-support_triage'))

    await waitFor(() => {
      expect(uninstallAgentPluginManifest).toHaveBeenCalledWith('support_triage')
    })
    expect(await screen.findByTestId('settings-agent-plugin-install-success')).toHaveTextContent(
      'Uninstalled support_triage; manifest deleted: yes.',
    )
  })
})
