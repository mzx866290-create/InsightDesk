import React from 'react'
import { RefreshCw, ShieldCheck } from 'lucide-react'

import type { SecurityAuditSummaryCategory } from '../../api/client'
import { Button } from '../ui/Button'
import {
  SECURITY_AUDIT_CATEGORY_OPTIONS,
  SECURITY_AUDIT_LIMIT_OPTIONS,
} from './securityAuditSummaryModel'

export interface SecurityAuditToolbarProps {
  category: SecurityAuditSummaryCategory
  limit: number
  loading: boolean
  onCategoryChange: (category: SecurityAuditSummaryCategory) => void
  onLimitChange: (limit: number) => void
  onRefresh: () => void
}

export const SecurityAuditToolbar: React.FC<SecurityAuditToolbarProps> = ({
  category,
  limit,
  loading,
  onCategoryChange,
  onLimitChange,
  onRefresh,
}) => (
  <div className="flex flex-wrap items-center justify-between gap-3">
    <h3 className="flex items-center gap-2 text-sm font-medium text-text-primary">
      <ShieldCheck size={14} className="text-accent-blue" />
      Security audit
    </h3>
    <div className="flex flex-wrap items-center gap-2">
      <select
        className="input-base py-1 text-xs"
        value={category}
        onChange={(event) => onCategoryChange(event.target.value as SecurityAuditSummaryCategory)}
        data-testid="settings-security-audit-category"
      >
        {SECURITY_AUDIT_CATEGORY_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <select
        className="input-base py-1 text-xs"
        value={limit}
        onChange={(event) => onLimitChange(Number(event.target.value))}
        data-testid="settings-security-audit-limit"
      >
        {SECURITY_AUDIT_LIMIT_OPTIONS.map((option) => (
          <option key={option} value={option}>
            Last {option}
          </option>
        ))}
      </select>
      <Button
        variant="ghost"
        size="sm"
        onClick={onRefresh}
        loading={loading}
        data-testid="settings-security-audit-refresh"
      >
        <RefreshCw size={12} />
        Refresh
      </Button>
    </div>
  </div>
)
