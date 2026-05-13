import React from 'react'
import { CheckCircle, PlugZap, RefreshCw, Save, Zap } from 'lucide-react'

import { Button } from '../ui/Button'

export interface IntegratorConnectorsToolbarPanelProps {
  totalCount: number
  configuredCount: number
  approvedCount: number
  storeLabel: string
  selectedConnectorId: string
  notice: string | null
  error: string | null
  loading: boolean
  saving: boolean
  testing: boolean
  testDisabled: boolean
  onRefresh: () => void
  onSave: () => void
  onTest: () => void
}

export const IntegratorConnectorsToolbarPanel: React.FC<IntegratorConnectorsToolbarPanelProps> = ({
  totalCount,
  configuredCount,
  approvedCount,
  storeLabel,
  selectedConnectorId,
  notice,
  error,
  loading,
  saving,
  testing,
  testDisabled,
  onRefresh,
  onSave,
  onTest,
}) => {
  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="flex items-center gap-2 text-sm font-medium text-text-primary">
          <PlugZap size={14} className="text-accent-blue" />
          Integration connectors
        </h3>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={onRefresh}
            loading={loading}
            data-testid="settings-integrators-refresh"
          >
            <RefreshCw size={12} />
            Refresh
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={onSave}
            loading={saving}
            data-testid="settings-integrators-save"
          >
            <Save size={12} />
            Save
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={onTest}
            loading={testing}
            disabled={testDisabled}
            data-testid="settings-integrator-test"
            data-connector-id={selectedConnectorId}
          >
            <Zap size={12} />
            Test
          </Button>
        </div>
      </div>

      <div className="grid gap-2 rounded-lg border border-bg-border bg-bg-tertiary/30 px-3 py-2 text-xs text-text-secondary sm:grid-cols-4">
        <span>Total: <b className="text-text-primary">{totalCount}</b></span>
        <span>Configured: <b className="text-text-primary">{configuredCount}</b></span>
        <span>Approved: <b className="text-text-primary">{approvedCount}</b></span>
        <span>Store: <b className="text-text-primary">{storeLabel}</b></span>
      </div>

      {notice && (
        <div className="flex items-center gap-2 rounded-lg border border-accent-green/30 bg-accent-green/10 px-3 py-2 text-xs text-accent-green">
          <CheckCircle size={13} />
          {notice}
        </div>
      )}

      {error && (
        <div
          className="rounded-lg border border-accent-red/30 bg-accent-red/10 px-3 py-2 text-xs text-accent-red"
          data-testid="settings-integrator-error"
        >
          {error}
        </div>
      )}
    </>
  )
}
