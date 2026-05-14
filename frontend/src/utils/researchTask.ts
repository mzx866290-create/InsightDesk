import type { TaskRecord } from '../api/client'

export interface ResearchTaskMeta {
  query: string
  rewrittenQuery: string
  mode: string
  requestedMode: string
  effectiveMode: string
  didFallback: boolean
  fallbackNote: string
  provider: string
  providerSummary: string
  summary: string
  sourceCount: number
  sourceStrategy: string
  facets: string[]
  caveats: string[]
  strategyIntent: string
  strategyRegion: string
  strategyFreshness: string
  strategySourceTypes: string[]
  strategyQueryVariants: string[]
  strategyRankingPolicy: string
  relatedQuestions: string[]
  findingCount: number
  contradictionCount: number
  roundCount: number
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null
}

function asString(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value
    .map((item) => asString(item))
    .filter(Boolean)
}

function asCount(value: unknown): number {
  return Array.isArray(value) ? value.length : 0
}

export function formatResearchModeLabel(mode: string): string {
  const normalized = asString(mode).toLowerCase()
  if (normalized === 'deep') return 'Deep'
  if (normalized === 'quick') return 'Quick'
  return normalized ? normalized[0].toUpperCase() + normalized.slice(1) : 'Quick'
}

export function getResearchTaskMeta(task?: TaskRecord | null): ResearchTaskMeta | null {
  if (!task || task.task_type !== 'web_research') return null

  const params = asRecord(task.params) ?? {}
  const researchPlan = asRecord(params.research_plan)
  const searchStrategyPlan = asRecord(params.search_strategy_plan)

  const query = asString(params.query)
  const rewrittenQuery = asString(params.research_rewritten_query)
  const provider = asString(params.research_provider) || asString(params.provider)
  const providerSummary = asString(params.research_provider_summary) || provider
  const summary = asString(params.research_summary)
  const effectiveMode = asString(params.research_mode) || 'quick'
  const requestedMode = asString(params.research_requested_mode) || effectiveMode
  const fallbackNote = asString(params.research_fallback_note)
  const didFallback = Boolean(
    requestedMode &&
      effectiveMode &&
      requestedMode.toLowerCase() !== effectiveMode.toLowerCase(),
  )
  const sourceCount = asCount(params.research_sources)
  const sourceStrategy = asString(params.research_source_strategy)
    || asString(researchPlan?.source_strategy)
    || 'web_only'
  const caveats = asStringArray(params.research_caveats)
  const facets = asStringArray(researchPlan?.facets)
  const strategyIntent = asString(searchStrategyPlan?.intent)
  const strategyRegion = asString(searchStrategyPlan?.region)
  const strategyFreshness = asString(searchStrategyPlan?.freshness)
  const strategySourceTypes = asStringArray(searchStrategyPlan?.source_types)
  const primaryStrategyQuery = asString(searchStrategyPlan?.primary_query)
  const strategyQueryVariants = [
    primaryStrategyQuery,
    ...asStringArray(searchStrategyPlan?.query_variants),
  ].filter((item, index, items) => item && items.indexOf(item) === index)
  const strategyRankingPolicy = asString(searchStrategyPlan?.ranking_policy)
  const relatedQuestions = asStringArray(params.research_related_questions)
  const findingCount = asCount(params.research_findings)
  const contradictionCount = asCount(params.research_contradictions)
  const roundCount = asCount(params.research_rounds)

  return {
    query,
    rewrittenQuery,
    mode: effectiveMode,
    requestedMode,
    effectiveMode,
    didFallback,
    fallbackNote,
    provider,
    providerSummary,
    summary,
    sourceCount,
    sourceStrategy,
    facets,
    caveats,
    strategyIntent,
    strategyRegion,
    strategyFreshness,
    strategySourceTypes,
    strategyQueryVariants,
    strategyRankingPolicy,
    relatedQuestions,
    findingCount,
    contradictionCount,
    roundCount,
  }
}
