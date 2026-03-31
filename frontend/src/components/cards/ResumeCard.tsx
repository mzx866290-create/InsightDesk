import React, { useState } from 'react'
import { User, Star, ChevronDown, ChevronUp, Award } from 'lucide-react'

export interface ResumeCardData {
  name?: string
  position?: string
  skills?: string[]
  score?: number
  summary?: string
  experience?: string
  education?: string
  highlights?: string[]
}

interface ResumeCardProps {
  data: ResumeCardData
  streaming?: boolean
}

export const ResumeCard: React.FC<ResumeCardProps> = ({ data, streaming }) => {
  const [expanded, setExpanded] = useState(false)

  const scoreColor =
    data.score === undefined
      ? 'text-text-secondary'
      : data.score >= 80
      ? 'text-accent-green'
      : data.score >= 60
      ? 'text-yellow-400'
      : 'text-red-400'

  return (
    <div className="my-3 rounded-xl border border-accent-blue/25 bg-bg-secondary/60 overflow-hidden shadow-sm">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 bg-accent-blue/8 border-b border-accent-blue/15">
        <div className="w-9 h-9 rounded-full bg-accent-blue/20 flex items-center justify-center shrink-0">
          <User size={16} className="text-accent-blue" />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold text-text-primary truncate">
            {data.name ?? '候选人简历'}
            {streaming && <span className="ml-1 animate-pulse text-text-secondary">…</span>}
          </h3>
          {data.position && (
            <p className="text-xs text-text-secondary/80 truncate">{data.position}</p>
          )}
        </div>
        {data.score !== undefined && (
          <div className="shrink-0 flex flex-col items-center">
            <span className={`text-xl font-bold ${scoreColor}`}>{data.score}</span>
            <span className="text-[10px] text-text-secondary/60">匹配分</span>
          </div>
        )}
      </div>

      {/* Body */}
      <div className="px-4 py-3 space-y-3 text-xs">
        {/* Skills */}
        {data.skills && data.skills.length > 0 && (
          <div>
            <p className="text-[10px] uppercase font-semibold text-text-secondary/60 tracking-wider mb-1.5">
              技能标签
            </p>
            <div className="flex flex-wrap gap-1.5">
              {data.skills.map((skill, i) => (
                <span
                  key={i}
                  className="px-2 py-0.5 rounded-full text-[11px] bg-accent-blue/15 text-accent-blue border border-accent-blue/20"
                >
                  {skill}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Summary */}
        {data.summary && (
          <div>
            <p className="text-[10px] uppercase font-semibold text-text-secondary/60 tracking-wider mb-1">
              综合评价
            </p>
            <p className="text-text-primary/80 leading-relaxed">{data.summary}</p>
          </div>
        )}

        {/* Highlights */}
        {data.highlights && data.highlights.length > 0 && (
          <div>
            <p className="text-[10px] uppercase font-semibold text-text-secondary/60 tracking-wider mb-1.5">
              亮点
            </p>
            <ul className="space-y-1">
              {data.highlights.map((h, i) => (
                <li key={i} className="flex items-start gap-1.5">
                  <Award size={10} className="text-accent-blue/60 shrink-0 mt-0.5" />
                  <span className="text-text-primary/80">{h}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Expandable details */}
        {(data.experience || data.education) && (
          <div>
            <button
              onClick={() => setExpanded((v) => !v)}
              className="flex items-center gap-1 text-[11px] text-accent-blue/70 hover:text-accent-blue transition-colors"
            >
              {expanded ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
              {expanded ? '收起详情' : '展开详情'}
            </button>
            {expanded && (
              <div className="mt-2 space-y-2 border-t border-bg-border pt-2">
                {data.experience && (
                  <div>
                    <p className="text-[10px] uppercase font-semibold text-text-secondary/60 tracking-wider mb-1">
                      工作经历
                    </p>
                    <p className="text-text-primary/80 leading-relaxed whitespace-pre-wrap">
                      {data.experience}
                    </p>
                  </div>
                )}
                {data.education && (
                  <div>
                    <p className="text-[10px] uppercase font-semibold text-text-secondary/60 tracking-wider mb-1">
                      教育背景
                    </p>
                    <p className="text-text-primary/80 leading-relaxed whitespace-pre-wrap">
                      {data.education}
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Score bar */}
      {data.score !== undefined && (
        <div className="px-4 pb-3">
          <div className="flex items-center gap-2">
            <div className="flex-1 h-1.5 rounded-full bg-bg-tertiary overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-700 ${
                  data.score >= 80
                    ? 'bg-accent-green'
                    : data.score >= 60
                    ? 'bg-yellow-400'
                    : 'bg-red-400'
                }`}
                style={{ width: `${Math.min(100, data.score)}%` }}
              />
            </div>
            <div className="flex">
              {[1, 2, 3, 4, 5].map((star) => (
                <Star
                  key={star}
                  size={10}
                  className={
                    star <= Math.round((data.score ?? 0) / 20)
                      ? 'text-yellow-400 fill-yellow-400'
                      : 'text-text-secondary/30'
                  }
                />
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
