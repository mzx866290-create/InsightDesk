import React, { Suspense, useEffect, useState } from 'react'
import { ChevronLeft, ChevronRight, Download, ExternalLink, Copy, Check, X } from 'lucide-react'

interface ReportPreviewModalProps {
  open: boolean
  onClose: () => void
  markdown: string
  title: string
  sessionId: string
}

const ReportMarkdown = React.lazy(() => import('./ReportMarkdown'))

function parseSlides(markdown: string): string[] {
  // Split on Slidev slide separator (--- on its own line)
  // but keep the frontmatter block intact
  const parts = markdown.split(/\n---\n/)
  // First part may be frontmatter, skip if it starts with "---"
  const slides: string[] = []
  for (const part of parts) {
    const trimmed = part.trim()
    if (!trimmed) continue
    // Skip pure frontmatter (has key: value lines at top, no heading)
    if (slides.length === 0 && /^(theme|title|class):/m.test(trimmed) && !trimmed.startsWith('#')) {
      continue
    }
    slides.push(trimmed)
  }
  return slides.length > 0 ? slides : [markdown]
}

export const ReportPreviewModal: React.FC<ReportPreviewModalProps> = ({
  open,
  onClose,
  markdown,
  title,
  sessionId,
}) => {
  const [currentSlide, setCurrentSlide] = useState(0)
  const [copied, setCopied] = useState(false)
  const [downloading, setDownloading] = useState(false)

  if (!open) return null

  const slides = parseSlides(markdown)
  const totalSlides = slides.length

  useEffect(() => {
    if (open) {
      setCurrentSlide(0)
    }
  }, [open, markdown])

  const goNext = () => setCurrentSlide((s) => Math.min(s + 1, totalSlides - 1))
  const goPrev = () => setCurrentSlide((s) => Math.max(s - 1, 0))

  const handleCopyMarkdown = () => {
    navigator.clipboard.writeText(markdown).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  const handleOpenSlidev = () => {
    // Copy markdown to clipboard and open Slidev
    navigator.clipboard.writeText(markdown).catch(() => {})
    window.open('https://sli.dev/new', '_blank', 'noopener,noreferrer')
  }

  const handleDownloadPptx = async () => {
    setDownloading(true)
    try {
      const res = await fetch(`/api/reports/download/${sessionId}`)
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }))
        alert('下载失败: ' + (err.detail ?? res.statusText))
        return
      }
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${title.slice(0, 40) || '报告'}.pptx`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      alert('下载失败: ' + (e as Error).message)
    } finally {
      setDownloading(false)
    }
  }

  const handleDownloadMd = () => {
    const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${title.slice(0, 40) || '报告'}.md`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="fixed inset-0 z-50 flex flex-col overflow-hidden bg-bg-primary/95 backdrop-blur-sm">
      {/* Top bar */}
      <div className="flex items-start justify-between gap-3 px-4 py-3 border-b border-bg-border bg-bg-secondary shrink-0 sm:px-5">
        <div className="flex min-w-0 items-center gap-3">
          <span className="text-sm font-semibold text-text-primary truncate max-w-[200px] sm:max-w-xs">
            {title}
          </span>
          <span className="text-xs text-text-secondary bg-bg-tertiary px-2 py-0.5 rounded-full">
            {currentSlide + 1} / {totalSlides}
          </span>
        </div>
        <div className="flex items-center gap-2 flex-wrap justify-end">
          <button
            onClick={handleCopyMarkdown}
            className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-lg border border-bg-border text-text-secondary hover:text-text-primary hover:border-accent-blue/40 transition-colors"
            title="复制 Markdown"
          >
            {copied ? <Check size={12} className="text-accent-green" /> : <Copy size={12} />}
            {copied ? '已复制' : '复制 MD'}
          </button>
          <button
            onClick={handleDownloadMd}
            className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-lg border border-bg-border text-text-secondary hover:text-text-primary hover:border-accent-blue/40 transition-colors"
            title="下载 Markdown 文件"
          >
            <Download size={12} />
            下载 MD
          </button>
          <button
            onClick={handleDownloadPptx}
            disabled={downloading}
            className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-lg bg-accent-blue/20 border border-accent-blue/40 text-accent-blue hover:bg-accent-blue/30 transition-colors disabled:opacity-50"
            title="下载 PPTX"
          >
            {downloading ? (
              <span className="w-3 h-3 border border-current border-t-transparent rounded-full animate-spin" />
            ) : (
              <Download size={12} />
            )}
            下载 PPTX
          </button>
          <button
            onClick={handleOpenSlidev}
            className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-lg border border-bg-border text-text-secondary hover:text-text-primary hover:border-accent-blue/40 transition-colors"
            title="在 Slidev 中编辑（会将 Markdown 复制到剪贴板）"
          >
            <ExternalLink size={12} />
            Slidev 编辑
          </button>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-text-secondary hover:text-text-primary hover:bg-bg-hover transition-colors"
          >
            <X size={16} />
          </button>
        </div>
      </div>

      {/* Slide preview */}
      <div className="flex-1 min-h-0 px-4 py-4 sm:px-6">
        <div className="w-full max-w-3xl h-full mx-auto flex min-h-0 flex-col gap-4">
          {/* Slide card */}
          <div className="flex-1 min-h-0 rounded-2xl border border-bg-border bg-bg-secondary shadow-xl">
            <div className="h-full overflow-y-auto p-6 sm:p-8">
              <div className="prose prose-invert prose-sm max-w-none">
                <Suspense
                  fallback={
                    <pre className="whitespace-pre-wrap break-words text-sm leading-6 text-text-primary">
                      {slides[currentSlide] ?? ''}
                    </pre>
                  }
                >
                  <ReportMarkdown content={slides[currentSlide] ?? ''} />
                </Suspense>
              </div>
            </div>
          </div>

          {/* Navigation */}
          <div className="flex shrink-0 items-center justify-between gap-3 rounded-2xl border border-bg-border bg-bg-secondary/95 px-4 py-3">
            <button
              onClick={goPrev}
              disabled={currentSlide === 0}
              className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm border border-bg-border text-text-secondary hover:text-text-primary hover:bg-bg-hover disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronLeft size={16} />
              上一页
            </button>

            {/* Dot indicators */}
            <div className="flex items-center gap-1.5">
              {slides.slice(0, Math.min(totalSlides, 10)).map((_, i) => (
                <button
                  key={i}
                  onClick={() => setCurrentSlide(i)}
                  className={`w-2 h-2 rounded-full transition-colors ${
                    i === currentSlide ? 'bg-accent-blue' : 'bg-bg-border hover:bg-text-secondary/30'
                  }`}
                />
              ))}
              {totalSlides > 10 && (
                <span className="text-xs text-text-secondary ml-1">+{totalSlides - 10}</span>
              )}
            </div>

            <button
              onClick={goNext}
              disabled={currentSlide === totalSlides - 1}
              className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm border border-bg-border text-text-secondary hover:text-text-primary hover:bg-bg-hover disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              下一页
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
      </div>

      {/* Keyboard hint */}
      <div className="shrink-0 px-4 pb-3 text-center text-[11px] text-text-secondary/40">
        提示：在 Slidev 编辑 会将 Markdown 复制到剪贴板，然后粘贴到 Slidev 编辑器即可
      </div>
    </div>
  )
}
