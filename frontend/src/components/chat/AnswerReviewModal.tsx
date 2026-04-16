import React from 'react'
import { AlertCircle, ArrowUpCircle, Check, Loader2, RefreshCcw, Scale, Sparkles } from 'lucide-react'
import type {
  AnswerGroupReviewComparison,
  AnswerGroupReviewResponse,
  AnswerGroupReviewResponseItem,
} from '../../api/client'
import { Modal } from '../ui/Modal'

interface AnswerReviewModalProps {
  open: boolean
  review: AnswerGroupReviewResponse | null
  loading: boolean
  error: string | null
  primaryPanelId?: string
  promotingPanelId?: string | null
  promotingRecommended?: boolean
  onClose: () => void
  onRefresh: () => void
  onPromotePanel: (panelId: string) => void
  onPromoteRecommended: () => void
}

function confidenceMeta(confidenceLabel: string): string {
  const normalized = confidenceLabel.trim().toLowerCase()
  if (normalized === 'high') return 'bg-accent-green/15 text-accent-green'
  if (normalized === 'medium') return 'bg-amber-300/15 text-amber-300'
  return 'bg-accent-red/15 text-accent-red'
}

function renderComparison(comparison: AnswerGroupReviewComparison) {
  return (
    <div
      key={comparison.against_panel_id}
      className="rounded-xl border border-bg-border bg-bg-tertiary/50 px-4 py-3 space-y-2"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-sm font-medium text-text-primary">
          对比 {comparison.against_panel_id}
          {comparison.against_model_id ? (
            <span className="ml-2 text-xs text-text-secondary">{comparison.against_model_id}</span>
          ) : null}
        </div>
        <span className="rounded-full bg-accent-blue/10 px-2 py-0.5 text-[11px] text-accent-blue">
          score gap {comparison.score_gap >= 0 ? '+' : ''}{comparison.score_gap.toFixed(2)}
        </span>
      </div>
      {comparison.recommended_advantages.length > 0 ? (
        <div className="space-y-1">
          <p className="text-[11px] font-medium text-text-secondary/70">推荐优势</p>
          <div className="flex flex-wrap gap-1.5">
            {comparison.recommended_advantages.map((item) => (
              <span
                key={item}
                className="rounded-full bg-accent-green/10 px-2 py-1 text-[11px] text-accent-green"
              >
                {item}
              </span>
            ))}
          </div>
        </div>
      ) : null}
      {comparison.tradeoffs.length > 0 ? (
        <div className="space-y-1">
          <p className="text-[11px] font-medium text-text-secondary/70">权衡点</p>
          <div className="space-y-1">
            {comparison.tradeoffs.map((item) => (
              <p key={item} className="text-xs text-text-secondary">
                {item}
              </p>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  )
}

function renderResponseCard(
  item: AnswerGroupReviewResponseItem,
  {
    primaryPanelId,
    recommendedPanelId,
    promotingPanelId,
    onPromotePanel,
  }: {
    primaryPanelId: string
    recommendedPanelId: string
    promotingPanelId: string | null | undefined
    onPromotePanel: (panelId: string) => void
  },
) {
  const isPrimary = item.panel_id === primaryPanelId
  const isRecommended = item.panel_id === recommendedPanelId
  const isPromoting = promotingPanelId === item.panel_id

  return (
    <div
      key={item.panel_id}
      className={`rounded-2xl border px-4 py-4 space-y-3 ${
        isRecommended
          ? 'border-accent-blue/40 bg-accent-blue/5'
          : 'border-bg-border bg-bg-tertiary/40'
      }`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold text-text-primary">{item.panel_id}</h3>
            {isPrimary ? (
              <span className="rounded-full bg-accent-green/15 px-2 py-0.5 text-[10px] text-accent-green">
                当前主答案
              </span>
            ) : null}
            {isRecommended ? (
              <span className="rounded-full bg-accent-blue/15 px-2 py-0.5 text-[10px] text-accent-blue">
                推荐答案
              </span>
            ) : null}
          </div>
          {item.model_id ? (
            <p className="mt-1 text-xs text-text-secondary truncate">{item.model_id}</p>
          ) : null}
        </div>
        <div className="flex items-center gap-2">
          <div className="rounded-xl bg-bg-secondary px-3 py-2 text-right">
            <div className="text-[10px] uppercase tracking-wide text-text-secondary/70">Score</div>
            <div className="text-sm font-semibold text-text-primary">{item.score.toFixed(2)}</div>
          </div>
          <button
            type="button"
            onClick={() => onPromotePanel(item.panel_id)}
            disabled={isPrimary || isPromoting}
            className="inline-flex items-center gap-1 rounded-lg border border-bg-border px-3 py-2 text-xs text-text-primary transition-colors hover:border-accent-blue/40 hover:text-accent-blue disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isPromoting ? <Loader2 size={12} className="animate-spin" /> : <ArrowUpCircle size={12} />}
            设为主答案
          </button>
        </div>
      </div>

      <div className="flex flex-wrap gap-1.5 text-[11px] text-text-secondary">
        <span className="rounded-full bg-bg-secondary px-2 py-1">证据 {item.source_count}</span>
        <span className="rounded-full bg-bg-secondary px-2 py-1">
          workflow {item.completed_workflow_count}/{item.workflow_node_count}
        </span>
        <span className="rounded-full bg-bg-secondary px-2 py-1">长度 {item.content_length}</span>
      </div>

      <p className="rounded-xl bg-bg-secondary/70 px-3 py-3 text-sm leading-relaxed text-text-primary">
        {item.excerpt || '暂无摘要'}
      </p>

      {item.strengths.length > 0 ? (
        <div className="space-y-1">
          <p className="text-[11px] font-medium text-text-secondary/70">优势</p>
          <div className="flex flex-wrap gap-1.5">
            {item.strengths.map((strength) => (
              <span
                key={strength}
                className="rounded-full bg-accent-green/10 px-2 py-1 text-[11px] text-accent-green"
              >
                {strength}
              </span>
            ))}
          </div>
        </div>
      ) : null}

      {item.concerns.length > 0 ? (
        <div className="space-y-1">
          <p className="text-[11px] font-medium text-text-secondary/70">风险</p>
          <div className="flex flex-wrap gap-1.5">
            {item.concerns.map((concern) => (
              <span
                key={concern}
                className="rounded-full bg-accent-red/10 px-2 py-1 text-[11px] text-accent-red"
              >
                {concern}
              </span>
            ))}
          </div>
        </div>
      ) : null}

      {Object.keys(item.score_breakdown ?? {}).length > 0 ? (
        <div className="space-y-1">
          <p className="text-[11px] font-medium text-text-secondary/70">评分构成</p>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(item.score_breakdown).map(([key, value]) => (
              <span key={key} className="rounded-full bg-bg-secondary px-2 py-1 text-[11px] text-text-secondary">
                {key} {value >= 0 ? '+' : ''}{value}
              </span>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  )
}

export const AnswerReviewModal: React.FC<AnswerReviewModalProps> = ({
  open,
  review,
  loading,
  error,
  primaryPanelId = '',
  promotingPanelId,
  promotingRecommended = false,
  onClose,
  onRefresh,
  onPromotePanel,
  onPromoteRecommended,
}) => {
  return (
    <Modal open={open} onClose={onClose} title="答案评审" width="max-w-6xl">
      {loading ? (
        <div className="flex items-center justify-center gap-2 py-14 text-sm text-text-secondary">
          <Loader2 size={16} className="animate-spin" />
          正在加载评审结果
        </div>
      ) : error ? (
        <div className="space-y-4">
          <div className="rounded-xl border border-accent-red/30 bg-accent-red/10 px-4 py-3 text-sm text-accent-red">
            {error}
          </div>
          <button
            type="button"
            onClick={onRefresh}
            className="inline-flex items-center gap-1 rounded-lg border border-bg-border px-3 py-2 text-xs text-text-primary transition-colors hover:border-accent-blue/40 hover:text-accent-blue"
          >
            <RefreshCcw size={12} />
            重新加载
          </button>
        </div>
      ) : review ? (
        <div className="space-y-5">
          <div className="rounded-2xl border border-bg-border bg-bg-tertiary/40 p-4 space-y-3">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="inline-flex items-center gap-1 rounded-full bg-accent-blue/10 px-2.5 py-1 text-[11px] text-accent-blue">
                    <Sparkles size={12} />
                    推荐 {review.recommended_panel_id}
                  </span>
                  <span className={`rounded-full px-2.5 py-1 text-[11px] ${confidenceMeta(review.confidence_label)}`}>
                    置信度 {review.confidence_label} {review.confidence.toFixed(2)}
                  </span>
                  {review.recommended_model_id ? (
                    <span className="rounded-full bg-bg-secondary px-2.5 py-1 text-[11px] text-text-secondary">
                      {review.recommended_model_id}
                    </span>
                  ) : null}
                </div>
                <p className="text-sm leading-relaxed text-text-primary">
                  {review.summary || review.why_recommended || '暂无评审摘要'}
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={onRefresh}
                  className="inline-flex items-center gap-1 rounded-lg border border-bg-border px-3 py-2 text-xs text-text-primary transition-colors hover:border-accent-blue/40 hover:text-accent-blue"
                >
                  <RefreshCcw size={12} />
                  刷新
                </button>
                <button
                  type="button"
                  onClick={onPromoteRecommended}
                  disabled={promotingRecommended}
                  className="inline-flex items-center gap-1 rounded-lg bg-accent-blue px-3 py-2 text-xs font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-60"
                >
                  {promotingRecommended ? <Loader2 size={12} className="animate-spin" /> : <Check size={12} />}
                  采用推荐答案
                </button>
              </div>
            </div>

            {review.decision_factors.length > 0 ? (
              <div className="grid gap-2 md:grid-cols-2">
                {review.decision_factors.map((factor) => (
                  <div key={`${factor.factor}-${factor.winner_panel_id}`} className="rounded-xl bg-bg-secondary/70 px-3 py-3">
                    <div className="flex items-center gap-2 text-xs font-medium text-text-primary">
                      <Scale size={12} className="text-accent-blue" />
                      {factor.factor}
                    </div>
                    <p className="mt-1 text-xs leading-relaxed text-text-secondary">{factor.detail}</p>
                  </div>
                ))}
              </div>
            ) : null}
          </div>

          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm font-medium text-text-primary">
              <Sparkles size={14} className="text-accent-blue" />
              面板答案对比
            </div>
            <div className="grid gap-3 xl:grid-cols-2">
              {review.responses.map((item) =>
                renderResponseCard(item, {
                  primaryPanelId,
                  recommendedPanelId: review.recommended_panel_id,
                  promotingPanelId,
                  onPromotePanel,
                }),
              )}
            </div>
          </div>

          {review.comparisons.length > 0 ? (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-sm font-medium text-text-primary">
                <AlertCircle size={14} className="text-accent-orange" />
                差异与权衡
              </div>
              <div className="grid gap-3 lg:grid-cols-2">
                {review.comparisons.map(renderComparison)}
              </div>
            </div>
          ) : null}
        </div>
      ) : (
        <div className="py-14 text-center text-sm text-text-secondary">暂无可展示的评审结果</div>
      )}
    </Modal>
  )
}
