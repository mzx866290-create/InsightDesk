import React from 'react'

import { Button } from '../ui/Button'

interface AdminTokenPanelProps {
  token: string
  saved: boolean
  error?: string | null
  description: string
  onTokenChange: (value: string) => void
  onSave: () => void
  onClear: () => void
  title?: string
  placeholder?: string
  statusText?: string | null
}

export const AdminTokenPanel: React.FC<AdminTokenPanelProps> = ({
  token,
  saved,
  error,
  description,
  onTokenChange,
  onSave,
  onClear,
  title = 'Remote API Token',
  placeholder = 'Enter API token',
  statusText = null,
}) => {
  const configured = token.trim().length > 0

  return (
    <div className="rounded-xl border border-bg-border bg-bg-tertiary/30 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-text-primary">{title}</h3>
          <p className="mt-1 text-xs leading-5 text-text-secondary">{description}</p>
        </div>
        <span className={`rounded-full px-2 py-1 text-[11px] ${
          configured
            ? 'bg-accent-green/10 text-accent-green'
            : 'bg-bg-secondary text-text-secondary'
        }`}>
          {configured ? 'Configured' : 'Not Set'}
        </span>
      </div>

      <div className="mt-4 flex gap-2">
        <input
          className="input-base flex-1 text-sm"
          type="password"
          placeholder={placeholder}
          value={token}
          onChange={(e) => onTokenChange(e.target.value)}
        />
        <Button variant="primary" onClick={onSave}>
          {saved ? 'Saved' : 'Save Token'}
        </Button>
        <Button variant="ghost" onClick={onClear}>
          Clear
        </Button>
      </div>

      <div className="mt-2 space-y-1">
        <p className="text-[11px] text-text-secondary">
          The token stays only in this browser's local storage and is not written back to server-side config.
        </p>
        {statusText && (
          <p className="text-[11px] text-accent-blue">
            Current identity: {statusText}
          </p>
        )}
      </div>

      {error && (
        <div className="mt-3 rounded-lg border border-accent-red/30 bg-accent-red/10 px-3 py-2 text-xs text-accent-red">
          {error}
        </div>
      )}
    </div>
  )
}
