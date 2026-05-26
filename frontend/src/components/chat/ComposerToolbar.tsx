import {
  Database,
  Eraser,
  Globe,
  ImagePlus,
  Loader2,
  Paperclip,
  Send,
  Sparkles,
  Square,
} from 'lucide-react'

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
  canSend,
  hasOnlyComposerDataFiles,
  effectiveComposerResearchMode,
  researchButtonLabel,
  researchButtonTitle,
  isResearchStarting,
  activeStopHandler,
  stopButtonTitle,
  onSelectResearchMode,
  onSelectResearchSourceStrategy,
  onToggleOmitHistory,
  onToggleWebSearch,
  onToggleKnowledgeBase,
  onChooseAttachment,
  onChooseImage,
  onStartResearch,
  onSend,
}: ComposerToolbarProps) {
  return (
    <div className="flex flex-wrap items-center justify-end gap-2 sm:pb-0.5">
      <div
        className="inline-flex items-center rounded-lg border border-bg-border bg-bg-primary/50 p-0.5"
        title="研究模式"
      >
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
              className={`min-h-10 rounded-md px-3 text-xs font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
                active
                  ? mode === 'deep'
                    ? 'bg-amber-400/20 text-amber-200'
                    : 'bg-accent-blue/20 text-accent-blue'
                  : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary'
              }`}
              title={
                mode === 'deep'
                  ? '深度研究：多轮检索与综合，成本更高'
                  : '快速研究：更快返回摘要与主要来源'
              }
            >
              {label}
            </button>
          )
        })}
      </div>

      <div
        className="inline-flex items-center rounded-lg border border-bg-border bg-bg-primary/50 p-0.5"
        title="来源策略"
      >
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
              className={`min-h-10 rounded-md px-3 text-xs font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
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

      <button
        type="button"
        onClick={onToggleOmitHistory}
        disabled={composerLocked}
        data-testid="composer-omit-history-toggle"
        className={`flex min-h-10 min-w-10 items-center gap-1 rounded-lg px-3 text-xs transition-colors ${
          omitHistoryForNextSend
            ? 'bg-accent-purple/20 text-accent-purple'
            : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary'
        }`}
        title="本次发送不带历史上下文，历史对话仍会保留"
      >
        <Eraser size={13} />
        <span className="hidden sm:inline">清上下文</span>
      </button>

      <button
        type="button"
        onClick={onToggleWebSearch}
        disabled={composerLocked}
        data-testid="composer-web-search-toggle"
        className={`flex min-h-10 min-w-10 items-center justify-center gap-1 rounded-lg px-3 text-xs transition-colors ${
          webSearchEnabled
            ? 'bg-accent-blue/20 text-accent-blue'
            : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary'
        }`}
        title="联网搜索"
      >
        <Globe size={13} />
      </button>

      <button
        type="button"
        onClick={onToggleKnowledgeBase}
        disabled={composerLocked}
        data-testid="composer-knowledge-base-toggle"
        className={`flex min-h-10 min-w-10 items-center justify-center gap-1 rounded-lg px-3 text-xs transition-colors ${
          knowledgeBaseEnabled
            ? 'bg-accent-green/20 text-accent-green'
            : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary'
        }`}
        title="知识库"
      >
        <Database size={13} />
      </button>

      <button
        type="button"
        onClick={onChooseAttachment}
        disabled={composerBusy || composerLocked}
        data-testid="composer-attachment-button"
        className="flex min-h-10 min-w-10 items-center justify-center gap-1 rounded-lg px-3 text-xs text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-40"
        title="附加文件"
      >
        <Paperclip size={13} />
      </button>

      <button
        type="button"
        onClick={onChooseImage}
        disabled={composerBusy || composerLocked}
        className="flex min-h-10 min-w-10 items-center justify-center gap-1 rounded-lg px-3 text-xs text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-40"
        title="上传图片"
      >
        <ImagePlus size={13} />
      </button>

      <button
        type="button"
        onClick={onStartResearch}
        disabled={!canResearch}
        data-testid="composer-research"
        className={`flex min-h-10 items-center gap-1 rounded-lg px-3 text-xs transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
          canResearch
            ? effectiveComposerResearchMode === 'deep' || hasOnlyComposerDataFiles
              ? 'bg-amber-400/15 text-amber-300 hover:bg-amber-400/20'
              : 'bg-accent-blue/15 text-accent-blue hover:bg-accent-blue/20'
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

      {activeStopHandler ? (
        <button
          type="button"
          onClick={activeStopHandler}
          className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent-red/20 text-accent-red transition-colors hover:bg-accent-red/30"
          title={stopButtonTitle}
        >
          <Square size={15} fill="currentColor" />
        </button>
      ) : (
        <button
          type="button"
          onClick={onSend}
          disabled={!canSend || composerBusy || composerLocked}
          data-testid="composer-send"
          className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent-blue text-white transition-colors hover:bg-accent-blue-hover disabled:cursor-not-allowed disabled:opacity-30"
          title="发送"
        >
          <Send size={15} />
        </button>
      )}
    </div>
  )
}
