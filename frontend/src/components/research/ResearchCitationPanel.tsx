import React, { useEffect, useMemo, useState } from 'react'
import {
  Archive,
  GitBranch,
  ExternalLink,
  FileSearch,
  Link2,
  RefreshCw,
  Search,
  ShieldCheck,
} from 'lucide-react'

import {
  getResearchArchiveList,
  type ClaimEvidenceChain,
  type ClaimEvidenceSource,
  type ClaimVerificationSummary,
  type ResearchArchive,
  type ResearchConflictGroup,
} from '../../api/client'

interface ResearchCitationPanelProps {
  chains: ClaimEvidenceChain[]
  summary?: ClaimVerificationSummary
  sessionId?: string
  taskId?: string
  className?: string
}

function normalizeToken(value: string | undefined): string {
  return (value || '').trim().toLowerCase()
}

function statusClass(status: string | undefined): string {
  const token = normalizeToken(status)
  if (token === 'verified') return 'border-accent-green/30 bg-accent-green/10 text-accent-green'
  if (token === 'partial') return 'border-amber-400/30 bg-amber-400/10 text-amber-200'
  return 'border-accent-red/30 bg-accent-red/10 text-accent-red'
}

function strengthClass(strength: string | undefined): string {
  const token = normalizeToken(strength)
  if (token === 'high') return 'border-accent-green/25 bg-accent-green/10 text-accent-green'
  if (token === 'medium') return 'border-accent-blue/25 bg-accent-blue/10 text-accent-blue'
  return 'border-bg-border bg-bg-primary/50 text-text-secondary'
}

function displaySourceTitle(source: ClaimEvidenceSource): string {
  return source.title || source.domain || source.url || `Source ${source.source_index}`
}

function buildClaimAnchorId(chain: ClaimEvidenceChain, index: number): string {
  const raw = chain.claim_id || `claim-${index + 1}`
  const stable = raw
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, '-')
    .replace(/^-+|-+$/g, '')
  return `claim-ref-${stable || index + 1}`
}

function verificationSummaryText(summary?: ClaimVerificationSummary): string {
  if (!summary) return 'No verification summary'
  return `${summary.verified_claims} verified / ${summary.partial_claims} partial / ${summary.unverified_claims} unverified`
}

function archiveConflictCount(archive: ResearchArchive): number {
  return (
    archive.conflict_summary?.conflict_count ||
    archive.conflict_summary?.conflicts.length ||
    archive.verification_summary?.contradiction_count ||
    0
  )
}

function recordText(value: unknown, keys: string[]): string {
  if (typeof value !== 'object' || value === null) return ''
  const record = value as Record<string, unknown>
  for (const key of keys) {
    const item = record[key]
    if (typeof item === 'string' && item.trim()) return item
  }
  return ''
}

function reviewStatusText(value: unknown): string {
  const status = recordText(value, ['review_status', 'status'])
  return status || 'unreviewed'
}

function recordCollection(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value)
    ? value.filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null)
    : []
}

function optionalRecord(value: unknown): Record<string, unknown> | undefined {
  return typeof value === 'object' && value !== null ? (value as Record<string, unknown>) : undefined
}

export const ResearchCitationPanel: React.FC<ResearchCitationPanelProps> = ({
  chains,
  summary,
  sessionId,
  taskId,
  className = '',
}) => {
  const [claimQuery, setClaimQuery] = useState('')
  const [selectedClaimId, setSelectedClaimId] = useState<string | null>(null)
  const [archiveQuery, setArchiveQuery] = useState('')
  const [graphQuery, setGraphQuery] = useState('')
  const [archives, setArchives] = useState<ResearchArchive[]>([])
  const [conflictGroups, setConflictGroups] = useState<ResearchConflictGroup[]>([])
  const [loadingArchives, setLoadingArchives] = useState(false)
  const [archiveError, setArchiveError] = useState<string | null>(null)

  const visibleChains = useMemo(
    () => chains.filter((chain) => chain.claim_text.trim()),
    [chains],
  )
  const filteredChains = useMemo(() => {
    const token = normalizeToken(claimQuery)
    if (!token) return visibleChains
    return visibleChains.filter((chain) => normalizeToken(chain.claim_text).includes(token))
  }, [claimQuery, visibleChains])

  const selectedClaim = useMemo(() => {
    if (filteredChains.length === 0) return undefined
    return (
      filteredChains.find((chain) => (chain.claim_id || chain.claim_text) === selectedClaimId) ??
      filteredChains[0]
    )
  }, [filteredChains, selectedClaimId])

  useEffect(() => {
    if (!selectedClaim && selectedClaimId) {
      setSelectedClaimId(null)
    }
  }, [selectedClaim, selectedClaimId])

  const loadArchives = async () => {
    setLoadingArchives(true)
    setArchiveError(null)
    try {
      const payload = await getResearchArchiveList({
        q: archiveQuery,
        session_id: sessionId,
        task_id: taskId,
        limit: 20,
      })
      setArchives(payload.archives)
      setConflictGroups(payload.conflict_groups)
    } catch (error) {
      setArchives([])
      setConflictGroups([])
      setArchiveError((error as Error).message || 'Failed to load research archives')
    } finally {
      setLoadingArchives(false)
    }
  }

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadArchives()
    }, 250)
    return () => window.clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [archiveQuery, sessionId, taskId])

  return (
    <section
      className={`rounded-2xl border border-bg-border bg-bg-secondary/70 p-4 ${className}`.trim()}
      data-testid="research-citation-panel"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <ShieldCheck size={16} className="text-accent-blue" />
            <h3 className="text-sm font-semibold text-text-primary">Research archives / Citation panel</h3>
          </div>
          <p className="mt-1 text-xs leading-5 text-text-secondary">
            Filter verified claims, inspect sources, and find reusable research archives.
          </p>
        </div>
        <span className="rounded-full border border-bg-border bg-bg-primary/50 px-2.5 py-1 text-[11px] text-text-secondary">
          {verificationSummaryText(summary)}
        </span>
      </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(0,1.45fr)_minmax(280px,0.75fr)]">
        <div className="min-w-0 rounded-xl border border-bg-border bg-bg-primary/35 p-3">
          <label className="flex items-center gap-2 rounded-lg border border-bg-border bg-bg-secondary px-2.5 py-2 text-xs text-text-secondary">
            <Search size={13} className="shrink-0" />
            <input
              value={claimQuery}
              onChange={(event) => setClaimQuery(event.target.value)}
              data-testid="research-citation-claim-filter"
              className="min-w-0 flex-1 bg-transparent text-text-primary outline-none placeholder:text-text-secondary/60"
              placeholder="Filter claim text"
            />
          </label>

          <div className="mt-3 max-h-80 space-y-2 overflow-y-auto pr-1">
            {filteredChains.length === 0 ? (
              <div className="rounded-lg border border-bg-border bg-bg-secondary/45 px-3 py-4 text-xs text-text-secondary">
                No matching claims.
              </div>
            ) : (
              filteredChains.map((chain, index) => {
                const chainKey = chain.claim_id || chain.claim_text
                const isSelected = (selectedClaim?.claim_id || selectedClaim?.claim_text) === chainKey
                const sourceCount = chain.sources.length || chain.supporting_source_count
                const anchorId = buildClaimAnchorId(chain, index)

                return (
                  <button
                    key={chainKey}
                    type="button"
                    onClick={() => setSelectedClaimId(chainKey)}
                    data-testid="research-citation-claim-row"
                    className={`w-full rounded-lg border px-3 py-2 text-left transition-colors ${
                      isSelected
                        ? 'border-accent-blue/45 bg-accent-blue/10'
                        : 'border-bg-border bg-bg-secondary/45 hover:border-accent-blue/30'
                    }`}
                  >
                    <div className="flex flex-wrap items-center gap-1.5 text-[10px]">
                      <span className={`rounded-full border px-2 py-0.5 ${statusClass(chain.status)}`}>
                        {chain.status || 'unverified'}
                      </span>
                      <span className={`rounded-full border px-2 py-0.5 ${strengthClass(chain.evidence_strength)}`}>
                        {chain.evidence_strength || 'low'}
                      </span>
                      <span className="inline-flex items-center gap-1 rounded-full border border-bg-border bg-bg-primary/50 px-2 py-0.5 text-text-secondary">
                        <FileSearch size={10} />
                        {sourceCount}
                      </span>
                    </div>
                    <p className="mt-1.5 line-clamp-2 text-xs leading-5 text-text-primary">
                      {chain.claim_text}
                    </p>
                    <div className="mt-1.5 flex items-center gap-1 text-[10px] text-text-secondary/60">
                      <Link2 size={10} />
                      <span className="font-mono">{anchorId}</span>
                    </div>
                  </button>
                )
              })
            )}
          </div>
        </div>

        <aside
          className="min-w-0 rounded-xl border border-bg-border bg-bg-primary/35 p-3"
          data-testid="research-archive-panel"
        >
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 text-sm font-semibold text-text-primary">
              <Archive size={15} className="text-accent-blue" />
              Research archives
            </div>
            <button
              type="button"
              onClick={() => void loadArchives()}
              disabled={loadingArchives}
              className="rounded-lg border border-bg-border p-1.5 text-text-secondary transition-colors hover:border-accent-blue/40 hover:text-text-primary disabled:opacity-50"
              title="Refresh archives"
            >
              <RefreshCw size={13} className={loadingArchives ? 'animate-spin' : ''} />
            </button>
          </div>

          <label className="mt-3 flex items-center gap-2 rounded-lg border border-bg-border bg-bg-secondary px-2.5 py-2 text-xs text-text-secondary">
            <Search size={13} className="shrink-0" />
            <input
              value={archiveQuery}
              onChange={(event) => setArchiveQuery(event.target.value)}
              data-testid="research-archive-search"
              className="min-w-0 flex-1 bg-transparent text-text-primary outline-none placeholder:text-text-secondary/60"
              placeholder="Search archives"
            />
          </label>

          <label className="mt-2 flex items-center gap-2 rounded-lg border border-bg-border bg-bg-secondary px-2.5 py-2 text-xs text-text-secondary">
            <GitBranch size={13} className="shrink-0" />
            <input
              value={graphQuery}
              onChange={(event) => setGraphQuery(event.target.value)}
              data-testid="research-citation-graph-filter"
              className="min-w-0 flex-1 bg-transparent text-text-primary outline-none placeholder:text-text-secondary/60"
              placeholder="Filter graph nodes"
            />
          </label>

          <div className="mt-3 max-h-80 space-y-2 overflow-y-auto pr-1">
            {archiveError && (
              <div className="rounded-lg border border-accent-red/25 bg-accent-red/10 px-3 py-2 text-xs text-accent-red">
                {archiveError}
              </div>
            )}
            {!archiveError && archives.length === 0 && (
              <div className="rounded-lg border border-bg-border bg-bg-secondary/45 px-3 py-4 text-xs text-text-secondary">
                {loadingArchives ? 'Loading archives...' : 'No research archives found.'}
              </div>
            )}
            {archives.map((archive) => (
              <article
                key={archive.archive_id || `${archive.title}-${archive.updated_at ?? archive.created_at ?? 0}`}
                data-testid="research-archive-row"
                className="rounded-lg border border-bg-border bg-bg-secondary/45 px-3 py-2"
              >
                <h4 className="line-clamp-2 text-xs font-semibold leading-5 text-text-primary">
                  {archive.title}
                </h4>
                <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[10px] text-text-secondary">
                  <span>{archive.claim_count} claims</span>
                  <span>{archive.source_count} sources</span>
                  <span>{verificationSummaryText(archive.verification_summary)}</span>
                  <span data-testid="research-citation-paragraph-link">
                    {archive.paragraph_citations.length} paragraphs
                  </span>
                  <span data-testid="research-citation-graph-summary">
                    {archive.citation_graph?.nodes.length ?? 0} nodes / {archive.citation_graph?.edges.length ?? 0} edges
                  </span>
                  <span data-testid="research-citation-conflict-summary">
                    {archiveConflictCount(archive)} conflicts
                  </span>
                </div>
                <details className="mt-2 rounded-lg border border-bg-border bg-bg-primary/35 px-2 py-1.5">
                  <summary
                    className="cursor-pointer text-[11px] font-medium text-text-secondary"
                    data-testid="research-citation-graph-details"
                  >
                    Citation graph
                  </summary>
                  <div className="mt-2 space-y-1">
                    {(archive.citation_graph?.nodes ?? [])
                      .filter((node) => {
                        const token = normalizeToken(graphQuery)
                        if (!token) return true
                        return normalizeToken(JSON.stringify(node)).includes(token)
                      })
                      .slice(0, 6)
                      .map((node, index) => (
                        <div
                          key={recordText(node, ['id']) || index}
                          className="flex items-center justify-between gap-2 rounded border border-bg-border bg-bg-secondary/50 px-2 py-1 text-[10px]"
                          data-testid="research-citation-graph-node"
                        >
                          <span className="truncate text-text-primary">
                            {recordText(node, ['text', 'title', 'label', 'id']) || 'Graph node'}
                          </span>
                          <span className="shrink-0 text-text-secondary">
                            {recordText(node, ['type']) || 'node'}
                          </span>
                        </div>
                      ))}
                  </div>
                </details>
                {archive.conflict_summary?.conflicts.length ? (
                  <details className="mt-2 rounded-lg border border-amber-400/20 bg-amber-400/5 px-2 py-1.5">
                    <summary className="cursor-pointer text-[11px] font-medium text-amber-100">
                      Conflict review
                    </summary>
                    <div className="mt-2 space-y-1">
                      {archive.conflict_summary.conflicts.slice(0, 4).map((conflict, index) => (
                        <div
                          key={recordText(conflict, ['conflict_id', 'claim_id']) || index}
                          className="rounded border border-bg-border bg-bg-secondary/50 px-2 py-1 text-[10px]"
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="truncate text-text-primary">
                              {recordText(conflict, ['text', 'claim_text']) || 'Conflict'}
                            </span>
                            <span className="shrink-0 text-amber-100">{reviewStatusText(conflict)}</span>
                          </div>
                          {optionalRecord(conflict.review) && (
                            <p className="mt-1 text-text-secondary">
                              {recordText(optionalRecord(conflict.review), ['resolution', 'note'])}
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  </details>
                ) : null}
              </article>
            ))}
          </div>

          {conflictGroups.length > 0 && (
            <div className="mt-3 rounded-xl border border-bg-border bg-bg-primary/35 p-2">
              <div className="text-xs font-semibold text-text-primary">Conflict groups</div>
              <div className="mt-2 space-y-1.5" data-testid="research-conflict-groups">
                {conflictGroups.slice(0, 4).map((group) => (
                  <div
                    key={group.group_id}
                    className="rounded-lg border border-bg-border bg-bg-secondary/45 px-2 py-1.5"
                    data-testid="research-conflict-group-row"
                  >
                    <p className="line-clamp-2 text-[11px] leading-4 text-text-primary">
                      {group.conflict_text || group.normalized_conflict_text || 'Conflict group'}
                    </p>
                    <div className="mt-1 flex flex-wrap gap-1 text-[10px] text-text-secondary">
                      <span>{group.total} matches</span>
                      <span>{group.archives.length} archives</span>
                      <span data-testid="research-conflict-review-status">
                        {group.review_statuses.join(', ') || 'unreviewed'}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </aside>
      </div>

      {selectedClaim && (
        <div className="mt-3 rounded-xl border border-bg-border bg-bg-primary/35 p-3">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="min-w-0">
              <div className="text-xs font-semibold text-text-primary">Selected claim sources</div>
              <p className="mt-1 text-xs leading-5 text-text-secondary">{selectedClaim.claim_text}</p>
            </div>
            <button
              type="button"
              className="inline-flex items-center gap-1.5 rounded-lg border border-bg-border px-2.5 py-1 text-[11px] text-text-secondary transition-colors hover:border-accent-blue/40 hover:text-text-primary"
              title="Claim reference"
            >
              <Link2 size={11} />
              claim reference
            </button>
          </div>

          <div className="mt-2 grid gap-2 sm:grid-cols-2">
            {selectedClaim.sources.length === 0 ? (
              <div className="rounded-lg border border-bg-border bg-bg-secondary/45 px-3 py-3 text-xs text-text-secondary">
                No sources attached to this claim yet.
              </div>
            ) : (
              selectedClaim.sources.map((source) => (
                <div
                  key={`${selectedClaim.claim_id || selectedClaim.claim_text}-${source.source_index}-${displaySourceTitle(source)}`}
                  className="rounded-lg border border-bg-border bg-bg-secondary/45 px-3 py-2"
                >
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
                  <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[10px] text-text-secondary/70">
                    {source.domain && <span>{source.domain}</span>}
                    {source.source_tier && <span>{source.source_tier}</span>}
                    {source.freshness_band && <span>{source.freshness_band}</span>}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </section>
  )
}
