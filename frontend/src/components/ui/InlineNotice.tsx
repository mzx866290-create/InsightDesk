import React from 'react'
import { AlertCircle, CheckCircle2, Info } from 'lucide-react'

interface InlineNoticeProps {
  message: string
  tone?: 'error' | 'success' | 'info'
}

export const InlineNotice: React.FC<InlineNoticeProps> = ({
  message,
  tone = 'info',
}) => {
  const palette = {
    error: {
      icon: <AlertCircle size={14} className="shrink-0 text-accent-red" />,
      className: 'border-accent-red/30 bg-accent-red/10 text-accent-red',
    },
    success: {
      icon: <CheckCircle2 size={14} className="shrink-0 text-accent-green" />,
      className: 'border-accent-green/30 bg-accent-green/10 text-accent-green',
    },
    info: {
      icon: <Info size={14} className="shrink-0 text-accent-blue" />,
      className: 'border-accent-blue/30 bg-accent-blue/10 text-accent-blue',
    },
  }[tone]

  return (
    <div className={`rounded-xl border px-3 py-2 text-xs ${palette.className}`}>
      <div className="flex items-start gap-2">
        {palette.icon}
        <span className="leading-5">{message}</span>
      </div>
    </div>
  )
}
