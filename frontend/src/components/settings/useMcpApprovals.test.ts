import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type {
  McpConfigResponse,
  McpConnector,
  McpConnectorApprovalsResponse,
  McpRuntimeHealthHistoryItem,
  McpRuntimeHealthResponse,
} from '../../api/client'
import { useMcpApprovals } from './useMcpApprovals'

const mocks = vi.hoisted(() => ({
  approveMcpConnector: vi.fn(),
  getMcpConfig: vi.fn(),
  getMcpConnectorApprovals: vi.fn(),
  getMcpConnectors: vi.fn(),
  getMcpRuntimeHealth: vi.fn(),
  getMcpRuntimeHealthHistory: vi.fn(),
  revokeMcpConnectorApproval: vi.fn(),
  saveMcpConfig: vi.fn(),
}))

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client')
  return {
    ...actual,
    approveMcpConnector: mocks.approveMcpConnector,
    getMcpConfig: mocks.getMcpConfig,
    getMcpConnectorApprovals: mocks.getMcpConnectorApprovals,
    getMcpConnectors: mocks.getMcpConnectors,
    getMcpRuntimeHealth: mocks.getMcpRuntimeHealth,
    getMcpRuntimeHealthHistory: mocks.getMcpRuntimeHealthHistory,
    revokeMcpConnectorApproval: mocks.revokeMcpConnectorApproval,
    saveMcpConfig: mocks.saveMcpConfig,
  }
})

const connector = (patch: Partial<McpConnector> = {}): McpConnector => ({
  name: 'filesystem',
  label: 'Filesystem',
  description: '',
  category: 'developer-tools',
  builtin: true,
  transport: 'stdio',
  source: 'catalog',
  enabled: true,
  healthy: true,
  requires_approval: false,
  ...patch,
})

const approvals = (
  patch: Partial<McpConnectorApprovalsResponse> = {},
): McpConnectorApprovalsResponse => ({
  approved_connectors: [],
  env_connectors: [],
  runtime_connectors: [],
  persisted_connectors: [],
  sources: {},
  persistence: { enabled: true, config_key: 'mcp.approvals' },
  total: 0,
  ...patch,
})

const config = (patch: Partial<McpConfigResponse> = {}): McpConfigResponse => ({
  connectors: [connector({ name: 'alpha', label: 'Alpha' })],
  config: { servers: { alpha: { command: 'node' } } },
  servers: { alpha: { command: 'node' } },
  default_enabled: [],
  persistence: { enabled: true, config_key: 'mcp.json' },
  sensitive_fields_redacted: false,
  source: 'config',
  path: '/tmp/mcp.json',
  total: 1,
  ...patch,
})

const runtimeSummary = {
  total: 1,
  healthy: 1,
  unhealthy: 0,
  tool_count: 2,
  status_counts: { healthy: 1 },
  alert_count: 0,
  unhealthy_connectors: [],
  slow_connectors: [],
}

const runtimeHistoryItem = (
  patch: Partial<McpRuntimeHealthHistoryItem> = {},
): McpRuntimeHealthHistoryItem => ({
  timestamp: 1_715_000_000,
  status: 'healthy',
  summary: runtimeSummary,
  servers: [
    {
      name: 'alpha',
      status: 'healthy',
      healthy: true,
      tool_count: 2,
      duration_ms: 5,
      error: null,
    },
  ],
  ...patch,
})

const runtimeHealth = (
  patch: Partial<McpRuntimeHealthResponse> = {},
): McpRuntimeHealthResponse => ({
  status: 'healthy',
  servers: [
    {
      name: 'alpha',
      status: 'healthy',
      healthy: true,
      tool_count: 2,
      tools: ['search', 'read'],
      duration_ms: 5,
      error: null,
    },
  ],
  summary: runtimeSummary,
  history: [runtimeHistoryItem()],
  history_limit: 10,
  ...patch,
})

async function waitForInitialLoad(result: { current: ReturnType<typeof useMcpApprovals> }) {
  await waitFor(() => {
    expect(result.current.loading).toBe(false)
    expect(result.current.loadingConfig).toBe(false)
    expect(result.current.loadingRuntimeHistory).toBe(false)
    expect(result.current.sortedConnectors).toHaveLength(2)
    expect(result.current.mcpConfig).not.toBeNull()
    expect(result.current.runtimeHealthHistory).toHaveLength(1)
  })
}

describe('useMcpApprovals', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.getMcpConnectors.mockResolvedValue({
      connectors: [
        connector({ name: 'zeta', label: 'Zeta', requires_approval: false }),
        connector({ name: 'alpha', label: 'Alpha', requires_approval: true }),
      ],
      default_enabled: [],
    })
    mocks.getMcpConnectorApprovals.mockResolvedValue(approvals({
      approved_connectors: ['alpha', 'ghost'],
      runtime_connectors: ['ghost'],
      sources: { alpha: ['runtime'] },
      total: 2,
    }))
    mocks.getMcpConfig.mockResolvedValue(config())
    mocks.getMcpRuntimeHealth.mockResolvedValue(runtimeHealth())
    mocks.getMcpRuntimeHealthHistory.mockResolvedValue({
      history: [runtimeHistoryItem()],
      limit: 10,
    })
    mocks.approveMcpConnector.mockResolvedValue(approvals({
      approved_connectors: ['alpha'],
      runtime_connectors: ['alpha'],
      total: 1,
    }))
    mocks.revokeMcpConnectorApproval.mockResolvedValue(approvals())
    mocks.saveMcpConfig.mockResolvedValue(config())
  })

  it('loads approvals, config, runtime history, and derived connector data on mount', async () => {
    const { result } = renderHook(() => useMcpApprovals())

    await waitForInitialLoad(result)

    expect(mocks.getMcpConnectors).toHaveBeenCalledTimes(1)
    expect(mocks.getMcpConnectorApprovals).toHaveBeenCalledTimes(1)
    expect(mocks.getMcpConfig).toHaveBeenCalledTimes(1)
    expect(mocks.getMcpRuntimeHealthHistory).toHaveBeenCalledWith(10)
    expect(result.current.sortedConnectors.map((item) => item.name)).toEqual(['alpha', 'zeta'])
    expect(result.current.unknownApprovedConnectors).toEqual(['ghost'])
    expect(result.current.connectorLabelByName.get('alpha')).toBe('Alpha')
    expect(result.current.mcpConfigText).toBe(JSON.stringify(config().config, null, 2))
    expect(result.current.error).toBeNull()
  })

  it('saves parsed config and refreshes approvals plus runtime history', async () => {
    const savedConfig = config({
      config: { servers: { github: { command: 'node' } } },
      servers: { github: { command: 'node' } },
      connectors: [connector({ name: 'github', label: 'GitHub' })],
    })
    mocks.saveMcpConfig.mockResolvedValueOnce(savedConfig)
    const { result } = renderHook(() => useMcpApprovals())

    await waitForInitialLoad(result)

    act(() => {
      result.current.setMcpConfigText('{"servers":{"github":{"command":"node"}}}')
    })

    await act(async () => {
      await result.current.handleSaveConfig()
    })

    expect(mocks.saveMcpConfig).toHaveBeenCalledWith({ servers: { github: { command: 'node' } } })
    expect(mocks.getMcpConnectors).toHaveBeenCalledTimes(2)
    expect(mocks.getMcpConnectorApprovals).toHaveBeenCalledTimes(2)
    expect(mocks.getMcpRuntimeHealthHistory).toHaveBeenCalledTimes(2)
    expect(result.current.mcpConfig).toEqual(savedConfig)
    expect(result.current.mcpConfigText).toBe(JSON.stringify(savedConfig.config, null, 2))
    expect(result.current.notice).toBe('Config saved')
    expect(result.current.savingConfig).toBe(false)
  })

  it('checks runtime health and refreshes runtime history in the background', async () => {
    mocks.getMcpRuntimeHealth.mockResolvedValueOnce(runtimeHealth({ status: 'degraded' }))
    const { result } = renderHook(() => useMcpApprovals())

    await waitForInitialLoad(result)

    await act(async () => {
      await result.current.handleRuntimeHealth()
      await Promise.resolve()
    })

    await waitFor(() => {
      expect(result.current.loadingRuntimeHistory).toBe(false)
    })

    expect(mocks.getMcpRuntimeHealth).toHaveBeenCalledTimes(1)
    expect(mocks.getMcpRuntimeHealthHistory).toHaveBeenCalledTimes(2)
    expect(result.current.runtimeHealth?.status).toBe('degraded')
    expect(result.current.notice).toBe('Runtime health: degraded')
    expect(result.current.checkingRuntime).toBe(false)
  })

  it('approves and revokes runtime connector approvals', async () => {
    const { result } = renderHook(() => useMcpApprovals())

    await waitForInitialLoad(result)

    await act(async () => {
      await result.current.handleRuntimeHealth()
      await Promise.resolve()
    })

    await act(async () => {
      await result.current.handleApprove('alpha')
    })

    expect(mocks.approveMcpConnector).toHaveBeenCalledWith('alpha')
    expect(result.current.approvals.runtime_connectors).toEqual(['alpha'])
    expect(result.current.runtimeHealth).toBeNull()
    expect(result.current.notice).toBe('Approved alpha')
    expect(result.current.actingName).toBeNull()

    await act(async () => {
      await result.current.handleRevoke('alpha')
    })

    expect(mocks.revokeMcpConnectorApproval).toHaveBeenCalledWith('alpha')
    expect(result.current.approvals.runtime_connectors).toEqual([])
    expect(result.current.notice).toBe('Revoked runtime approval for alpha')
    expect(result.current.actingName).toBeNull()
  })

  it('surfaces config parse errors without calling save', async () => {
    const { result } = renderHook(() => useMcpApprovals())

    await waitForInitialLoad(result)

    act(() => {
      result.current.setMcpConfigText('[]')
    })

    await act(async () => {
      await result.current.handleSaveConfig()
    })

    expect(mocks.saveMcpConfig).not.toHaveBeenCalled()
    expect(result.current.error).toBe('MCP config must be a JSON object')
    expect(result.current.savingConfig).toBe(false)
  })
})
