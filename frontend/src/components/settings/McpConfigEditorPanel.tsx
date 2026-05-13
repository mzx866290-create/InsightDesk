import React from 'react'
import { CheckCircle } from 'lucide-react'

import type { McpConfigResponse } from '../../api/client'
import { Button } from '../ui/Button'

interface McpConfigEditorPanelProps {
  config: McpConfigResponse | null
  value: string
  loading: boolean
  saving: boolean
  onValueChange: (value: string) => void
  onSave: () => void
}

export const McpConfigEditorPanel: React.FC<McpConfigEditorPanelProps> = ({
  config,
  value,
  loading,
  saving,
  onValueChange,
  onSave,
}) => (
  <div
    className="space-y-2 rounded-lg border border-bg-border bg-bg-tertiary/30 p-3"
    data-testid="settings-mcp-config-panel"
  >
    <div className="flex flex-wrap items-center justify-between gap-2">
      <div className="flex flex-wrap items-center gap-2 text-[11px] text-text-secondary">
        <span className="font-medium uppercase tracking-wide">Config</span>
        <span>{config?.persistence.enabled ? config.persistence.config_key : '-'}</span>
        {config?.sensitive_fields_redacted && <span>redacted</span>}
      </div>
      <Button
        variant="ghost"
        size="sm"
        onClick={onSave}
        loading={saving}
        disabled={loading || saving || !value.trim()}
        data-testid="settings-mcp-config-save"
      >
        <CheckCircle size={12} />
        Save
      </Button>
    </div>
    <textarea
      value={value}
      onChange={(event) => onValueChange(event.target.value)}
      spellCheck={false}
      disabled={loading || saving}
      className="h-44 w-full resize-y rounded-md border border-bg-border bg-bg-primary px-3 py-2 font-mono text-xs leading-relaxed text-text-primary outline-none transition focus:border-accent-blue disabled:cursor-not-allowed disabled:opacity-70"
      data-testid="settings-mcp-config-editor"
    />
  </div>
)
