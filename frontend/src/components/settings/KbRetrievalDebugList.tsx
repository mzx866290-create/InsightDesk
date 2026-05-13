import React from 'react'
import type { RetrievalDebugItem } from '../../api/client'

type KbRetrievalDebugTone = 'blue' | 'green' | 'amber'

const TONE_CLASS_NAMES: Record<KbRetrievalDebugTone, string> = {
  blue: 'bg-accent-blue/15 text-accent-blue',
  green: 'bg-accent-green/15 text-accent-green',
  amber: 'bg-amber-300/15 text-amber-300',
}

interface KbRetrievalDebugListProps {
  title: string
  items?: readonly RetrievalDebugItem[]
  tone?: KbRetrievalDebugTone
}

function RetrievalFeedbackSummary({ item }: { item: RetrievalDebugItem }) {
  const positiveCount = typeof item.feedback_positive_count === 'number' ? item.feedback_positive_count : 0
  const negativeCount = typeof item.feedback_negative_count === 'number' ? item.feedback_negative_count : 0
  const netFeedback = typeof item.feedback_net === 'number' ? item.feedback_net : positiveCount - negativeCount
  const feedbackBoost = typeof item.feedback_boost === 'number' ? item.feedback_boost : 0
  const hasFeedbackSignal =
    positiveCount > 0 ||
    negativeCount > 0 ||
    netFeedback !== 0 ||
    Math.abs(feedbackBoost) >= 0.0005

  if (!hasFeedbackSignal) return null

  return (
    <div className="flex flex-wrap gap-1">
      <span className="rounded-full bg-bg-tertiary px-1.5 py-0.5 text-[10px] text-text-secondary">
        反馈 +{positiveCount}/-{negativeCount}
      </span>
      <span className="rounded-full bg-bg-tertiary px-1.5 py-0.5 text-[10px] text-text-secondary">
        净值 {netFeedback >= 0 ? '+' : ''}{netFeedback}
      </span>
      <span className="rounded-full bg-bg-tertiary px-1.5 py-0.5 text-[10px] text-text-secondary">
        boost {feedbackBoost >= 0 ? '+' : ''}{feedbackBoost.toFixed(3)}
      </span>
    </div>
  )
}

export function KbRetrievalDebugList({ title, items, tone = 'blue' }: KbRetrievalDebugListProps) {
  if (!items || items.length === 0) return null

  const toneClassName = TONE_CLASS_NAMES[tone]

  return (
    <div className="space-y-1.5 mt-2">
      <p className="text-[11px] font-medium text-text-secondary/70">{title}</p>
      {items.map((item, index) => (
        <div key={`${title}-${index}`} className="bg-bg-secondary/60 rounded-md p-2 space-y-1">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-1.5 min-w-0">
              <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${toneClassName}`}>
                #{item.rank ?? index + 1}
              </span>
              <p className="text-[11px] font-medium text-accent-blue/80 truncate">{item.source}</p>
            </div>
            <span className="text-[10px] text-text-secondary/70 whitespace-nowrap">
              分数 {Number(item.score ?? 0).toFixed(3)}
            </span>
          </div>
          <RetrievalFeedbackSummary item={item} />
          <p className="text-[11px] text-text-secondary/80 leading-relaxed">{item.snippet}</p>
          {item.matched_terms && item.matched_terms.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {item.matched_terms.slice(0, 6).map((term) => (
                <span key={term} className="rounded-full bg-bg-tertiary px-1.5 py-0.5 text-[10px] text-text-secondary">
                  {term}
                </span>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
