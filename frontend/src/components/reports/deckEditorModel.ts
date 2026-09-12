/**
 * Pure helpers and constants for the deck editor.
 *
 * Split out of DeckEditorModal.tsx: label maps, quality/evidence coverage
 * and export-gate computations. No React imports by design.
 */

import type {
  DeckBlock,
  DeckCitationValidation,
  DeckEvidenceCoverage,
  DeckEvidenceReview,
  DeckEvidenceReviewActionItem,
  DeckSlide,
  DeckSpec,
} from '../../api/client'

export const DECK_THEMES = [
  { value: 'default', label: '经典蓝图' },
  { value: 'midnight', label: '深夜简报' },
  { value: 'sunrise', label: '晨曦回顾' },
] as const

export const SLIDE_TYPE_LABELS: Record<string, string> = {
  cover: '封面页',
  agenda: '目录页',
  section: '章节页',
  content: '内容页',
  summary: '总结页',
  closing: '结尾页',
}

export const SLIDE_LAYOUT_LABELS: Record<string, string> = {
  cover: '封面',
  agenda: '目录',
  section: '章节',
  content: '内容',
  two_column: '双栏',
  comparison: '对比',
  timeline: '时间线',
  closing: '结尾',
}

export const BLOCK_KIND_LABELS: Record<string, string> = {
  paragraph: '段落',
  bullet_list: '列表',
  heading: '标题',
  quote: '引用',
  table: '表格',
}

export const BLOCK_ROLE_LABELS: Record<string, string> = {
  summary: '摘要',
  main_points: '核心要点',
  evidence: '证据',
  insight: '洞察',
  callout: '提示',
  speaker_notes: '备注',
}

export const EVIDENCE_COVERAGE_EXCLUDED_SLIDE_TYPES = new Set(['cover', 'outline', 'appendix_sources'])

export function cloneDeck(deck: DeckSpec): DeckSpec {
  return JSON.parse(JSON.stringify(deck)) as DeckSpec
}

export function blockValue(block: DeckBlock): string {
  if (block.kind === 'bullet_list') {
    return (block.content.items ?? []).join('\n')
  }
  if (block.kind === 'chart') {
    const labels = block.content.labels ?? []
    const series = (block.content.datasets ?? []).map((dataset) => dataset.label).join(', ')
    return [
      `标题: ${block.content.title ?? '图表'}`,
      block.content.description ? `说明: ${block.content.description}` : '',
      `类型: ${block.content.chart_type ?? 'unknown'}`,
      labels.length > 0 ? `标签: ${labels.join(', ')}` : '',
      series ? `系列: ${series}` : '',
      '',
      '图表块当前为只读。',
    ]
      .filter(Boolean)
      .join('\n')
  }
  return block.content.text ?? ''
}

export function updateBlockValue(block: DeckBlock, value: string): DeckBlock {
  if (block.kind === 'bullet_list') {
    const items = value
      .split('\n')
      .map((item) => item.trim())
      .filter(Boolean)
    return { ...block, content: { ...block.content, items } }
  }
  if (block.kind === 'chart') {
    return block
  }
  return { ...block, content: { ...block.content, text: value } }
}

export function createEditableBlock(kind: 'paragraph' | 'bullet_list'): DeckBlock {
  const blockId =
    globalThis.crypto?.randomUUID?.() ?? `block_${Date.now()}_${Math.random().toString(16).slice(2)}`
  return {
    id: blockId,
    kind,
    role: kind === 'bullet_list' ? 'main_points' : 'summary',
    content: kind === 'bullet_list' ? { items: [] } : { text: '' },
    editable: true,
  }
}

export function isSlideManuallyConfirmed(slide: DeckSlide): boolean {
  return slide.quality_state !== 'supported' && slide.status.review_state === 'confirmed'
}

export function slideNeedsAttention(slide: DeckSlide): boolean {
  return slide.quality_state !== 'supported' && !isSlideManuallyConfirmed(slide)
}

export function qualityBadgeClass(slide: DeckSlide): string {
  if (isSlideManuallyConfirmed(slide)) {
    return 'border-accent-green/30 bg-accent-green/10 text-accent-green'
  }

  switch (slide.quality_state) {
    case 'supported':
      return 'border-accent-green/30 bg-accent-green/10 text-accent-green'
    case 'manual':
      return 'border-accent-red/30 bg-accent-red/10 text-accent-red'
    default:
      return 'border-amber-400/30 bg-amber-400/10 text-amber-300'
  }
}

export function qualityLabel(slide: DeckSlide): string {
  if (isSlideManuallyConfirmed(slide)) {
    return '已人工确认'
  }

  switch (slide.quality_state) {
    case 'supported':
      return '证据充分'
    case 'manual':
      return '需人工确认'
    default:
      return '证据偏弱'
  }
}

export function sourceModeLabel(sourceMode: DeckSpec['meta']['source_mode']): string {
  return sourceMode === 'kb_plus_chat' ? '知识库 + 聊天' : '仅聊天'
}

export function deckThemeLabel(theme: DeckSpec['meta']['theme']): string {
  return DECK_THEMES.find((item) => item.value === theme)?.label ?? theme
}

export function slideTypeLabel(value: string): string {
  return SLIDE_TYPE_LABELS[value] ?? value
}

export function slideLayoutLabel(value: string): string {
  return SLIDE_LAYOUT_LABELS[value] ?? value
}

export function blockKindLabel(value: string): string {
  return BLOCK_KIND_LABELS[value] ?? value
}

export function blockRoleLabel(value: string): string {
  return BLOCK_ROLE_LABELS[value] ?? value
}

export function previewShellClass(theme: DeckSpec['meta']['theme']): string {
  switch (theme) {
    case 'midnight':
      return 'border-slate-700 bg-gradient-to-br from-slate-950 via-slate-900 to-sky-950 text-slate-100'
    case 'sunrise':
      return 'border-orange-200 bg-gradient-to-br from-orange-50 via-amber-50 to-rose-100 text-orange-950'
    default:
      return 'border-bg-border bg-gradient-to-br from-bg-secondary to-bg-primary text-text-primary'
  }
}

export function previewEyebrowClass(theme: DeckSpec['meta']['theme']): string {
  switch (theme) {
    case 'midnight':
      return 'text-sky-300'
    case 'sunrise':
      return 'text-orange-500'
    default:
      return 'text-accent-blue/70'
  }
}

export function previewCardClass(theme: DeckSpec['meta']['theme']): string {
  switch (theme) {
    case 'midnight':
      return 'border-slate-700/80 bg-slate-900/60'
    case 'sunrise':
      return 'border-orange-200/80 bg-white/70'
    default:
      return 'border-bg-border/80 bg-bg-secondary/60'
  }
}

export function isEvidenceCoverableSlide(slide: DeckSlide, evidenceRefCount: number): boolean {
  if (evidenceRefCount > 0) return true
  return !EVIDENCE_COVERAGE_EXCLUDED_SLIDE_TYPES.has(slide.type)
}

export function buildFallbackDeckEvidenceCoverage(deck: DeckSpec): DeckEvidenceCoverage {
  let coverableSlideCount = 0
  let slidesWithEvidence = 0
  let totalEvidenceRefs = 0
  const unsupportedSlideIds: string[] = []

  const slides = deck.slides.map((slide) => {
    const evidenceRefCount = slide.evidence_refs.length
    const hasEvidence = evidenceRefCount > 0
    const isCoverable = isEvidenceCoverableSlide(slide, evidenceRefCount)

    totalEvidenceRefs += evidenceRefCount
    if (isCoverable) {
      coverableSlideCount += 1
      if (hasEvidence) {
        slidesWithEvidence += 1
      } else {
        unsupportedSlideIds.push(slide.id)
      }
    }

    return {
      slide_id: slide.id,
      slide_type: slide.type,
      evidence_ref_count: evidenceRefCount,
      has_evidence: hasEvidence,
      is_coverable: isCoverable,
      quality_state: slide.quality_state,
    }
  })

  return {
    total_slides: deck.slides.length,
    coverable_slide_count: coverableSlideCount,
    slides_with_evidence: slidesWithEvidence,
    total_evidence_refs: totalEvidenceRefs,
    coverage_ratio: coverableSlideCount ? Number((slidesWithEvidence / coverableSlideCount).toFixed(4)) : 0,
    unsupported_slide_ids: unsupportedSlideIds,
    slides,
  }
}

export function resolveDeckEvidenceCoverage(deck: DeckSpec): DeckEvidenceCoverage {
  return deck.generation.evidence_coverage ?? buildFallbackDeckEvidenceCoverage(deck)
}

export function uniqueStrings(values: string[]): string[] {
  return Array.from(new Set(values.map((value) => value.trim()).filter(Boolean)))
}

export function buildFallbackDeckEvidenceReview(
  deck: DeckSpec,
  evidenceCoverage: DeckEvidenceCoverage,
): DeckEvidenceReview {
  const slidesById = new Map(deck.slides.map((slide) => [slide.id, slide]))
  const sourceTitlesById = new Map(
    deck.source_registry.map((source) => [source.id, source.title.trim()]),
  )
  const needsReviewSlideIds: string[] = []

  const slides = evidenceCoverage.slides.map((item) => {
    const slide = slidesById.get(item.slide_id)
    const refs = slide?.evidence_refs ?? []
    const sourceIds = uniqueStrings(refs.map((ref) => ref.source_id))
    const sourceTitles = uniqueStrings(
      refs.map((ref) => ref.source_title || sourceTitlesById.get(ref.source_id) || ''),
    )
    const needsReview =
      item.is_coverable && (!item.has_evidence || item.quality_state === 'weak_support')

    if (needsReview) {
      needsReviewSlideIds.push(item.slide_id)
    }

    return {
      slide_id: item.slide_id,
      title: slide?.title ?? '',
      slide_type: item.slide_type,
      is_coverable: item.is_coverable,
      has_evidence: item.has_evidence,
      evidence_ref_count: item.evidence_ref_count,
      quality_state: item.quality_state,
      needs_review: needsReview,
      source_ids: sourceIds,
      source_titles: sourceTitles,
    }
  })

  const actionItems: DeckEvidenceReviewActionItem[] = []
  if (evidenceCoverage.unsupported_slide_ids.length > 0) {
    actionItems.push({
      code: 'add_missing_slide_evidence',
      severity: 'warning',
      message: 'Add evidence references to unsupported slides.',
      slide_ids: evidenceCoverage.unsupported_slide_ids,
    })
  }
  if (evidenceCoverage.coverable_slide_count > 0 && evidenceCoverage.total_evidence_refs === 0) {
    actionItems.push({
      code: 'attach_deck_sources',
      severity: 'warning',
      message: 'Attach at least one source before final export.',
      slide_ids: evidenceCoverage.unsupported_slide_ids,
    })
  }

  const weakSupportedIds = slides
    .filter((item) => item.is_coverable && item.has_evidence && item.quality_state === 'weak_support')
    .map((item) => item.slide_id)
  if (weakSupportedIds.length > 0) {
    actionItems.push({
      code: 'review_weak_support',
      severity: 'info',
      message: 'Review slides marked as weakly supported.',
      slide_ids: weakSupportedIds,
    })
  }

  const status =
    evidenceCoverage.coverable_slide_count === 0
      ? 'not_applicable'
      : evidenceCoverage.unsupported_slide_ids.length === 0 && evidenceCoverage.coverage_ratio >= 1
        ? 'supported'
        : 'needs_review'

  return {
    status,
    coverage_ratio: evidenceCoverage.coverage_ratio,
    coverable_slide_count: evidenceCoverage.coverable_slide_count,
    slides_with_evidence: evidenceCoverage.slides_with_evidence,
    unsupported_slide_ids: evidenceCoverage.unsupported_slide_ids,
    needs_review_slide_ids: uniqueStrings(needsReviewSlideIds),
    action_count: actionItems.length,
    action_items: actionItems,
    slides,
  }
}

export function resolveDeckEvidenceReview(
  deck: DeckSpec,
  evidenceCoverage: DeckEvidenceCoverage,
): DeckEvidenceReview {
  return deck.generation.evidence_review ?? buildFallbackDeckEvidenceReview(deck, evidenceCoverage)
}

export function formatCoveragePercent(value: number): string {
  const ratio = Number.isFinite(value) ? Math.max(0, Math.min(1, value)) : 0
  return `${Math.round(ratio * 100)}%`
}

export function evidenceReviewStatusLabel(status: DeckEvidenceReview['status']): string {
  switch (status) {
    case 'supported':
      return 'supported'
    case 'not_applicable':
      return 'not applicable'
    default:
      return 'needs review'
  }
}

export function resolveDeckCitationValidation(deck: DeckSpec): DeckCitationValidation | null {
  return (
    deck.citation_validation ??
    deck.generation.citation_validation ??
    deck.generation.evidence_review?.citation_validation ??
    null
  )
}

export function citationValidationLabel(validation: DeckCitationValidation | null): string {
  if (!validation) return 'unknown'
  return validation.status === 'passed' ? 'passed' : 'failed'
}

export function citationValidationClass(validation: DeckCitationValidation | null): string {
  if (!validation) return 'border-bg-border bg-bg-tertiary text-text-secondary'
  return validation.can_export
    ? 'border-accent-green/30 bg-accent-green/10 text-accent-green'
    : 'border-accent-red/30 bg-accent-red/10 text-accent-red'
}

export interface DeckBlockEvidenceBinding {
  blockId: string
  label: string
  sourceTitles: string[]
  evidenceRefIds: string[]
}

export interface DeckExportGateDecision {
  allowed: boolean
  allowUnsafeExport: boolean
  overrideReason?: string
}

export function buildDeckExportGateIssues(deck: DeckSpec): string[] {
  const issues: string[] = []
  const validation = resolveDeckCitationValidation(deck)
  if (validation && !validation.can_export) {
    issues.push(`Citation validation failed with ${validation.issue_count} issue(s).`)
  }
  if (deck.meta.source_mode === 'chat_only') {
    issues.push('Deck uses chat-only source mode and has no knowledge-base evidence validation.')
  }
  const weakSlides = deck.slides.filter((slide) => slideNeedsAttention(slide))
  if (weakSlides.length > 0) {
    issues.push(`${weakSlides.length} slide(s) still have weak evidence or need manual confirmation.`)
  }
  return issues
}

export function blockEvidenceRefIds(block: DeckBlock, slide: DeckSlide): string[] {
  const explicitRefIds = new Set(block.content.evidence_ref_ids ?? [])
  const explicitSourceIds = new Set(block.content.evidence_source_ids ?? [])
  const explicitExcerptIds = new Set(block.content.evidence_excerpt_ids ?? [])
  const matchedIds = slide.evidence_refs
    .filter((ref) => {
      if (explicitRefIds.has(ref.id)) return true
      if (explicitSourceIds.has(ref.source_id)) return true
      return Boolean(ref.excerpt_id && explicitExcerptIds.has(ref.excerpt_id))
    })
    .map((ref) => ref.id)
  return uniqueStrings([...explicitRefIds, ...matchedIds])
}

export function buildBlockEvidenceBindings(slide: DeckSlide): DeckBlockEvidenceBinding[] {
  const refsById = new Map(slide.evidence_refs.map((ref) => [ref.id, ref]))
  return slide.blocks.map((block) => {
    const evidenceRefIds = blockEvidenceRefIds(block, slide)
    const sourceTitles = uniqueStrings(
      evidenceRefIds.map((refId) => refsById.get(refId)?.source_title ?? ''),
    )
    return {
      blockId: block.id,
      label: `${blockKindLabel(block.kind)} / ${blockRoleLabel(block.role)}`,
      sourceTitles,
      evidenceRefIds,
    }
  })
}
