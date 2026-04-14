import React, { useEffect } from 'react'
import {
  Check,
  Copy,
  Download,
  ExternalLink,
  FileText,
  Globe,
  Image as ImageIcon,
  Paperclip,
  X,
} from 'lucide-react'
import type { SourceItem } from '../../api/client'

interface DocumentPreviewModalProps {
  source: SourceItem
  onClose: () => void
}

type SourceVisual = {
  badge: string
  badgeClass: string
  iconClass: string
  Icon: typeof FileText
}

function getSourceVisual(source: SourceItem): SourceVisual {
  if (source.type === 'attachment') {
    if (source.attachment_kind === 'image') {
      return {
        badge: '会话图片',
        badgeClass: 'bg-amber-400/15 text-amber-300',
        iconClass: 'bg-amber-400/15 text-amber-300',
        Icon: ImageIcon,
      }
    }
    return {
      badge: '会话附件',
      badgeClass: 'bg-amber-400/15 text-amber-300',
      iconClass: 'bg-amber-400/15 text-amber-300',
      Icon: Paperclip,
    }
  }

  if (source.type === 'web') {
    return {
      badge: '网络来源',
      badgeClass: 'bg-accent-green/15 text-accent-green',
      iconClass: 'bg-accent-green/15 text-accent-green',
      Icon: Globe,
    }
  }

  return {
    badge: '知识库文档',
    badgeClass: 'bg-accent-blue/15 text-accent-blue',
    iconClass: 'bg-accent-blue/15 text-accent-blue',
    Icon: FileText,
  }
}

export const DocumentPreviewModal: React.FC<DocumentPreviewModalProps> = ({ source, onClose }) => {
  const [copied, setCopied] = React.useState(false)
  const visual = getSourceVisual(source)
  const previewText = source.snippet ?? ''
  const previewImage = source.type === 'attachment' && source.attachment_kind === 'image'
    ? source.data_url
    : ''

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose])

  const handleCopy = () => {
    navigator.clipboard.writeText(previewText).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />

      <div
        className="relative z-10 flex max-h-[80vh] w-full max-w-lg flex-col rounded-xl border border-bg-border bg-bg-primary shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex shrink-0 items-start gap-3 border-b border-bg-border px-4 py-3">
          <div className={`mt-0.5 rounded-md p-1.5 ${visual.iconClass}`}>
            <visual.Icon size={14} />
          </div>

          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${visual.badgeClass}`}>
                {visual.badge}
              </span>
              {source.index !== undefined && (
                <span className="text-[10px] text-text-secondary/60">引用 [{source.index}]</span>
              )}
            </div>
            <h3 className="mt-1 truncate text-sm font-semibold leading-snug text-text-primary">
              {source.title}
            </h3>
            {source.media_type && (
              <p className="mt-0.5 truncate text-[11px] text-text-secondary">{source.media_type}</p>
            )}
            {source.url && (
              <a
                href={source.url}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-1 flex items-center gap-1 truncate text-[11px] text-accent-blue hover:underline underline-offset-2"
              >
                <ExternalLink size={10} />
                {source.url}
              </a>
            )}
          </div>

          <button
            onClick={onClose}
            className="shrink-0 rounded-md p-1.5 text-text-secondary transition-colors hover:bg-bg-tertiary hover:text-text-primary"
          >
            <X size={14} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-3">
          {previewImage && (
            <div className="mb-3 overflow-hidden rounded-xl border border-bg-border bg-black/10">
              <img
                src={previewImage}
                alt={source.title}
                className="max-h-[18rem] w-full object-contain"
              />
            </div>
          )}

          {previewText ? (
            <div className="group relative">
              <pre className="whitespace-pre-wrap break-words text-xs font-sans leading-relaxed text-text-primary/90">
                {previewText}
              </pre>
              <button
                onClick={handleCopy}
                className="absolute right-0 top-0 rounded-md bg-bg-tertiary/80 p-1.5 text-text-secondary opacity-0 transition-opacity group-hover:opacity-100 hover:text-text-primary"
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
            <p className="text-xs italic text-text-secondary/60">暂无可预览内容</p>
          )}
        </div>

        <div className="flex shrink-0 items-center justify-between border-t border-bg-border bg-bg-secondary/30 px-4 py-2">
          <span className="text-[10px] text-text-secondary/50">
            {previewText ? `${previewText.length} 字符` : ''}
          </span>

          <div className="flex items-center gap-3">
            {previewText && (
              <button
                onClick={handleCopy}
                className="flex items-center gap-1 text-[11px] text-text-secondary transition-colors hover:text-text-primary"
              >
                {copied ? (
                  <>
                    <Check size={10} className="text-accent-green" />
                    已复制
                  </>
                ) : (
                  <>
                    <Copy size={10} />
                    复制内容
                  </>
                )}
              </button>
            )}

            {source.type === 'attachment' && source.data_url && (
              <a
                href={source.data_url}
                download={source.title}
                className="flex items-center gap-1 text-[11px] text-accent-blue transition-colors hover:text-accent-blue-hover"
              >
                <Download size={10} />
                下载附件
              </a>
            )}

            {source.url && (
              <a
                href={source.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-[11px] text-accent-blue transition-colors hover:text-accent-blue-hover"
              >
                在新标签页打开
                <ExternalLink size={10} />
              </a>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
