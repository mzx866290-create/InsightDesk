import React from 'react'

export interface SecurityAuditKpiItemProps {
  label: string
  value: string | number
  tone?: 'default' | 'green' | 'red'
}

export const SecurityAuditKpiItem: React.FC<SecurityAuditKpiItemProps> = ({
  label,
  value,
  tone = 'default',
}) => {
  const valueTone = {
    default: 'text-text-primary',
    green: 'text-accent-green',
    red: 'text-accent-red',
  }[tone]

  return (
    <div className="min-w-0 rounded-md border border-bg-border bg-bg-primary/30 px-3 py-2">
      <p className="truncate text-[11px] text-text-secondary">{label}</p>
      <p className={`mt-1 truncate text-base font-semibold ${valueTone}`}>{value}</p>
    </div>
  )
}
