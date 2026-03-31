import React, { useState } from 'react'
import { AlertTriangle, ChevronDown, ChevronUp, RefreshCw, Eraser, Settings } from 'lucide-react'

interface ErrorBannerProps {
  content: string
  errorCode?: string
  suggestion?: string
  onRetry?: () => void
  onClearContext?: () => void
  onOpenSettings?: () => void
}

export const ErrorBanner: React.FC<ErrorBannerProps> = ({
  content,
  errorCode,
  suggestion,
  onRetry,
  onClearContext,
  onOpenSettings,
}) => {
  const [expanded, setExpanded] = useState(false)

  const showSettingsAction =
    errorCode === 'AUTH_FAILED' || errorCode === 'MODEL_NOT_FOUND'
  const showClearAction =
    errorCode === 'INTERNAL_ERROR' || errorCode === 'TIMEOUT' || !errorCode

  return (
    <div className="flex justify-start mb-4 animate-fade-in">
      <div className="max-w-[95%] w-full bg-accent-red/10 border border-accent-red/30 rounded-xl px-4 py-3">
        {/* Header row */}
        <div className="flex items-start gap-2.5">
          <AlertTriangle size={15} className="text-accent-red shrink-0 mt-0.5" />
          <div className="flex-1 min-w-0">
            <p className="text-sm text-accent-red font-medium leading-snug">{content}</p>
            {suggestion && (
              <p className="text-xs text-text-secondary mt-1 leading-relaxed">{suggestion}</p>
            )}
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2 mt-3 flex-wrap">
          {onRetry && (
            <button
              onClick={onRetry}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs bg-accent-red/10 text-accent-red hover:bg-accent-red/20 transition-colors border border-accent-red/20"
            >
              <RefreshCw size={11} />
              重试
            </button>
          )}
          {showClearAction && onClearContext && (
            <button
              onClick={onClearContext}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs text-text-secondary hover:text-text-primary hover:bg-bg-hover transition-colors border border-bg-border"
            >
              <Eraser size={11} />
              清除上下文
            </button>
          )}
          {showSettingsAction && onOpenSettings && (
            <button
              onClick={onOpenSettings}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs text-text-secondary hover:text-text-primary hover:bg-bg-hover transition-colors border border-bg-border"
            >
              <Settings size={11} />
              打开设置
            </button>
          )}
          {errorCode && (
            <button
              onClick={() => setExpanded((v) => !v)}
              className="flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] text-text-secondary/50 hover:text-text-secondary transition-colors ml-auto"
            >
              {expanded ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
              技术详情
            </button>
          )}
        </div>

        {/* Collapsible technical details */}
        {expanded && errorCode && (
          <div className="mt-2.5 px-3 py-2 bg-bg-tertiary rounded-lg border border-bg-border">
            <p className="text-[10px] text-text-secondary font-mono">错误码: {errorCode}</p>
          </div>
        )}
      </div>
    </div>
  )
}
