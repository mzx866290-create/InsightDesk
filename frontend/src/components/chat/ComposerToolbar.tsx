import {
  Database,
  Eraser,
  Globe,
  Loader2,
  Sparkles,
  SlidersHorizontal,
} from 'lucide-react'
import { useState } from 'react'

import type { ResearchMode, ResearchSourceStrategy } from '../../stores/chatStore'
import type { ResearchSourceStrategyOption } from './composerResearchConfig'

interface ComposerToolbarProps {
  researchMode: ResearchMode
  researchSourceStrategy: ResearchSourceStrategy
  researchSourceStrategyOptions: ResearchSourceStrategyOption[]
  omitHistoryForNextSend: boolean
  webSearchEnabled: boolean
  knowledgeBaseEnabled: boolean
  composerBusy: boolean
  composerLocked: boolean
  canResearch: boolean
  canSend: boolean
  hasOnlyComposerDataFiles: boolean
  effectiveComposerResearchMode: ResearchMode
  researchButtonLabel: string
  researchButtonTitle: string
  isResearchStarting: boolean
  activeStopHandler: (() => void) | null
  stopButtonTitle: string
  onSelectResearchMode: (mode: ResearchMode) => void
  onSelectResearchSourceStrategy: (strategy: ResearchSourceStrategy) => void
  onToggleOmitHistory: () => void
  onToggleWebSearch: () => void
  onToggleKnowledgeBase: () => void
  onChooseAttachment: () => void
  onChooseImage: () => void
  onStartResearch: () => void
  onSend: () => void
}

export function ComposerToolbar({
  researchMode,
  researchSourceStrategy,
  researchSourceStrategyOptions,
  omitHistoryForNextSend,
  webSearchEnabled,
  knowledgeBaseEnabled,
  composerBusy,
  composerLocked,
  canResearch,
  hasOnlyComposerDataFiles,
  effectiveComposerResearchMode,
  researchButtonLabel,
  researchButtonTitle,
  isResearchStarting,
  onSelectResearchMode,
  onSelectResearchSourceStrategy,
  onToggleOmitHistory,
  onToggleWebSearch,
  onToggleKnowledgeBase,
  onStartResearch,
}: ComposerToolbarProps) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="flex items-center gap-1">
      {/* Compact toggle icons — always visible */}
      <button
        type="button"
        onClick={onToggleWebSearch}
        disabled={composerLocked}
        data-testid="composer-web-search-toggle"
        className={`flex h-7 w-7 items-center justify-center rounded-md transition-colors ${
          webSearchEnabled
            ? 'text-accent-blue'
            : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary'
        }`}
        title="联网搜索"
      >
        <Globe size={15} />
      </button>

      <button
        type="button"
        onClick={onToggleKnowledgeBase}
        disabled={composerLocked}
        data-testid="composer-knowledge-base-toggle"
        className={`flex h-7 w-7 items-center justify-center rounded-md transition-colors ${
          knowledgeBaseEnabled
            ? 'text-accent-green'
            : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary'
        }`}
        title="知识库"
      >
        <Database size={15} />
      </button>

      <button
        type="button"
        onClick={onToggleOmitHistory}
        disabled={composerLocked}
        data-testid="composer-omit-history-toggle"
        className={`flex h-7 w-7 items-center justify-center rounded-md transition-colors ${
          omitHistoryForNextSend
            ? 'text-accent-purple'
            : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary'
        }`}
        title="清上下文"
      >
        <Eraser size={15} />
      </button>

      {/* Research button */}
      <button
        type="button"
        onClick={onStartResearch}
        disabled={!canResearch}
        data-testid="composer-research"
        className={`flex h-7 items-center gap-1 rounded-md px-2 text-xs transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
          canResearch
            ? effectiveComposerResearchMode === 'deep' || hasOnlyComposerDataFiles
              ? 'text-amber-300 hover:bg-amber-400/10'
              : 'text-accent-blue hover:bg-accent-blue/10'
            : 'text-text-secondary'
        }`}
        title={researchButtonTitle}
      >
        {isResearchStarting ? (
          <Loader2 size={13} className="animate-spin" />
        ) : (
          <Sparkles size={13} />
        )}
        <span>{researchButtonLabel}</span>
      </button>

      {/* Expand strategy panel */}
      <div className="relative">
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className={`flex h-7 w-7 items-center justify-center rounded-md transition-colors ${
            expanded
              ? 'bg-bg-hover text-text-primary'
              : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary'
          }`}
          title="研究策略设置"
        >
          <SlidersHorizontal size={14} />
        </button>

        {expanded && (
          <div className="absolute bottom-full right-0 z-20 mb-2 rounded-xl border border-bg-border bg-bg-secondary p-3 shadow-xl">
            <div className="flex flex-col gap-2.5">
              <div>
                <p className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-text-secondary">研究模式</p>
                <div className="inline-flex items-center rounded-lg border border-bg-border bg-bg-primary/50 p-0.5">
                  {(['quick', 'deep'] as const).map((mode) => {
                    const active = researchMode === mode
                    const label = mode === 'quick' ? '快研' : '深研'
                    return (
                      <button
                        key={mode}
                        type="button"
                        onClick={() => onSelectResearchMode(mode)}
                        disabled={composerBusy || composerLocked}
                        data-testid={`composer-research-mode-${mode}`}
                        className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
                          active
                            ? mode === 'deep'
                              ? 'bg-amber-400/20 text-amber-200'
                              : 'bg-accent-blue/20 text-accent-blue'
                            : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary'
                        }`}
                      >
                        {label}
                      </button>
                    )
                  })}
                </div>
              </div>

              <div>
                <p className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-text-secondary">来源策略</p>
                <div className="inline-flex items-center rounded-lg border border-bg-border bg-bg-primary/50 p-0.5">
                  {researchSourceStrategyOptions.map((option) => {
                    const active = researchSourceStrategy === option.value
                    const isCommunity = option.value === 'community_first'
                    const isStrict = option.value === 'evidence_strict'
                    return (
                      <button
                        key={option.value}
                        type="button"
                        onClick={() => onSelectResearchSourceStrategy(option.value)}
                        disabled={composerBusy || composerLocked}
                        data-testid={`composer-research-source-${option.value}`}
                        className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
                          active
                            ? isCommunity
                              ? 'bg-accent-green/20 text-accent-green'
                              : isStrict
                                ? 'bg-amber-400/20 text-amber-200'
                                : 'bg-accent-blue/20 text-accent-blue'
                            : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary'
                        }`}
                        title={option.title}
                      >
                        {option.label}
                      </button>
                    )
                  })}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
