import React, { useEffect, useMemo, useState } from 'react'
import { GitCompare, RefreshCw } from 'lucide-react'
import type { Panel, PanelMessage } from '../../stores/chatStore'

interface PanelDiffViewProps {
  panels: Panel[]
}

type DiffKind = 'same' | 'add' | 'remove'

interface DiffSegment {
  kind: DiffKind
  text: string
}

interface DiffResult {
  segments: DiffSegment[]
  addedChars: number
  removedChars: number
  fallback: boolean
}

const TOKEN_SPLIT_REGEX = /(\s+)/
const MAX_DIFF_TOKENS = 320
const MAX_DIFF_MATRIX_CELLS = 160000

function findLatestAssistantMessage(panel: Panel): PanelMessage | null {
  for (let index = panel.messages.length - 1; index >= 0; index -= 1) {
    const message = panel.messages[index]
    if (message.role === 'assistant' && message.content.trim()) {
      return message
    }
  }
  return null
}

function tokenizeForDiff(text: string): string[] {
  return text.split(TOKEN_SPLIT_REGEX).filter((token) => token.length > 0)
}

function mergeSegments(segments: DiffSegment[]): DiffSegment[] {
  if (segments.length === 0) return segments
  const merged: DiffSegment[] = [segments[0]]
  for (let index = 1; index < segments.length; index += 1) {
    const current = segments[index]
    const previous = merged[merged.length - 1]
    if (previous.kind === current.kind) {
      previous.text += current.text
    } else {
      merged.push({ ...current })
    }
  }
  return merged
}

function buildDiff(baseText: string, targetText: string): DiffResult {
  if (baseText === targetText) {
    return {
      segments: [{ kind: 'same', text: targetText }],
      addedChars: 0,
      removedChars: 0,
      fallback: false,
    }
  }

  const baseTokens = tokenizeForDiff(baseText).slice(0, MAX_DIFF_TOKENS)
  const targetTokens = tokenizeForDiff(targetText).slice(0, MAX_DIFF_TOKENS)
  const n = baseTokens.length
  const m = targetTokens.length

  if (n === 0 && m === 0) {
    return { segments: [], addedChars: 0, removedChars: 0, fallback: false }
  }

  if (n * m > MAX_DIFF_MATRIX_CELLS) {
    return {
      segments: mergeSegments([
        ...(baseText ? [{ kind: 'remove' as const, text: baseText }] : []),
        ...(targetText ? [{ kind: 'add' as const, text: targetText }] : []),
      ]),
      addedChars: targetText.length,
      removedChars: baseText.length,
      fallback: true,
    }
  }

  const dp: number[][] = Array.from({ length: n + 1 }, () => Array<number>(m + 1).fill(0))
  for (let i = n - 1; i >= 0; i -= 1) {
    for (let j = m - 1; j >= 0; j -= 1) {
      if (baseTokens[i] === targetTokens[j]) {
        dp[i][j] = dp[i + 1][j + 1] + 1
      } else {
        dp[i][j] = Math.max(dp[i + 1][j], dp[i][j + 1])
      }
    }
  }

  let i = 0
  let j = 0
  let addedChars = 0
  let removedChars = 0
  const segments: DiffSegment[] = []

  while (i < n && j < m) {
    if (baseTokens[i] === targetTokens[j]) {
      segments.push({ kind: 'same', text: targetTokens[j] })
      i += 1
      j += 1
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      segments.push({ kind: 'remove', text: baseTokens[i] })
      removedChars += baseTokens[i].length
      i += 1
    } else {
      segments.push({ kind: 'add', text: targetTokens[j] })
      addedChars += targetTokens[j].length
      j += 1
    }
  }

  while (i < n) {
    segments.push({ kind: 'remove', text: baseTokens[i] })
    removedChars += baseTokens[i].length
    i += 1
  }
  while (j < m) {
    segments.push({ kind: 'add', text: targetTokens[j] })
    addedChars += targetTokens[j].length
    j += 1
  }

  return {
    segments: mergeSegments(segments),
    addedChars,
    removedChars,
    fallback: false,
  }
}

const segmentClassMap: Record<DiffKind, string> = {
  same: 'text-text-secondary/85',
  add: 'rounded-sm bg-accent-green/20 text-accent-green',
  remove: 'rounded-sm bg-accent-red/20 text-accent-red line-through decoration-accent-red/70',
}

export const PanelDiffView: React.FC<PanelDiffViewProps> = ({ panels }) => {
  const [baselinePanelId, setBaselinePanelId] = useState<string>(panels[0]?.id ?? '')

  useEffect(() => {
    if (!panels.some((panel) => panel.id === baselinePanelId)) {
      setBaselinePanelId(panels[0]?.id ?? '')
    }
  }, [baselinePanelId, panels])

  const latestByPanel = useMemo(() => {
    const map = new Map<string, PanelMessage | null>()
    panels.forEach((panel) => {
      map.set(panel.id, findLatestAssistantMessage(panel))
    })
    return map
  }, [panels])

  const baselinePanel = panels.find((panel) => panel.id === baselinePanelId) ?? panels[0] ?? null
  const baselineMessage = baselinePanel ? latestByPanel.get(baselinePanel.id) ?? null : null
  const baselineText = baselineMessage?.content ?? ''

  if (panels.length <= 1) {
    return (
      <div className="flex h-full items-center justify-center rounded-2xl border border-dashed border-bg-border bg-bg-tertiary/20 p-8 text-sm text-text-secondary">
        至少需要 2 个面板才能进行对比
      </div>
    )
  }

  return (
    <div className="flex h-full min-h-0 flex-col rounded-2xl border border-bg-border bg-bg-secondary/20 p-3">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-bg-border pb-2">
        <div className="flex items-center gap-2 text-xs text-text-secondary">
          <GitCompare size={13} className="text-accent-blue" />
          <span>多面板 Diff 对比（基线：最新回答）</span>
        </div>
        <div className="flex items-center gap-2">
          <select
            className="input-base text-xs min-w-[180px]"
            value={baselinePanel?.id ?? ''}
            onChange={(event) => setBaselinePanelId(event.target.value)}
          >
            {panels.map((panel, index) => (
              <option key={panel.id} value={panel.id}>
                基线面板 {index + 1}: {panel.modelConfig.model}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto pr-1">
        {!baselineMessage && (
          <div className="rounded-xl border border-dashed border-bg-border bg-bg-tertiary/20 px-3 py-4 text-xs text-text-secondary">
            当前基线面板还没有可对比的助手回答
          </div>
        )}

        {panels
          .filter((panel) => panel.id !== baselinePanel?.id)
          .map((panel, index) => {
            const targetMessage = latestByPanel.get(panel.id) ?? null
            const targetText = targetMessage?.content ?? ''
            const diff = buildDiff(baselineText, targetText)
            return (
              <div key={panel.id} className="rounded-xl border border-bg-border bg-bg-tertiary/30 p-3">
                <div className="mb-2 flex flex-wrap items-center justify-between gap-2 text-[11px]">
                  <div className="text-text-secondary">
                    对比面板 {index + 1}: <span className="text-text-primary">{panel.modelConfig.model}</span>
                  </div>
                  <div className="flex items-center gap-3 text-text-secondary/80">
                    <span className="text-accent-green">+{diff.addedChars}</span>
                    <span className="text-accent-red">-{diff.removedChars}</span>
                    {diff.fallback && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-bg-hover px-2 py-0.5 text-[10px]">
                        <RefreshCw size={10} />
                        文本较长，使用降级比对
                      </span>
                    )}
                  </div>
                </div>

                {!targetMessage ? (
                  <div className="rounded-lg border border-dashed border-bg-border px-3 py-3 text-xs text-text-secondary">
                    此面板暂时没有助手回答
                  </div>
                ) : (
                  <div className="rounded-lg border border-bg-border bg-bg-primary/50 px-3 py-2.5 text-xs leading-relaxed whitespace-pre-wrap break-words">
                    {diff.segments.map((segment, segmentIndex) => (
                      <span key={`${panel.id}-${segmentIndex}`} className={segmentClassMap[segment.kind]}>
                        {segment.text}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )
          })}
      </div>
    </div>
  )
}

