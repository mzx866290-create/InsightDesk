import { afterEach, describe, expect, it, vi } from 'vitest'

import type { McpConfigResponse, McpConnector, McpConnectorApprovalsResponse } from '../../api/client'
import {
  buildConnectorLabelByName,
  buildMcpApprovalsConnectorView,
  connectorNeedsApproval,
  emptyApprovalPayload,
  findUnknownRuntimeApprovedConnectors,
  formatMcpConfigEditorValue,
  formatRuntimeHistoryTimestamp,
  hasApproval,
  MCP_RUNTIME_HEALTH_HISTORY_LIMIT,
  mcpErrorMessage,
  normalizeApprovalPayload,
  parseMcpConfigEditorValue,
  riskClass,
  sortMcpConnectorsByApproval,
  sourceLabel,
  statusClass,
} from './mcpApprovalsModel'

const connector = (patch: Partial<McpConnector>): McpConnector => ({
  name: 'alpha',
  label: 'Alpha',
  description: '',
  category: 'core',
  builtin: true,
  transport: 'stdio',
  source: 'catalog',
  enabled: true,
  risk_level: 'medium',
  requires_approval: false,
  ...patch,
})

const config = (patch: Partial<McpConfigResponse>): McpConfigResponse => ({
  connectors: [],
  default_enabled: [],
  config: {},
  servers: {},
  persistence: { enabled: false, config_key: '' },
  sensitive_fields_redacted: false,
  ...patch,
})

describe('mcpApprovalsModel', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('builds and normalizes approval payloads', () => {
    const empty = emptyApprovalPayload()

    expect(empty).toMatchObject({
      approved_connectors: [],
      runtime_connectors: [],
      persistence: { enabled: false, config_key: '' },
      total: 0,
    })
    expect(normalizeApprovalPayload(null)).toEqual(empty)

    const payload: McpConnectorApprovalsResponse = {
      ...empty,
      approved_connectors: ['alpha'],
      total: 1,
    }
    expect(normalizeApprovalPayload(payload)).toBe(payload)
  })

  it('detects approval and connector approval requirements', () => {
    expect(hasApproval('alpha', ['*'])).toBe(true)
    expect(hasApproval('alpha', ['beta'])).toBe(false)
    expect(hasApproval('alpha', ['alpha'])).toBe(true)

    expect(connectorNeedsApproval(connector({ requires_approval: true }))).toBe(true)
    expect(connectorNeedsApproval(connector({
      policy: {
        allowed: true,
        requires_approval: true,
        missing_scopes: [],
        reasons: ['filesystem access'],
        connector_approved: false,
        risk_level: 'high',
        capability_scopes: [],
      },
    }))).toBe(true)
    expect(connectorNeedsApproval(connector({ requires_approval: false }))).toBe(false)
  })

  it('sorts approval-required connectors first and then by label', () => {
    const sorted = sortMcpConnectorsByApproval([
      connector({ name: 'zeta', label: 'Zeta', requires_approval: false }),
      connector({ name: 'beta', label: 'Beta', requires_approval: true }),
      connector({ name: 'alpha', label: 'Alpha', requires_approval: true }),
    ])

    expect(sorted.map((item) => item.name)).toEqual(['alpha', 'beta', 'zeta'])
  })

  it('builds derived connector view data', () => {
    const connectors = [
      connector({ name: 'zeta', label: '', requires_approval: false }),
      connector({ name: 'alpha', label: 'Alpha', requires_approval: true }),
    ]
    const payload = {
      ...emptyApprovalPayload(),
      runtime_connectors: ['alpha', 'ghost'],
    }

    const labelByName = buildConnectorLabelByName(connectors)
    expect(labelByName.get('alpha')).toBe('Alpha')
    expect(labelByName.get('zeta')).toBe('zeta')
    expect(findUnknownRuntimeApprovedConnectors(payload, connectors)).toEqual(['ghost'])

    expect(buildMcpApprovalsConnectorView(connectors, payload)).toMatchObject({
      sortedConnectors: [connectors[1], connectors[0]],
      unknownApprovedConnectors: ['ghost'],
      connectorLabelByName: labelByName,
    })
  })

  it('formats display helper classes and labels', () => {
    expect(riskClass('critical')).toContain('text-accent-red')
    expect(riskClass('unknown')).toBe('bg-bg-hover text-text-secondary')
    expect(sourceLabel('env')).toBe('env')
    expect(sourceLabel('runtime')).toBe('runtime')
    expect(sourceLabel('config')).toBe('config')
    expect(statusClass(true)).toBe('text-accent-green')
    expect(statusClass(false)).toBe('text-accent-red')
  })

  it('formats runtime history timestamps', () => {
    vi.spyOn(Date.prototype, 'toLocaleString').mockReturnValue('2026/05/08 14:40')

    expect(formatRuntimeHistoryTimestamp(0)).toBe('-')
    expect(formatRuntimeHistoryTimestamp(Number.NaN)).toBe('-')
    expect(formatRuntimeHistoryTimestamp(1_715_000_000)).toBe('2026/05/08 14:40')
  })

  it('formats config editor content from config or fallback fields', () => {
    expect(formatMcpConfigEditorValue(null)).toBe('')
    expect(formatMcpConfigEditorValue(config({ config: { default_enabled: true } }))).toBe(
      JSON.stringify({ default_enabled: true }, null, 2),
    )
    expect(formatMcpConfigEditorValue(config({
      connectors: [connector({ name: 'alpha' })],
      default_enabled: ['alpha'],
      config: {},
    }))).toBe(JSON.stringify({
      connectors: [connector({ name: 'alpha' })],
      default_enabled: ['alpha'],
    }, null, 2))
  })

  it('parses config editor JSON and rejects non-object JSON', () => {
    expect(parseMcpConfigEditorValue('{"default_enabled":true}')).toEqual({ default_enabled: true })
    expect(() => parseMcpConfigEditorValue('[]')).toThrow('MCP config must be a JSON object')
    expect(() => parseMcpConfigEditorValue('null')).toThrow('MCP config must be a JSON object')
    expect(() => parseMcpConfigEditorValue('bad json')).toThrow()
  })

  it('formats hook-level constants and fallback errors', () => {
    expect(MCP_RUNTIME_HEALTH_HISTORY_LIMIT).toBe(10)
    expect(mcpErrorMessage(new Error('boom'), 'fallback')).toBe('boom')
    expect(mcpErrorMessage('', 'fallback')).toBe('fallback')
    expect(mcpErrorMessage('plain error', 'fallback')).toBe('plain error')
  })
})
