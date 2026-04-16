import React, { useEffect, useState } from 'react'
import { FileText, Globe, ChevronDown, ChevronUp, Eye, Image as ImageIcon, Link2, Loader2, Paperclip, ThumbsDown, ThumbsUp } from 'lucide-react'
import { buildRetrievalSourceKey, getRetrievalFeedback, setRetrievalFeedback } from '../../api/client'
import type { RetrievalFeedbackValue, SourceItem } from '../../api/client'
import { DocumentPreviewModal } from './DocumentPreviewModal'
import { useChatStore } from '../../stores/chatStore'

interface CitationPanelProps {
  sources: SourceItem[]
  panelId?: string
  answerGroupId?: string
  streaming?: boolean
}

export const CitationPanel: React.FC<CitationPanelProps> = ({
  sources,
  panelId,
  answerGroupId,
  streaming,
}) => {
  const currentSessionId = useChatStore((state) => state.currentSessionId)
  const [previewSource, setPreviewSource] = useState<SourceItem | null>(null)
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null)
  const [sourceFeedbackMap, setSourceFeedbackMap] = useState<Record<string, RetrievalFeedbackValue>>({})
  const [savingSourceKey, setSavingSourceKey] = useState<string | null>(null)

  if (!sources || sources.length === 0) return null

  const docSources = sources.filter((s) => s.type === 'doc')
  const webSources = sources.filter((s) => s.type === 'web')
  const attachmentSources = sources.filter((s) => s.type === 'attachment')

  useEffect(() => {
    if (!currentSessionId || !panelId || !answerGroupId) {
      setSourceFeedbackMap({})
      return
    }
    let disposed = false
    getRetrievalFeedback(currentSessionId, panelId, answerGroupId)
      .then((items) => {
        if (disposed) return
        const nextMap: Record<string, RetrievalFeedbackValue> = {}
        items.forEach((item) => {
          nextMap[item.source_key] = item.feedback_value
        })
        setSourceFeedbackMap(nextMap)
      })
      .catch(() => {
        if (!disposed) setSourceFeedbackMap({})
      })
    return () => {
      disposed = true
    }
  }, [currentSessionId, panelId, answerGroupId])

  const handleSourceFeedback = async (source: SourceItem, value: 1 | -1) => {
    if (!currentSessionId || !panelId || !answerGroupId) return
    const sourceKey = buildRetrievalSourceKey(source)
    const currentValue = sourceFeedbackMap[sourceKey] ?? 0
    const nextValue: RetrievalFeedbackValue = currentValue === value ? 0 : value

    setSavingSourceKey(sourceKey)
    setSourceFeedbackMap((current) => ({
      ...current,
      [sourceKey]: nextValue,
    }))
    try {
      const feedback = await setRetrievalFeedback(currentSessionId, {
        panel_id: panelId,
        answer_group_id: answerGroupId,
        source,
        value: nextValue,
      })
      setSourceFeedbackMap((current) => ({
        ...current,
        [feedback.source_key]: feedback.feedback_value,
      }))
    } catch {
      setSourceFeedbackMap((current) => ({
        ...current,
        [sourceKey]: currentValue,
      }))
    } finally {
      setSavingSourceKey(null)
    }
  }

  const renderSourceFeedback = (source: SourceItem, accent: 'blue' | 'amber' | 'green') => {
    const sourceKey = buildRetrievalSourceKey(source)
    const feedbackValue = sourceFeedbackMap[sourceKey] ?? 0
    const isSaving = savingSourceKey === sourceKey
    const activeUpClass =
      accent === 'blue'
        ? 'text-accent-blue'
        : accent === 'amber'
          ? 'text-amber-300'
          : 'text-accent-green'
    const activeDownClass = 'text-accent-red'

    return (
      <div className="mt-2 flex items-center gap-1.5 text-[10px]">
        <button
          type="button"
          onClick={() => {
            void handleSourceFeedback(source, 1)
          }}
          disabled={isSaving}
          className={`inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 transition-colors ${
            feedbackValue === 1
              ? activeUpClass
              : 'text-text-secondary/55 hover:bg-bg-hover hover:text-text-secondary'
          }`}
          title="相关"
        >
          {isSaving && feedbackValue === 1 ? <Loader2 size={10} className="animate-spin" /> : <ThumbsUp size={10} />}
          相关
        </button>
        <button
          type="button"
          onClick={() => {
            void handleSourceFeedback(source, -1)
          }}
          disabled={isSaving}
          className={`inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 transition-colors ${
            feedbackValue === -1
              ? activeDownClass
              : 'text-text-secondary/55 hover:bg-bg-hover hover:text-text-secondary'
          }`}
          title="不相关"
        >
          {isSaving && feedbackValue === -1 ? <Loader2 size={10} className="animate-spin" /> : <ThumbsDown size={10} />}
          不相关
        </button>
      </div>
    )
  }

  const renderRetrievalMeta = (source: SourceItem) => {
    const bits: string[] = []
    const positiveCount = typeof source.feedback_positive_count === 'number' ? source.feedback_positive_count : 0
    const negativeCount = typeof source.feedback_negative_count === 'number' ? source.feedback_negative_count : 0
    const netFeedback = typeof source.feedback_net === 'number' ? source.feedback_net : positiveCount - negativeCount
    const feedbackBoost = typeof source.feedback_boost === 'number' ? source.feedback_boost : 0
    const hasFeedbackSignal =
      positiveCount > 0 ||
      negativeCount > 0 ||
      netFeedback !== 0 ||
      Math.abs(feedbackBoost) >= 0.0005

    if (source.retrieval_mode) bits.push(source.retrieval_mode)
    if (source.search_channel && source.search_channel !== source.retrieval_mode) {
      bits.push(source.search_channel)
    }
    if (typeof source.score === 'number') bits.push(`score ${source.score.toFixed(3)}`)
    if (hasFeedbackSignal) {
      bits.push(`反馈 +${positiveCount}/-${negativeCount}`)
      bits.push(`净值 ${netFeedback >= 0 ? '+' : ''}${netFeedback}`)
      bits.push(`boost ${feedbackBoost >= 0 ? '+' : ''}${feedbackBoost.toFixed(3)}`)
    }
    if (bits.length === 0 && (!source.matched_terms || source.matched_terms.length === 0)) {
      return null
    }

    return (
      <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[10px] text-text-secondary/60">
        {bits.map((bit) => (
          <span key={bit} className="rounded-full bg-bg-secondary px-1.5 py-0.5">
            {bit}
          </span>
        ))}
        {source.matched_terms && source.matched_terms.length > 0 && (
          <span className="truncate">
            命中词: {source.matched_terms.slice(0, 4).join(' / ')}
          </span>
        )}
      </div>
    )
  }

  const jumpToAnswerGroup = (answerGroupId?: string) => {
    const targetGroupId = (answerGroupId ?? '').trim()
    if (!targetGroupId) return

    const target = Array.from(
      document.querySelectorAll<HTMLElement>('[data-role="user"][data-answer-group-id]'),
    ).find((element) => element.dataset.answerGroupId === targetGroupId)

    target?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  return (
    <>
      <div className="mt-4 space-y-1.5">
        {/* Section label */}
        <div className="flex items-center gap-1.5 mb-2">
          <div className="h-px flex-1 bg-bg-border/60" />
          <span className="text-[10px] font-medium text-text-secondary/60 uppercase tracking-wider px-2">
            引用来源 {streaming && <span className="animate-pulse">•</span>}
          </span>
          <div className="h-px flex-1 bg-bg-border/60" />
        </div>

        {/* Doc citations */}
        {docSources.length > 0 && (
          <div className="space-y-1.5">
            {docSources.map((src, i) => {
              const globalIdx = sources.indexOf(src)
              const citationNum = src.index ?? globalIdx + 1
              const isExpanded = expandedIdx === globalIdx

              return (
                <div
                  key={`doc-${i}`}
                  className="group relative rounded-lg border border-bg-border bg-bg-secondary/40 hover:bg-bg-secondary/70 hover:border-accent-blue/30 transition-all duration-150"
                >
                  <div className="flex items-start gap-2.5 px-3 py-2.5">
                    {/* Citation number badge */}
                    <span className="shrink-0 w-5 h-5 flex items-center justify-center rounded-full bg-accent-blue/15 text-accent-blue text-[10px] font-bold mt-0.5">
                      {citationNum}
                    </span>

                    <FileText size={13} className="text-accent-blue/60 shrink-0 mt-0.5" />

                    <div className="min-w-0 flex-1">
                      <p className="font-medium text-text-primary/90 text-xs truncate leading-tight">
                        {src.title}
                      </p>
                      {src.snippet && (
                        <p
                          className={`text-text-secondary/70 mt-1 leading-relaxed text-[11px] ${
                            isExpanded ? '' : 'line-clamp-2'
                          }`}
                        >
                          {src.snippet}
                        </p>
                      )}
                      {src.snippet && src.snippet.length > 120 && (
                        <button
                          onClick={() => setExpandedIdx(isExpanded ? null : globalIdx)}
                          className="mt-1 flex items-center gap-1 text-[10px] text-accent-blue/70 hover:text-accent-blue transition-colors"
                        >
                          {isExpanded ? (
                            <><ChevronUp size={10} /> 收起</>
                          ) : (
                            <><ChevronDown size={10} /> 展开</>
                          )}
                        </button>
                      )}
                      {renderRetrievalMeta(src)}
                      {!streaming && renderSourceFeedback(src, 'blue')}
                    </div>

                    {/* Preview button */}
                    <button
                      onClick={() => setPreviewSource(src)}
                      className="shrink-0 p-1 rounded-md text-text-secondary/40 hover:text-accent-blue hover:bg-accent-blue/10 opacity-0 group-hover:opacity-100 transition-all"
                      title="预览文档片段"
                    >
                      <Eye size={12} />
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {/* Attachment citations */}
        {attachmentSources.length > 0 && (
          <div className="space-y-1.5">
            {attachmentSources.map((src, i) => {
              const globalIdx = sources.indexOf(src)
              const citationNum = src.index ?? globalIdx + 1
              const isExpanded = expandedIdx === globalIdx
              const isImage = src.attachment_kind === 'image'

              return (
                <div
                  key={`attachment-${i}`}
                  className="group relative rounded-lg border border-bg-border bg-bg-secondary/40 hover:bg-bg-secondary/70 hover:border-amber-400/30 transition-all duration-150"
                >
                  <div className="flex items-start gap-2.5 px-3 py-2.5">
                    <span className="shrink-0 w-5 h-5 flex items-center justify-center rounded-full bg-amber-400/15 text-amber-300 text-[10px] font-bold mt-0.5">
                      {citationNum}
                    </span>

                    {isImage ? (
                      <ImageIcon size={13} className="text-amber-300/70 shrink-0 mt-0.5" />
                    ) : (
                      <Paperclip size={13} className="text-amber-300/70 shrink-0 mt-0.5" />
                    )}

                    <div className="min-w-0 flex-1">
                      <p className="font-medium text-text-primary/90 text-xs truncate leading-tight">
                        {src.title}
                      </p>
                      {src.snippet && (
                        <p
                          className={`text-text-secondary/70 mt-1 leading-relaxed text-[11px] ${
                            isExpanded ? '' : 'line-clamp-2'
                          }`}
                        >
                          {src.snippet}
                        </p>
                      )}
                      <div className="mt-1 flex flex-wrap items-center gap-2 text-[10px] text-text-secondary/60">
                        <span>{isImage ? '会话图片' : '会话附件'}</span>
                        {src.media_type && <span>{src.media_type}</span>}
                      </div>
                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        {src.snippet && src.snippet.length > 120 && (
                          <button
                            onClick={() => setExpandedIdx(isExpanded ? null : globalIdx)}
                            className="flex items-center gap-1 text-[10px] text-amber-300/80 hover:text-amber-200 transition-colors"
                          >
                            {isExpanded ? (
                              <><ChevronUp size={10} /> 收起</>
                            ) : (
                              <><ChevronDown size={10} /> 展开</>
                            )}
                          </button>
                        )}
                        {src.answer_group_id && (
                          <button
                            onClick={() => jumpToAnswerGroup(src.answer_group_id)}
                            className="flex items-center gap-1 text-[10px] text-amber-300/80 hover:text-amber-200 transition-colors"
                          >
                            <Link2 size={10} />
                            回到原附件
                          </button>
                        )}
                      </div>
                      {!streaming && renderSourceFeedback(src, 'amber')}
                    </div>

                    <button
                      onClick={() => setPreviewSource(src)}
                      className="shrink-0 p-1 rounded-md text-text-secondary/40 hover:text-amber-300 hover:bg-amber-400/10 opacity-0 group-hover:opacity-100 transition-all"
                      title="预览附件来源"
                    >
                      <Eye size={12} />
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {/* Web citations */}
        {webSources.length > 0 && (
          <div className="space-y-1.5">
            {webSources.map((src, i) => {
              const globalIdx = sources.indexOf(src)
              const citationNum = src.index ?? globalIdx + 1
              const isExpanded = expandedIdx === globalIdx

              return (
                <div
                  key={`web-${i}`}
                  className="group relative rounded-lg border border-bg-border bg-bg-secondary/40 hover:bg-bg-secondary/70 hover:border-accent-green/30 transition-all duration-150"
                >
                  <div className="flex items-start gap-2.5 px-3 py-2.5">
                    <span className="shrink-0 w-5 h-5 flex items-center justify-center rounded-full bg-accent-green/15 text-accent-green text-[10px] font-bold mt-0.5">
                      {citationNum}
                    </span>

                    <Globe size={13} className="text-accent-green/60 shrink-0 mt-0.5" />

                    <div className="min-w-0 flex-1">
                      {src.url ? (
                        <a
                          href={src.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="font-medium text-xs text-accent-blue hover:underline underline-offset-2 truncate block leading-tight"
                        >
                          {src.title}
                        </a>
                      ) : (
                        <p className="font-medium text-text-primary/90 text-xs truncate leading-tight">
                          {src.title}
                        </p>
                      )}
                      {src.snippet && (
                        <p
                          className={`text-text-secondary/70 mt-1 leading-relaxed text-[11px] ${
                            isExpanded ? '' : 'line-clamp-2'
                          }`}
                        >
                          {src.snippet}
                        </p>
                      )}
                      {src.url && (
                        <p className="text-text-secondary/30 mt-0.5 truncate text-[10px]">{src.url}</p>
                      )}
                      {src.snippet && src.snippet.length > 120 && (
                        <button
                          onClick={() => setExpandedIdx(isExpanded ? null : globalIdx)}
                          className="mt-1 flex items-center gap-1 text-[10px] text-accent-green/70 hover:text-accent-green transition-colors"
                        >
                          {isExpanded ? (
                            <><ChevronUp size={10} /> 收起</>
                          ) : (
                            <><ChevronDown size={10} /> 展开</>
                          )}
                        </button>
                      )}
                      {renderRetrievalMeta(src)}
                      {!streaming && renderSourceFeedback(src, 'green')}
                    </div>

                    <button
                      onClick={() => setPreviewSource(src)}
                      className="shrink-0 p-1 rounded-md text-text-secondary/40 hover:text-accent-green hover:bg-accent-green/10 opacity-0 group-hover:opacity-100 transition-all"
                      title="预览来源"
                    >
                      <Eye size={12} />
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Document preview modal */}
      {previewSource && (
        <DocumentPreviewModal
          source={previewSource}
          onClose={() => setPreviewSource(null)}
        />
      )}
    </>
  )
}
