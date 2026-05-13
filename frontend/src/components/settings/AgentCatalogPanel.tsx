import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Bot, RefreshCw, Trash2 } from 'lucide-react'

import {
  getAgentCatalog,
  installAgentPluginManifest,
  uninstallAgentPluginManifest,
  type AgentCatalogResponse,
  type AgentPluginManifest,
} from '../../api/client'
import { Button } from '../ui/Button'

const DEFAULT_AGENT_PLUGIN_MANIFEST = JSON.stringify({
  name: 'support_triage',
  version: '1.0.0',
  description: 'Static support triage plugin.',
  capabilities: ['support_triage'],
  output_prefix: 'Support triage completed',
  risk_level: 'medium',
  requires_approval: true,
  approval_reason: 'Reviews customer support context before routing tasks.',
  metadata: {
    owner: 'ops',
  },
}, null, 2)

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

function parseAgentPluginManifestDraft(rawDraft: string): AgentPluginManifest {
  const parsed = JSON.parse(rawDraft) as unknown
  const manifest = isRecord(parsed) && isRecord(parsed.manifest)
    ? parsed.manifest
    : parsed
  if (!isRecord(manifest)) {
    throw new Error('Agent plugin manifest must be a JSON object.')
  }
  return manifest as unknown as AgentPluginManifest
}

function formatMetadataValue(value: unknown): string {
  if (Array.isArray(value)) return value.map((item) => String(item)).join(', ')
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  return ''
}

export const AgentCatalogPanel: React.FC = () => {
  const [catalog, setCatalog] = useState<AgentCatalogResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [installing, setInstalling] = useState(false)
  const [uninstallingName, setUninstallingName] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [installMessage, setInstallMessage] = useState<string | null>(null)
  const [manifestDraft, setManifestDraft] = useState(DEFAULT_AGENT_PLUGIN_MANIFEST)
  const [marketplaceQuery, setMarketplaceQuery] = useState('')
  const [marketplaceCategory, setMarketplaceCategory] = useState('all')

  const loadCatalog = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setCatalog(await getAgentCatalog())
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err || 'Failed to load agent catalog'))
    } finally {
      setLoading(false)
    }
  }, [])

  const installManifest = useCallback(async (manifest: AgentPluginManifest) => {
    setInstalling(true)
    setError(null)
    setInstallMessage(null)
    try {
      const nextCatalog = await installAgentPluginManifest({ manifest })
      setCatalog(nextCatalog)
      const installedName = nextCatalog.installed?.name || manifest.name || 'plugin'
      setInstallMessage(`Installed ${installedName}; entrypoint execution: no.`)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err || 'Failed to install agent plugin manifest'))
    } finally {
      setInstalling(false)
    }
  }, [])

  const uninstallManifest = useCallback(async (name: string) => {
    const pluginName = name.trim()
    if (!pluginName) return
    setUninstallingName(pluginName)
    setError(null)
    setInstallMessage(null)
    try {
      const nextCatalog = await uninstallAgentPluginManifest(pluginName)
      setCatalog(nextCatalog)
      const uninstalledName = nextCatalog.uninstalled?.name || pluginName
      setInstallMessage(`Uninstalled ${uninstalledName}; manifest deleted: yes.`)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err || 'Failed to uninstall agent plugin manifest'))
    } finally {
      setUninstallingName(null)
    }
  }, [])

  const handleInstallManifest = useCallback(async () => {
    try {
      await installManifest(parseAgentPluginManifestDraft(manifestDraft))
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err || 'Failed to install agent plugin manifest'))
    }
  }, [installManifest, manifestDraft])

  const handleUseMarketplaceTemplate = useCallback((manifest: AgentPluginManifest) => {
    setManifestDraft(JSON.stringify(manifest, null, 2))
    setInstallMessage(null)
  }, [])

  useEffect(() => {
    void loadCatalog()
  }, [loadCatalog])

  const agents = catalog?.agents ?? []
  const marketplaceTemplates = catalog?.marketplace?.templates ?? []
  const marketplaceIssues = catalog?.marketplace?.issues ?? []
  const manifestIssues = catalog?.plugin_manifests.issues ?? []
  const manifestIssueCount = catalog?.plugin_manifests.issue_count ?? manifestIssues.length
  const marketplaceCategories = useMemo(
    () => Array.from(
      new Set(marketplaceTemplates.map((template) => template.category || 'custom')),
    ).sort((a, b) => a.localeCompare(b)),
    [marketplaceTemplates],
  )
  const filteredMarketplaceTemplates = useMemo(() => {
    const query = marketplaceQuery.trim().toLowerCase()
    return marketplaceTemplates.filter((template) => {
      const category = template.category || 'custom'
      if (marketplaceCategory !== 'all' && category !== marketplaceCategory) return false
      if (!query) return true
      const haystack = [
        template.name,
        template.description,
        category,
        template.risk_level,
        ...template.capabilities,
      ].join(' ').toLowerCase()
      return haystack.includes(query)
    })
  }, [marketplaceCategory, marketplaceQuery, marketplaceTemplates])

  return (
    <div className="space-y-4" data-testid="settings-agent-catalog-panel">
      <div className="rounded-xl border border-bg-border bg-bg-tertiary/30 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="flex items-center gap-2 text-sm font-semibold text-text-primary">
              <Bot size={15} className="text-accent-blue" />
              Agent catalog
            </h3>
            <p className="mt-1 text-xs leading-5 text-text-secondary">
              Built-in specialists plus declarative manifest plugins. Manifests register static agents only; no plugin code is executed.
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={loadCatalog}
            loading={loading}
            data-testid="settings-agent-catalog-refresh"
          >
            <RefreshCw size={12} />
            Refresh
          </Button>
        </div>

        {catalog && (
          <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-text-secondary" data-testid="settings-agent-catalog-summary">
            <span>Total: <b className="text-text-primary">{catalog.summary.total}</b></span>
            <span>Built-in: <b className="text-text-primary">{catalog.summary.builtin}</b></span>
            <span>Plugins: <b className="text-text-primary">{catalog.summary.plugin}</b></span>
            <span>Manifest dirs: <b className="text-text-primary">{catalog.plugin_manifests.directory_count}</b></span>
            <span>Scanned: <b className="text-text-primary">{catalog.plugin_manifests.scanned_count ?? 0}</b></span>
            <span>Loaded: <b className="text-text-primary">{catalog.plugin_manifests.loaded_count ?? 0}</b></span>
            <span>Issues: <b className={manifestIssueCount > 0 ? 'text-amber-300' : 'text-text-primary'}>{manifestIssueCount}</b></span>
            <span>Manifest loading: <b className="text-text-primary">{catalog.plugin_manifests.enabled ? 'on' : 'off'}</b></span>
          </div>
        )}
      </div>

      {error && (
        <div className="rounded-lg border border-accent-red/30 bg-accent-red/10 px-3 py-2 text-xs text-accent-red" data-testid="settings-agent-catalog-error">
          {error}
        </div>
      )}

      {marketplaceTemplates.length > 0 && (
        <div className="rounded-xl border border-bg-border bg-bg-tertiary/20 p-4" data-testid="settings-agent-plugin-marketplace">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h4 className="text-sm font-semibold text-text-primary">Agent plugin marketplace</h4>
              <p className="mt-1 text-xs leading-5 text-text-secondary">
                Install curated static manifests directly, or copy one into the JSON editor before saving.
              </p>
            </div>
            {catalog?.marketplace && (
              <div className="flex flex-wrap gap-2 text-[11px] text-text-secondary" data-testid="settings-agent-plugin-marketplace-summary">
                <span>Total: <b className="text-text-primary">{catalog.marketplace.summary.total}</b></span>
                <span>Available: <b className="text-text-primary">{catalog.marketplace.summary.available}</b></span>
                <span>Installed: <b className="text-text-primary">{catalog.marketplace.summary.installed}</b></span>
              </div>
            )}
          </div>
          <div className="mt-3 grid gap-2 md:grid-cols-[1fr_180px]">
            <input
              value={marketplaceQuery}
              onChange={(event) => setMarketplaceQuery(event.target.value)}
              placeholder="Search templates, capabilities, or risk level"
              className="rounded-lg border border-bg-border bg-bg-primary px-3 py-2 text-xs text-text-primary outline-none transition-colors placeholder:text-text-muted focus:border-accent-blue"
              data-testid="settings-agent-plugin-marketplace-query"
            />
            <select
              value={marketplaceCategory}
              onChange={(event) => setMarketplaceCategory(event.target.value)}
              className="rounded-lg border border-bg-border bg-bg-primary px-3 py-2 text-xs text-text-primary outline-none transition-colors focus:border-accent-blue"
              data-testid="settings-agent-plugin-marketplace-category"
            >
              <option value="all">All categories</option>
              {marketplaceCategories.map((category) => (
                <option key={category} value={category}>
                  {category}
                </option>
              ))}
            </select>
          </div>
          <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {filteredMarketplaceTemplates.map((template) => (
              (() => {
                const pluginName = template.manifest.name || template.name
                return (
              <div
                key={template.name}
                className="rounded-lg border border-bg-border bg-bg-secondary/40 p-3"
                data-testid="settings-agent-plugin-marketplace-row"
                data-agent-plugin-template={template.name}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <h5 className="truncate text-xs font-semibold text-text-primary">{template.name}</h5>
                    <p className="mt-1 line-clamp-2 text-[11px] leading-4 text-text-secondary">{template.description}</p>
                  </div>
                  <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] ${template.installed ? 'bg-accent-green/10 text-accent-green' : 'bg-accent-blue/10 text-accent-blue'}`}>
                    {template.installed ? 'Installed' : 'Template'}
                  </span>
                </div>
                <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-text-secondary">
                  <span>{template.category || 'custom'}</span>
                  <span>{template.risk_level || 'medium'}</span>
                  <span>{template.manifest.runtime || 'static_manifest'}</span>
                  <span>{template.requires_approval ? 'approval required' : 'no approval gate'}</span>
                </div>
                {template.manifest.workflow && template.manifest.workflow.length > 0 && (
                  <div className="mt-2 rounded-md bg-bg-primary/60 px-2 py-1 text-[11px] text-text-secondary">
                    Workflow steps: <b className="text-text-primary">{template.manifest.workflow.length}</b>
                  </div>
                )}
                <div className="mt-2 flex flex-wrap gap-1">
                  {template.capabilities.map((capability) => (
                    <span key={capability} className="rounded-full bg-bg-primary/70 px-2 py-0.5 text-[10px] text-text-secondary">
                      {capability}
                    </span>
                  ))}
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <button
                    type="button"
                    className="rounded-md border border-bg-border px-2 py-1 text-[11px] text-text-secondary transition-colors hover:border-accent-blue hover:text-accent-blue"
                    onClick={() => handleUseMarketplaceTemplate(template.manifest)}
                    data-testid={`settings-agent-plugin-template-use-${template.name}`}
                  >
                    Use template
                  </button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => installManifest(template.manifest)}
                    loading={installing}
                    disabled={template.installed || Boolean(uninstallingName)}
                    data-testid={`settings-agent-plugin-template-install-${template.name}`}
                  >
                    {template.installed ? 'Installed' : 'Install'}
                  </Button>
                  {template.installed && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => uninstallManifest(pluginName)}
                      loading={uninstallingName === pluginName}
                      disabled={installing || Boolean(uninstallingName)}
                      data-testid={`settings-agent-plugin-template-uninstall-${template.name}`}
                    >
                      <Trash2 size={12} />
                      Uninstall
                    </Button>
                  )}
                </div>
              </div>
                )
              })()
            ))}
          </div>
          {filteredMarketplaceTemplates.length === 0 && (
            <div className="mt-3 rounded-lg border border-bg-border bg-bg-primary/60 px-3 py-4 text-center text-xs text-text-secondary" data-testid="settings-agent-plugin-marketplace-empty">
              No marketplace templates match the current filters.
            </div>
          )}
          {marketplaceIssues.length > 0 && (
            <div className="mt-3 rounded-lg border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-xs text-amber-300" data-testid="settings-agent-plugin-marketplace-issues">
              {marketplaceIssues.length} marketplace template issue(s) found.
            </div>
          )}
        </div>
      )}

      <div className="rounded-xl border border-bg-border bg-bg-tertiary/20 p-4" data-testid="settings-agent-plugin-install-panel">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h4 className="text-sm font-semibold text-text-primary">Install Agent plugin manifest</h4>
            <p className="mt-1 text-xs leading-5 text-text-secondary">
              Paste a declarative manifest JSON. The backend validates and persists it, but never imports or executes plugin entrypoints.
            </p>
          </div>
          <Button
            variant="primary"
            size="sm"
            onClick={handleInstallManifest}
            loading={installing}
            data-testid="settings-agent-plugin-install-submit"
          >
            Install manifest
          </Button>
        </div>
        <textarea
          value={manifestDraft}
          onChange={(event) => setManifestDraft(event.target.value)}
          className="mt-3 h-48 w-full rounded-lg border border-bg-border bg-bg-primary p-3 font-mono text-xs leading-5 text-text-primary outline-none focus:border-accent-blue"
          spellCheck={false}
          data-testid="settings-agent-plugin-manifest-input"
        />
        {installMessage && (
          <div className="mt-2 rounded-lg border border-accent-green/30 bg-accent-green/10 px-3 py-2 text-xs text-accent-green" data-testid="settings-agent-plugin-install-success">
            {installMessage}
          </div>
        )}
      </div>

      {manifestIssues.length > 0 && (
        <div className="rounded-xl border border-amber-400/30 bg-amber-400/10 p-3 text-xs text-text-secondary" data-testid="settings-agent-catalog-manifest-issues">
          <div className="mb-2 flex items-center gap-2 font-medium text-amber-300">
            <AlertTriangle size={13} />
            Manifest validation issues
          </div>
          <div className="space-y-2">
            {manifestIssues.map((issue, index) => (
              <div key={`${issue.file}-${issue.code}-${index}`} className="rounded-lg bg-bg-primary/50 px-2 py-1.5">
                <p className="font-medium text-text-primary">{issue.file || 'unknown manifest'}</p>
                <p className="mt-0.5">
                  {issue.code || 'invalid'}: {issue.message || 'Manifest was skipped.'}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid gap-3 md:grid-cols-2">
        {agents.map((agent) => {
          const isPlugin = Boolean(agent.metadata?.plugin)
          const metadataEntries = Object.entries(agent.metadata ?? {})
            .filter(([key]) => !['plugin'].includes(key))
            .map(([key, value]) => [key, formatMetadataValue(value)] as const)
            .filter(([, value]) => value)

          return (
            <div
              key={agent.name}
              className="rounded-xl border border-bg-border bg-bg-tertiary/20 p-4"
              data-testid="settings-agent-catalog-row"
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h4 className="text-sm font-medium text-text-primary">{agent.name}</h4>
                  <p className="mt-1 text-xs leading-5 text-text-secondary">{agent.description}</p>
                </div>
                <div className="flex shrink-0 flex-col items-end gap-2">
                  <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${isPlugin ? 'bg-accent-blue/10 text-accent-blue' : 'bg-bg-secondary text-text-secondary'}`}>
                    {isPlugin ? 'Plugin' : 'Built-in'}
                  </span>
                  {isPlugin && typeof agent.metadata?.runtime === 'string' && (
                    <span className="rounded-full bg-bg-secondary px-2 py-0.5 text-[10px] text-text-secondary">
                      {agent.metadata.runtime}
                    </span>
                  )}
                  {isPlugin && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => uninstallManifest(agent.name)}
                      loading={uninstallingName === agent.name}
                      disabled={installing || Boolean(uninstallingName)}
                      data-testid={`settings-agent-catalog-uninstall-${agent.name}`}
                    >
                      <Trash2 size={12} />
                      Uninstall
                    </Button>
                  )}
                </div>
              </div>
              <div className="mt-3 flex flex-wrap gap-1">
                {agent.capabilities.map((capability) => (
                  <span key={capability} className="rounded-full bg-bg-secondary px-2 py-0.5 text-[10px] text-text-secondary">
                    {capability}
                  </span>
                ))}
              </div>
              {metadataEntries.length > 0 && (
                <div className="mt-3 space-y-1 text-[11px] text-text-secondary">
                  {metadataEntries.map(([key, value]) => (
                    <p key={key}>
                      {key}: <b className="text-text-primary">{value}</b>
                    </p>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {!loading && !error && agents.length === 0 && (
        <div className="rounded-lg border border-bg-border bg-bg-tertiary/20 px-3 py-4 text-center text-xs text-text-secondary">
          No agents are registered yet.
        </div>
      )}
    </div>
  )
}
