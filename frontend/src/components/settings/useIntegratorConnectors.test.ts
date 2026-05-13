import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type {
  IntegratorConnector,
  IntegratorConnectorTestResult,
  IntegratorConnectorsResponse,
} from '../../api/client'
import { useIntegratorConnectors } from './useIntegratorConnectors'

const mocks = vi.hoisted(() => ({
  getIntegratorConnectors: vi.fn(),
  saveIntegratorConnectors: vi.fn(),
  testIntegratorConnector: vi.fn(),
}))

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client')
  return {
    ...actual,
    getIntegratorConnectors: mocks.getIntegratorConnectors,
    saveIntegratorConnectors: mocks.saveIntegratorConnectors,
    testIntegratorConnector: mocks.testIntegratorConnector,
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

const emailConnector: IntegratorConnector = {
  id: 'email-1',
  type: 'email',
  name: 'Digest Email',
  description: '',
  enabled: false,
  approved: false,
  settings: {
    to: 'ops@example.invalid',
  },
}

const connectorsResponse = (
  patch: Partial<IntegratorConnectorsResponse> = {},
): IntegratorConnectorsResponse => ({
  connectors: [webhookConnector, emailConnector],
  total: 2,
  supported_types: ['webhook', 'email'],
  persistence: {
    enabled: true,
    config_key: 'integrations.connectors',
    sensitive_fields_redacted: true,
  },
  ...patch,
})

const testResult = (
  patch: Partial<IntegratorConnectorTestResult> = {},
): IntegratorConnectorTestResult => ({
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
  ...patch,
})

describe('useIntegratorConnectors', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  it('loads connectors and derives selected state', async () => {
    mocks.getIntegratorConnectors.mockResolvedValue(connectorsResponse())

    const { result } = renderHook(() => useIntegratorConnectors())

    await act(async () => {
      await result.current.loadConnectors()
    })

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(mocks.getIntegratorConnectors).toHaveBeenCalledTimes(1)
    expect(result.current.connectors).toHaveLength(2)
    expect(result.current.connectors[0].settings.token).toBe('***redacted***')
    expect(result.current.selectedIndex).toBe(0)
    expect(result.current.selectedConnector?.id).toBe('webhook-1')
    expect(result.current.connectorStats.configuredCount).toBe(1)
    expect(result.current.connectorStats.approvedCount).toBe(1)
    expect(result.current.supportedTypes).toEqual(['webhook', 'email'])
    expect(result.current.persistence?.config_key).toBe('integrations.connectors')
    expect(result.current.error).toBeNull()
  })

  it('captures load failures and keeps fallback supported types', async () => {
    mocks.getIntegratorConnectors.mockRejectedValue(new Error('load failed'))

    const { result } = renderHook(() => useIntegratorConnectors())

    await act(async () => {
      await result.current.loadConnectors()
    })

    expect(result.current.error).toBe('load failed')
    expect(result.current.loading).toBe(false)
    expect(result.current.supportedTypes).toEqual(['webhook', 'email', 'feishu', 'dingtalk'])
  })

  it('adds, updates, and removes connector drafts', () => {
    const { result } = renderHook(() => useIntegratorConnectors())

    act(() => {
      result.current.addConnector()
    })

    expect(result.current.connectors).toHaveLength(1)
    expect(result.current.connectors[0].name).toBe('Webhook 1')
    expect(result.current.selectedIndex).toBe(0)

    act(() => {
      result.current.updateConnector(0, { name: 'Updated webhook', approved: true })
    })

    expect(result.current.connectors[0].name).toBe('Updated webhook')
    expect(result.current.connectors[0].approved).toBe(true)

    act(() => {
      result.current.addConnector()
      result.current.addConnector()
    })

    act(() => {
      result.current.setSelectedIndex(2)
      result.current.removeConnector(1)
    })

    expect(result.current.connectors).toHaveLength(2)
    expect(result.current.selectedIndex).toBe(1)
    expect(result.current.notice).toBeNull()
    expect(result.current.testResult).toBeNull()
  })

  it('saves connectors and refreshes audit records', async () => {
    const onAuditRefresh = vi.fn()
    mocks.getIntegratorConnectors.mockResolvedValue(connectorsResponse())
    mocks.saveIntegratorConnectors.mockResolvedValue(connectorsResponse({
      connectors: [{ ...webhookConnector, name: 'Saved Webhook' }],
      supported_types: [],
    }))

    const { result } = renderHook(() => useIntegratorConnectors({ onAuditRefresh }))

    await act(async () => {
      await result.current.loadConnectors()
    })

    act(() => {
      result.current.updateConnector(0, {
        settingsJson: '{\n  "url": "https://example.invalid/hooks/ops"\n}',
      })
    })

    await act(async () => {
      await result.current.handleSave()
    })

    expect(mocks.saveIntegratorConnectors).toHaveBeenCalledWith([
      {
        id: 'webhook-1',
        type: 'webhook',
        name: 'Ops Webhook',
        description: 'Operations alerts',
        enabled: true,
        approved: true,
        settings: {
          url: 'https://example.invalid/hooks/ops',
        },
      },
      {
        id: 'email-1',
        type: 'email',
        name: 'Digest Email',
        description: undefined,
        enabled: false,
        approved: false,
        settings: {
          to: 'ops@example.invalid',
        },
      },
    ])
    expect(result.current.connectors[0].name).toBe('Saved Webhook')
    expect(result.current.supportedTypes).toEqual(['webhook', 'email'])
    expect(result.current.notice).toBe('Integration connector configuration saved')
    expect(result.current.saving).toBe(false)
    expect(onAuditRefresh).toHaveBeenCalledTimes(1)
  })

  it('tests the selected connector and reports failures', async () => {
    const onAuditRefresh = vi.fn()
    mocks.getIntegratorConnectors.mockResolvedValue(connectorsResponse())
    mocks.testIntegratorConnector.mockResolvedValue(testResult({ status: 'warning' }))

    const { result } = renderHook(() => useIntegratorConnectors({ onAuditRefresh }))

    await act(async () => {
      await result.current.loadConnectors()
    })

    act(() => {
      result.current.updateConnector(0, {
        settingsJson: '{\n  "url": "https://example.invalid/hooks/ops"\n}',
      })
    })

    await act(async () => {
      await result.current.handleTest()
    })

    expect(mocks.testIntegratorConnector).toHaveBeenCalledWith({
      id: 'webhook-1',
      type: 'webhook',
      name: 'Ops Webhook',
      description: 'Operations alerts',
      enabled: true,
      approved: true,
      settings: {
        url: 'https://example.invalid/hooks/ops',
      },
    })
    expect(result.current.testResult?.status).toBe('warning')
    expect(result.current.notice).toBe('Connector test warning')
    expect(result.current.testing).toBe(false)
    expect(onAuditRefresh).toHaveBeenCalledTimes(1)

    mocks.testIntegratorConnector.mockRejectedValue(new Error('test failed'))

    await act(async () => {
      await result.current.handleTest()
    })

    expect(result.current.error).toBe('test failed')
    expect(result.current.testing).toBe(false)
  })
})
