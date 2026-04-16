import React, { Suspense, useEffect, useState } from 'react'
import {
  Check,
  ChevronLeft,
  ChevronRight,
  Copy,
  Download,
  ExternalLink,
  Layers3,
  X,
} from 'lucide-react'
import { exportArtifact, getDeck } from '../../api/client'
import type { DeckSpec } from '../../api/client'
import { useChatStore } from '../../stores/chatStore'
import { createAndTrackTask, useTaskStore } from '../../stores/taskStore'
import { TaskProgressCard } from '../cards/TaskProgressCard'
import { InlineNotice } from '../ui/InlineNotice'
import { ArtifactMatrix } from './ArtifactMatrix'
import { DeckEditorModal } from './DeckEditorModal'
import { DeckGenerationModal } from './DeckGenerationModal'

interface ReportPreviewModalProps {
  open: boolean
  onClose: () => void
  markdown: string
  title: string
  sessionId: string
  answerGroupId?: string
  panelId?: string
  artifactId?: string
}

const ReportMarkdown = React.lazy(() => import('./ReportMarkdown'))

function parseSlides(markdown: string): string[] {
  const parts = markdown.split(/\n---\n/)
  const slides: string[] = []
  for (const part of parts) {
    const trimmed = part.trim()
    if (!trimmed) continue
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
  answerGroupId,
  panelId,
  artifactId,
}) => {
  const panels = useChatStore((s) => s.panels)
  const knowledgeBaseEnabled = useChatStore((s) => s.knowledgeBaseEnabled)

  const [activeMarkdown, setActiveMarkdown] = useState(markdown)
  const [activeTitle, setActiveTitle] = useState(title)
  const [activeArtifactId, setActiveArtifactId] = useState<string | undefined>(artifactId)
  const [activeAnswerGroupId, setActiveAnswerGroupId] = useState(answerGroupId)
  const [activePanelId, setActivePanelId] = useState(panelId)
  const [currentSlide, setCurrentSlide] = useState(0)
  const [copied, setCopied] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [deckConfigOpen, setDeckConfigOpen] = useState(false)
  const [deckOpen, setDeckOpen] = useState(false)
  const [deckData, setDeckData] = useState<DeckSpec | null>(null)
  const [creatingDeckTask, setCreatingDeckTask] = useState(false)
  const [deckTaskId, setDeckTaskId] = useState<string | null>(null)
  const [handledDeckTaskId, setHandledDeckTaskId] = useState<string | null>(null)

  const deckTask = useTaskStore((s) => (deckTaskId ? s.tasks[deckTaskId] : undefined))

  const slides = parseSlides(activeMarkdown)
  const totalSlides = slides.length
  const effectivePanelId = activePanelId?.trim() || panels[0]?.id || ''
  const canGenerateDeck = Boolean(sessionId.trim()) && panels.length > 0
  const isDeckTaskActive =
    deckTask?.status === 'pending' || deckTask?.status === 'running'

  useEffect(() => {
    setActiveMarkdown(markdown)
    setActiveTitle(title)
    setActiveArtifactId(artifactId)
    setActiveAnswerGroupId(answerGroupId)
    setActivePanelId(panelId)
  }, [answerGroupId, artifactId, markdown, panelId, title])

  useEffect(() => {
    if (!open) return
    setCurrentSlide(0)
    setError(null)
  }, [open, activeMarkdown])

  useEffect(() => {
    if (!deckTaskId || !deckTask || handledDeckTaskId === deckTaskId) return

    if (deckTask.status === 'completed') {
      const nextDeckId =
        typeof deckTask.params?.deck_id === 'string' ? deckTask.params.deck_id : ''
      if (!nextDeckId) {
        setError('Deck 任务已完成，但没有返回可打开的 deck_id。')
        setHandledDeckTaskId(deckTaskId)
        return
      }

      void getDeck(nextDeckId)
        .then((deck) => {
          setDeckData(deck)
          setDeckOpen(true)
          setError(null)
          setHandledDeckTaskId(deckTaskId)
        })
        .catch((taskError) => {
          setError((taskError as Error).message || '打开生成后的 Deck 失败。')
          setHandledDeckTaskId(deckTaskId)
        })
      return
    }

    if (deckTask.status === 'failed') {
      setError(deckTask.error ?? '生成 Deck 失败，请稍后重试。')
      setHandledDeckTaskId(deckTaskId)
    }
  }, [deckTask, deckTaskId, handledDeckTaskId])

  if (!open && !deckConfigOpen && !deckOpen) return null

  const goNext = () => setCurrentSlide((value) => Math.min(value + 1, totalSlides - 1))
  const goPrev = () => setCurrentSlide((value) => Math.max(value - 1, 0))

  const handleCopyMarkdown = () => {
    navigator.clipboard.writeText(activeMarkdown).then(() => {
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2000)
    })
  }

  const handleOpenSlidev = () => {
    navigator.clipboard.writeText(activeMarkdown).catch(() => {})
    window.open('https://sli.dev/new', '_blank', 'noopener,noreferrer')
  }

  const handleDownloadPptx = async () => {
    setDownloading(true)
    setError(null)
    try {
      if (activeArtifactId) {
        const blob = await exportArtifact(activeArtifactId, 'pptx')
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `${activeTitle.slice(0, 40) || 'report'}.pptx`
        a.click()
        URL.revokeObjectURL(url)
        return
      }
      const params = new URLSearchParams()
      if (activeAnswerGroupId?.trim()) params.set('answer_group_id', activeAnswerGroupId.trim())
      if (activePanelId?.trim()) params.set('panel_id', activePanelId.trim())
      const query = params.toString()
      const res = await fetch(`/api/reports/download/${sessionId}${query ? `?${query}` : ''}`)
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }))
        setError(`下载 PPTX 失败：${err.detail ?? res.statusText}`)
        return
      }
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${activeTitle.slice(0, 40) || 'report'}.pptx`
      a.click()
      URL.revokeObjectURL(url)
    } catch (downloadError) {
      setError(`下载 PPTX 失败：${(downloadError as Error).message}`)
    } finally {
      setDownloading(false)
    }
  }

  const handleDownloadMd = () => {
    if (activeArtifactId) {
      void exportArtifact(activeArtifactId, 'md')
        .then((blob) => {
          const url = URL.createObjectURL(blob)
          const a = document.createElement('a')
          a.href = url
          a.download = `${activeTitle.slice(0, 40) || 'report'}.md`
          a.click()
          URL.revokeObjectURL(url)
        })
        .catch((downloadError) => {
          setError((downloadError as Error).message || '下载 Markdown 失败。')
        })
      return
    }
    const blob = new Blob([activeMarkdown], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${activeTitle.slice(0, 40) || 'report'}.md`
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleGenerateDeck = async (payload: {
    panel_config: (typeof panels)[number]['modelConfig']
    target_slide_count: number
    theme: 'default' | 'midnight' | 'sunrise'
  }) => {
    if (!sessionId.trim()) {
      setError('缺少 session_id，暂时无法生成 Deck。')
      return
    }

    setCreatingDeckTask(true)
    setError(null)
    try {
      const task = await createAndTrackTask(
        'generate_deck',
        {
          panel_config: payload.panel_config,
          knowledge_base_enabled: knowledgeBaseEnabled,
          target_slide_count: payload.target_slide_count,
          theme: payload.theme,
          answer_group_id: activeAnswerGroupId?.trim() || undefined,
          panel_id: activePanelId?.trim() || undefined,
        },
        sessionId,
      )
      setDeckTaskId(task.task_id)
      setHandledDeckTaskId(null)
    } catch (taskError) {
      setError((taskError as Error).message || '生成 Deck 失败，请稍后重试。')
    } finally {
      setCreatingDeckTask(false)
    }
  }

  return (
    <>
      {open && (
        <div
          className="fixed inset-0 z-50 flex flex-col overflow-hidden bg-bg-primary/95 backdrop-blur-sm"
          data-testid="report-preview-modal"
        >
          <div className="flex shrink-0 items-start justify-between gap-3 border-b border-bg-border bg-bg-secondary px-4 py-3 sm:px-5">
            <div className="flex min-w-0 items-center gap-3">
              <span className="max-w-[200px] truncate text-sm font-semibold text-text-primary sm:max-w-xs">
                {activeTitle}
              </span>
              <span className="rounded-full bg-bg-tertiary px-2 py-0.5 text-xs text-text-secondary">
                {currentSlide + 1} / {totalSlides}
              </span>
            </div>
            <div className="flex flex-wrap items-center justify-end gap-2">
              <button
                onClick={handleCopyMarkdown}
                className="flex items-center gap-1.5 rounded-lg border border-bg-border px-2.5 py-1.5 text-xs text-text-secondary transition-colors hover:border-accent-blue/40 hover:text-text-primary"
                title="复制 Markdown"
              >
                {copied ? <Check size={12} className="text-accent-green" /> : <Copy size={12} />}
                {copied ? '已复制' : '复制 MD'}
              </button>
              <button
                onClick={handleDownloadMd}
                className="flex items-center gap-1.5 rounded-lg border border-bg-border px-2.5 py-1.5 text-xs text-text-secondary transition-colors hover:border-accent-blue/40 hover:text-text-primary"
                title="下载 Markdown 文件"
              >
                <Download size={12} />
                下载 MD
              </button>
              <button
                onClick={() => setDeckConfigOpen(true)}
                data-testid="report-generate-deck"
                disabled={!canGenerateDeck || creatingDeckTask || isDeckTaskActive}
                className="flex items-center gap-1.5 rounded-lg border border-accent-blue/35 bg-accent-blue/10 px-2.5 py-1.5 text-xs text-accent-blue transition-colors hover:bg-accent-blue/20 disabled:opacity-50"
                title={canGenerateDeck ? '基于当前报告范围生成 Deck 草稿' : '当前没有可用面板'}
              >
                {creatingDeckTask || isDeckTaskActive ? (
                  <span className="h-3 w-3 animate-spin rounded-full border border-current border-t-transparent" />
                ) : (
                  <Layers3 size={12} />
                )}
                {creatingDeckTask || isDeckTaskActive ? '生成中' : '生成 Deck'}
              </button>
              <button
                onClick={handleDownloadPptx}
                data-testid="report-download-pptx"
                disabled={downloading}
                className="flex items-center gap-1.5 rounded-lg border border-accent-blue/40 bg-accent-blue/20 px-2.5 py-1.5 text-xs text-accent-blue transition-colors hover:bg-accent-blue/30 disabled:opacity-50"
                title="下载 PPTX"
              >
                {downloading ? (
                  <span className="h-3 w-3 animate-spin rounded-full border border-current border-t-transparent" />
                ) : (
                  <Download size={12} />
                )}
                下载 PPTX
              </button>
              <button
                onClick={handleOpenSlidev}
                data-testid="report-open-slidev"
                className="flex items-center gap-1.5 rounded-lg border border-bg-border px-2.5 py-1.5 text-xs text-text-secondary transition-colors hover:border-accent-blue/40 hover:text-text-primary"
                title="在 Slidev 中继续编辑"
              >
                <ExternalLink size={12} />
                Slidev 编辑
              </button>
              <button
                onClick={onClose}
                data-testid="report-preview-close"
                className="rounded-lg p-1.5 text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
              >
                <X size={16} />
              </button>
            </div>
          </div>

          {(error || deckTaskId) && (
            <div className="space-y-3 px-4 pt-3 sm:px-5">
              {error && <InlineNotice message={error} tone="error" />}
              {deckTaskId && (
                <TaskProgressCard
                  taskId={deckTaskId}
                  taskType="generate_deck"
                  sessionId={sessionId}
                />
              )}
            </div>
          )}

          <div className="min-h-0 flex-1 px-4 py-4 sm:px-6">
            <div className="mx-auto flex h-full w-full max-w-3xl min-h-0 flex-col gap-4">
              <div className="min-h-0 flex-1 rounded-2xl border border-bg-border bg-bg-secondary shadow-xl">
                <div
                  className="h-full overflow-y-auto p-6 sm:p-8"
                  data-testid="report-preview-content"
                >
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

              <div className="flex shrink-0 items-center justify-between gap-3 rounded-2xl border border-bg-border bg-bg-secondary/95 px-4 py-3">
                <button
                  onClick={goPrev}
                  disabled={currentSlide === 0}
                  className="flex items-center gap-1.5 rounded-xl border border-bg-border px-4 py-2 text-sm text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-30"
                >
                  <ChevronLeft size={16} />
                  上一页
                </button>

                <div className="flex items-center gap-1.5">
                  {slides.slice(0, Math.min(totalSlides, 10)).map((_, index) => (
                    <button
                      key={index}
                      onClick={() => setCurrentSlide(index)}
                      className={`h-2 w-2 rounded-full transition-colors ${
                        index === currentSlide
                          ? 'bg-accent-blue'
                          : 'bg-bg-border hover:bg-text-secondary/30'
                      }`}
                    />
                  ))}
                  {totalSlides > 10 && (
                    <span className="ml-1 text-xs text-text-secondary">+{totalSlides - 10}</span>
                  )}
                </div>

                <button
                  onClick={goNext}
                  disabled={currentSlide === totalSlides - 1}
                  className="flex items-center gap-1.5 rounded-xl border border-bg-border px-4 py-2 text-sm text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-30"
                >
                  下一页
                  <ChevronRight size={16} />
                </button>
              </div>

              <ArtifactMatrix
                sessionId={sessionId}
                activeArtifactId={activeArtifactId}
                onOpenReport={(artifact) => {
                  setActiveArtifactId(artifact.artifactId)
                  setActiveTitle(artifact.title)
                  setActiveMarkdown(artifact.markdown)
                  setActiveAnswerGroupId(artifact.answerGroupId)
                  setActivePanelId(artifact.panelId)
                  setCurrentSlide(0)
                  setError(null)
                }}
                onOpenDeck={(deck) => {
                  setDeckData(deck)
                  setDeckOpen(true)
                  setError(null)
                }}
              />
            </div>
          </div>

          <div className="shrink-0 px-4 pb-3 text-center text-[11px] text-text-secondary/40">
            提示：打开 Slidev 时会先把 Markdown 复制到剪贴板，方便你直接粘贴继续编辑。
          </div>
        </div>
      )}

      <DeckGenerationModal
        open={deckConfigOpen}
        onClose={() => setDeckConfigOpen(false)}
        panels={panels}
        knowledgeBaseEnabled={knowledgeBaseEnabled}
        initialPanelId={effectivePanelId}
        onSubmit={handleGenerateDeck}
      />

      {deckData && (
        <DeckEditorModal
          open={deckOpen}
          onClose={() => setDeckOpen(false)}
          deck={deckData}
          panels={panels}
          onDeckChange={setDeckData}
        />
      )}
    </>
  )
}
