import { describe, expect, it } from 'vitest'

import {
  connectorIdentifier,
  credentialTemplateById,
  formatAuditTime,
  mcpCategoryLabel,
  scheduleDisplayName,
} from './integratorConnectorsModel'

describe('integratorConnectorsModel compatibility exports', () => {
  it('re-exports connector, credentials, schedule, audit, and MCP helpers', () => {
    expect(connectorIdentifier({
      id: 'connector-1',
      type: 'webhook',
      enabled: true,
      approved: true,
      settings: {},
      settingsJson: '{}',
    })).toBe('connector-1')
    expect(credentialTemplateById('token').id).toBe('token')
    expect(scheduleDisplayName({ name: 'Nightly', connector_id: 'connector-1', cron: '@daily', interval_minutes: 60, enabled: true, settings: {} })).toBe('Nightly')
    expect(formatAuditTime(0)).toBe('-')
    expect(mcpCategoryLabel('developer-tools')).toBe('Developer Tools')
  })
})
