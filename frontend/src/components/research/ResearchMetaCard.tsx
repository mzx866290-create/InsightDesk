import React from 'react'

import { formatResearchModeLabel, type ResearchTaskMeta } from '../../utils/researchTask'

interface ResearchMetaCardProps {
  meta: ResearchTaskMeta
  compact?: boolean
  className?: string
}

function badgeClass(tone: 'neutral' | 'accent' | 'warm'): string {
  if (tone === 'accent') {
    return 'border-accent-blue/30 bg-accent-blue/10 text-accent-blue'
  }
  if (tone === 'warm') {
    return 'border-amber-400/30 bg-amber-400/10 text-amber-200'
  }
  return 'border-bg-border bg-bg-primary/40 text-text-secondary'
}

function normalizeText(value: string): string {
  return value.trim()
}

function formatStrategyToken(value: string): string {
  return normalizeText(value).replace(/[_-]+/g, ' ')
}

function isDifferentQuery(left: string, right: string): boolean {
  const normalizedLeft = normalizeText(left).toLowerCase()
  const normalizedRight = normalizeText(right).toLowerCase()
  return Boolean(normalizedLeft && normalizedRight && normalizedLeft !== normalizedRight)
}

function modeBadgeClass(mode: string): string {
  return mode.toLowerCase() === 'deep' ? badgeClass('warm') : badgeClass('accent')
}

function copyRelatedQuestion(question: string): void {
  if (typeof navigator === 'undefined' || !navigator.clipboard?.writeText) return
  void navigator.clipboard.writeText(question)
}

export const ResearchMetaCard: React.FC<ResearchMetaCardProps> = ({
  meta,
  compact = false,
  className = '',
}) => {
  const query = normalizeText(meta.query)
  const rewrittenQuery = normalizeText(meta.rewrittenQuery)
  const providerSummary = normalizeText(meta.providerSummary || meta.provider)
  const requestedMode = normalizeText(meta.requestedMode || meta.mode)
  const effectiveMode = normalizeText(meta.effectiveMode || meta.mode)
  const didFallback = meta.didFallback
  const fallbackNote = normalizeText(meta.fallbackNote)
  const facets = meta.facets.slice(0, compact ? 4 : 6)
  const caveats = meta.caveats
    .filter((item) => normalizeText(item) !== fallbackNote)
    .slice(0, compact ? 2 : 3)
  const sourceStrategy = formatStrategyToken(meta.sourceStrategy)
  const strategyIntent = formatStrategyToken(meta.strategyIntent)
  const strategyRegion = normalizeText(meta.strategyRegion)
  const strategyFreshness = formatStrategyToken(meta.strategyFreshness)
  const strategySourceTypes = meta.strategySourceTypes
    .map(formatStrategyToken)
    .filter(Boolean)
    .slice(0, compact ? 4 : 6)
  const strategyQueryVariants = meta.strategyQueryVariants
    .map(normalizeText)
    .filter(Boolean)
    .slice(0, compact ? 2 : 4)
  const strategyRankingPolicy = normalizeText(meta.strategyRankingPolicy)
  const relatedQuestions = meta.relatedQuestions
    .map(normalizeText)
    .filter(Boolean)
    .slice(0, compact ? 3 : 5)
  const strategyBadges = [
    sourceStrategy && sourceStrategy !== 'web only' ? `Source: ${sourceStrategy}` : '',
    strategyIntent ? `Intent: ${strategyIntent}` : '',
    strategyRegion ? `Region: ${strategyRegion}` : '',
    strategyFreshness ? `Freshness: ${strategyFreshness}` : '',
  ].filter(Boolean)
  const showStrategy = Boolean(
    strategyBadges.length > 0 ||
      strategySourceTypes.length > 0 ||
      strategyQueryVariants.length > 0 ||
      strategyRankingPolicy,
  )
  const showRewrittenQuery = isDifferentQuery(query, rewrittenQuery)
  const countItems = [
    meta.sourceCount > 0 ? `${meta.sourceCount} sources` : '',
    meta.findingCount > 0 ? `${meta.findingCount} findings` : '',
    meta.contradictionCount > 0 ? `${meta.contradictionCount} contradictions` : '',
    meta.roundCount > 0 ? `${meta.roundCount} rounds` : '',
  ].filter(Boolean)

  if (
    !query &&
    !providerSummary &&
    countItems.length === 0 &&
    facets.length === 0 &&
    caveats.length === 0 &&
    relatedQuestions.length === 0 &&
    !showStrategy &&
    !fallbackNote
  ) {
    return null
  }

  return (
    <div
      className={`rounded-xl border border-bg-border bg-bg-secondary/45 ${
        compact ? 'px-3 py-3' : 'px-4 py-4'
      } ${className}`.trim()}
    >
      <div className="flex flex-wrap items-center gap-2 text-[11px]">
        <span className={`rounded-full border px-2 py-0.5 ${badgeClass('neutral')}`}>
          Research
        </span>
        {didFallback ? (
          <>
            <span className={`rounded-full border px-2 py-0.5 ${modeBadgeClass(requestedMode)}`}>
              Requested {formatResearchModeLabel(requestedMode)}
            </span>
            <span className={`rounded-full border px-2 py-0.5 ${modeBadgeClass(effectiveMode)}`}>
              Executed {formatResearchModeLabel(effectiveMode)}
            </span>
          </>
        ) : (
          <span className={`rounded-full border px-2 py-0.5 ${modeBadgeClass(effectiveMode)}`}>
            {formatResearchModeLabel(effectiveMode)}
          </span>
        )}
        {providerSummary && (
          <span className={`rounded-full border px-2 py-0.5 ${badgeClass('neutral')}`}>
            {providerSummary}
          </span>
        )}
        {countItems.map((item) => (
          <span
            key={item}
            className={`rounded-full border px-2 py-0.5 ${badgeClass('neutral')}`}
          >
            {item}
          </span>
        ))}
      </div>

      <div className="mt-3 space-y-2 text-[11px]">
        {didFallback && fallbackNote && (
          <div className="rounded-lg border border-amber-400/20 bg-amber-400/10 px-2.5 py-2 text-amber-100">
            <p className="text-text-secondary/80">Mode Fallback</p>
            <p className="mt-1 break-words text-amber-100">{fallbackNote}</p>
          </div>
        )}

        {query && (
          <div>
            <p className="text-text-secondary/70">Query</p>
            <p className="mt-1 break-words text-text-primary">{query}</p>
          </div>
        )}

        {showRewrittenQuery && (
          <div>
            <p className="text-text-secondary/70">Search Query</p>
            <p className="mt-1 break-words text-text-primary">{rewrittenQuery}</p>
          </div>
        )}

        {showStrategy && (
          <div data-testid="research-search-strategy">
            <p className="text-text-secondary/70">Search Strategy</p>
            {(strategyBadges.length > 0 || strategySourceTypes.length > 0) && (
              <div className="mt-1 flex flex-wrap gap-1.5">
                {strategyBadges.map((item) => (
                  <span
                    key={item}
                    className="rounded-full border border-accent-blue/20 bg-accent-blue/5 px-2 py-0.5 text-text-secondary"
                  >
                    {item}
                  </span>
                ))}
                {strategySourceTypes.map((item) => (
                  <span
                    key={item}
                    className="rounded-full border border-bg-border bg-bg-primary/40 px-2 py-0.5 text-text-secondary"
                  >
                    {item}
                  </span>
                ))}
              </div>
            )}
            {strategyQueryVariants.length > 0 && (
              <div className="mt-2 space-y-1">
                <p className="text-text-secondary/70">Planned Queries</p>
                {strategyQueryVariants.map((variant) => (
                  <p key={variant} className="break-words text-text-primary">
                    {variant}
                  </p>
                ))}
              </div>
            )}
            {strategyRankingPolicy && (
              <p className="mt-2 break-words text-text-secondary">
                Ranking: {strategyRankingPolicy}
              </p>
            )}
          </div>
        )}

        {relatedQuestions.length > 0 && (
          <div data-testid="research-related-questions">
            <p className="text-text-secondary/70">Continue Exploring</p>
            <div className="mt-1 flex flex-wrap gap-1.5">
              {relatedQuestions.map((question) => (
                <button
                  key={question}
                  type="button"
                  className="rounded-full border border-accent-blue/20 bg-accent-blue/5 px-2 py-1 text-left text-text-primary transition hover:border-accent-blue/40 hover:bg-accent-blue/10"
                  title="Copy question"
                  aria-label={`Copy related question: ${question}`}
                  onClick={() => copyRelatedQuestion(question)}
                >
                  {question}
                </button>
              ))}
            </div>
          </div>
        )}

        {facets.length > 0 && (
          <div>
            <p className="text-text-secondary/70">Facets</p>
            <div className="mt-1 flex flex-wrap gap-1.5">
              {facets.map((facet) => (
                <span
                  key={facet}
                  className="rounded-full border border-accent-blue/20 bg-accent-blue/5 px-2 py-0.5 text-text-secondary"
                >
                  {facet}
                </span>
              ))}
            </div>
          </div>
        )}

        {caveats.length > 0 && (
          <div>
            <p className="text-text-secondary/70">Notes</p>
            <div className="mt-1 space-y-1">
              {caveats.map((caveat) => (
                <p key={caveat} className="break-words text-text-secondary">
                  {caveat}
                </p>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
