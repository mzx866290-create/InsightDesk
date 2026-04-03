import React from 'react'
import { ResumeCard, type ResumeCardData } from './ResumeCard'
import { DataSummaryCard, type DataSummaryCardData } from './DataSummaryCard'
import { DashboardCard, type DashboardCardData } from './DashboardCard'

/**
 * Parses structured intent blocks from AI content.
 *
 * Expected format in AI output:
 *   :::resume-card
 *   { "name": "...", "skills": [...], "score": 85 }
 *   :::
 *
 * Returns an array of detected intent blocks. Content segments between/around
 * blocks are returned as { type: 'text', content: string }.
 */

type IntentBlock =
  | { type: 'text'; content: string }
  | { type: 'resume-card'; data: ResumeCardData }
  | { type: 'data-summary'; data: DataSummaryCardData }
  | { type: 'dashboard-card'; data: DashboardCardData }

const INTENT_BLOCK_RE = /:::(\w[\w-]*)\s*\n([\s\S]*?):::/g

function parseIntentBlocks(content: string): IntentBlock[] {
  const blocks: IntentBlock[] = []
  let lastIndex = 0
  let match: RegExpExecArray | null

  INTENT_BLOCK_RE.lastIndex = 0

  while ((match = INTENT_BLOCK_RE.exec(content)) !== null) {
    const [fullMatch, intent, rawJson] = match
    const matchStart = match.index

    // Text before this block
    if (matchStart > lastIndex) {
      const text = content.slice(lastIndex, matchStart)
      if (text.trim()) blocks.push({ type: 'text', content: text })
    }

    let parsed: Record<string, unknown> = {}
    try {
      parsed = JSON.parse(rawJson.trim())
    } catch {
      // If JSON is malformed, treat whole block as text
      blocks.push({ type: 'text', content: fullMatch })
      lastIndex = matchStart + fullMatch.length
      continue
    }

    if (intent === 'resume-card') {
      blocks.push({ type: 'resume-card', data: parsed as ResumeCardData })
    } else if (intent === 'data-summary') {
      blocks.push({ type: 'data-summary', data: parsed as DataSummaryCardData })
    } else if (intent === 'dashboard-card') {
      blocks.push({ type: 'dashboard-card', data: parsed as DashboardCardData })
    } else {
      // Unknown intent — render as code block fallback
      blocks.push({ type: 'text', content: fullMatch })
    }

    lastIndex = matchStart + fullMatch.length
  }

  // Remaining text after last block
  if (lastIndex < content.length) {
    const tail = content.slice(lastIndex)
    if (tail.trim()) blocks.push({ type: 'text', content: tail })
  }

  return blocks
}

interface IntentCardRendererProps {
  content: string
  streaming?: boolean
  /** Called with the "text-only" portion so the parent can still render Markdown */
  onTextContent?: (text: string) => void
}

/**
 * Detects intent blocks in AI content and renders the appropriate card components.
 * Returns null when there are no intent blocks (pure text — handled by ReactMarkdown).
 */
export const IntentCardRenderer: React.FC<IntentCardRendererProps> = ({
  content,
  streaming,
}) => {
  // During streaming the block may be incomplete — only render complete blocks
  const hasCompleteBlock = /:::\w[\w-]*\s*\n[\s\S]*?:::/s.test(content)
  if (!hasCompleteBlock) return null

  const blocks = parseIntentBlocks(content)
  const hasCard = blocks.some((b) => b.type !== 'text')
  if (!hasCard) return null

  return (
    <div className="space-y-2">
      {blocks.map((block, i) => {
        if (block.type === 'text') {
          // Plain text segments between cards — rendered by parent ReactMarkdown
          // We suppress them here to avoid duplication; parent will receive stripped content
          return null
        }
        if (block.type === 'resume-card') {
          return <ResumeCard key={i} data={block.data} streaming={streaming} />
        }
        if (block.type === 'data-summary') {
          return <DataSummaryCard key={i} data={block.data} streaming={streaming} />
        }
        if (block.type === 'dashboard-card') {
          return <DashboardCard key={i} data={block.data} streaming={streaming} />
        }
        return null
      })}
    </div>
  )
}

/**
 * Strips intent blocks from content, returning only the plain-text portions.
 * Used by MessageBubble to feed ReactMarkdown with clean text when cards are present.
 */
export function stripIntentBlocks(content: string): string {
  return content.replace(/:::\w[\w-]*\s*\n[\s\S]*?:::/gs, '').trim()
}
