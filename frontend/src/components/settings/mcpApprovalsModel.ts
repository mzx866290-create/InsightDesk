import type {
  McpConfigResponse,
  McpConnector,
  McpConnectorApprovalsResponse,
  SaveMcpConfigPayload,
} from '../../api/client'

export const MCP_RUNTIME_HEALTH_HISTORY_LIMIT = 10

const RISK_TONE: Record<string, string> = {
  low: 'bg-accent-green/15 text-accent-green',
  medium: 'bg-accent-blue/15 text-accent-blue',
  high: 'bg-amber-300/15 text-amber-300',
  critical: 'bg-accent-red/15 text-accent-red',
}

export interface McpApprovalsConnectorView {
  sortedConnectors: McpConnector[]
  unknownApprovedConnectors: string[]
  connectorLabelByName: Map<string, string>
}

export function emptyApprovalPayload(): McpConnectorApprovalsResponse {
  return {
    approved_connectors: [],
    env_connectors: [],
    runtime_connectors: [],
    persisted_connectors: [],
    sources: {},
    persistence: { enabled: false, config_key: '' },
    total: 0,
  }
}

export function normalizeApprovalPayload(payload?: McpConnectorApprovalsResponse | null): McpConnectorApprovalsResponse {
  return payload ?? emptyApprovalPayload()
}

export function hasApproval(name: string, names: string[]): boolean {
  return names.includes('*') || names.includes(name)
}

export function connectorNeedsApproval(connector: McpConnector): boolean {
  return connector.requires_approval === true || connector.policy?.requires_approval === true
}

export function sortMcpConnectorsByApproval(connectors: McpConnector[]): McpConnector[] {
  return [...connectors].sort((left, right) => {
    const leftNeedsApproval = connectorNeedsApproval(left) ? 0 : 1
    const rightNeedsApproval = connectorNeedsApproval(right) ? 0 : 1
    if (leftNeedsApproval !== rightNeedsApproval) return leftNeedsApproval - rightNeedsApproval
    return left.label.localeCompare(right.label)
  })
}

export function buildConnectorLabelByName(connectors: McpConnector[]): Map<string, string> {
  return new Map(connectors.map((connector) => [connector.name, connector.label || connector.name]))
}

export function findUnknownRuntimeApprovedConnectors(
  approvals: McpConnectorApprovalsResponse,
  connectors: McpConnector[],
): string[] {
  const connectorNameSet = new Set(connectors.map((connector) => connector.name))
  return approvals.runtime_connectors.filter((name) => !connectorNameSet.has(name))
}

export function buildMcpApprovalsConnectorView(
  connectors: McpConnector[],
  approvals: McpConnectorApprovalsResponse,
): McpApprovalsConnectorView {
  return {
    sortedConnectors: sortMcpConnectorsByApproval(connectors),
    unknownApprovedConnectors: findUnknownRuntimeApprovedConnectors(approvals, connectors),
    connectorLabelByName: buildConnectorLabelByName(connectors),
  }
}

export function riskClass(riskLevel: string): string {
  return RISK_TONE[riskLevel] ?? 'bg-bg-hover text-text-secondary'
}

export function sourceLabel(source: string): string {
  if (source === 'env') return 'env'
  if (source === 'runtime') return 'runtime'
  return source
}

export function statusClass(healthy: boolean): string {
  return healthy ? 'text-accent-green' : 'text-accent-red'
}

export function formatRuntimeHistoryTimestamp(timestamp: number): string {
  if (!Number.isFinite(timestamp) || timestamp <= 0) return '-'
  return new Date(timestamp * 1000).toLocaleString()
}

export function formatMcpConfigEditorValue(payload: McpConfigResponse | null): string {
  if (!payload) return ''
  const config = Object.keys(payload.config).length > 0
    ? payload.config
    : {
        connectors: payload.connectors,
        default_enabled: payload.default_enabled,
      }
  return JSON.stringify(config, null, 2)
}

export function parseMcpConfigEditorValue(value: string): SaveMcpConfigPayload {
  const parsed = JSON.parse(value) as unknown
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('MCP config must be a JSON object')
  }
  return parsed as SaveMcpConfigPayload
}

export function mcpErrorMessage(err: unknown, fallback: string): string {
  return err instanceof Error ? err.message : String(err || fallback)
}
