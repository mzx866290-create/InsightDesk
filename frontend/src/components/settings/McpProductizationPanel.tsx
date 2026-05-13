import React from 'react'
import { Activity, CheckCircle, PlusCircle, RefreshCw, Save } from 'lucide-react'

import type { McpConnector, McpMarketplaceCategory, McpRuntimeHealthResponse } from '../../api/client'
import * as mcpMarketplaceModel from './mcpMarketplaceModel'
import type { McpManifestValidationResult } from './mcpMarketplaceModel'
import { McpMarketplaceCategoryTabs } from './McpMarketplaceCategoryTabs'
import { McpMarketplaceConnectorGrid } from './McpMarketplaceConnectorGrid'
import { McpProductizationSummaryPanel } from './McpProductizationSummaryPanel'
import { Button } from '../ui/Button'

interface McpProductizationPanelProps {
  marketplaceSummary: mcpMarketplaceModel.McpMarketplaceSummaryView
  marketplaceCategories: McpMarketplaceCategory[]
  marketplaceCategoryId: string
  visibleConnectors: McpConnector[]
  fallbackSource?: string | null
  runtimeHealth: McpRuntimeHealthResponse | null
  notice: string | null
  error: string | null
  manifestText: string
  manifestValidation?: McpManifestValidationResult
  loading: boolean
  pinging: boolean
  hotUpdating: boolean
  installing: boolean
  hotUpdateDisabled: boolean
  installDisabled: boolean
  onRefresh: () => void
  onRuntimePing: () => void
  onHotUpdate: () => void
  onManifestInstall: () => void
  onManifestTextChange: (value: string) => void
  onTemplateSelect: (connector: McpConnector) => void
  onMarketplaceCategoryChange: (categoryId: string) => void
}

export const McpProductizationPanel: React.FC<McpProductizationPanelProps> = ({
  marketplaceSummary,
  marketplaceCategories,
  marketplaceCategoryId,
  visibleConnectors,
  fallbackSource,
  runtimeHealth,
  notice,
  error,
  manifestText,
  manifestValidation,
  loading,
  pinging,
  hotUpdating,
  installing,
  hotUpdateDisabled,
  installDisabled,
  onRefresh,
  onRuntimePing,
  onHotUpdate,
  onManifestInstall,
  onManifestTextChange,
  onTemplateSelect,
  onMarketplaceCategoryChange,
}) => {
  const manifestErrors = manifestValidation?.errors ?? []
  const requiredFields = manifestValidation?.requiredFields ?? []
  const sensitiveFields = manifestValidation?.sensitiveFields ?? []

  return (
    <div
      className="rounded-lg border border-bg-border bg-bg-tertiary/20 p-3"
      data-testid="settings-mcp-productization-panel"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h4 className="flex items-center gap-2 text-sm font-medium text-text-primary">
            <Activity size={14} className="text-accent-blue" />
            MCP connectors
          </h4>
          <p className="mt-1 text-xs text-text-secondary">Marketplace catalog, hot update, and runtime health.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={onRefresh}
            loading={loading}
            data-testid="settings-mcp-refresh"
          >
            <RefreshCw size={12} />
            Refresh
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={onRuntimePing}
            loading={pinging}
            data-testid="settings-mcp-runtime-ping"
          >
            <Activity size={12} />
            Runtime
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={onHotUpdate}
            loading={hotUpdating}
            disabled={hotUpdateDisabled}
            data-testid="settings-mcp-hot-update"
          >
            <Save size={12} />
            Hot update
          </Button>
        </div>
      </div>

      {notice && (
        <div
          className="mt-3 flex items-center gap-2 rounded-lg border border-accent-green/30 bg-accent-green/10 px-3 py-2 text-xs text-accent-green"
          data-testid="settings-mcp-notice"
        >
          <CheckCircle size={13} />
          {notice}
        </div>
      )}

      {error && (
        <div
          className="mt-3 rounded-lg border border-accent-red/30 bg-accent-red/10 px-3 py-2 text-xs text-accent-red"
          data-testid="settings-mcp-error"
        >
          {error}
        </div>
      )}

      <div className="mt-3 rounded-lg border border-bg-border bg-bg-secondary/40 p-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h5 className="text-xs font-medium text-text-primary">Install marketplace manifest</h5>
            <p className="mt-1 text-[11px] text-text-secondary">
              Paste connector manifest JSON. The backend persists config but never executes install commands.
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={onManifestInstall}
            loading={installing}
            disabled={installDisabled}
            data-testid="settings-mcp-manifest-install"
          >
            <PlusCircle size={12} />
            Install
          </Button>
        </div>
        <textarea
          className="mt-2 min-h-[88px] w-full resize-y rounded-lg border border-bg-border bg-bg-primary px-3 py-2 font-mono text-xs text-text-primary outline-none focus:border-accent-blue"
          value={manifestText}
          onChange={(event) => onManifestTextChange(event.target.value)}
          placeholder='{"name":"github","transport":"stdio","install_command":"npx -y @modelcontextprotocol/server-github","scopes":["github:read"]}'
          spellCheck={false}
          data-testid="settings-mcp-manifest-text"
        />
        {(requiredFields.length > 0 || sensitiveFields.length > 0 || manifestErrors.length > 0) && (
          <div className="mt-2 space-y-1 text-[11px]" data-testid="settings-mcp-manifest-hints">
            {requiredFields.length > 0 && (
              <p className="text-text-secondary">
                Required: {requiredFields.join(', ')}
              </p>
            )}
            {sensitiveFields.length > 0 && (
              <p className="text-amber-300">
                Sensitive fields are persisted locally and redacted in API responses: {sensitiveFields.join(', ')}
              </p>
            )}
            {manifestErrors.map((item) => (
              <p key={item} className="text-accent-red">
                {item}
              </p>
            ))}
          </div>
        )}
      </div>

      <McpProductizationSummaryPanel
        marketplaceSummary={marketplaceSummary}
        runtimeHealth={runtimeHealth}
      />

      <McpMarketplaceCategoryTabs
        marketplaceSummary={marketplaceSummary}
        marketplaceCategories={marketplaceCategories}
        marketplaceCategoryId={marketplaceCategoryId}
        onMarketplaceCategoryChange={onMarketplaceCategoryChange}
      />

      <McpMarketplaceConnectorGrid
        connectors={visibleConnectors}
        fallbackSource={fallbackSource}
        onUseTemplate={onTemplateSelect}
      />
    </div>
  )
}
