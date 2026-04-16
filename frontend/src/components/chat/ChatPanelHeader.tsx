import React, { useRef } from 'react'
import {
  Download,
  Eraser,
  Eye,
  EyeOff,
  Search,
  Sparkles,
  Square,
  X,
} from 'lucide-react'
import { ModelSelector } from './ModelSelector'
import type { Panel, PanelMessage } from '../../stores/chatStore'
import type { ActiveStreamControl } from './streamControl'

interface ChatPanelHeaderProps {
  panel: Panel
  canRemove: boolean
  isStreaming: boolean
  loadingElapsedMs: number
  isInteractionLocked: boolean
  isStoppingSingleRunAvailable: boolean
  activeStreamControl: ActiveStreamControl | null
  msgCount: number
  contextUsed: number
  contextLimit: number
  hasWorkflowActivity: boolean
  workflowVisible: boolean
  searchOpen: boolean
  searchQuery: string
  matchedCount: number
  confirmClear: boolean
  clearing: boolean
  onRemovePanel: () => void
  onToggleWorkflowVisible: () => void
  onToggleSearch: () => void
  onSearchQueryChange: (q: string) => void
  onClearContext: () => void
  onExport: () => void
}

function formatLoadingElapsed(loadingElapsedMs: number): string {
  const totalSeconds = Math.max(0, Math.floor(loadingElapsedMs / 1000))
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  if (minutes <= 0) return `${seconds}s`
  return `${minutes}m ${String(seconds).padStart(2, '0')}s`
}

export const ChatPanelHeader: React.FC<ChatPanelHeaderProps> = ({
  panel,
  canRemove,
  isStreaming,
  loadingElapsedMs,
  isInteractionLocked,
  isStoppingSingleRunAvailable,
  activeStreamControl,
  msgCount,
  contextUsed,
  contextLimit,
  hasWorkflowActivity,
  workflowVisible,
  searchOpen,
  searchQuery,
  matchedCount,
  confirmClear,
  clearing,
  onRemovePanel,
  onToggleWorkflowVisible,
  onToggleSearch,
  onSearchQueryChange,
  onClearContext,
  onExport,
}) => {
  const searchInputRef = useRef<HTMLInputElement>(null)

  React.useEffect(() => {
    if (!searchOpen) return
    const timer = window.setTimeout(() => searchInputRef.current?.focus(), 50)
    return () => window.clearTimeout(timer)
  }, [searchOpen])

  return (
    <>
      <div className="flex shrink-0 items-center justify-between border-b border-bg-border bg-bg-tertiary/50 px-4 py-2.5">
        <ModelSelector
          panelId={panel.id}
          modelConfig={panel.modelConfig}
          onRemove={onRemovePanel}
          canRemove={canRemove}
          disabled={isInteractionLocked}
        />

        <div className="flex items-center gap-2">
          {isStreaming && (
            <div className="flex items-center gap-1.5 text-[10px] text-accent-blue">
              <Sparkles size={10} className="animate-pulse" />
              <span>生成中</span>
              <span className="rounded-full bg-accent-blue/10 px-1.5 py-0.5 tabular-nums">
                {formatLoadingElapsed(loadingElapsedMs)}
              </span>
            </div>
          )}

          {isStoppingSingleRunAvailable && activeStreamControl && (
            <button
              type="button"
              onClick={activeStreamControl.stop}
              className="flex items-center gap-1 rounded-md bg-accent-red/15 px-1.5 py-1 text-[10px] text-accent-red transition-colors hover:bg-accent-red/25"
              title={activeStreamControl.mode === 'single_continue' ? '停止当前续写' : '停止当前重跑'}
            >
              <Square size={10} fill="currentColor" />
              停止
            </button>
          )}

          {msgCount > 0 && !isStreaming && (
            <span
              className="text-[10px] text-text-secondary/60"
              title="当前上下文条数 / 窗口上限"
            >
              {contextUsed}/{contextLimit}
            </span>
          )}

          {(isStreaming || hasWorkflowActivity) && (
            <button
              type="button"
              onClick={onToggleWorkflowVisible}
              className="flex items-center gap-1 rounded-md px-1.5 py-1 text-[10px] text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
              title={workflowVisible ? '隐藏执行流程' : '显示执行流程'}
            >
              {workflowVisible ? <Eye size={11} /> : <EyeOff size={11} />}
            </button>
          )}

          {(panel.messages as PanelMessage[]).length > 0 && (
            <button
              type="button"
              onClick={onToggleSearch}
              className={`flex items-center gap-1 rounded-md px-1.5 py-1 text-[10px] transition-colors ${
                searchOpen
                  ? 'bg-accent-blue/20 text-accent-blue'
                  : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary'
              }`}
              title="搜索对话"
            >
              <Search size={11} />
            </button>
          )}

          {(panel.messages as PanelMessage[]).length > 0 && !isStreaming && (
            <button
              type="button"
              onClick={onExport}
              className="flex items-center gap-1 rounded-md px-1.5 py-1 text-[10px] text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
              title="导出对话（Markdown）"
            >
              <Download size={11} />
            </button>
          )}

          {(panel.messages as PanelMessage[]).length > 0 && (
            <button
              type="button"
              onClick={onClearContext}
              disabled={clearing || isInteractionLocked}
              className={`flex items-center gap-1 rounded-md px-1.5 py-1 text-[10px] transition-colors ${
                confirmClear
                  ? 'bg-accent-red/20 text-accent-red'
                  : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary'
              }`}
              title={confirmClear ? '再次点击确认清除' : '清除上下文'}
            >
              {clearing ? (
                <span className="block h-3 w-3 animate-spin rounded-full border border-current border-t-transparent" />
              ) : (
                <Eraser size={11} />
              )}
              {confirmClear ? '确认清除' : '清除'}
            </button>
          )}
        </div>
      </div>

      {searchOpen && (
        <div className="flex shrink-0 items-center gap-2 border-b border-bg-border/50 bg-bg-secondary/30 px-4 py-2">
          <Search size={12} className="shrink-0 text-text-secondary" />
          <input
            ref={searchInputRef}
            value={searchQuery}
            onChange={(event) => onSearchQueryChange(event.target.value)}
            placeholder="搜索消息内容..."
            className="flex-1 bg-transparent text-xs text-text-primary outline-none placeholder:text-text-secondary"
            onKeyDown={(event) => event.key === 'Escape' && onToggleSearch()}
          />
          {searchQuery && (
            <span className="shrink-0 text-[10px] text-text-secondary">
              {matchedCount} 条匹配
            </span>
          )}
          <button
            type="button"
            onClick={onToggleSearch}
            className="rounded p-0.5 text-text-secondary hover:text-text-primary"
          >
            <X size={12} />
          </button>
        </div>
      )}
    </>
  )
}
