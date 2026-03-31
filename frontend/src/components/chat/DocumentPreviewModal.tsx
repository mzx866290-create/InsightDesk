import React, { useEffect } from 'react'
import { X, FileText, Globe, ExternalLink, Copy, Check } from 'lucide-react'
import type { SourceItem } from '../../api/client'

interface DocumentPreviewModalProps {
  source: SourceItem
  onClose: () => void
}

export const DocumentPreviewModal: React.FC<DocumentPreviewModalProps> = ({ source, onClose }) => {
  const [copied, setCopied] = React.useState(false)

  // Close on Escape key
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose])

  const handleCopy = () => {
    navigator.clipboard.writeText(source.snippet ?? '').then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  const isDoc = source.type === 'doc'
  const accentColor = isDoc ? 'accent-blue' : 'accent-green'

  return (
    /* Backdrop */
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />

      {/* Modal card */}
      <div
        className="relative z-10 w-full max-w-lg rounded-xl border border-bg-border bg-bg-primary shadow-2xl flex flex-col max-h-[80vh]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start gap-3 px-4 py-3 border-b border-bg-border shrink-0">
          <div className={`p-1.5 rounded-md bg-${accentColor}/15 shrink-0 mt-0.5`}>
            {isDoc ? (
              <FileText size={14} className={`text-${accentColor}`} />
            ) : (
              <Globe size={14} className={`text-${accentColor}`} />
            )}
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span
                className={`text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded bg-${accentColor}/15 text-${accentColor}`}
              >
                {isDoc ? '知识库文档' : '网络来源'}
              </span>
              {source.index !== undefined && (
                <span className="text-[10px] text-text-secondary/60">引用 [{source.index}]</span>
              )}
            </div>
            <h3 className="mt-1 text-sm font-semibold text-text-primary leading-snug truncate">
              {source.title}
            </h3>
            {source.url && (
              <a
                href={source.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 mt-0.5 text-[11px] text-accent-blue hover:underline underline-offset-2 truncate"
              >
                <ExternalLink size={10} />
                {source.url}
              </a>
            )}
          </div>

          <button
            onClick={onClose}
            className="shrink-0 p-1.5 rounded-md text-text-secondary hover:text-text-primary hover:bg-bg-tertiary transition-colors"
          >
            <X size={14} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-4 py-3">
          {source.snippet ? (
            <div className="relative group">
              <pre className="whitespace-pre-wrap break-words text-xs text-text-primary/90 leading-relaxed font-sans">
                {source.snippet}
              </pre>
              <button
                onClick={handleCopy}
                className="absolute top-0 right-0 p-1.5 rounded-md bg-bg-tertiary/80 text-text-secondary hover:text-text-primary opacity-0 group-hover:opacity-100 transition-opacity"
                title="复制内容"
              >
                {copied ? (
                  <Check size={11} className="text-accent-green" />
                ) : (
                  <Copy size={11} />
                )}
              </button>
            </div>
          ) : (
            <p className="text-xs text-text-secondary/60 italic">暂无内容摘要</p>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-4 py-2 border-t border-bg-border shrink-0 bg-bg-secondary/30">
          <span className="text-[10px] text-text-secondary/50">
            {source.snippet ? `${source.snippet.length} 字符` : ''}
          </span>
          {source.url && (
            <a
              href={source.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 text-[11px] text-accent-blue hover:text-accent-blue-hover transition-colors"
            >
              在新标签页打开
              <ExternalLink size={10} />
            </a>
          )}
          {!source.url && (
            <button
              onClick={handleCopy}
              className="flex items-center gap-1 text-[11px] text-text-secondary hover:text-text-primary transition-colors"
            >
              {copied ? (
                <><Check size={10} className="text-accent-green" /> 已复制</>
              ) : (
                <><Copy size={10} /> 复制内容</>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
