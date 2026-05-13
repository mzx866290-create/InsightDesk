import { describe, expect, it } from 'vitest'

import type { IntegratorConnector } from '../../api/client'
import {
  connectorIdentifier,
  connectorStats,
  DEFAULT_CONNECTOR,
  displayName,
  draftToConnector,
  hasConfiguredEndpoint,
  redactSettingsForDisplay,
  statusLabel,
  statusTone,
  toDraft,
} from './integratorConnectorModel'

describe('integratorConnectorModel', () => {
  it('redacts nested connector settings and round-trips drafts', () => {
    const connector: IntegratorConnector = {
      id: 'conn-1',
      type: 'webhook',
      name: '  Example  ',
      description: '  Demo  ',
      enabled: true,
      approved: false,
      settings: {
        url: 'https://example.invalid',
        token: 'raw-token',
        nested: {
          password: 'raw-password',
          safe: 'value',
        },
      },
    }

    const draft = toDraft(connector)
    expect(draft.settings.url).toBe('***redacted***')
    expect(draft.settings.nested).toEqual({ password: '***redacted***', safe: 'value' })
    expect(draft.settingsJson).toContain('***redacted***')

    const parsed = draftToConnector({
      ...draft,
      id: ' conn-1 ',
      name: ' Example ',
      description: ' Demo ',
      settingsJson: '{\n  "token": ""\n}',
    })
    expect(parsed).toEqual({
      id: 'conn-1',
      type: 'webhook',
      name: 'Example',
      description: 'Demo',
      enabled: true,
      approved: false,
      settings: { token: '' },
    })

    expect(() =>
      draftToConnector({
        ...draft,
        settingsJson: '[]',
      }),
    ).toThrow('Connector settings JSON must be a JSON object')
  })

  it('derives connector display and status helpers', () => {
    const connector: IntegratorConnector = {
      id: ' conn-1 ',
      type: 'webhook',
      name: ' Demo ',
      enabled: true,
      approved: true,
      settings: { url: 'https://example.invalid' },
    }

    const draft = toDraft(connector)
    expect(connectorIdentifier(draft)).toBe('conn-1')
    expect(displayName(draft)).toBe(' Demo ')
    expect(statusTone(draft)).toContain('accent-green')
    expect(statusLabel(draft)).toBe('Approved')
    expect(hasConfiguredEndpoint(draft)).toBe(true)
    expect(connectorStats([draft]).configuredCount).toBe(1)
    expect(connectorStats([draft]).approvedCount).toBe(1)
  })

  it('exposes the default connector shape for new drafts', () => {
    expect(DEFAULT_CONNECTOR.type).toBe('webhook')
    expect(DEFAULT_CONNECTOR.enabled).toBe(true)
    expect(redactSettingsForDisplay({ token: '' })).toEqual({ token: '' })
  })
})
