import React, { useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  Check,
  ChevronLeft,
  ChevronRight,
  Download,
  RefreshCw,
  Save,
  Share2,
  Trash2,
  X,
} from 'lucide-react'
import {
  createDeckShareLink,
  exportDeck,
  regenerateDeckSlide,
  updateDeck,
  updateDeckBlockRefs,
} from '../../api/client'
import type {
  DeckBlock,
  DeckCitationValidation,
  DeckEvidenceCoverage,
  DeckEvidenceReview,
  DeckEvidenceReviewActionItem,
  DeckSlide,
  DeckSpec,
  ModelConfig,
} from '../../api/client'
import { EChartsRenderer, type ChartData } from '../charts/EChartsRenderer'
import { buildDeckDownloadFilename, buildDeckMarkdown, buildDeckPrintHtml } from './deckMarkdown'

interface DeckEditorModalProps {
  open: boolean
  onClose: () => void
  deck: DeckSpec
  panels: Array<{ id: string; modelConfig: ModelConfig }>
  onDeckChange: (deck: DeckSpec) => void
}


import { DECK_THEMES, SLIDE_TYPE_LABELS, SLIDE_LAYOUT_LABELS, BLOCK_KIND_LABELS, BLOCK_ROLE_LABELS, EVIDENCE_COVERAGE_EXCLUDED_SLIDE_TYPES, cloneDeck, blockValue, updateBlockValue, createEditableBlock, isSlideManuallyConfirmed, slideNeedsAttention, qualityBadgeClass, qualityLabel, sourceModeLabel, deckThemeLabel, slideTypeLabel, slideLayoutLabel, blockKindLabel, blockRoleLabel, previewShellClass, previewEyebrowClass, previewCardClass, isEvidenceCoverableSlide, buildFallbackDeckEvidenceCoverage, resolveDeckEvidenceCoverage, uniqueStrings, buildFallbackDeckEvidenceReview, resolveDeckEvidenceReview, formatCoveragePercent, evidenceReviewStatusLabel, resolveDeckCitationValidation, citationValidationLabel, citationValidationClass, DeckBlockEvidenceBinding, DeckExportGateDecision, buildDeckExportGateIssues, blockEvidenceRefIds, buildBlockEvidenceBindings } from './deckEditorModel'

function renderBlock(block: DeckBlock) {
  if (block.kind === 'chart') {
    const chartType = block.content.chart_type
    const labels = block.content.labels ?? []
    const datasets = block.content.datasets ?? []
    const chartData: ChartData | null =
      (chartType === 'bar' || chartType === 'line' || chartType === 'pie') &&
      labels.length > 0 &&
      datasets.length > 0
        ? {
            type: chartType,
            labels,
            datasets,
          }
        : null

    return (
      <div className="space-y-3">
        <div>
          <p className="text-sm font-medium text-text-primary">{block.content.title ?? 'Chart'}</p>
          {block.content.description && (
            <p className="mt-1 text-xs leading-5 text-text-secondary">{block.content.description}</p>
          )}
        </div>
        {chartData ? (
          <EChartsRenderer chartData={chartData} height={220} />
        ) : (
          <p className="text-xs leading-5 text-text-secondary">Chart data is incomplete, so preview is unavailable.</p>
        )}
      </div>
    )
  }

  if (block.kind === 'bullet_list') {
    const items = block.content.items ?? []
    return (
      <ul className="list-disc space-y-2 pl-5 text-sm leading-6">
        {items.map((item, index) => (
          <li key={`${block.id}-${index}`}>{item}</li>
        ))}
      </ul>
    )
  }

  return <p className="whitespace-pre-wrap text-sm leading-6">{block.content.text ?? ''}</p>
}


export const DeckEditorModal: React.FC<DeckEditorModalProps> = ({
  open,
  onClose,
  deck,
  panels,
  onDeckChange,
}) => {
  const [workingDeck, setWorkingDeck] = useState<DeckSpec>(deck)
  const [currentSlide, setCurrentSlide] = useState(0)
  const [saving, setSaving] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [exportingPdf, setExportingPdf] = useState(false)
  const [regenerating, setRegenerating] = useState(false)
  const [syncingBlockRefId, setSyncingBlockRefId] = useState<string | null>(null)
  const [sharing, setSharing] = useState(false)
  const [shareCopied, setShareCopied] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saveMessage, setSaveMessage] = useState('')

  useEffect(() => {
    if (!open) return
    setCurrentSlide(0)
    setError(null)
    setSaveMessage('')
  }, [open])

  useEffect(() => {
    if (!open) return
    setWorkingDeck(cloneDeck(deck))
    setError(null)
  }, [deck, open])

  const dirty = useMemo(
    () => JSON.stringify(workingDeck) !== JSON.stringify(deck),
    [deck, workingDeck],
  )

  const riskySlides = useMemo(
    () => workingDeck.slides.filter((slide) => slideNeedsAttention(slide)),
    [workingDeck.slides],
  )

  const evidenceCoverage = useMemo(
    () => resolveDeckEvidenceCoverage(workingDeck),
    [workingDeck],
  )

  const evidenceReview = useMemo(
    () => resolveDeckEvidenceReview(workingDeck, evidenceCoverage),
    [evidenceCoverage, workingDeck],
  )

  const citationValidation = useMemo(
    () => resolveDeckCitationValidation(workingDeck),
    [workingDeck],
  )
  const exportGateIssues = useMemo(
    () => buildDeckExportGateIssues(workingDeck),
    [workingDeck],
  )

  const regenerationPanel = useMemo(
    () =>
      panels.find((panel) => panel.id === workingDeck.meta.generator_panel_id) ??
      panels[0] ??
      null,
    [panels, workingDeck.meta.generator_panel_id],
  )

  if (!open) return null

  const slides = workingDeck.slides
  const activeSlide = slides[currentSlide] ?? slides[0]
  if (!activeSlide) return null
  const activeSlideCoverage = evidenceCoverage.slides.find(
    (slide) => slide.slide_id === activeSlide.id,
  )
  const activeSlideReview = evidenceReview.slides.find(
    (slide) => slide.slide_id === activeSlide.id,
  )
  const coveragePercent = formatCoveragePercent(evidenceCoverage.coverage_ratio)
  const unsupportedSlideIds = evidenceCoverage.unsupported_slide_ids
  const activeBlockEvidenceBindings = buildBlockEvidenceBindings(activeSlide)
  const activeBlockEvidenceBindingsById = new Map(
    activeBlockEvidenceBindings.map((binding) => [binding.blockId, binding]),
  )
  const citationGateLabel = citationValidationLabel(citationValidation)

  const replaceActiveSlide = (updater: (slide: DeckSlide) => DeckSlide) => {
    setWorkingDeck((prev) => ({
      ...prev,
      slides: prev.slides.map((slide, index) => (index === currentSlide ? updater(slide) : slide)),
      generation: {
        ...prev.generation,
        actual_slide_count: prev.slides.length,
      },
    }))
    setSaveMessage('')
  }

  const applyBlockEvidenceRefs = (blockId: string, evidenceRefIds: string[]) => {
    replaceActiveSlide((slide) => {
      const normalizedRefIds = uniqueStrings(evidenceRefIds)
      const selectedRefs = slide.evidence_refs.filter((ref) => normalizedRefIds.includes(ref.id))
      return {
        ...slide,
        blocks: slide.blocks.map((block) =>
          block.id === blockId
            ? {
                ...block,
                content: {
                  ...block.content,
                  evidence_ref_ids: normalizedRefIds,
                  evidence_source_ids: uniqueStrings(selectedRefs.map((ref) => ref.source_id)),
                  evidence_excerpt_ids: uniqueStrings(
                    selectedRefs.map((ref) => ref.excerpt_id ?? ''),
                  ),
                },
              }
            : block,
        ),
        status: {
          ...slide.status,
          dirty: true,
          review_state: 'draft',
        },
      }
    })
  }

  const syncBlockEvidenceRefs = async (blockId: string, evidenceRefIds: string[]) => {
    const normalizedRefIds = uniqueStrings(evidenceRefIds)
    const selectedRefs = activeSlide.evidence_refs.filter((ref) =>
      normalizedRefIds.includes(ref.id),
    )
    applyBlockEvidenceRefs(blockId, normalizedRefIds)
    setSyncingBlockRefId(blockId)
    setError(null)
    try {
      const response = await updateDeckBlockRefs(
        workingDeck.deck_id,
        activeSlide.id,
        blockId,
        {
          evidence_ref_ids: normalizedRefIds,
          evidence_source_ids: uniqueStrings(selectedRefs.map((ref) => ref.source_id)),
          evidence_excerpt_ids: uniqueStrings(selectedRefs.map((ref) => ref.excerpt_id ?? '')),
        },
      )
      const cloned = cloneDeck(response.deck)
      setWorkingDeck(cloned)
      onDeckChange(response.deck)
      const nextIndex = cloned.slides.findIndex((slide) => slide.id === activeSlide.id)
      if (nextIndex >= 0) {
        setCurrentSlide(nextIndex)
      }
      setSaveMessage('Citation bindings synced.')
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setSyncingBlockRefId(null)
    }
  }

  const persistDeck = async (): Promise<DeckSpec | null> => {
    setSaving(true)
    setError(null)
    try {
      const saved = await updateDeck(workingDeck.deck_id, {
        title: workingDeck.meta.title,
        theme: workingDeck.meta.theme,
        slides: workingDeck.slides,
      })
      const cloned = cloneDeck(saved)
      setWorkingDeck(cloned)
      onDeckChange(saved)
      setSaveMessage('已保存到演示稿草稿')
      return cloned
    } catch (err) {
      setError((err as Error).message)
      return null
    } finally {
      setSaving(false)
    }
  }

  const confirmRiskyExport = (latestDeck: DeckSpec): DeckExportGateDecision => {
    const issues = buildDeckExportGateIssues(latestDeck)
    if (issues.length === 0) {
      return { allowed: true, allowUnsafeExport: false }
    }

    const allowed = window.confirm(
      [
        'Export is blocked by citation/evidence checks unless you explicitly override it.',
        '',
        ...issues.map((issue) => `- ${issue}`),
        '',
        'Continue with an unsafe PPTX export?',
      ].join('\n'),
    )

    return {
      allowed,
      allowUnsafeExport: allowed,
      overrideReason: allowed ? issues.join(' | ') : undefined,
    }
  }

  const handleExport = async () => {
    setExporting(true)
    setError(null)
    try {
      let latestDeck = workingDeck
      if (dirty) {
        const saved = await persistDeck()
        if (!saved) return
        latestDeck = saved
      }
      const exportGateDecision = confirmRiskyExport(latestDeck)
      if (!exportGateDecision.allowed) return

      const blob = await exportDeck(latestDeck.deck_id, 'pptx', {
        allowUnsafeExport: exportGateDecision.allowUnsafeExport,
        overrideReason: exportGateDecision.overrideReason,
      })
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = buildDeckDownloadFilename(latestDeck.meta.title, 'pptx')
      anchor.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setExporting(false)
    }
  }

  const handleDownloadMarkdown = () => {
    setError(null)
    const markdown = buildDeckMarkdown(workingDeck)
    const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = buildDeckDownloadFilename(workingDeck.meta.title, 'md')
    anchor.click()
    URL.revokeObjectURL(url)
  }

  const handleExportPdf = async () => {
    setExportingPdf(true)
    setError(null)
    try {
      let latestDeck = workingDeck
      if (dirty) {
        const saved = await persistDeck()
        if (!saved) return
        latestDeck = saved
      }
      if (!confirmRiskyExport(latestDeck).allowed) return

      const printWindow = window.open('', '_blank', 'noopener,noreferrer')
      if (!printWindow) {
        throw new Error('无法打开打印窗口，请检查浏览器是否拦截了弹窗。')
      }

      const html = buildDeckPrintHtml(latestDeck)
      printWindow.document.open()
      printWindow.document.write(html)
      printWindow.document.close()
      printWindow.focus()
      printWindow.onload = () => {
        printWindow.print()
      }
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setExportingPdf(false)
    }
  }

  const handleShareDeck = async () => {
    setSharing(true)
    setError(null)
    try {
      let latestDeck = workingDeck
      if (dirty) {
        const saved = await persistDeck()
        if (!saved) return
        latestDeck = saved
      }

      const payload = await createDeckShareLink(latestDeck.deck_id)
      await navigator.clipboard.writeText(payload.share_url)
      setShareCopied(true)
      setSaveMessage('已复制演示稿分享链接')
      window.setTimeout(() => setShareCopied(false), 2000)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setSharing(false)
    }
  }

  const handleRegenerateSlide = async () => {
    if (!regenerationPanel) {
      setError('当前没有可用的生成面板。')
      return
    }

    setRegenerating(true)
    setError(null)
    setSaveMessage('')
    try {
      let latestDeck = workingDeck
      if (dirty) {
        const saved = await persistDeck()
        if (!saved) return
        latestDeck = saved
      }
      const regenerated = await regenerateDeckSlide(latestDeck.deck_id, activeSlide.id, {
        panel_config: regenerationPanel.modelConfig,
        knowledge_base_enabled: latestDeck.meta.source_mode === 'kb_plus_chat',
      })
      const cloned = cloneDeck(regenerated)
      setWorkingDeck(cloned)
      onDeckChange(regenerated)
      const nextIndex = cloned.slides.findIndex((slide) => slide.id === activeSlide.id)
      if (nextIndex >= 0) {
        setCurrentSlide(nextIndex)
      }
      setSaveMessage('当前页已重新生成。')
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setRegenerating(false)
    }
  }

  const goNext = () => setCurrentSlide((slide) => Math.min(slide + 1, slides.length - 1))
  const goPrev = () => setCurrentSlide((slide) => Math.max(slide - 1, 0))

  const appendBlock = (kind: 'paragraph' | 'bullet_list') => {
    replaceActiveSlide((slide) => ({
      ...slide,
      blocks: [...slide.blocks, createEditableBlock(kind)],
    }))
  }

  const removeBlock = (indexToRemove: number) => {
    replaceActiveSlide((slide) => ({
      ...slide,
      blocks: slide.blocks.filter((_, index) => index !== indexToRemove),
    }))
  }

  const toggleActiveSlideManualConfirmation = () => {
    if (activeSlide.quality_state === 'supported') return

    replaceActiveSlide((slide) => ({
      ...slide,
      status: {
        ...slide.status,
        review_state: slide.status.review_state === 'confirmed' ? 'draft' : 'confirmed',
        dirty: true,
      },
    }))
    setSaveMessage('')
  }

  return (
    <div
      className="fixed inset-0 z-50 flex flex-col overflow-hidden bg-bg-primary/95 backdrop-blur-sm"
      data-testid="deck-editor-modal"
    >
      <div className="flex items-start justify-between gap-3 border-b border-bg-border bg-bg-secondary px-4 py-3 sm:px-5">
        <div className="min-w-0">
          <p
            className="truncate text-sm font-semibold text-text-primary"
            data-testid="deck-editor-title"
          >
            {workingDeck.meta.title}
          </p>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-text-secondary">
            <span>{workingDeck.generation.actual_slide_count} 页</span>
            <span className="rounded-full bg-bg-tertiary px-2 py-0.5">
              {currentSlide + 1} / {slides.length}
            </span>
            <span className="rounded-full border border-bg-border px-2 py-0.5">
              {sourceModeLabel(workingDeck.meta.source_mode)}
            </span>
            <span className="rounded-full border border-bg-border px-2 py-0.5">
              证据覆盖: {coveragePercent}
            </span>
            <span
              className={`rounded-full border px-2 py-0.5 ${citationValidationClass(citationValidation)}`}
              data-testid="deck-citation-gate-status"
            >
              Citation gate: {citationGateLabel}
            </span>
            <span className="rounded-full border border-bg-border px-2 py-0.5">
              主题: {deckThemeLabel(workingDeck.meta.theme)}
            </span>
            {dirty && <span className="text-amber-400">有未保存修改</span>}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => void handleRegenerateSlide()}
            data-testid="deck-editor-regenerate"
            disabled={regenerating || !regenerationPanel}
            className="flex items-center gap-1.5 rounded-lg border border-bg-border px-3 py-1.5 text-xs text-text-secondary transition-colors hover:border-accent-blue/40 hover:text-text-primary disabled:opacity-50"
            title="重新生成当前页"
          >
            {regenerating ? (
              <span className="h-3 w-3 animate-spin rounded-full border border-current border-t-transparent" />
            ) : (
              <RefreshCw size={12} />
            )}
            重生成当前页
          </button>

          <button
            onClick={() => void persistDeck()}
            data-testid="deck-editor-save"
            disabled={saving}
            className="flex items-center gap-1.5 rounded-lg border border-bg-border px-3 py-1.5 text-xs text-text-secondary transition-colors hover:border-accent-blue/40 hover:text-text-primary disabled:opacity-50"
            title="保存演示稿草稿"
          >
            {saving ? (
              <span className="h-3 w-3 animate-spin rounded-full border border-current border-t-transparent" />
            ) : (
              <Save size={12} />
            )}
            保存
          </button>

          <button
            onClick={() => void handleShareDeck()}
            data-testid="deck-editor-share"
            disabled={sharing}
            className={`flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs transition-colors disabled:opacity-50 ${
              shareCopied
                ? 'border-accent-green/40 bg-accent-green/10 text-accent-green'
                : 'border-bg-border text-text-secondary hover:border-accent-blue/40 hover:text-text-primary'
            }`}
            title="复制演示稿分享链接"
          >
            {sharing ? (
              <span className="h-3 w-3 animate-spin rounded-full border border-current border-t-transparent" />
            ) : shareCopied ? (
              <Check size={12} />
            ) : (
              <Share2 size={12} />
            )}
            {shareCopied ? '已复制链接' : '分享'}
          </button>

          <button
            onClick={handleDownloadMarkdown}
            className="flex items-center gap-1.5 rounded-lg border border-bg-border px-3 py-1.5 text-xs text-text-secondary transition-colors hover:border-accent-blue/40 hover:text-text-primary"
            title="下载 Markdown"
          >
            <Download size={12} />
            下载 MD
          </button>

          <button
            onClick={() => void handleExportPdf()}
            data-testid="deck-editor-export-pdf"
            disabled={exportingPdf}
            className="flex items-center gap-1.5 rounded-lg border border-bg-border px-3 py-1.5 text-xs text-text-secondary transition-colors hover:border-accent-blue/40 hover:text-text-primary disabled:opacity-50"
            title="导出 PDF"
          >
            {exportingPdf ? (
              <span className="h-3 w-3 animate-spin rounded-full border border-current border-t-transparent" />
            ) : (
              <Download size={12} />
            )}
            导出 PDF
          </button>

          <button
            onClick={() => void handleExport()}
            data-testid="deck-editor-export-pptx"
            disabled={exporting}
            className="flex items-center gap-1.5 rounded-lg border border-accent-blue/40 bg-accent-blue/15 px-3 py-1.5 text-xs text-accent-blue transition-colors hover:bg-accent-blue/25 disabled:opacity-50"
            title="导出 PPTX"
          >
            {exporting ? (
              <span className="h-3 w-3 animate-spin rounded-full border border-current border-t-transparent" />
            ) : (
              <Download size={12} />
            )}
            导出 PPTX
          </button>

          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
            title="关闭"
          >
            <X size={16} />
          </button>
        </div>
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-0 overflow-y-auto lg:grid-cols-[280px_minmax(0,1fr)_380px] lg:overflow-hidden">
        <aside className="min-h-0 border-b border-bg-border bg-bg-secondary/70 lg:border-b-0 lg:border-r">
          <div className="flex h-full min-h-0 flex-col">
            <div className="border-b border-bg-border px-4 py-3 text-xs font-medium uppercase tracking-wide text-text-secondary/70">
              演示稿结构
            </div>
            <div className="min-h-[12rem] flex-1 space-y-2 overflow-y-auto px-3 py-3 lg:min-h-0">
              {slides.map((slide, index) => (
                <button
                  key={slide.id}
                  onClick={() => setCurrentSlide(index)}
                  className={`w-full rounded-xl border px-3 py-3 text-left transition-colors ${
                    index === currentSlide
                      ? 'border-accent-blue/40 bg-accent-blue/10'
                      : 'border-bg-border bg-bg-primary/40 hover:border-accent-blue/25 hover:bg-bg-hover'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[10px] uppercase tracking-wide text-text-secondary/60">{slideTypeLabel(slide.type)}</span>
                    <span className={`rounded-full border px-2 py-0.5 text-[10px] ${qualityBadgeClass(slide)}`}>
                      {qualityLabel(slide)}
                    </span>
                  </div>
                  <p className="mt-2 line-clamp-2 text-sm font-medium text-text-primary">
                    {slide.title || '未命名页面'}
                  </p>
                  {slide.subtitle && (
                    <p className="mt-1 line-clamp-1 text-xs text-text-secondary">{slide.subtitle}</p>
                  )}
                </button>
              ))}
            </div>
          </div>
        </aside>

        <section className="flex min-h-0 flex-col bg-bg-primary">
          <div className="flex items-center justify-between border-b border-bg-border px-4 py-3 text-xs text-text-secondary">
            <span>站内预览</span>
            <div className="flex items-center gap-2">
              <button
                onClick={goPrev}
                disabled={currentSlide === 0}
                className="rounded-lg border border-bg-border px-2 py-1 transition-colors hover:border-accent-blue/30 hover:text-text-primary disabled:opacity-30"
              >
                <ChevronLeft size={14} />
              </button>
              <button
                onClick={goNext}
                disabled={currentSlide === slides.length - 1}
                className="rounded-lg border border-bg-border px-2 py-1 transition-colors hover:border-accent-blue/30 hover:text-text-primary disabled:opacity-30"
              >
                <ChevronRight size={14} />
              </button>
            </div>
          </div>

          <div className="min-h-[20rem] flex-1 overflow-y-auto p-4 sm:p-6 lg:min-h-0">
            <div className="mx-auto max-w-4xl">
              <div className={`aspect-[16/9] rounded-[28px] border p-8 shadow-2xl ${previewShellClass(workingDeck.meta.theme)}`}>
                <div className="flex h-full flex-col">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <p className={`text-[11px] uppercase tracking-[0.24em] ${previewEyebrowClass(workingDeck.meta.theme)}`}>
                        {slideLayoutLabel(activeSlide.layout)}
                      </p>
                      <span className={`rounded-full border px-2 py-0.5 text-[10px] ${qualityBadgeClass(activeSlide)}`}>
                        {qualityLabel(activeSlide)}
                      </span>
                    </div>
                    <h2 className="mt-3 text-2xl font-semibold leading-tight sm:text-3xl">
                      {activeSlide.title || '未命名页面'}
                    </h2>
                    {activeSlide.subtitle && (
                      <p className="mt-3 text-sm leading-6 opacity-80 sm:text-base">{activeSlide.subtitle}</p>
                    )}
                  </div>

                  <div className="mt-8 flex-1 space-y-4 overflow-y-auto">
                    {activeSlide.blocks.map((block) => (
                      <div key={block.id} className={`rounded-2xl border p-4 ${previewCardClass(workingDeck.meta.theme)}`}>
                        {renderBlock(block)}
                      </div>
                    ))}
                    {activeSlide.blocks.length === 0 && (
                      <div className={`rounded-2xl border border-dashed p-4 text-sm opacity-75 ${previewCardClass(workingDeck.meta.theme)}`}>
                        当前页还没有内容块。
                      </div>
                    )}
                  </div>

                  {activeSlide.evidence_refs.length > 0 && (
                    <div className="mt-6 flex flex-wrap gap-2 text-[11px] opacity-80">
                      {activeSlide.evidence_refs.map((evidence) => (
                        <span key={evidence.id} className={`rounded-full border px-2 py-1 ${previewCardClass(workingDeck.meta.theme)}`}>
                          {evidence.source_id}: {evidence.source_title}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </section>

        <aside className="min-h-0 border-t border-bg-border bg-bg-secondary/80 lg:border-l lg:border-t-0">
          <div className="flex h-full min-h-0 flex-col">
            <div className="border-b border-bg-border px-4 py-3 text-xs font-medium uppercase tracking-wide text-text-secondary/70">
              编辑与校验
            </div>
            <div className="min-h-[18rem] flex-1 space-y-5 overflow-y-auto px-4 py-4 lg:min-h-0">
              {error && (
                <div
                  className="rounded-xl border border-accent-red/30 bg-accent-red/10 px-3 py-2 text-sm text-accent-red"
                  data-testid="deck-export-blocked-message"
                >
                  {error}
                </div>
              )}

              {saveMessage && !error && (
                <div
                  className="rounded-xl border border-accent-green/30 bg-accent-green/10 px-3 py-2 text-sm text-accent-green"
                  data-testid="deck-editor-save-message"
                >
                  {saveMessage}
                </div>
              )}

              {exportGateIssues.length > 0 && !error && (
                <div
                  className="rounded-xl border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-xs leading-5 text-amber-200"
                  data-testid="deck-export-gate-warning"
                >
                  <p className="font-medium text-amber-100">PPTX export requires an explicit unsafe-export override.</p>
                  <ul className="mt-2 list-disc space-y-1 pl-4">
                    {exportGateIssues.map((issue) => (
                      <li key={issue}>{issue}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="space-y-2">
                <label className="text-xs font-medium text-text-secondary">演示稿标题</label>
                <input
                  data-testid="deck-editor-title-input"
                  value={workingDeck.meta.title}
                  onChange={(event) => {
                    const nextTitle = event.target.value
                    setWorkingDeck((prev) => ({
                      ...prev,
                      meta: { ...prev.meta, title: nextTitle },
                      slides: prev.slides.map((slide, index) =>
                        index === 0 && slide.type === 'cover' ? { ...slide, title: nextTitle } : slide,
                      ),
                    }))
                    setSaveMessage('')
                  }}
                  className="w-full rounded-xl border border-bg-border bg-bg-primary px-3 py-2 text-sm text-text-primary outline-none transition-colors focus:border-accent-blue/40"
                />
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-2">
                  <label className="text-xs font-medium text-text-secondary">主题模板</label>
                  <select
                    value={workingDeck.meta.theme}
                    onChange={(event) => {
                      const nextTheme = event.target.value as DeckSpec['meta']['theme']
                      setWorkingDeck((prev) => ({
                        ...prev,
                        meta: { ...prev.meta, theme: nextTheme },
                      }))
                      setSaveMessage('')
                    }}
                    className="w-full rounded-xl border border-bg-border bg-bg-primary px-3 py-2 text-sm text-text-primary outline-none transition-colors focus:border-accent-blue/40"
                  >
                    {DECK_THEMES.map((theme) => (
                      <option key={theme.value} value={theme.value}>
                        {theme.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="space-y-2">
                  <label className="text-xs font-medium text-text-secondary">重生成面板</label>
                  <div className="rounded-xl border border-bg-border bg-bg-primary px-3 py-2 text-sm text-text-primary">
                    {regenerationPanel ? regenerationPanel.modelConfig.model : '未找到面板'}
                  </div>
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-xs font-medium text-text-secondary">当前页标题</label>
                <input
                  value={activeSlide.title}
                  onChange={(event) =>
                    replaceActiveSlide((slide) => ({ ...slide, title: event.target.value }))
                  }
                  className="w-full rounded-xl border border-bg-border bg-bg-primary px-3 py-2 text-sm text-text-primary outline-none transition-colors focus:border-accent-blue/40"
                />
              </div>

              <div className="space-y-2">
                <label className="text-xs font-medium text-text-secondary">当前页副标题</label>
                <input
                  value={activeSlide.subtitle}
                  onChange={(event) =>
                    replaceActiveSlide((slide) => ({ ...slide, subtitle: event.target.value }))
                  }
                  className="w-full rounded-xl border border-bg-border bg-bg-primary px-3 py-2 text-sm text-text-primary outline-none transition-colors focus:border-accent-blue/40"
                />
              </div>

              <div className="space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-xs font-medium text-text-secondary">内容块</p>
                    <p className="mt-1 text-[11px] text-text-secondary/80">
                      当前页共有 {activeSlide.blocks.length} 个内容块
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => appendBlock('bullet_list')}
                      className="rounded-lg border border-bg-border px-2.5 py-1 text-[11px] text-text-secondary transition-colors hover:border-accent-blue/40 hover:text-text-primary"
                    >
                      添加列表
                    </button>
                    <button
                      type="button"
                      onClick={() => appendBlock('paragraph')}
                      className="rounded-lg border border-bg-border px-2.5 py-1 text-[11px] text-text-secondary transition-colors hover:border-accent-blue/40 hover:text-text-primary"
                    >
                      添加段落
                    </button>
                  </div>
                </div>

                {activeSlide.blocks.length === 0 ? (
                  <div className="rounded-2xl border border-dashed border-bg-border bg-bg-primary/40 px-4 py-5">
                    <p className="text-sm text-text-primary">当前页还没有内容块。</p>
                    <p className="mt-1 text-xs leading-5 text-text-secondary">
                      可以先添加一个列表块或段落块，再继续编辑这一页的正文内容。
                    </p>
                  </div>
                ) : (
                  activeSlide.blocks.map((block, index) => (
                    <div key={block.id} className="rounded-2xl border border-bg-border bg-bg-primary/60 p-3">
                      <div className="mb-2 flex items-center justify-between gap-2">
                        <div>
                          <span className="text-xs font-medium text-text-primary">{blockKindLabel(block.kind)}</span>
                          <span className="ml-2 text-[11px] text-text-secondary">{blockRoleLabel(block.role)}</span>
                        </div>
                        <button
                          type="button"
                          onClick={() => removeBlock(index)}
                          className="rounded-lg p-1 text-text-secondary transition-colors hover:bg-bg-hover hover:text-accent-red"
                          title="删除内容块"
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                      <textarea
                        value={blockValue(block)}
                        onChange={(event) =>
                          replaceActiveSlide((slide) => ({
                            ...slide,
                            blocks: slide.blocks.map((item, itemIndex) =>
                              itemIndex === index ? updateBlockValue(item, event.target.value) : item,
                            ),
                          }))
                        }
                        rows={block.kind === 'bullet_list' ? 6 : 5}
                        className="w-full rounded-xl border border-bg-border bg-bg-primary px-3 py-2 text-sm leading-6 text-text-primary outline-none transition-colors focus:border-accent-blue/40"
                      />
                      {block.kind === 'bullet_list' && (
                        <p className="mt-2 text-[11px] text-text-secondary">一行对应一个 bullet。</p>
                      )}
                    </div>
                  ))
                )}
              </div>

              <div className="space-y-2">
                <label className="text-xs font-medium text-text-secondary">演讲备注</label>
                <textarea
                  value={activeSlide.speaker_notes}
                  onChange={(event) =>
                    replaceActiveSlide((slide) => ({ ...slide, speaker_notes: event.target.value }))
                  }
                  rows={5}
                  className="w-full rounded-xl border border-bg-border bg-bg-primary px-3 py-2 text-sm leading-6 text-text-primary outline-none transition-colors focus:border-accent-blue/40"
                />
              </div>

              <div
                className="space-y-4 rounded-2xl border border-bg-border bg-bg-primary/50 p-4"
                data-testid="deck-evidence-coverage"
              >
                <div className="flex items-center gap-2">
                  <AlertTriangle size={14} className="text-amber-400" />
                  <p className="text-xs font-medium text-text-primary">证据与提示</p>
                </div>

                <div className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
                  <div>
                    <p className="text-[11px] text-text-secondary">覆盖率</p>
                    <p
                      className="mt-1 text-lg font-semibold text-text-primary"
                      data-testid="deck-evidence-coverage-ratio"
                    >
                      {coveragePercent}
                    </p>
                  </div>
                  <div>
                    <p className="text-[11px] text-text-secondary">已覆盖页数</p>
                    <p
                      className="mt-1 text-lg font-semibold text-text-primary"
                      data-testid="deck-evidence-covered-slides"
                    >
                      {evidenceCoverage.slides_with_evidence} / {evidenceCoverage.coverable_slide_count}
                    </p>
                  </div>
                  <div>
                    <p className="text-[11px] text-text-secondary">引用总数</p>
                    <p
                      className="mt-1 text-lg font-semibold text-text-primary"
                      data-testid="deck-evidence-total-refs"
                    >
                      {evidenceCoverage.total_evidence_refs}
                    </p>
                  </div>
                  <div>
                    <p className="text-[11px] text-text-secondary">当前页引用</p>
                    <p className="mt-1 text-lg font-semibold text-text-primary">
                      {activeSlideCoverage?.evidence_ref_count ?? activeSlide.evidence_refs.length}
                    </p>
                  </div>
                </div>

                <div className="border-t border-bg-border pt-3">
                  <div className="grid grid-cols-4 gap-3 text-xs">
                    <div>
                      <p className="text-[11px] text-text-secondary">review status</p>
                      <p
                        className="mt-1 font-medium text-text-primary"
                        data-testid="deck-evidence-review-status"
                      >
                        {evidenceReviewStatusLabel(evidenceReview.status)}
                      </p>
                    </div>
                    <div>
                      <p className="text-[11px] text-text-secondary">actions</p>
                      <p
                        className="mt-1 font-medium text-text-primary"
                        data-testid="deck-evidence-review-action-count"
                      >
                        {evidenceReview.action_count}
                      </p>
                    </div>
                    <div>
                      <p className="text-[11px] text-text-secondary">review slides</p>
                      <p
                        className="mt-1 font-medium text-text-primary"
                        data-testid="deck-evidence-review-slide-count"
                      >
                        {evidenceReview.needs_review_slide_ids.length}
                      </p>
                    </div>
                    <div>
                      <p className="text-[11px] text-text-secondary">export gate</p>
                      <p
                        className={`mt-1 inline-flex rounded-full border px-2 py-0.5 font-medium ${citationValidationClass(citationValidation)}`}
                        data-testid="deck-citation-validation-status"
                      >
                        {citationGateLabel}
                      </p>
                    </div>
                  </div>

                  <div
                    className="mt-3 space-y-2 text-xs leading-5 text-text-secondary"
                    data-testid="deck-citation-validation-details"
                  >
                    {citationValidation ? (
                      <>
                        <p>
                          can export:
                          <span className="ml-2 text-text-primary">
                            {citationValidation.can_export ? 'yes' : 'no'}
                          </span>
                          <span className="ml-3">
                            issues:
                            <span className="ml-2 text-text-primary">
                              {citationValidation.issue_count}
                            </span>
                          </span>
                        </p>
                        {citationValidation.missing_source_ids.length > 0 && (
                          <p>
                            missing sources:
                            <span className="ml-2 break-all text-text-primary">
                              {citationValidation.missing_source_ids.join(', ')}
                            </span>
                          </p>
                        )}
                        {citationValidation.missing_block_evidence_ref_ids.length > 0 && (
                          <p>
                            missing block refs:
                            <span className="ml-2 break-all text-text-primary">
                              {citationValidation.missing_block_evidence_ref_ids.join(', ')}
                            </span>
                          </p>
                        )}
                      </>
                    ) : (
                      <p>No citation validation payload.</p>
                    )}
                  </div>

                  <div
                    className="mt-3 space-y-2 text-xs leading-5 text-text-secondary"
                    data-testid="deck-evidence-review-action-items"
                  >
                    {evidenceReview.action_items.length > 0 ? (
                      evidenceReview.action_items.map((item) => (
                        <div key={`${item.code}-${item.slide_ids.join('-')}`} className="border-l border-bg-border pl-3">
                          <span className="font-medium text-text-primary">{item.message}</span>
                          {item.slide_ids.length > 0 && (
                            <span className="ml-2 break-all">({item.slide_ids.join(', ')})</span>
                          )}
                        </div>
                      ))
                    ) : (
                      <p>No evidence review actions.</p>
                    )}
                  </div>

                  <div className="mt-3 text-xs leading-5 text-text-secondary">
                    current sources:
                    <span
                      className="ml-2 break-all text-text-primary"
                      data-testid="deck-evidence-review-active-sources"
                    >
                      {activeSlideReview && activeSlideReview.source_titles.length > 0
                        ? activeSlideReview.source_titles.join(', ')
                        : 'none'}
                    </span>
                  </div>

                  <div
                    className="mt-3 space-y-2 text-xs leading-5 text-text-secondary"
                    data-testid="deck-evidence-block-bindings"
                  >
                    <p className="text-[11px] font-medium text-text-secondary">content bindings</p>
                    {activeSlide.blocks.length > 0 ? (
                      activeSlide.blocks.map((block) => {
                        const binding = activeBlockEvidenceBindingsById.get(block.id)
                        const selectedRefIds = new Set(binding?.evidenceRefIds ?? [])
                        const isSyncingBlockRefs = syncingBlockRefId === block.id
                        return (
                          <div
                            key={block.id}
                            className="space-y-2 border-l border-bg-border pl-3"
                            data-testid="deck-block-ref-editor"
                          >
                            <div>
                              <span className="font-medium text-text-primary">{block.id}</span>
                              <span className="ml-2">{binding?.label ?? `${blockKindLabel(block.kind)} / ${blockRoleLabel(block.role)}`}</span>
                              <span className="ml-2 break-all text-text-primary">
                                {binding && binding.sourceTitles.length > 0
                                  ? binding.sourceTitles.join(', ')
                                  : 'unbound'}
                              </span>
                              {isSyncingBlockRefs && (
                                <span className="ml-2 text-accent-blue">syncing...</span>
                              )}
                            </div>
                            {activeSlide.evidence_refs.length > 0 ? (
                              <div className="flex flex-wrap gap-2">
                                {activeSlide.evidence_refs.map((evidence) => (
                                  <label
                                    key={`${block.id}-${evidence.id}`}
                                    className="inline-flex items-center gap-1.5 rounded-lg border border-bg-border px-2 py-1 text-[11px] text-text-secondary"
                                  >
                                    <input
                                      type="checkbox"
                                      disabled={isSyncingBlockRefs}
                                      checked={selectedRefIds.has(evidence.id)}
                                      onChange={(event) => {
                                        const currentIds = binding?.evidenceRefIds ?? []
                                        const nextIds = event.target.checked
                                          ? uniqueStrings([...currentIds, evidence.id])
                                          : currentIds.filter((refId) => refId !== evidence.id)
                                        void syncBlockEvidenceRefs(block.id, nextIds)
                                      }}
                                      className="h-3 w-3 accent-accent-blue"
                                    />
                                    <span>{evidence.source_title || evidence.id}</span>
                                  </label>
                                ))}
                              </div>
                            ) : (
                              <p>No slide evidence refs to bind.</p>
                            )}
                          </div>
                        )
                      })
                    ) : (
                      <p>No content blocks.</p>
                    )}
                  </div>
                </div>

                <div className="border-t border-bg-border pt-3 text-xs leading-5 text-text-secondary">
                  unsupported slide ids:
                  <span
                    className="ml-2 break-all text-text-primary"
                    data-testid="deck-evidence-unsupported-slide-ids"
                  >
                    {unsupportedSlideIds.length > 0 ? unsupportedSlideIds.join(', ') : '无'}
                  </span>
                </div>

                <div className="border-t border-bg-border pt-3 text-sm text-text-secondary">
                  当前页状态
                  <span className={`ml-2 inline-flex rounded-full border px-2 py-0.5 text-xs ${qualityBadgeClass(activeSlide)}`}>
                    {qualityLabel(activeSlide)}
                  </span>
                </div>

                {activeSlide.quality_state !== 'supported' && (
                  <div className="border-t border-bg-border pt-3 text-sm text-text-secondary">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="text-sm text-text-primary">
                          {isSlideManuallyConfirmed(activeSlide) ? '本页已人工确认' : '本页尚未人工确认'}
                        </p>
                        <p className="mt-1 text-xs leading-5 text-text-secondary">
                          人工确认后，这一页不会再被计入导出前的风险页统计；导出 PPTX 也会显示“已人工确认”。
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={toggleActiveSlideManualConfirmation}
                        className={`rounded-lg border px-3 py-1.5 text-xs transition-colors ${
                          isSlideManuallyConfirmed(activeSlide)
                            ? 'border-accent-green/40 bg-accent-green/10 text-accent-green hover:bg-accent-green/15'
                            : 'border-accent-blue/40 bg-accent-blue/10 text-accent-blue hover:bg-accent-blue/15'
                        }`}
                      >
                        {isSlideManuallyConfirmed(activeSlide) ? '撤销人工确认' : '标记本页已人工确认'}
                      </button>
                    </div>
                  </div>
                )}

                <div className="border-t border-bg-border pt-3 text-sm text-text-secondary">
                  风险页数
                  <span className="ml-2 font-medium text-text-primary">{riskySlides.length}</span>
                </div>

                {activeSlide.evidence_refs.length > 0 ? (
                  <div className="space-y-3 border-t border-bg-border pt-3">
                    {activeSlide.evidence_refs.map((evidence) => (
                      <div key={evidence.id} className="border-l border-bg-border pl-3">
                        <div className="flex items-center justify-between gap-2">
                          <p className="text-xs font-medium text-text-primary">{evidence.source_title}</p>
                          <span className="text-[11px] text-text-secondary">
                            {Math.round((evidence.confidence ?? 0) * 100)}%
                          </span>
                        </div>
                        {evidence.snippet && (
                          <p className="mt-2 text-xs leading-5 text-text-secondary">{evidence.snippet}</p>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs leading-5 text-text-secondary">
                    当前页暂无证据引用。重生成后如果仍然为空，建议人工补充。
                  </p>
                )}
              </div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  )
}
