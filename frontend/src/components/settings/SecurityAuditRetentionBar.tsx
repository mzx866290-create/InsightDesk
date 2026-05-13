import React from 'react'
import { Search, Trash2 } from 'lucide-react'

import type { SecurityAuditCleanupResponse } from '../../api/client'
import { Button } from '../ui/Button'
import { formatRetentionCount } from './securityAuditSummaryModel'

export interface SecurityAuditRetentionBarProps {
  keepLatest: string
  loading: 'preview' | 'cleanup' | null
  result: SecurityAuditCleanupResponse | null
  error: string | null
  onKeepLatestChange: (value: string) => void
  onPreview: () => void
  onCleanup: () => void | Promise<void>
}

export const SecurityAuditRetentionBar: React.FC<SecurityAuditRetentionBarProps> = ({
  keepLatest,
  loading,
  result,
  error,
  onKeepLatestChange,
  onPreview,
  onCleanup,
}) => {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-bg-border bg-bg-primary/30 px-3 py-2">
      <div className="flex flex-wrap items-center gap-2 text-xs text-text-secondary">
        <span className="font-medium text-text-primary">Retention</span>
        <input
          className="input-base w-28 py-1 text-xs"
          type="number"
          min={0}
          step={1}
          value={keepLatest}
          onChange={(event) => onKeepLatestChange(event.target.value)}
          data-testid="settings-security-audit-retention-keep-latest"
        />
        <span>keep latest events</span>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Button
          variant="ghost"
          size="sm"
          onClick={onPreview}
          loading={loading === 'preview'}
          data-testid="settings-security-audit-retention-preview"
        >
          <Search size={12} />
          Preview
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => void onCleanup()}
          loading={loading === 'cleanup'}
          data-testid="settings-security-audit-retention-cleanup"
        >
          <Trash2 size={12} />
          Cleanup
        </Button>
      </div>
      {(result || error) && (
        <div
          className={`basis-full rounded-md border px-3 py-2 text-xs ${
            error
              ? 'border-accent-red/30 bg-accent-red/10 text-accent-red'
              : 'border-bg-border bg-bg-tertiary/40 text-text-secondary'
          }`}
          data-testid={
            error
              ? 'settings-security-audit-retention-error'
              : 'settings-security-audit-retention-result'
          }
        >
          {error ? (
            <span>{error}</span>
          ) : result ? (
            <span>
              {result.dry_run ? 'Would delete' : 'Deleted'}{' '}
              {formatRetentionCount(result.would_delete_count ?? result.deleted_count)}
              {' '}events, remaining {formatRetentionCount(result.remaining_count)}
              {' '}with keep latest {formatRetentionCount(result.keep_latest)}.
            </span>
          ) : null}
        </div>
      )}
    </div>
  )
}
