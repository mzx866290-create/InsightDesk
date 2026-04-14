import React, { useEffect } from 'react'
import { Check, Copy, Download, FileText, X } from 'lucide-react'
import type { ChatFile } from '../../api/client'

interface AttachmentPreviewModalProps {
  file: ChatFile
  onClose: () => void
}

export const AttachmentPreviewModal: React.FC<AttachmentPreviewModalProps> = ({
  file,
  onClose,
}) => {
  const [copied, setCopied] = React.useState(false)
  const previewText = (file.extracted_text ?? '').trim()

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose])

  const handleCopy = () => {
    if (!previewText) return
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
        className="relative z-10 flex max-h-[80vh] w-full max-w-2xl flex-col rounded-xl border border-bg-border bg-bg-primary shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start gap-3 border-b border-bg-border px-4 py-3">
          <div className="mt-0.5 rounded-md bg-accent-blue/15 p-1.5">
            <FileText size={14} className="text-accent-blue" />
          </div>

          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="rounded bg-accent-blue/15 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-accent-blue">
                会话附件
              </span>
              {file.size_bytes > 0 && (
                <span className="text-[10px] text-text-secondary/60">
                  {(file.size_bytes / 1024).toFixed(file.size_bytes >= 1024 ? 1 : 0)} KB
                </span>
              )}
            </div>
            <h3 className="mt-1 truncate text-sm font-semibold leading-snug text-text-primary">
              {file.name || '未命名附件'}
            </h3>
            <p className="mt-0.5 text-[11px] text-text-secondary">{file.media_type}</p>
          </div>

          <button
            onClick={onClose}
            className="rounded-md p-1.5 text-text-secondary transition-colors hover:bg-bg-tertiary hover:text-text-primary"
          >
            <X size={14} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-3">
          {previewText ? (
            <div className="group relative">
              <pre className="whitespace-pre-wrap break-words text-xs leading-relaxed text-text-primary/90">
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
            <p className="text-xs italic text-text-secondary/60">该附件暂时没有可预览的文本内容。</p>
          )}
        </div>

        <div className="flex items-center justify-between border-t border-bg-border bg-bg-secondary/30 px-4 py-2">
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
                    <Check size={10} className="text-accent-green" /> 已复制
                  </>
                ) : (
                  <>
                    <Copy size={10} /> 复制内容
                  </>
                )}
              </button>
            )}
            {file.data_url && (
              <a
                href={file.data_url}
                download={file.name}
                className="flex items-center gap-1 text-[11px] text-accent-blue transition-colors hover:text-accent-blue-hover"
              >
                <Download size={10} />
                下载原文件
              </a>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
