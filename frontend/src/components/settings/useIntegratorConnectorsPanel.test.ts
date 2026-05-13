import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type {
  IntegratorAuditEventsResponse,
  IntegratorConnector,
  IntegratorConnectorProbeResponse,
  IntegratorConnectorTestResult,
  IntegratorConnectorsResponse,
  IntegratorSchedulesResponse,
  IntegratorScheduleTickResponse,
  McpConfigResponse,
  McpRuntimeHealthResponse,
} from '../../api/client'
import { useIntegratorConnectorsPanel } from './useIntegratorConnectorsPanel'

const mocks = vi.hoisted(() => ({
  getMcpConfig: vi.fn(),
  getMcpRuntimeHealth: vi.fn(),
  saveMcpConfig: vi.fn(),
  getIntegratorConnectors: vi.fn(),
  saveIntegratorConnectors: vi.fn(),
  testIntegratorConnector: vi.fn(),
  rotateIntegratorConnectorCredentials: vi.fn(),
  probeIntegratorConnector: vi.fn(),
  getIntegratorAuditEvents: vi.fn(),
  getIntegratorSchedules: vi.fn(),
  saveIntegratorSchedules: vi.fn(),
  triggerIntegratorSchedule: vi.fn(),
  triggerIntegratorScheduleTick: vi.fn(),
}))

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client')

  return {
    ...actual,
    getMcpConfig: mocks.getMcpConfig,
    getMcpRuntimeHealth: mocks.getMcpRuntimeHealth,
    saveMcpConfig: mocks.saveMcpConfig,
    getIntegratorConnectors: mocks.getIntegratorConnectors,
    saveIntegratorConnectors: mocks.saveIntegratorConnectors,
    testIntegratorConnector: mocks.testIntegratorConnector,
    rotateIntegratorConnectorCredentials: mocks.rotateIntegratorConnectorCredentials,
    probeIntegratorConnector: mocks.probeIntegratorConnector,
    getIntegratorAuditEvents: mocks.getIntegratorAuditEvents,
    getIntegratorSchedules: mocks.getIntegratorSchedules,
    saveIntegratorSchedules: mocks.saveIntegratorSchedules,
    triggerIntegratorSchedule: mocks.triggerIntegratorSchedule,
    triggerIntegratorScheduleTick: mocks.triggerIntegratorScheduleTick,
  }
})

const webhookConnector: IntegratorConnector = {
  id: 'webhook-1',
  type: 'webhook',
  name: 'Ops Webhook',
  description: 'Operations alerts',
  enabled: true,
  approved: true,
  settings: {
    url: 'https://example.invalid/hooks/ops',
    token: 'secret-token',
  },
}

const connectorsResponse: IntegratorConnectorsResponse = {
  connectors: [webhookConnector],
  total: 1,
  supported_types: ['webhook', 'email'],
  persistence: {
    enabled: true,
    config_key: 'integrations.connectors',
    sensitive_fields_redacted: true,
  },
}

const mcpConfigResponse: McpConfigResponse = {
  connectors: [
    {
      name: 'filesystem',
      label: 'Filesystem',
      description: 'Local file tools',
      category: 'data',
      builtin: true,
      transport: 'stdio',
      source: 'runtime',
      capability_scopes: ['read'],
      risk_level: 'low',
      requires_approval: false,
      enabled: true,
      configured: true,
      healthy: true,
      status: 'healthy',
    },
  ],
  config: {},
  servers: {},
  default_enabled: ['filesystem'],
  persistence: {
    enabled: true,
    config_key: 'mcp.servers',
  },
  marketplace: {
    summary: {
      total: 1,
      builtin: 1,
      custom: 0,
      enabled: 1,
      healthy: 1,
      requires_approval: 0,
      categories: 1,
    },
    categories: [
      {
        id: 'data',
        label: 'Data',
        total: 1,
        enabled: 1,
        healthy: 1,
        requires_approval: 0,
        connectors: ['filesystem'],
      },
    ],
  },
  sensitive_fields_redacted: true,
  source: 'runtime',
  total: 1,
}

const mcpRuntimeHealthResponse: McpRuntimeHealthResponse = {
  status: 'healthy',
  servers: [],
  summary: {
    total: 0,
    healthy: 0,
    unhealthy: 0,
    tool_count: 0,
    status_counts: {},
    alert_count: 0,
    unhealthy_connectors: [],
    slow_connectors: [],
  },
  history: [],
  history_limit: 10,
}

const auditResponse: IntegratorAuditEventsResponse = {
  events: [
    {
      timestamp: 1_715_000_000,
      action: 'connector.test',
      result: 'success',
      connector_id: 'webhook-1',
      connector_type: 'webhook',
      actor: 'settings',
      request_id: 'req-1',
      details: {
        connector_name: 'Ops Webhook',
      },
    },
  ],
  total: 1,
  limit: 20,
}

const schedulesResponse: IntegratorSchedulesResponse = {
  schedules: [
    {
      schedule_id: 'schedule-1',
      name: 'Hourly sync',
      connector_id: 'webhook-1',
      cron: '0 * * * *',
      timezone: 'UTC',
      interval_minutes: 60,
      enabled: true,
      settings: {},
      last_run_at: null,
      next_run_at: null,
    },
  ],
  total: 1,
  persistence: {
    enabled: true,
    config_key: 'integrations.schedules',
    sensitive_fields_redacted: true,
  },
  scheduler: {
    mode: 'polling',
    automatic_dispatch: true,
    manual_trigger_supported: true,
  },
}

const testResult: IntegratorConnectorTestResult = {
  ok: true,
  status: 'passed',
  dry_run: true,
  executed: false,
  connector: webhookConnector,
  checks: [],
  summary: {
    check_count: 0,
    failed_count: 0,
    blocking_failure_count: 0,
    warning_count: 0,
  },
}

const probeResult: IntegratorConnectorProbeResponse = {
  ok: true,
  status: 'passed',
  dry_run: true,
  executed: false,
  connector: webhookConnector,
  checks: [],
  probe: {
    mode: 'static',
    outbound_request_sent: false,
  },
  summary: {
    check_count: 0,
    failed_count: 0,
    blocking_failure_count: 0,
    warning_count: 0,
    probe_mode: 'static',
  },
}

const tickResult: IntegratorScheduleTickResponse = {
  dry_run: true,
  executed: false,
  checked: 1,
  due_count: 0,
  skipped: {
    disabled: 0,
    not_due: 1,
  },
  now: 1_715_000_000,
}

describe('useIntegratorConnectorsPanel', () => {
  beforeEach(() => {
    mocks.getMcpConfig.mockResolvedValue(mcpConfigResponse)
    mocks.getMcpRuntimeHealth.mockResolvedValue(mcpRuntimeHealthResponse)
    mocks.saveMcpConfig.mockResolvedValue(mcpConfigResponse)
    mocks.getIntegratorConnectors.mockResolvedValue(connectorsResponse)
    mocks.saveIntegratorConnectors.mockResolvedValue(connectorsResponse)
    mocks.testIntegratorConnector.mockResolvedValue(testResult)
    mocks.rotateIntegratorConnectorCredentials.mockResolvedValue({
      ok: true,
      status: 'rotated',
      connector: webhookConnector,
      rotated_fields: ['token'],
      preserved_fields: [],
      summary: {
        rotated_count: 1,
        preserved_count: 0,
      },
    })
    mocks.probeIntegratorConnector.mockResolvedValue(probeResult)
    mocks.getIntegratorAuditEvents.mockResolvedValue(auditResponse)
    mocks.getIntegratorSchedules.mockResolvedValue(schedulesResponse)
    mocks.saveIntegratorSchedules.mockResolvedValue(schedulesResponse)
    mocks.triggerIntegratorSchedule.mockResolvedValue({
      ok: true,
      schedule_id: 'schedule-1',
      status: 'triggered',
      triggered_at: 1_715_000_000,
    })
    mocks.triggerIntegratorScheduleTick.mockResolvedValue(tickResult)
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('loads all controller data and maps child panel props', async () => {
    const { result } = renderHook(() => useIntegratorConnectorsPanel())

    await waitFor(() => {
      expect(result.current.connectorToolbarProps.totalCount).toBe(1)
      expect(result.current.schedulesPanelProps.schedules).toHaveLength(1)
      expect(result.current.auditPanelProps.auditEvents).toHaveLength(1)
      expect(result.current.mcpProductizationPanelProps.visibleConnectors).toHaveLength(1)
    })

    expect(mocks.getMcpConfig).toHaveBeenCalledTimes(1)
    expect(mocks.getMcpRuntimeHealth).toHaveBeenCalledTimes(1)
    expect(mocks.getIntegratorConnectors).toHaveBeenCalledTimes(1)
    expect(mocks.getIntegratorAuditEvents).toHaveBeenCalledWith(20)
    expect(mocks.getIntegratorSchedules).toHaveBeenCalledTimes(1)

    expect(result.current.mcpProductizationPanelProps.fallbackSource).toBe('runtime')
    expect(result.current.mcpProductizationPanelProps.hotUpdateDisabled).toBe(false)
    expect(result.current.connectorToolbarProps).toMatchObject({
      configuredCount: 1,
      approvedCount: 1,
      selectedConnectorId: 'webhook-1',
      storeLabel: 'integrations.connectors',
      testDisabled: false,
    })
    expect(result.current.connectorListProps.connectors[0].id).toBe('webhook-1')
    expect(result.current.connectorDetailsProps.connector?.id).toBe('webhook-1')
    expect(result.current.credentialPanelProps?.connector.id).toBe('webhook-1')
    expect(result.current.schedulesPanelProps.selectedSchedule?.schedule_id).toBe('schedule-1')
    expect(result.current.auditPanelProps.auditEvents[0].request_id).toBe('req-1')
  })

  it('keeps key child actions wired to the same API semantics', async () => {
    const { result } = renderHook(() => useIntegratorConnectorsPanel())

    await waitFor(() => {
      expect(result.current.credentialPanelProps?.connector.id).toBe('webhook-1')
    })

    vi.clearAllMocks()

    act(() => {
      result.current.connectorToolbarProps.onRefresh()
    })
    await waitFor(() => {
      expect(mocks.getIntegratorConnectors).toHaveBeenCalledTimes(1)
    })

    act(() => {
      result.current.connectorToolbarProps.onTest()
    })
    await waitFor(() => {
      expect(mocks.testIntegratorConnector).toHaveBeenCalledTimes(1)
    })
    expect(mocks.testIntegratorConnector).toHaveBeenCalledWith(expect.objectContaining({
      id: 'webhook-1',
      type: 'webhook',
      approved: true,
    }))

    act(() => {
      result.current.credentialPanelProps?.onProbeConnector()
    })
    await waitFor(() => {
      expect(mocks.probeIntegratorConnector).toHaveBeenCalledWith('webhook-1', { mode: 'static' })
    })

    act(() => {
      result.current.schedulesPanelProps.onDryRunScheduleTick()
    })
    await waitFor(() => {
      expect(mocks.triggerIntegratorScheduleTick).toHaveBeenCalledWith(true)
    })
  })
})
