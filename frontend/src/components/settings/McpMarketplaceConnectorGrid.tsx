import React from 'react'

import type { McpConnector } from '../../api/client'
import * as mcpMarketplaceModel from './mcpMarketplaceModel'

interface McpMarketplaceConnectorGridProps {
  connectors: McpConnector[]
  fallbackSource?: string | null
  onUseTemplate?: (connector: McpConnector) => void
}

export const McpMarketplaceConnectorGrid: React.FC<McpMarketplaceConnectorGridProps> = ({
  connectors,
  fallbackSource,
  onUseTemplate,
}) => {
  return (
    <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
      {connectors.map((connector) => (
        <div
          key={connector.name}
          className="rounded-lg border border-bg-border bg-bg-secondary/40 px-3 py-2"
          data-testid="settings-mcp-marketplace-row"
          data-connector-name={connector.name}
        >
          <div className="flex items-center justify-between gap-2">
            <span className="min-w-0 truncate text-xs font-medium text-text-primary">
              {connector.label || connector.name}
            </span>
            <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] ${mcpMarketplaceModel.mcpConnectorTone(connector)}`}>
              {mcpMarketplaceModel.mcpConnectorLabel(connector)}
            </span>
          </div>
          <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-text-secondary">
            <span>{connector.category || 'custom'}</span>
            <span>{connector.transport || 'stdio'}</span>
            <span>{connector.risk_level || 'medium'}</span>
            <span>{connector.source || fallbackSource || '-'}</span>
          </div>
          {(connector.template || connector.source === 'template') && onUseTemplate && (
            <button
              type="button"
              className="mt-2 rounded-md border border-bg-border px-2 py-1 text-[11px] text-text-secondary transition-colors hover:border-accent-blue hover:text-accent-blue"
              onClick={() => onUseTemplate(connector)}
              data-testid={`settings-mcp-use-template-${connector.name}`}
            >
              Use template
            </button>
          )}
        </div>
      ))}
    </div>
  )
}
