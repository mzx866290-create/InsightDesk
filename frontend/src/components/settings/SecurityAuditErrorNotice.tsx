import React from 'react'
import { AlertTriangle } from 'lucide-react'

export interface SecurityAuditErrorNoticeProps {
  testId: string
  message: string
}

export const SecurityAuditErrorNotice: React.FC<SecurityAuditErrorNoticeProps> = ({ testId, message }) => (
  <div
    className="flex items-start gap-2 rounded-lg border border-accent-red/30 bg-accent-red/10 px-3 py-2 text-xs text-accent-red"
    data-testid={testId}
  >
    <AlertTriangle size={13} className="mt-0.5 shrink-0" />
    <span>{message}</span>
  </div>
)
