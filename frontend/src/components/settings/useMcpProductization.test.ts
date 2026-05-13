import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type {
  McpConfigResponse,
  McpConnector,
  McpRuntimeHealthResponse,
} from '../../api/client'
import { useMcpProductization } from './useMcpProductization'

const mocks = vi.hoisted(() => ({
  getMcpConfig: vi.fn(),
  getMcpRuntimeHealth: vi.fn(),
  installMcpConnectorManifest: vi.fn(),
  saveMcpConfig: vi.fn(),
}))

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client')
  return {
    ...actual,
    getMcpConfig: mocks.getMcpConfig,
    getMcpRuntimeHealth: mocks.getMcpRuntimeHealth,
    installMcpConnectorManifest: mocks.installMcpConnectorManifest,
    saveMcpConfig: mocks.saveMcpConfig,
  }
})

const connector = (patch: Partial<McpConnector>): McpConnector => ({
  name: 'filesystem',
  label: 'Filesystem',
  description: '',
  category: 'developer-tools',
  builtin: true,
  transport: 'stdio',
  source: 'config',
  enabled: true,
  healthy: true,
  requires_approval: false,
  ...patch,
})

const config = (patch: Partial<McpConfigResponse> = {}): McpConfigResponse => ({
  connectors: [connector({ name: 'filesystem' }), connector({ name: 'github', category: 'platform' })],
  config: { servers: { filesystem: { path: '/tmp' } } },
  servers: { filesystem: { path: '/tmp' } },
  default_enabled: [],
  persistence: { enabled: true, config_key: 'mcp.json' },
  sensitive_fields_redacted: true,
  source: 'config',
  path: '/tmp/mcp.json',
  total: 2,
  marketplace: {
    summary: {
      total: 2,
      builtin: 1,
      custom: 1,
      enabled: 2,
      healthy: 1,
      requires_approval: 0,
      categories: 2,
    },
    categories: [
      {
        id: 'developer-tools',
        label: 'Developer Tools',
        total: 1,
        enabled: 1,
        healthy: 1,
        requires_approval: 0,
        connectors: ['filesystem'],
      },
      {
        id: 'platform',
        label: 'Platform',
        total: 1,
        enabled: 1,
        healthy: 0,
        requires_approval: 0,
        connectors: ['github'],
      },
    ],
  },
  ...patch,
})

const health = (patch: Partial<McpRuntimeHealthResponse> = {}): McpRuntimeHealthResponse => ({
  status: 'healthy',
  servers: [],
  summary: {
    total: 2,
    healthy: 2,
    unhealthy: 0,
    tool_count: 4,
    status_counts: { healthy: 2 },
    alert_count: 0,
    unhealthy_connectors: [],
    slow_connectors: [],
  },
  history: [],
  history_limit: 10,
  ...patch,
})

describe('useMcpProductization', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  it('loads MCP productization state', async () => {
    mocks.getMcpConfig.mockResolvedValueOnce(config())
    mocks.getMcpRuntimeHealth.mockResolvedValueOnce(health())

    const { result } = renderHook(() => useMcpProductization())

    await act(async () => {
      await result.current.loadMcpProductization()
    })

    await waitFor(() => {
      expect(result.current.mcpLoading).toBe(false)
    })

    expect(result.current.mcpConfig?.source).toBe('config')
    expect(result.current.mcpRuntimeHealth?.status).toBe('healthy')
    expect(result.current.mcpError).toBeNull()
    expect(result.current.mcpNotice).toBeNull()
    expect(result.current.mcpMarketplaceSummary.total).toBe(2)
    expect(result.current.mcpMarketplaceCategories).toHaveLength(2)
    expect(result.current.visibleMcpConnectors).toHaveLength(2)
    expect(mocks.getMcpConfig).toHaveBeenCalledTimes(1)
    expect(mocks.getMcpRuntimeHealth).toHaveBeenCalledTimes(1)
  })

  it('surfaces load errors', async () => {
    mocks.getMcpConfig.mockRejectedValueOnce(new Error('load failed'))
    mocks.getMcpRuntimeHealth.mockResolvedValueOnce(health())

    const { result } = renderHook(() => useMcpProductization())

    await act(async () => {
      await result.current.loadMcpProductization()
    })

    await waitFor(() => {
      expect(result.current.mcpLoading).toBe(false)
    })

    expect(result.current.mcpError).toBe('load failed')
    expect(result.current.mcpNotice).toBeNull()
  })

  it('pings runtime health and updates notice', async () => {
    mocks.getMcpRuntimeHealth.mockResolvedValueOnce(health({ status: 'degraded' }))

    const { result } = renderHook(() => useMcpProductization())

    await act(async () => {
      await result.current.handleMcpRuntimePing()
    })

    await waitFor(() => {
      expect(result.current.mcpPinging).toBe(false)
    })

    expect(result.current.mcpRuntimeHealth?.status).toBe('degraded')
    expect(result.current.mcpNotice).toBe('MCP runtime health degraded')
    expect(result.current.mcpError).toBeNull()
  })

  it('hot updates config, then pings runtime health', async () => {
    mocks.getMcpConfig.mockResolvedValueOnce(config())
    mocks.getMcpRuntimeHealth.mockResolvedValueOnce(health())
    mocks.saveMcpConfig.mockResolvedValueOnce(config({ source: 'runtime' }))
    mocks.getMcpRuntimeHealth.mockResolvedValueOnce(health({ status: 'healthy' }))

    const { result } = renderHook(() => useMcpProductization())

    await act(async () => {
      await result.current.loadMcpProductization()
    })
    await waitFor(() => {
      expect(result.current.mcpConfig).not.toBeNull()
    })
    await act(async () => {
      await result.current.handleMcpHotUpdate()
    })

    await waitFor(() => {
      expect(result.current.mcpHotUpdating).toBe(false)
    })

    expect(mocks.saveMcpConfig).toHaveBeenCalledWith({ servers: { filesystem: { path: '/tmp' } } })
    expect(mocks.getMcpRuntimeHealth).toHaveBeenCalledTimes(2)
    expect(result.current.mcpConfig?.source).toBe('runtime')
    expect(result.current.mcpNotice).toBe('MCP configuration hot update applied')
    expect(result.current.mcpError).toBeNull()
  })

  it('installs a manifest and keeps install command execution explicit', async () => {
    mocks.installMcpConnectorManifest.mockResolvedValueOnce(config({
      connectors: [connector({ name: 'github', category: 'platform' })],
      installed: {
        name: 'github',
        executed_install_command: false,
        connector: connector({ name: 'github', category: 'platform' }),
      },
    }))

    const { result } = renderHook(() => useMcpProductization())

    act(() => {
      result.current.setMcpManifestText(JSON.stringify({
        name: 'github',
        transport: 'stdio',
        install_command: 'npx -y @modelcontextprotocol/server-github',
      }))
    })
    await act(async () => {
      await result.current.handleMcpManifestInstall()
    })

    await waitFor(() => {
      expect(result.current.mcpInstalling).toBe(false)
    })

    expect(mocks.installMcpConnectorManifest).toHaveBeenCalledWith({
      manifest: {
        name: 'github',
        transport: 'stdio',
        install_command: 'npx -y @modelcontextprotocol/server-github',
      },
    })
    expect(result.current.mcpConfig?.installed?.name).toBe('github')
    expect(result.current.mcpManifestText).toBe('')
    expect(result.current.mcpNotice).toBe('Installed MCP connector github; install commands were not executed')
    expect(result.current.mcpError).toBeNull()
  })

  it('rejects invalid manifest JSON before calling the API', async () => {
    const { result } = renderHook(() => useMcpProductization())

    act(() => {
      result.current.setMcpManifestText('[]')
    })
    await act(async () => {
      await result.current.handleMcpManifestInstall()
    })

    expect(mocks.installMcpConnectorManifest).not.toHaveBeenCalled()
    expect(result.current.mcpInstalling).toBe(false)
    expect(result.current.mcpError).toBe('MCP connector manifest must be a JSON object')
  })

  it('rejects incomplete template manifests before calling the API', async () => {
    const { result } = renderHook(() => useMcpProductization())

    act(() => {
      result.current.setMcpManifestText(JSON.stringify({
        name: 'fetch',
        transport: 'stdio',
        config_schema: {
          required: ['command'],
          sensitive: ['env'],
        },
      }))
    })
    await act(async () => {
      await result.current.handleMcpManifestInstall()
    })

    expect(mocks.installMcpConnectorManifest).not.toHaveBeenCalled()
    expect(result.current.mcpInstalling).toBe(false)
    expect(result.current.mcpManifestValidation.requiredFields).toEqual(['name', 'command'])
    expect(result.current.mcpManifestValidation.sensitiveFields).toEqual(['env'])
    expect(result.current.mcpError).toBe('command: required by connector manifest')
  })

  it('loads template connector manifests into the editor', () => {
    const { result } = renderHook(() => useMcpProductization())

    act(() => {
      result.current.handleMcpTemplateSelect(connector({
        name: 'fetch',
        label: 'Fetch',
        source: 'template',
        template: true,
        capability_scopes: ['web:fetch'],
        config_schema: {
          transport: 'stdio',
          required: ['command'],
          optional: ['args'],
          sensitive: ['env'],
        },
      }))
    })

    expect(JSON.parse(result.current.mcpManifestText)).toMatchObject({
      name: 'fetch',
      label: 'Fetch',
      transport: 'stdio',
      scopes: ['web:fetch'],
      command: '',
      args: [],
    })
    expect(result.current.mcpNotice).toBe('Loaded template for Fetch; fill command or URL before installing')
    expect(result.current.mcpError).toBeNull()
  })

  it('resets invalid categories and filters visible connectors', async () => {
    mocks.getMcpConfig.mockResolvedValueOnce(config())
    mocks.getMcpRuntimeHealth.mockResolvedValueOnce(health())

    const { result } = renderHook(() => useMcpProductization())

    await act(async () => {
      await result.current.loadMcpProductization()
    })

    act(() => {
      result.current.setMcpMarketplaceCategoryId('missing')
    })

    await waitFor(() => {
      expect(result.current.mcpMarketplaceCategoryId).toBe('all')
    })

    expect(result.current.visibleMcpConnectors).toHaveLength(2)

    act(() => {
      result.current.setMcpMarketplaceCategoryId('developer-tools')
    })

    await waitFor(() => {
      expect(result.current.mcpMarketplaceCategoryId).toBe('developer-tools')
    })

    expect(result.current.visibleMcpConnectors.map((item) => item.name)).toEqual(['filesystem'])
  })
})
