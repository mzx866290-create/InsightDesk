import type { IntegratorConnector } from '../../api/client'

export type ConnectorDraft = IntegratorConnector & {
  settingsJson: string
}

export interface ConnectorStats {
  configuredCount: number
  approvedCount: number
}

export const DEFAULT_CONNECTOR: ConnectorDraft = {
  type: 'webhook',
  name: 'Ops Webhook',
  description: '',
  enabled: true,
  approved: false,
  settings: {
    url: '',
    token: '',
  },
  settingsJson: '{\n  "url": "",\n  "token": ""\n}',
}

const REDACTED_CREDENTIAL_VALUE = '***redacted***'
const SENSITIVE_SETTING_KEY_PATTERN = /(url|token|secret|client_secret|password|credential|authorization|auth|api_key|key|username)/i

export function redactSettingsForDisplay(settings: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(settings).map(([key, value]) => {
      if (SENSITIVE_SETTING_KEY_PATTERN.test(key)) {
        return [key, value === '' || value === null || value === undefined ? value : REDACTED_CREDENTIAL_VALUE]
      }
      if (value && typeof value === 'object' && !Array.isArray(value)) {
        return [key, redactSettingsForDisplay(value as Record<string, unknown>)]
      }
      return [key, value]
    }),
  )
}

export function toDraft(connector: IntegratorConnector): ConnectorDraft {
  const displaySettings = redactSettingsForDisplay(connector.settings ?? {})
  return {
    ...connector,
    settings: displaySettings,
    settingsJson: JSON.stringify(displaySettings, null, 2),
  }
}

export function draftToConnector(draft: ConnectorDraft): IntegratorConnector {
  let parsed: unknown
  try {
    parsed = JSON.parse(draft.settingsJson.trim() || '{}') as unknown
  } catch {
    throw new Error(`Connector settings JSON is invalid: ${draft.name || draft.id || draft.type}`)
  }
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error(`Connector settings JSON must be a JSON object: ${draft.name || draft.id || draft.type}`)
  }
  const settings = parsed as Record<string, unknown>
  return {
    id: draft.id?.trim() || undefined,
    type: draft.type || 'webhook',
    name: draft.name?.trim() || undefined,
    description: draft.description?.trim() || undefined,
    enabled: draft.enabled !== false,
    approved: draft.approved === true,
    settings,
  }
}

export function connectorIdentifier(connector: ConnectorDraft): string {
  return connector.id?.trim() || connector.name?.trim() || connector.type
}

export function displayName(connector: ConnectorDraft): string {
  return connector.name || connector.id || connector.type || 'connector'
}

export function hasConfiguredEndpoint(connector: ConnectorDraft): boolean {
  const settings = connector.settings ?? {}
  return Boolean(settings.url || settings.webhook_url || settings.endpoint || settings.to)
}

export function statusTone(connector: ConnectorDraft): string {
  if (!connector.enabled) return 'bg-bg-hover text-text-secondary'
  if (!connector.approved) return 'bg-amber-300/15 text-amber-300'
  return 'bg-accent-green/15 text-accent-green'
}

export function statusLabel(connector: ConnectorDraft): string {
  if (!connector.enabled) return 'Disabled'
  if (!connector.approved) return 'Needs approval'
  return 'Approved'
}

export function connectorStats(connectors: ConnectorDraft[]): ConnectorStats {
  return {
    configuredCount: connectors.filter((connector) => connector.enabled && hasConfiguredEndpoint(connector)).length,
    approvedCount: connectors.filter((connector) => connector.approved).length,
  }
}
