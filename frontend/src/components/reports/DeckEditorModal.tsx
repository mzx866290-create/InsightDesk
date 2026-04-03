import React, { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, ChevronLeft, ChevronRight, Download, Save, X } from 'lucide-react'
import { exportDeck, updateDeck } from '../../api/client'
import type { DeckBlock, DeckSlide, DeckSpec } from '../../api/client'

interface DeckEditorModalProps {
  open: boolean
  onClose: () => void
  deck: DeckSpec
  onDeckChange: (deck: DeckSpec) => void
}

function cloneDeck(deck: DeckSpec): DeckSpec {
  return JSON.parse(JSON.stringify(deck)) as DeckSpec
}

function blockValue(block: DeckBlock): string {
  if (block.kind === 'bullet_list') {
    return (block.content.items ?? []).join('\n')
  }
  return block.content.text ?? ''
}

function updateBlockValue(block: DeckBlock, value: string): DeckBlock {
  if (block.kind === 'bullet_list') {
    const items = value
      .split('\n')
      .map((item) => item.trim())
      .filter(Boolean)
    return { ...block, content: { ...block.content, items } }
  }
  return { ...block, content: { ...block.content, text: value } }
}

function renderBlock(block: DeckBlock) {
  if (block.kind === 'bullet_list') {
    const items = block.content.items ?? []
    return (
      <ul className="space-y-2 pl-5 list-disc text-sm text-text-primary/90">
        {items.map((item, index) => (
          <li key={`${block.id}-${index}`} className="leading-6">
            {item}
          </li>
        ))}
      </ul>
    )
  }

  return (
    <p className="text-sm leading-6 text-text-primary/85 whitespace-pre-wrap">
      {block.content.text ?? ''}
    </p>
  )
}

function qualityBadgeClass(qualityState: DeckSlide['quality_state']): string {
  switch (qualityState) {
    case 'supported':
      return 'border-accent-green/30 bg-accent-green/10 text-accent-green'
    case 'manual':
      return 'border-accent-red/30 bg-accent-red/10 text-accent-red'
    default:
      return 'border-amber-400/30 bg-amber-400/10 text-amber-300'
  }
}

function qualityLabel(qualityState: DeckSlide['quality_state']): string {
  switch (qualityState) {
    case 'supported':
      return '证据充分'
    case 'manual':
      return '需人工确认'
    default:
      return '证据偏弱'
  }
}

function sourceModeLabel(sourceMode: DeckSpec['meta']['source_mode']): string {
  return sourceMode === 'kb_plus_chat' ? '知识库 + 聊天' : '仅聊天'
}

export const DeckEditorModal: React.FC<DeckEditorModalProps> = ({
  open,
  onClose,
  deck,
  onDeckChange,
}) => {
  const [workingDeck, setWorkingDeck] = useState<DeckSpec>(deck)
  const [currentSlide, setCurrentSlide] = useState(0)
  const [saving, setSaving] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saveMessage, setSaveMessage] = useState('')

  useEffect(() => {
    if (open) {
      setWorkingDeck(cloneDeck(deck))
      setCurrentSlide(0)
      setError(null)
      setSaveMessage('')
    }
  }, [deck, open])

  const dirty = useMemo(
    () => JSON.stringify(workingDeck) !== JSON.stringify(deck),
    [deck, workingDeck],
  )

  const riskySlides = useMemo(
    () => workingDeck.slides.filter((slide) => slide.quality_state !== 'supported'),
    [workingDeck.slides],
  )

  if (!open) return null

  const slides = workingDeck.slides
  const activeSlide = slides[currentSlide] ?? slides[0]

  if (!activeSlide) return null

  const replaceActiveSlide = (updater: (slide: DeckSlide) => DeckSlide) => {
    setWorkingDeck((prev) => ({
      ...prev,
      slides: prev.slides.map((slide, index) =>
        index === currentSlide ? updater(slide) : slide,
      ),
      generation: {
        ...prev.generation,
        actual_slide_count: prev.slides.length,
      },
    }))
    setSaveMessage('')
  }

  const persistDeck = async (): Promise<DeckSpec | null> => {
    setSaving(true)
    setError(null)
    try {
      const saved = await updateDeck(workingDeck.deck_id, {
        title: workingDeck.meta.title,
        slides: workingDeck.slides,
      })
      setWorkingDeck(cloneDeck(saved))
      onDeckChange(saved)
      setSaveMessage('已保存到 deck 草稿')
      return saved
    } catch (err) {
      setError((err as Error).message)
      return null
    } finally {
      setSaving(false)
    }
  }

  const confirmRiskyExport = (latestDeck: DeckSpec) => {
    const issues: string[] = []
    if (latestDeck.meta.source_mode === 'chat_only') {
      issues.push('当前为仅聊天模式，缺少知识库证据校验。')
    }
    const weakSlides = latestDeck.slides.filter((slide) => slide.quality_state !== 'supported')
    if (weakSlides.length > 0) {
      issues.push(`当前有 ${weakSlides.length} 页处于证据偏弱或需人工确认状态。`)
    }
    if (issues.length === 0) return true
    return window.confirm(`${issues.join('\n')}\n\n仍要继续导出 PPTX 吗？`)
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

      if (!confirmRiskyExport(latestDeck)) return

      const blob = await exportDeck(latestDeck.deck_id)
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `${latestDeck.meta.title.slice(0, 40) || 'deck'}.pptx`
      anchor.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setExporting(false)
    }
  }

  const goNext = () => setCurrentSlide((slide) => Math.min(slide + 1, slides.length - 1))
  const goPrev = () => setCurrentSlide((slide) => Math.max(slide - 1, 0))

  return (
    <div className="fixed inset-0 z-50 flex flex-col overflow-hidden bg-bg-primary/95 backdrop-blur-sm">
      <div className="flex items-start justify-between gap-3 border-b border-bg-border bg-bg-secondary px-4 py-3 sm:px-5">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-text-primary">
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
              生成面板: {workingDeck.meta.generator_panel_id}
            </span>
            {dirty && <span className="text-amber-400">有未保存修改</span>}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              void persistDeck()
            }}
            disabled={saving}
            className="flex items-center gap-1.5 rounded-lg border border-bg-border px-3 py-1.5 text-xs text-text-secondary transition-colors hover:border-accent-blue/40 hover:text-text-primary disabled:opacity-50"
            title="保存 deck 草稿"
          >
            {saving ? (
              <span className="h-3 w-3 animate-spin rounded-full border border-current border-t-transparent" />
            ) : (
              <Save size={12} />
            )}
            保存
          </button>

          <button
            onClick={() => {
              void handleExport()
            }}
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

      <div className="grid flex-1 grid-cols-1 gap-0 overflow-hidden lg:grid-cols-[280px_minmax(0,1fr)_380px]">
        <aside className="border-b border-bg-border bg-bg-secondary/70 lg:border-b-0 lg:border-r">
          <div className="flex h-full flex-col">
            <div className="border-b border-bg-border px-4 py-3 text-xs font-medium uppercase tracking-wide text-text-secondary/70">
              Deck 结构
            </div>
            <div className="flex-1 space-y-2 overflow-y-auto px-3 py-3">
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
                    <span className="text-[10px] uppercase tracking-wide text-text-secondary/60">
                      {slide.type}
                    </span>
                    <span
                      className={`rounded-full border px-2 py-0.5 text-[10px] ${qualityBadgeClass(slide.quality_state)}`}
                    >
                      {qualityLabel(slide.quality_state)}
                    </span>
                  </div>
                  <p className="mt-2 line-clamp-2 text-sm font-medium text-text-primary">
                    {slide.title || '未命名页面'}
                  </p>
                  {slide.subtitle && (
                    <p className="mt-1 line-clamp-1 text-xs text-text-secondary">
                      {slide.subtitle}
                    </p>
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

          <div className="flex-1 overflow-y-auto p-4 sm:p-6">
            <div className="mx-auto max-w-4xl">
              <div className="aspect-[16/9] rounded-[28px] border border-bg-border bg-gradient-to-br from-bg-secondary to-bg-primary p-8 shadow-2xl">
                <div className="flex h-full flex-col">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-[11px] uppercase tracking-[0.24em] text-accent-blue/70">
                        {activeSlide.layout}
                      </p>
                      <span
                        className={`rounded-full border px-2 py-0.5 text-[10px] ${qualityBadgeClass(activeSlide.quality_state)}`}
                      >
                        {qualityLabel(activeSlide.quality_state)}
                      </span>
                    </div>
                    <h2 className="mt-3 text-2xl font-semibold leading-tight text-text-primary sm:text-3xl">
                      {activeSlide.title || '未命名页面'}
                    </h2>
                    {activeSlide.subtitle && (
                      <p className="mt-3 text-sm leading-6 text-text-secondary sm:text-base">
                        {activeSlide.subtitle}
                      </p>
                    )}
                  </div>

                  <div className="mt-8 flex-1 space-y-4 overflow-y-auto">
                    {activeSlide.blocks.map((block) => (
                      <div
                        key={block.id}
                        className="rounded-2xl border border-bg-border/80 bg-bg-secondary/60 p-4"
                      >
                        {renderBlock(block)}
                      </div>
                    ))}
                  </div>

                  {activeSlide.evidence_refs.length > 0 && (
                    <div className="mt-6 flex flex-wrap gap-2 text-[11px] text-text-secondary">
                      {activeSlide.evidence_refs.map((evidence) => (
                        <span
                          key={evidence.id}
                          className="rounded-full border border-bg-border bg-bg-secondary px-2 py-1"
                        >
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

        <aside className="border-t border-bg-border bg-bg-secondary/80 lg:border-l lg:border-t-0">
          <div className="flex h-full flex-col">
            <div className="border-b border-bg-border px-4 py-3 text-xs font-medium uppercase tracking-wide text-text-secondary/70">
              编辑与校验
            </div>
            <div className="flex-1 space-y-5 overflow-y-auto px-4 py-4">
              {error && (
                <div className="rounded-xl border border-accent-red/30 bg-accent-red/10 px-3 py-2 text-sm text-accent-red">
                  {error}
                </div>
              )}

              {saveMessage && !error && (
                <div className="rounded-xl border border-accent-green/30 bg-accent-green/10 px-3 py-2 text-sm text-accent-green">
                  {saveMessage}
                </div>
              )}

              <div className="space-y-3 rounded-2xl border border-bg-border bg-bg-primary/50 p-4">
                <div className="flex items-center gap-2">
                  <AlertTriangle size={14} className="text-amber-400" />
                  <p className="text-xs font-medium text-text-primary">质量状态</p>
                </div>

                <div className="flex flex-wrap gap-2 text-xs">
                  <span className="rounded-full border border-bg-border px-2 py-1 text-text-secondary">
                    来源模式: {sourceModeLabel(workingDeck.meta.source_mode)}
                  </span>
                  <span className="rounded-full border border-bg-border px-2 py-1 text-text-secondary">
                    目标页数: {workingDeck.generation.target_slide_count}
                  </span>
                  <span className="rounded-full border border-bg-border px-2 py-1 text-text-secondary">
                    实际页数: {workingDeck.generation.actual_slide_count}
                  </span>
                </div>

                {workingDeck.meta.source_mode === 'chat_only' && (
                  <div className="rounded-xl border border-amber-400/20 bg-amber-400/10 px-3 py-2 text-sm text-text-secondary">
                    当前为仅聊天模式，导出前建议重点核对结论和措辞。
                  </div>
                )}

                {workingDeck.generation.warnings.map((warning) => (
                  <div
                    key={warning.code}
                    className="rounded-xl border border-amber-400/20 bg-amber-400/10 px-3 py-2"
                  >
                    <p className="text-xs font-medium text-text-primary">{warning.code}</p>
                    <p className="mt-1 text-[11px] leading-5 text-text-secondary">
                      {warning.message}
                    </p>
                  </div>
                ))}

                {riskySlides.length > 0 && (
                  <div className="rounded-xl border border-accent-red/20 bg-accent-red/10 px-3 py-2 text-sm text-text-secondary">
                    当前有 {riskySlides.length} 页处于证据偏弱或需人工确认状态，导出时会再次提示确认。
                  </div>
                )}
              </div>

              <div className="space-y-2">
                <label className="text-xs font-medium text-text-secondary">Deck 标题</label>
                <input
                  value={workingDeck.meta.title}
                  onChange={(event) => {
                    const nextTitle = event.target.value
                    setWorkingDeck((prev) => ({
                      ...prev,
                      meta: { ...prev.meta, title: nextTitle },
                      slides: prev.slides.map((slide, index) =>
                        index === 0 && slide.type === 'cover'
                          ? { ...slide, title: nextTitle }
                          : slide,
                      ),
                    }))
                    setSaveMessage('')
                  }}
                  className="w-full rounded-xl border border-bg-border bg-bg-primary px-3 py-2 text-sm text-text-primary outline-none transition-colors focus:border-accent-blue/40"
                />
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
                <p className="text-xs font-medium text-text-secondary">内容块</p>
                {activeSlide.blocks.map((block, index) => (
                  <div key={block.id} className="rounded-2xl border border-bg-border bg-bg-primary/60 p-3">
                    <div className="mb-2 flex items-center justify-between">
                      <span className="text-xs font-medium text-text-primary">{block.kind}</span>
                      <span className="text-[11px] text-text-secondary">{block.role}</span>
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
                      <p className="mt-2 text-[11px] text-text-secondary">
                        一行对应一个 bullet，导出时会保留为列表。
                      </p>
                    )}
                  </div>
                ))}
              </div>

              <div className="space-y-2">
                <label className="text-xs font-medium text-text-secondary">演讲备注</label>
                <textarea
                  value={activeSlide.speaker_notes}
                  onChange={(event) =>
                    replaceActiveSlide((slide) => ({
                      ...slide,
                      speaker_notes: event.target.value,
                    }))
                  }
                  rows={5}
                  className="w-full rounded-xl border border-bg-border bg-bg-primary px-3 py-2 text-sm leading-6 text-text-primary outline-none transition-colors focus:border-accent-blue/40"
                />
              </div>

              <div className="space-y-3 rounded-2xl border border-bg-border bg-bg-primary/50 p-4">
                <div className="flex items-center gap-2">
                  <AlertTriangle size={14} className="text-amber-400" />
                  <p className="text-xs font-medium text-text-primary">证据与提示</p>
                </div>

                <div className="rounded-xl border border-bg-border px-3 py-2 text-sm text-text-secondary">
                  当前页状态:
                  <span className={`ml-2 inline-flex rounded-full border px-2 py-0.5 text-xs ${qualityBadgeClass(activeSlide.quality_state)}`}>
                    {qualityLabel(activeSlide.quality_state)}
                  </span>
                </div>

                {activeSlide.evidence_refs.length > 0 ? (
                  <div className="space-y-2">
                    {activeSlide.evidence_refs.map((evidence) => (
                      <div key={evidence.id} className="rounded-xl border border-bg-border px-3 py-2">
                        <div className="flex items-center justify-between gap-2">
                          <p className="text-xs font-medium text-text-primary">
                            {evidence.source_id} · {evidence.source_title}
                          </p>
                          <span className="text-[11px] text-text-secondary">
                            置信度 {Math.round(evidence.confidence * 100)}%
                          </span>
                        </div>
                        {evidence.excerpt_id && (
                          <p className="mt-1 text-[11px] text-text-secondary">
                            excerpt: {evidence.excerpt_id}
                          </p>
                        )}
                        {evidence.snippet && (
                          <p className="mt-2 text-[11px] leading-5 text-text-secondary">
                            {evidence.snippet}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm leading-6 text-text-secondary">
                    当前页没有绑定证据引用。若这是仅聊天模式或人工编辑页，导出前请人工确认内容准确性。
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
