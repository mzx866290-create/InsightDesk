import React from 'react'
import { Trash2 } from 'lucide-react'

import { Button } from '../ui/Button'
import type { ConnectorDraft } from './integratorConnectorModel'
import { connectorIdentifier } from './integratorConnectorModel'

export interface IntegratorConnectorDetailsPanelProps {
  connector: ConnectorDraft | null
  selectedIndex: number
  supportedTypes: string[]
  loading: boolean
  children?: React.ReactNode
  onUpdateConnector: (index: number, patch: Partial<ConnectorDraft>) => void
  onRemoveConnector: (index: number) => void
}

export const IntegratorConnectorDetailsPanel: React.FC<IntegratorConnectorDetailsPanelProps> = ({
  connector,
  selectedIndex,
  supportedTypes,
  loading,
  children,
  onUpdateConnector,
  onRemoveConnector,
}) => {
  if (!connector) {
    return (
      <div className="rounded-lg border border-bg-border bg-bg-tertiary/20 p-3">
        <div className="flex min-h-[16rem] items-center justify-center text-xs text-text-secondary">
          {loading ? 'Loading connectors...' : 'No connector selected'}
        </div>
      </div>
    )
  }

  const connectorId = connectorIdentifier(connector)

  return (
    <div className="rounded-lg border border-bg-border bg-bg-tertiary/20 p-3">
      <div
        className="space-y-3"
        data-testid="settings-integrator-connector-details"
        data-connector-id={connectorId}
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <h4 className="text-sm font-medium text-text-primary">Connector details</h4>
            <p className="mt-1 text-xs text-text-secondary">Sensitive values remain redacted after save.</p>
          </div>
          <Button
            variant="danger"
            size="sm"
            onClick={() => onRemoveConnector(selectedIndex)}
            data-testid="settings-integrator-remove"
            data-connector-id={connectorId}
          >
            <Trash2 size={12} />
            Remove
          </Button>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <label className="space-y-1 text-xs text-text-secondary">
            Name
            <input
              className="input-base h-9 w-full"
              value={connector.name ?? ''}
              onChange={(event) => onUpdateConnector(selectedIndex, { name: event.target.value })}
              data-testid="settings-integrator-name"
            />
          </label>

          <label className="space-y-1 text-xs text-text-secondary">
            Type
            <select
              className="input-base h-9 w-full"
              value={connector.type}
              onChange={(event) => onUpdateConnector(selectedIndex, { type: event.target.value })}
              data-testid="settings-integrator-type"
            >
              {supportedTypes.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </select>
          </label>

          <label className="space-y-1 text-xs text-text-secondary sm:col-span-2">
            Description
            <input
              className="input-base h-9 w-full"
              value={connector.description ?? ''}
              onChange={(event) => onUpdateConnector(selectedIndex, { description: event.target.value })}
            />
          </label>

          <label className="flex items-center gap-2 text-xs text-text-secondary">
            <input
              type="checkbox"
              checked={connector.enabled}
              onChange={(event) => onUpdateConnector(selectedIndex, { enabled: event.target.checked })}
              data-testid="settings-integrator-enabled"
            />
            <span>Enabled</span>
          </label>

          <label className="flex items-center gap-2 text-xs text-text-secondary">
            <input
              type="checkbox"
              checked={connector.approved}
              onChange={(event) => onUpdateConnector(selectedIndex, { approved: event.target.checked })}
              data-testid="settings-integrator-approved"
            />
            <span>Approved for execution</span>
          </label>
        </div>

        <label className="space-y-1 text-xs text-text-secondary">
          Settings JSON
          <textarea
            className="input-base min-h-[12rem] w-full resize-y font-mono text-xs leading-5"
            value={connector.settingsJson}
            onChange={(event) => onUpdateConnector(selectedIndex, { settingsJson: event.target.value })}
            spellCheck={false}
            data-testid="settings-integrator-settings-json"
          />
        </label>

        {children ? <>{children}</> : null}
      </div>
    </div>
  )
}
