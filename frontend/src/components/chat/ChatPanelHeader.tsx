/**
 * ChatPanel 头部组件
 * 包含：模型选择器、流式状态、操作按钮（停止/搜索/导出/清除）、搜索栏
 * 从 ChatPanel.tsx 拆分，减少单组件体积
 */

import React, { useRef } from 'react'
import { Sparkles, Square, Eye, EyeOff, Search, X, Eraser, Download } from 'lucide-react'
import { ModelSelector } from './ModelSelector'
import type { Panel, PanelMessage } from '../../stores/chatStore'
import type { ActiveStreamControl } from './streamControl'

interface ChatPanelHeaderProps {
  panel: Panel
  canRemove: boolean
  isStreaming: boolean
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

export const ChatPanelHeader: React.FC<ChatPanelHeaderProps> = ({
  panel,
  canRemove,
  isStreaming,
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

  // 搜索框打开时自动聚焦
  React.useEffect(() => {
    if (searchOpen) {
      setTimeout(() => searchInputRef.current?.focus(), 50)
    }
  }, [searchOpen])

  return (
    <>
      {/* 面板头部工具栏 */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-bg-border bg-bg-tertiary/50 shrink-0">
        <ModelSelector
          panelId={panel.id}
          modelConfig={panel.modelConfig}
          onRemove={onRemovePanel}
          canRemove={canRemove}
          disabled={isInteractionLocked}
        />

        <div className="flex items-center gap-2">
          {isStreaming && (
            <div className="flex items-center gap-1.5 text-accent-blue text-[10px]">
              <Sparkles size={10} className="animate-pulse" />
              生成中…
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
            <span className="text-[10px] text-text-secondary/60" title="当前上下文条数 / 窗口上限">
              {contextUsed}/{contextLimit}
            </span>
          )}

          {(isStreaming || hasWorkflowActivity) && (
            <button
              onClick={onToggleWorkflowVisible}
              className="flex items-center gap-1 px-1.5 py-1 rounded-md text-[10px] text-text-secondary hover:text-text-primary hover:bg-bg-hover transition-colors"
              title={workflowVisible ? '隐藏执行流程' : '显示执行流程'}
            >
              {workflowVisible ? <Eye size={11} /> : <EyeOff size={11} />}
            </button>
          )}

          {(panel.messages as PanelMessage[]).length > 0 && (
            <button
              onClick={onToggleSearch}
              className={`flex items-center gap-1 px-1.5 py-1 rounded-md text-[10px] transition-colors ${
                searchOpen
                  ? 'bg-accent-blue/20 text-accent-blue'
                  : 'text-text-secondary hover:text-text-primary hover:bg-bg-hover'
              }`}
              title="搜索对话"
            >
              <Search size={11} />
            </button>
          )}

          {(panel.messages as PanelMessage[]).length > 0 && !isStreaming && (
            <button
              onClick={onExport}
              className="flex items-center gap-1 px-1.5 py-1 rounded-md text-[10px] text-text-secondary hover:text-text-primary hover:bg-bg-hover transition-colors"
              title="导出对话（Markdown）"
            >
              <Download size={11} />
            </button>
          )}

          {(panel.messages as PanelMessage[]).length > 0 && (
            <button
              onClick={onClearContext}
              disabled={clearing || isInteractionLocked}
              className={`flex items-center gap-1 px-1.5 py-1 rounded-md text-[10px] transition-colors ${
                confirmClear
                  ? 'bg-accent-red/20 text-accent-red'
                  : 'text-text-secondary hover:text-text-primary hover:bg-bg-hover'
              }`}
              title={confirmClear ? '再次点击确认清除' : '清除上下文'}
            >
              {clearing ? (
                <span className="w-3 h-3 border border-current border-t-transparent rounded-full animate-spin block" />
              ) : (
                <Eraser size={11} />
              )}
              {confirmClear ? '确认清除' : '清除'}
            </button>
          )}
        </div>
      </div>

      {/* 搜索栏 */}
      {searchOpen && (
        <div className="px-4 py-2 border-b border-bg-border/50 bg-bg-secondary/30 shrink-0 flex items-center gap-2">
          <Search size={12} className="text-text-secondary shrink-0" />
          <input
            ref={searchInputRef}
            value={searchQuery}
            onChange={(e) => onSearchQueryChange(e.target.value)}
            placeholder="搜索消息内容…"
            className="flex-1 bg-transparent text-xs text-text-primary outline-none placeholder:text-text-secondary"
            onKeyDown={(e) => e.key === 'Escape' && onToggleSearch()}
          />
          {searchQuery && (
            <span className="text-[10px] text-text-secondary shrink-0">
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
