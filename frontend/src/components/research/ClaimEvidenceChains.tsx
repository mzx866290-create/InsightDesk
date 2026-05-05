import React, { useMemo, useState } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  ExternalLink,
  FileSearch,
  ShieldCheck,
} from 'lucide-react'

import type {
  ClaimEvidenceChain,
  ClaimEvidenceSource,
  ClaimVerificationSummary,
} from '../../api/client'

interface ClaimEvidenceChainsProps {
  chains: ClaimEvidenceChain[]
  summary?: ClaimVerificationSummary
  className?: string
}

type StatusTone = 'verified' | 'partial' | 'unverified'
type StrengthTone = 'high' | 'medium' | 'low'

function normalizeToken(value: string | undefined): string {
  return (value || '').trim().toLowerCase()
}

function statusTone(status: string | undefined): StatusTone {
  const token = normalizeToken(status)
  if (token === 'verified') return 'verified'
  if (token === 'partial') return 'partial'
  return 'unverified'
}

function strengthTone(strength: string | undefined): StrengthTone {
  const token = normalizeToken(strength)
  if (token === 'high') return 'high'
  if (token === 'medium') return 'medium'
  return 'low'
}

function statusClass(status: string | undefined): string {
  const tone = statusTone(status)
  if (tone === 'verified') {
    return 'border-accent-green/30 bg-accent-green/10 text-accent-green'
  }
  if (tone === 'partial') {
    return 'border-amber-400/30 bg-amber-400/10 text-amber-200'
  }
  return 'border-accent-red/30 bg-accent-red/10 text-accent-red'
}

function strengthClass(strength: string | undefined): string {
  const tone = strengthTone(strength)
  if (tone === 'high') {
    return 'border-accent-green/25 bg-accent-green/10 text-accent-green'
  }
  if (tone === 'medium') {
    return 'border-accent-blue/25 bg-accent-blue/10 text-accent-blue'
  }
  return 'border-bg-border bg-bg-primary/50 text-text-secondary'
}

function sourceTierClass(source: ClaimEvidenceSource): string {
  return normalizeToken(source.source_tier) === 'primary'
    ? 'border-accent-green/25 bg-accent-green/10 text-accent-green'
    : 'border-bg-border bg-bg-primary/50 text-text-secondary'
}

function displaySourceTitle(source: ClaimEvidenceSource): string {
  return source.title || source.domain || source.url || `Source ${source.source_index}`
}

function buildSummaryStats(
  chains: ClaimEvidenceChain[],
  summary?: ClaimVerificationSummary,
): Array<{ label: string; value: number; tone: 'neutral' | 'good' | 'warn' | 'danger' }> {
  const total = summary?.total_claims || chains.length
  const verified =
    summary?.verified_claims ??
    chains.filter((chain) => statusTone(chain.status) === 'verified').length
  const partial =
    summary?.partial_claims ??
    chains.filter((chain) => statusTone(chain.status) === 'partial').length
  const unverified =
    summary?.unverified_claims ??
    chains.filter((chain) => statusTone(chain.status) === 'unverified').length
  const attention = summary?.claims_needing_attention.length ?? chains.filter((chain) => chain.needs_attention).length
  const contradictions = summary?.contradiction_count ?? 0

  return [
    { label: 'Claims', value: total, tone: 'neutral' },
    { label: 'Verified', value: verified, tone: 'good' },
    { label: 'Partial', value: partial, tone: 'warn' },
    { label: 'Unverified', value: unverified, tone: 'danger' },
    { label: 'Needs review', value: attention, tone: attention > 0 ? 'warn' : 'neutral' },
    { label: 'Contradictions', value: contradictions, tone: contradictions > 0 ? 'danger' : 'neutral' },
  ]
}

function summaryStatClass(tone: 'neutral' | 'good' | 'warn' | 'danger'): string {
  if (tone === 'good') return 'border-accent-green/20 bg-accent-green/10 text-accent-green'
  if (tone === 'warn') return 'border-amber-400/20 bg-amber-400/10 text-amber-200'
  if (tone === 'danger') return 'border-accent-red/20 bg-accent-red/10 text-accent-red'
  return 'border-bg-border bg-bg-primary/45 text-text-secondary'
}

export const ClaimEvidenceChains: React.FC<ClaimEvidenceChainsProps> = ({
  chains,
  summary,
  className = '',
}) => {
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const visibleChains = chains.filter((chain) => chain.claim_text.trim())
  const stats = useMemo(() => buildSummaryStats(visibleChains, summary), [summary, visibleChains])

  if (visibleChains.length === 0) return null

  return (
    <section className={`rounded-2xl border border-bg-border bg-bg-secondary/70 p-4 ${className}`.trim()}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <ShieldCheck size={16} className="text-accent-blue" />
            <h3 className="text-sm font-semibold text-text-primary">Claim Evidence</h3>
          </div>
          <p className="mt-1 text-xs leading-5 text-text-secondary">
            Statement-level verification chains from the Research V2 artifact.
          </p>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
        {stats.map((item) => (
          <div
            key={item.label}
            className={`rounded-lg border px-2.5 py-2 ${summaryStatClass(item.tone)}`}
          >
            <div className="text-[10px] text-current/70">{item.label}</div>
            <div className="mt-0.5 text-sm font-semibold">{item.value}</div>
          </div>
        ))}
      </div>

      <div className="mt-3 space-y-2">
        {visibleChains.map((chain) => {
          const isExpanded = expandedId === chain.claim_id
          const sourceCount = chain.sources.length || chain.supporting_source_count
          const chainKey = chain.claim_id || chain.claim_text

          return (
            <article
              key={chainKey}
              className="rounded-xl border border-bg-border bg-bg-primary/45 px-3 py-3"
            >
              <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
                <span className={`rounded-full border px-2 py-0.5 ${statusClass(chain.status)}`}>
                  {chain.status || 'unverified'}
                </span>
                <span
                  className={`rounded-full border px-2 py-0.5 ${strengthClass(
                    chain.evidence_strength,
                  )}`}
                >
                  {chain.evidence_strength || 'low'} strength
                </span>
                {chain.has_primary_source && (
                  <span className="rounded-full border border-accent-green/25 bg-accent-green/10 px-2 py-0.5 text-accent-green">
                    primary source
                  </span>
                )}
                {chain.facet && (
                  <span className="rounded-full border border-bg-border bg-bg-secondary px-2 py-0.5 text-text-secondary">
                    {chain.facet}
                  </span>
                )}
                {chain.needs_attention && (
                  <span className="inline-flex items-center gap-1 rounded-full border border-amber-400/25 bg-amber-400/10 px-2 py-0.5 text-amber-200">
                    <AlertTriangle size={10} />
                    review
                  </span>
                )}
              </div>

              <p className="mt-2 text-sm leading-6 text-text-primary">{chain.claim_text}</p>

              <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-text-secondary">
                <span className="inline-flex items-center gap-1">
                  <FileSearch size={11} />
                  {sourceCount} sources
                </span>
                {chain.independent_source_families.length > 0 && (
                  <span>{chain.independent_source_families.length} independent families</span>
                )}
                {chain.date && <span>{chain.date}</span>}
                {chain.claim_id && <span className="font-mono text-text-secondary/60">{chain.claim_id}</span>}
              </div>

              {chain.verification_note && (
                <p className="mt-2 rounded-lg border border-bg-border bg-bg-secondary/50 px-2.5 py-2 text-xs leading-5 text-text-secondary">
                  {chain.verification_note}
                </p>
              )}

              {chain.sources.length > 0 && (
                <div className="mt-2">
                  <button
                    type="button"
                    onClick={() => setExpandedId(isExpanded ? null : chain.claim_id)}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-bg-border px-2.5 py-1 text-[11px] text-text-secondary transition-colors hover:border-accent-blue/40 hover:text-text-primary"
                  >
                    {isExpanded ? 'Hide sources' : 'Show sources'}
                  </button>

                  {isExpanded && (
                    <div className="mt-2 space-y-2">
                      {chain.sources.map((source) => (
                        <div
                          key={`${chainKey}-${source.source_index}-${displaySourceTitle(source)}`}
                          className="rounded-lg border border-bg-border bg-bg-secondary/45 px-2.5 py-2"
                        >
                          <div className="flex items-start gap-2">
                            <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-accent-blue/15 text-[10px] font-semibold text-accent-blue">
                              {source.source_index || '?'}
                            </span>
                            <div className="min-w-0 flex-1">
                              {source.url ? (
                                <a
                                  href={source.url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="inline-flex max-w-full items-center gap-1 text-xs font-medium text-accent-blue hover:underline"
                                >
                                  <span className="truncate">{displaySourceTitle(source)}</span>
                                  <ExternalLink size={11} className="shrink-0" />
                                </a>
                              ) : (
                                <p className="truncate text-xs font-medium text-text-primary">
                                  {displaySourceTitle(source)}
                                </p>
                              )}
                              <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[10px]">
                                {source.source_tier && (
                                  <span className={`rounded-full border px-1.5 py-0.5 ${sourceTierClass(source)}`}>
                                    {source.source_tier}
                                  </span>
                                )}
                                {source.source_family && (
                                  <span className="rounded-full bg-bg-primary px-1.5 py-0.5 text-text-secondary/75">
                                    {source.source_family}
                                  </span>
                                )}
                                {source.freshness_band && (
                                  <span className="rounded-full bg-bg-primary px-1.5 py-0.5 text-text-secondary/75">
                                    {source.freshness_band}
                                  </span>
                                )}
                                {source.domain && (
                                  <span className="truncate text-text-secondary/60">{source.domain}</span>
                                )}
                              </div>
                              {source.selection_reason && (
                                <p className="mt-1 text-[11px] leading-5 text-text-secondary/80">
                                  {source.selection_reason}
                                </p>
                              )}
                              {source.provider_caveat && (
                                <p className="mt-1 text-[11px] leading-5 text-amber-200/80">
                                  {source.provider_caveat}
                                </p>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </article>
          )
        })}
      </div>
    </section>
  )
}
