import { describe, expect, it } from 'vitest'

import type { McpConfigResponse, McpConnector } from '../../api/client'
import {
  buildMcpConnectorManifestDraft,
  formatMcpConnectorManifestDraft,
  mcpCategoryLabel,
  mcpConnectorLabel,
  mcpConnectorTone,
  mcpMarketplaceCategoriesFromConfig,
  mcpMarketplaceSummaryFromConfig,
  normalizeMcpCategoryId,
  validateMcpConnectorManifestText,
  visibleMcpConnectors,
} from './mcpMarketplaceModel'

describe('mcpMarketplaceModel', () => {
  it('builds mcp marketplace summaries and category filters', () => {
    const connectors: McpConnector[] = [
      {
        name: 'alpha',
        label: 'Alpha',
        description: 'Alpha connector',
        category: 'Ops Tools',
        enabled: true,
        healthy: true,
        requires_approval: false,
        builtin: false,
        transport: 'stdio',
        risk_level: 'medium',
        source: 'catalog',
      },
      {
        name: 'beta',
        label: 'Beta',
        description: 'Beta connector',
        category: 'custom',
        enabled: false,
        healthy: false,
        requires_approval: true,
        builtin: true,
        transport: 'http',
        risk_level: 'high',
        source: 'catalog',
      },
    ]
    const config = {
      marketplace: {
        summary: {
          total: 9,
          enabled: 8,
          healthy: 7,
          requires_approval: 2,
          builtin: 6,
          custom: 3,
          categories: 4,
        },
        categories: [
          {
            id: 'ops tools',
            label: 'Ops Tools',
            total: 1,
            enabled: 1,
            healthy: 1,
            requires_approval: 0,
            connectors: ['alpha'],
          },
        ],
      },
    } as McpConfigResponse

    expect(mcpMarketplaceSummaryFromConfig(config, connectors)).toEqual({
      total: 9,
      enabled: 8,
      healthy: 7,
      approval: 2,
      builtin: 6,
      custom: 3,
      categories: 4,
    })
    expect(mcpMarketplaceCategoriesFromConfig(null, connectors)).toEqual([
      {
        id: 'custom',
        label: 'Custom',
        total: 1,
        enabled: 0,
        healthy: 0,
        requires_approval: 1,
        connectors: ['beta'],
      },
      {
        id: 'ops-tools',
        label: 'Ops Tools',
        total: 1,
        enabled: 1,
        healthy: 1,
        requires_approval: 0,
        connectors: ['alpha'],
      },
    ])
    expect(visibleMcpConnectors(config, connectors, 'ops-tools').map((item) => item.name)).toEqual(['alpha'])
    expect(normalizeMcpCategoryId('Ops Tools')).toBe('ops-tools')
    expect(mcpCategoryLabel('ops_tools')).toBe('Ops Tools')
    expect(mcpConnectorTone(connectors[0])).toContain('accent-green')
    expect(mcpConnectorLabel(connectors[1])).toBe('Disabled')
  })

  it('builds editable manifest drafts from marketplace templates', () => {
    const connector: McpConnector = {
      name: 'fetch',
      label: 'Fetch',
      description: 'Fetch web pages',
      category: 'data',
      builtin: false,
      transport: 'stdio',
      source: 'template',
      template: true,
      capability_scopes: ['web:fetch'],
      risk_level: 'medium',
      requires_approval: false,
      config_schema: {
        transport: 'stdio',
        required: ['command'],
        optional: ['args', 'env'],
        sensitive: ['env'],
      },
    }

    expect(mcpConnectorLabel(connector)).toBe('Template')
    expect(buildMcpConnectorManifestDraft(connector)).toEqual({
      name: 'fetch',
      label: 'Fetch',
      description: 'Fetch web pages',
      category: 'data',
      transport: 'stdio',
      scopes: ['web:fetch'],
      risk_level: 'medium',
      requires_approval: false,
      command: '',
      args: [],
      config_schema: {
        transport: 'stdio',
        required: ['command'],
        optional: ['args', 'env'],
        sensitive: ['env'],
      },
    })
    expect(formatMcpConnectorManifestDraft(connector)).toContain('"command": ""')
  })

  it('validates manifest drafts before install', () => {
    expect(validateMcpConnectorManifestText('[]')).toMatchObject({
      valid: false,
      errors: ['MCP connector manifest must be a JSON object'],
    })

    expect(validateMcpConnectorManifestText(JSON.stringify({
      name: 'bad connector',
      transport: 'stdio',
      command: 'npx',
    })).errors[0]).toContain('name:')

    expect(validateMcpConnectorManifestText(JSON.stringify({
      name: 'fetch',
      transport: 'stdio',
      config_schema: {
        required: ['command'],
        sensitive: ['env'],
      },
    }))).toMatchObject({
      valid: false,
      requiredFields: ['name', 'command'],
      sensitiveFields: ['env'],
      errors: ['command: required by connector manifest'],
    })

    expect(validateMcpConnectorManifestText(JSON.stringify({
      name: 'fetch',
      transport: 'stdio',
      install_command: 'npx -y @modelcontextprotocol/server-fetch',
      config_schema: {
        required: ['command'],
      },
    }))).toMatchObject({
      valid: true,
      errors: [],
    })
  })
})
