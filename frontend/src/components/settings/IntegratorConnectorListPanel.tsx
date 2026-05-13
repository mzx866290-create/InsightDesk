import React from 'react'
import { Plus } from 'lucide-react'

import {
  connectorIdentifier,
  displayName,
  hasConfiguredEndpoint,
  statusLabel,
  statusTone,
  type ConnectorDraft,
} from './integratorConnectorModel'
import { Button } from '../ui/Button'

export interface IntegratorConnectorListPanelProps {
  connectors: ConnectorDraft[]
  selectedIndex: number
  loading: boolean
  onAddConnector: () => void
  onSelectConnector: (index: number) => void
}

export const IntegratorConnectorListPanel: React.FC<IntegratorConnectorListPanelProps> = ({
  connectors,
  selectedIndex,
  loading,
  onAddConnector,
  onSelectConnector,
}) => {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-text-secondary">Connectors</span>
        <Button variant="outline" size="sm" onClick={onAddConnector} data-testid="settings-integrator-add">
          <Plus size={12} />
          Add
        </Button>
      </div>

      {connectors.length === 0 && !loading && (
        <button
          type="button"
          onClick={onAddConnector}
          className="w-full rounded-lg border border-dashed border-bg-border bg-bg-tertiary/20 px-3 py-6 text-center text-xs text-text-secondary hover:border-accent-blue/40 hover:text-text-primary"
          data-testid="settings-integrator-empty"
        >
          Add the first webhook connector
        </button>
      )}

      {connectors.map((connector, index) => (
        <button
          key={`${connector.id || connector.name || connector.type}-${index}`}
          type="button"
          onClick={() => onSelectConnector(index)}
          data-testid="settings-integrator-connector-row"
          data-connector-id={connectorIdentifier(connector)}
          data-connector-type={connector.type}
          className={`w-full rounded-lg border px-3 py-2 text-left transition-colors ${
            selectedIndex === index
              ? 'border-accent-blue/50 bg-accent-blue/10'
              : 'border-bg-border bg-bg-tertiary/30 hover:border-accent-blue/30'
          }`}
        >
          <div className="flex items-center justify-between gap-2">
            <span className="min-w-0 truncate text-sm font-medium text-text-primary">
              {displayName(connector)}
            </span>
            <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] ${statusTone(connector)}`}>
              {statusLabel(connector)}
            </span>
          </div>
          <div className="mt-1 flex items-center justify-between gap-2 text-[11px] text-text-secondary">
            <span>{connector.type}</span>
            <span>{hasConfiguredEndpoint(connector) ? 'configured' : 'missing endpoint'}</span>
          </div>
        </button>
      ))}
    </div>
  )
}
