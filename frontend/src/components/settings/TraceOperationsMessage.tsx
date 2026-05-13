import React from 'react'

interface TraceOperationsMessageProps {
  error: string | null
  notice: string | null
}

export const TraceOperationsMessage: React.FC<TraceOperationsMessageProps> = ({
  error,
  notice,
}) => {
  const message = error ?? notice
  if (!message) return null

  return (
    <div
      className={`rounded-lg border px-3 py-2 text-xs ${
        error
          ? 'border-accent-red/30 bg-accent-red/10 text-accent-red'
          : 'border-accent-green/30 bg-accent-green/10 text-accent-green'
      }`}
      data-testid="settings-trace-message"
    >
      {message}
    </div>
  )
}
