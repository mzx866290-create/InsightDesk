import type { RetrievalTestResult } from '../../api/client'

export type KbRetrievalResultVariant = 'diagnostic' | 'tab'
export type KbRetrievalCandidateTone = 'blue' | 'green' | 'amber'

type KbRetrievalCandidateKey =
  | 'top_results'
  | 'semantic_candidates'
  | 'keyword_candidates'
  | 'fused_candidates'

interface KbRetrievalCandidateListConfig {
  key: KbRetrievalCandidateKey
  tone: KbRetrievalCandidateTone
  titles: Record<KbRetrievalResultVariant, string>
}

export const KB_RETRIEVAL_CANDIDATE_LISTS: readonly KbRetrievalCandidateListConfig[] = [
  {
    key: 'top_results',
    tone: 'blue',
    titles: {
      diagnostic: 'Top 命中切片',
      tab: 'Top 命中片段',
    },
  },
  {
    key: 'semantic_candidates',
    tone: 'green',
    titles: {
      diagnostic: '语义候选',
      tab: '向量候选',
    },
  },
  {
    key: 'keyword_candidates',
    tone: 'amber',
    titles: {
      diagnostic: '关键词候选',
      tab: '关键词候选',
    },
  },
  {
    key: 'fused_candidates',
    tone: 'blue',
    titles: {
      diagnostic: '融合候选',
      tab: '融合候选',
    },
  },
]

export function hasKbRetrievalTopResults(result: RetrievalTestResult) {
  return Boolean(result.top_results && result.top_results.length > 0)
}

export function getKbRetrievalSearchModeClassName(searchMode: string) {
  if (searchMode.includes('rerank')) return 'bg-accent-green/15 text-accent-green'
  if (searchMode === 'keyword') return 'bg-amber-300/15 text-amber-300'
  return 'bg-accent-blue/15 text-accent-blue'
}

export function getKbRetrievalTestId(prefix: string | undefined, name: string) {
  return prefix ? `${prefix}-${name}` : undefined
}
