import React, { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Activity,
  CheckCircle,
  LockKeyhole,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Trash2,
} from 'lucide-react'

import {
  approveMcpConnector,
  getMcpConfig,
  getMcpConnectorApprovals,
  getMcpConnectors,
  getMcpRuntimeHealth,
  getMcpRuntimeHealthHistory,
  revokeMcpConnectorApproval,
  saveMcpConfig,
} from '../../api/client'
import type {
  McpConfigResponse,
  McpConnector,
  McpConnectorApprovalsResponse,
  McpRuntimeHealthHistoryItem,
  McpRuntimeHealthResponse,
  SaveMcpConfigPayload,
} from '../../api/client'
import { Button } from '../ui/Button'

const RUNTIME_HEALTH_HISTORY_LIMIT = 10

const RISK_TONE: Record<string, string> = {
  low: 'bg-accent-green/15 text-accent-green',
  medium: 'bg-accent-blue/15 text-accent-blue',
  high: 'bg-amber-300/15 text-amber-300',
  critical: 'bg-accent-red/15 text-accent-red',
}

function emptyApprovalPayload(): McpConnectorApprovalsResponse {
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

function normalizeApprovalPayload(payload?: McpConnectorApprovalsResponse | null): McpConnectorApprovalsResponse {
  return payload ?? emptyApprovalPayload()
}

function hasApproval(name: string, names: string[]): boolean {
  return names.includes('*') || names.includes(name)
}

function connectorNeedsApproval(connector: McpConnector): boolean {
  return connector.requires_approval === true || connector.policy?.requires_approval === true
}

function riskClass(riskLevel: string): string {
  return RISK_TONE[riskLevel] ?? 'bg-bg-hover text-text-secondary'
}

function sourceLabel(source: string): string {
  if (source === 'env') return 'env'
  if (source === 'runtime') return 'runtime'
  return source
}

function statusClass(healthy: boolean): string {
  return healthy ? 'text-accent-green' : 'text-accent-red'
}

function formatRuntimeHistoryTimestamp(timestamp: number): string {
  if (!Number.isFinite(timestamp) || timestamp <= 0) return '-'
  return new Date(timestamp * 1000).toLocaleString()
}

function formatMcpConfigEditorValue(payload: McpConfigResponse | null): string {
  if (!payload) return ''
  const config = Object.keys(payload.config).length > 0
    ? payload.config
    : {
        connectors: payload.connectors,
        default_enabled: payload.default_enabled,
      }
  return JSON.stringify(config, null, 2)
}

function parseMcpConfigEditorValue(value: string): SaveMcpConfigPayload {
  const parsed = JSON.parse(value) as unknown
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('MCP config must be a JSON object')
  }
  return parsed as SaveMcpConfigPayload
}

export const McpApprovalsPanel: React.FC = () => {
  const [connectors, setConnectors] = useState<McpConnector[]>([])
  const [approvals, setApprovals] = useState<McpConnectorApprovalsResponse>(() => emptyApprovalPayload())
  const [mcpConfig, setMcpConfig] = useState<McpConfigResponse | null>(null)
  const [mcpConfigText, setMcpConfigText] = useState('')
  const [runtimeHealth, setRuntimeHealth] = useState<McpRuntimeHealthResponse | null>(null)
  const [runtimeHealthHistory, setRuntimeHealthHistory] = useState<McpRuntimeHealthHistoryItem[]>([])
  const [loading, setLoading] = useState(false)
  const [loadingConfig, setLoadingConfig] = useState(false)
  const [savingConfig, setSavingConfig] = useState(false)
  const [checkingRuntime, setCheckingRuntime] = useState(false)
  const [loadingRuntimeHistory, setLoadingRuntimeHistory] = useState(false)
  const [actingName, setActingName] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [runtimeHistoryError, setRuntimeHistoryError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const loadState = useCallback(async () => {
    setLoading(true)
    setError(null)
    setNotice(null)
    try {
      const [catalogPayload, approvalsPayload] = await Promise.all([
        getMcpConnectors(),
        getMcpConnectorApprovals(),
      ])
      setConnectors(catalogPayload.connectors)
      setApprovals(normalizeApprovalPayload(approvalsPayload))
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err || 'Failed to load MCP approvals'))
    } finally {
      setLoading(false)
    }
  }, [])

  const loadConfig = useCallback(async () => {
    setLoadingConfig(true)
    setError(null)
    try {
      const payload = await getMcpConfig()
      setMcpConfig(payload)
      setMcpConfigText(formatMcpConfigEditorValue(payload))
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err || 'Failed to load MCP config'))
    } finally {
      setLoadingConfig(false)
    }
  }, [])

  const loadRuntimeHealthHistory = useCallback(async () => {
    setLoadingRuntimeHistory(true)
    setRuntimeHistoryError(null)
    try {
      const payload = await getMcpRuntimeHealthHistory(RUNTIME_HEALTH_HISTORY_LIMIT)
      setRuntimeHealthHistory(payload.history)
    } catch (err) {
      setRuntimeHistoryError(err instanceof Error ? err.message : String(err || 'Failed to load MCP runtime history'))
    } finally {
      setLoadingRuntimeHistory(false)
    }
  }, [])

  useEffect(() => {
    void loadState()
  }, [loadState])

  useEffect(() => {
    void loadConfig()
  }, [loadConfig])

  useEffect(() => {
    void loadRuntimeHealthHistory()
  }, [loadRuntimeHealthHistory])

  const sortedConnectors = useMemo(
    () =>
      [...connectors].sort((left, right) => {
        const leftNeedsApproval = connectorNeedsApproval(left) ? 0 : 1
        const rightNeedsApproval = connectorNeedsApproval(right) ? 0 : 1
        if (leftNeedsApproval !== rightNeedsApproval) return leftNeedsApproval - rightNeedsApproval
        return left.label.localeCompare(right.label)
      }),
    [connectors],
  )

  const connectorLabelByName = useMemo(
    () => new Map(connectors.map((connector) => [connector.name, connector.label || connector.name])),
    [connectors],
  )

  const unknownApprovedConnectors = useMemo(
    () => approvals.runtime_connectors.filter((name) => !connectors.some((connector) => connector.name === name)),
    [approvals.runtime_connectors, connectors],
  )

  const handleRuntimeHealth = async () => {
    setCheckingRuntime(true)
    setError(null)
    setNotice(null)
    try {
      const payload = await getMcpRuntimeHealth()
      setRuntimeHealth(payload)
      void loadRuntimeHealthHistory()
      setNotice(`Runtime health: ${payload.status}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err || 'Failed to check MCP runtime health'))
    } finally {
      setCheckingRuntime(false)
    }
  }

  const handleSaveConfig = async () => {
    setSavingConfig(true)
    setError(null)
    setNotice(null)
    try {
      const payload = parseMcpConfigEditorValue(mcpConfigText)
      const saved = await saveMcpConfig(payload)
      setMcpConfig(saved)
      setMcpConfigText(formatMcpConfigEditorValue(saved))
      setRuntimeHealth(null)
      await Promise.all([loadState(), loadRuntimeHealthHistory()])
      setNotice('Config saved')
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err || 'Failed to save MCP config'))
    } finally {
      setSavingConfig(false)
    }
  }

  const handleApprove = async (name: string) => {
    setActingName(name)
    setError(null)
    setNotice(null)
    try {
      const payload = await approveMcpConnector(name)
      setApprovals(normalizeApprovalPayload(payload))
      setRuntimeHealth(null)
      setNotice(`Approved ${name}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err || 'Failed to approve MCP connector'))
    } finally {
      setActingName(null)
    }
  }

  const handleRevoke = async (name: string) => {
    setActingName(name)
    setError(null)
    setNotice(null)
    try {
      const payload = await revokeMcpConnectorApproval(name)
      setApprovals(normalizeApprovalPayload(payload))
      setRuntimeHealth(null)
      setNotice(`Revoked runtime approval for ${name}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err || 'Failed to revoke MCP connector approval'))
    } finally {
      setActingName(null)
    }
  }

  return (
    <div className="space-y-4" data-testid="settings-mcp-approvals-panel">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="flex items-center gap-2 text-sm font-medium text-text-primary">
          <ShieldAlert size={14} className="text-accent-blue" />
          MCP approvals
        </h3>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => void handleRuntimeHealth()}
            loading={checkingRuntime}
            data-testid="settings-mcp-runtime-health-check"
          >
            <Activity size={12} />
            Runtime check
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => void loadState()}
            loading={loading}
            data-testid="settings-mcp-approvals-refresh"
          >
            <RefreshCw size={12} />
            Refresh
          </Button>
        </div>
      </div>

      <div className="grid gap-2 rounded-lg border border-bg-border bg-bg-tertiary/30 px-3 py-2 text-xs text-text-secondary sm:grid-cols-4">
        <span>Effective: <b className="text-text-primary">{approvals.approved_connectors.length}</b></span>
        <span>Runtime: <b className="text-text-primary">{approvals.runtime_connectors.length}</b></span>
        <span>Env: <b className="text-text-primary">{approvals.env_connectors.length}</b></span>
        <span>Store: <b className="text-text-primary">{approvals.persistence.enabled ? approvals.persistence.config_key : '-'}</b></span>
      </div>

      <div
        className="space-y-2 rounded-lg border border-bg-border bg-bg-tertiary/30 p-3"
        data-testid="settings-mcp-config-panel"
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2 text-[11px] text-text-secondary">
            <span className="font-medium uppercase tracking-wide">Config</span>
            <span>{mcpConfig?.persistence.enabled ? mcpConfig.persistence.config_key : '-'}</span>
            {mcpConfig?.sensitive_fields_redacted && <span>redacted</span>}
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => void handleSaveConfig()}
            loading={savingConfig}
            disabled={loadingConfig || savingConfig || !mcpConfigText.trim()}
            data-testid="settings-mcp-config-save"
          >
            <CheckCircle size={12} />
            Save
          </Button>
        </div>
        <textarea
          value={mcpConfigText}
          onChange={(event) => setMcpConfigText(event.target.value)}
          spellCheck={false}
          disabled={loadingConfig || savingConfig}
          className="h-44 w-full resize-y rounded-md border border-bg-border bg-bg-primary px-3 py-2 font-mono text-xs leading-relaxed text-text-primary outline-none transition focus:border-accent-blue disabled:cursor-not-allowed disabled:opacity-70"
          data-testid="settings-mcp-config-editor"
        />
      </div>

      {runtimeHealth && (
        <div
          className="space-y-2 rounded-lg border border-bg-border bg-bg-tertiary/30 p-3"
          data-testid="settings-mcp-runtime-health"
        >
          <div className="grid gap-2 text-xs text-text-secondary sm:grid-cols-4">
            <span>Status: <b className="text-text-primary">{runtimeHealth.status}</b></span>
            <span>Healthy: <b className="text-accent-green">{runtimeHealth.summary.healthy}</b></span>
            <span>Unhealthy: <b className="text-accent-red">{runtimeHealth.summary.unhealthy}</b></span>
            <span>Tools: <b className="text-text-primary">{runtimeHealth.summary.tool_count}</b></span>
          </div>
          <div className="overflow-hidden rounded-md border border-bg-border">
            {runtimeHealth.servers.length === 0 ? (
              <div className="px-3 py-3 text-xs text-text-secondary" data-testid="settings-mcp-runtime-health-empty">
                No active runtime connectors.
              </div>
            ) : (
              runtimeHealth.servers.map((server) => (
                <div
                  key={server.name}
                  className="grid gap-2 border-t border-bg-border px-3 py-2 text-xs text-text-secondary first:border-t-0 md:grid-cols-[minmax(10rem,1fr)_6rem_5rem_minmax(12rem,1fr)]"
                  data-testid="settings-mcp-runtime-health-row"
                  data-connector-name={server.name}
                >
                  <span className="font-medium text-text-primary">
                    {connectorLabelByName.get(server.name) ?? server.name}
                  </span>
                  <span className={statusClass(server.healthy)}>{server.status}</span>
                  <span>{server.duration_ms.toFixed(server.duration_ms >= 10 ? 1 : 2)} ms</span>
                  <span className="min-w-0 truncate" title={server.error ?? server.tools.join(', ')}>
                    {server.error ?? (server.tools.length > 0 ? server.tools.join(', ') : '-')}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      <div
        className="space-y-2 rounded-lg border border-bg-border bg-bg-tertiary/30 p-3"
        data-testid="settings-mcp-runtime-health-history"
      >
        <div className="flex items-center justify-between gap-2">
          <p className="text-[11px] font-medium uppercase tracking-wide text-text-secondary">
            Runtime health history
          </p>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => void loadRuntimeHealthHistory()}
            loading={loadingRuntimeHistory}
            data-testid="settings-mcp-runtime-health-history-refresh"
          >
            <RefreshCw size={12} />
            Refresh
          </Button>
        </div>
        {runtimeHistoryError ? (
          <div className="rounded-md border border-accent-red/30 bg-accent-red/10 px-3 py-2 text-xs text-accent-red">
            {runtimeHistoryError}
          </div>
        ) : loadingRuntimeHistory && runtimeHealthHistory.length === 0 ? (
          <div className="px-3 py-3 text-xs text-text-secondary">
            Loading runtime health history...
          </div>
        ) : runtimeHealthHistory.length === 0 ? (
          <div className="px-3 py-3 text-xs text-text-secondary">
            No runtime health history.
          </div>
        ) : (
          <div className="space-y-1 rounded-md border border-bg-border bg-bg-tertiary/20 px-3 py-2">
            {runtimeHealthHistory.map((item) => {
              const connectorNames = item.servers
                .map((server) => connectorLabelByName.get(server.name) ?? server.name)
                .filter(Boolean)
              const connectorSummary = connectorNames.length > 0
                ? connectorNames.join(', ')
                : formatRuntimeHistoryTimestamp(item.timestamp)
              const historyHealthy = item.summary.unhealthy === 0
              return (
                <div
                  key={`${item.timestamp}-${item.status}`}
                  className="grid gap-1 text-[11px] text-text-secondary md:grid-cols-[7rem_9rem_5rem_minmax(12rem,1fr)]"
                  data-testid="settings-mcp-runtime-health-history-row"
                >
                  <span className={statusClass(historyHealthy)}>{item.status}</span>
                  <span>{item.summary.healthy} healthy / {item.summary.unhealthy} unhealthy</span>
                  <span>alerts {item.summary.alert_count}</span>
                  <span className="min-w-0 truncate" title={connectorSummary}>
                    {connectorSummary}
                  </span>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {(error || notice) && (
        <div
          className={`rounded-lg border px-3 py-2 text-xs ${
            error
              ? 'border-accent-red/30 bg-accent-red/10 text-accent-red'
              : 'border-accent-green/30 bg-accent-green/10 text-accent-green'
          }`}
          data-testid="settings-mcp-approvals-message"
        >
          {error ?? notice}
        </div>
      )}

      <div className="overflow-hidden rounded-lg border border-bg-border" data-testid="settings-mcp-approvals-list">
        <div className="hidden grid-cols-[minmax(13rem,1.3fr)_7rem_7rem_minmax(11rem,1fr)_9rem] gap-3 bg-bg-tertiary/60 px-3 py-2 text-[11px] font-medium uppercase tracking-wide text-text-secondary md:grid">
          <span>Connector</span>
          <span>Risk</span>
          <span>Approval</span>
          <span>Sources</span>
          <span>Action</span>
        </div>

        {loading && sortedConnectors.length === 0 && (
          <div className="flex justify-center py-8">
            <span className="h-5 w-5 animate-spin rounded-full border-2 border-accent-blue border-t-transparent" />
          </div>
        )}

        {!loading && sortedConnectors.length === 0 && (
          <div className="px-3 py-8 text-center text-xs text-text-secondary" data-testid="settings-mcp-approvals-empty">
            No MCP connectors.
          </div>
        )}

        {sortedConnectors.map((connector) => {
          const riskLevel = connector.policy?.risk_level ?? connector.risk_level ?? 'medium'
          const approved = hasApproval(connector.name, approvals.approved_connectors)
          const runtimeApproved = hasApproval(connector.name, approvals.runtime_connectors)
          const envApproved = hasApproval(connector.name, approvals.env_connectors)
          const sources = approvals.sources[connector.name] ?? []
          const needsApproval = connectorNeedsApproval(connector)
          const actionDisabled = actingName !== null || loading
          return (
            <div
              key={connector.name}
              className="grid gap-2 border-t border-bg-border px-3 py-2 text-xs text-text-secondary first:border-t-0 md:grid-cols-[minmax(13rem,1.3fr)_7rem_7rem_minmax(11rem,1fr)_9rem] md:items-center md:gap-3"
              data-testid="settings-mcp-approval-row"
              data-connector-name={connector.name}
            >
              <div className="min-w-0">
                <p className="truncate font-medium text-text-primary">{connector.label || connector.name}</p>
                <p className="mt-0.5 line-clamp-2 text-[11px] leading-relaxed text-text-secondary/80">
                  {connector.description || connector.name}
                </p>
              </div>
              <div>
                <span className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium ${riskClass(riskLevel)}`}>
                  {riskLevel}
                </span>
              </div>
              <div className="flex items-center gap-1.5">
                {approved ? (
                  <CheckCircle size={13} className="text-accent-green" />
                ) : needsApproval ? (
                  <ShieldAlert size={13} className="text-accent-red" />
                ) : (
                  <ShieldCheck size={13} className="text-accent-blue" />
                )}
                <span className={approved ? 'text-accent-green' : needsApproval ? 'text-accent-red' : 'text-text-secondary'}>
                  {approved ? 'approved' : needsApproval ? 'pending' : 'not required'}
                </span>
              </div>
              <div className="flex flex-wrap gap-1">
                {sources.length > 0 ? (
                  sources.map((source) => (
                    <span key={source} className="rounded-full bg-bg-hover px-2 py-0.5 text-[11px] text-text-secondary">
                      {sourceLabel(source)}
                    </span>
                  ))
                ) : (
                  <span className="text-[11px] text-text-secondary/70">-</span>
                )}
                {envApproved && !runtimeApproved && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-bg-hover px-2 py-0.5 text-[11px] text-text-secondary">
                    <LockKeyhole size={10} />
                    env
                  </span>
                )}
              </div>
              <div>
                {runtimeApproved ? (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => void handleRevoke(connector.name)}
                    loading={actingName === connector.name}
                    disabled={actionDisabled && actingName !== connector.name}
                    className="text-accent-red hover:text-accent-red"
                    data-testid={`settings-mcp-revoke-${connector.name}`}
                  >
                    <Trash2 size={12} />
                    Revoke
                  </Button>
                ) : (
                  <Button
                    variant={needsApproval && !approved ? 'primary' : 'ghost'}
                    size="sm"
                    onClick={() => void handleApprove(connector.name)}
                    loading={actingName === connector.name}
                    disabled={actionDisabled || approved}
                    data-testid={`settings-mcp-approve-${connector.name}`}
                  >
                    <ShieldCheck size={12} />
                    Approve
                  </Button>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {unknownApprovedConnectors.length > 0 && (
        <div className="rounded-lg border border-bg-border bg-bg-tertiary/30 px-3 py-2 text-xs text-text-secondary">
          <p className="mb-2 font-medium text-text-primary">Runtime approvals outside the current catalog</p>
          <div className="flex flex-wrap gap-2">
            {unknownApprovedConnectors.map((name) => (
              <Button
                key={name}
                variant="ghost"
                size="sm"
                onClick={() => void handleRevoke(name)}
                loading={actingName === name}
                className="text-accent-red hover:text-accent-red"
                data-testid={`settings-mcp-revoke-${name}`}
              >
                <Trash2 size={12} />
                {name}
              </Button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
