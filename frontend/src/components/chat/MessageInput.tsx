import React, { useEffect, useRef, useState } from 'react'
import { Send, Globe, Square, Database, ImagePlus, Paperclip, Sparkles, Loader2, X, Eraser } from 'lucide-react'
import { useChatStore } from '../../stores/chatStore'
import type { ResearchMode, ResearchSourceStrategy } from '../../stores/chatStore'
import type { SourceItem } from '../../api/client'
import { useTaskStore } from '../../stores/taskStore'
import type { ActiveStreamControl } from './streamControl'
import { useWorkflowStore } from '../../stores/workflowStore'
import {
  type ResearchRequestConfig,
  formatFileSize,
  isWorkflowDataFile,
  mergeComposerText,
} from './messageInputUtils'
import { useComposerAttachments } from './useComposerAttachments'
import { useComposerResearchSubmit } from './useComposerResearchSubmit'
import { useComposerSendSubmit } from './useComposerSendSubmit'
import { useComposerSession } from './useComposerSession'
import { useComposerSuggestions } from './useComposerSuggestions'

interface MessageInputProps {
  onStreamingChange: (panelId: string, streaming: boolean) => void
  isInteractionLocked: boolean
  activeStreamControl: ActiveStreamControl | null
  setActiveStreamControl: (control: ActiveStreamControl | null) => void
}

export const MessageInput: React.FC<MessageInputProps> = ({
  onStreamingChange,
  isInteractionLocked,
  activeStreamControl,
  setActiveStreamControl,
}) => {
  const {
    panels,
    currentSessionId,
    currentWorkspaceId,
    webSearchEnabled,
    setWebSearchEnabled,
    knowledgeBaseEnabled,
    setKnowledgeBaseEnabled,
    researchMode,
    setResearchMode,
    researchSourceStrategy,
    setResearchSourceStrategy,
    replaceAssistantMessageByAnswerGroup,
    addSession,
    setCurrentSession,
    updateSession,
    composerSeed,
    adjustWorkspaceSessionCount,
  } = useChatStore()
  const tasksMap = useTaskStore((state) => state.tasks)

  const researchSourceStrategyOptions: Array<{
    value: ResearchSourceStrategy
    label: string
    title: string
  }> = [
    {
      value: 'web_only',
      label: 'Web',
      title: 'Standard web-first deep research',
    },
    {
      value: 'community_first',
      label: 'Community',
      title: 'Community-first deep research using search-indexed social/forum leads plus independent verification',
    },
    {
      value: 'evidence_strict',
      label: 'Strict',
      title: 'Strict evidence mode; social and community pages stay contextual unless independently verified',
    },
  ]
  const effectiveComposerResearchMode =
    researchSourceStrategy === 'web_only' ? researchMode : 'deep'
  const researchModeLabel = effectiveComposerResearchMode === 'quick' ? 'Quick' : 'Deep'
  const researchSourceStrategyLabel =
    researchSourceStrategy === 'community_first'
      ? 'Community'
      : researchSourceStrategy === 'evidence_strict'
        ? 'Strict'
        : researchSourceStrategy === 'web_and_community'
          ? 'Web+Community'
          : 'Web'
  const researchRequestConfig: Record<ResearchMode, ResearchRequestConfig> = {
    quick: {
      searchDepth: 'basic',
      maxResults: 5,
      maxRounds: 1,
      maxResultsPerQuery: 2,
    },
    deep: {
      searchDepth: 'advanced',
      maxResults: 8,
      maxRounds: 2,
      maxResultsPerQuery: 4,
    },
  }

  const [input, setInput] = useState('')
  const [pendingEditAnswerGroupId, setPendingEditAnswerGroupId] = useState<string | null>(null)
  const [omitHistoryForNextSend, setOmitHistoryForNextSend] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const imageInputRef = useRef<HTMLInputElement>(null)
  const attachmentInputRef = useRef<HTMLInputElement>(null)
  const syncedResearchTaskSignaturesRef = useRef<Map<string, string>>(new Map())

  const {
    images,
    files,
    mergeAttachments,
    clearAttachments,
    restoreAttachments,
    handleSelectImages,
    handleRemoveImage,
    handleSelectFiles,
    handleRemoveFile,
    handlePaste,
  } = useComposerAttachments()

  const adjustHeight = () => {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = 'auto'
    ta.style.height = `${Math.min(ta.scrollHeight, 180)}px`
  }

  const {
    suggestions,
    activeSuggestionIndex,
    setActiveSuggestionIndex,
    closeSuggestions,
    updateSuggestions,
    applySuggestion,
  } = useComposerSuggestions({
    input,
    setInput,
    textareaRef,
    adjustHeight,
  })

  const {
    ensureActiveSession,
    syncSessionMetaFromPanels,
  } = useComposerSession({
    currentSessionId,
    currentWorkspaceId,
    setCurrentSession,
    addSession,
    updateSession,
    adjustWorkspaceSessionCount,
  })

  useEffect(() => {
    if (composerSeed.token === 0) return

    setInput((current) => mergeComposerText(current, composerSeed.text))
    mergeAttachments(composerSeed.images, composerSeed.files)
    setPendingEditAnswerGroupId(composerSeed.editAnswerGroupId ?? null)

    window.requestAnimationFrame(() => {
      adjustHeight()
      textareaRef.current?.focus()
    })
  }, [composerSeed])

  useEffect(() => {
    const taskRecords = Object.values(tasksMap)

    for (const panel of panels) {
      for (const message of panel.messages) {
        if (
          message.role !== 'assistant' ||
          message.taskType !== 'web_research' ||
          !message.answerGroupId
        ) {
          continue
        }

        const task = taskRecords
          .filter((item) => {
            if (item.task_type !== 'web_research') return false
            if ((item.session_id ?? '') !== (currentSessionId ?? '')) return false
            const params = item.params ?? {}
            return (
              params.answer_group_id === message.answerGroupId &&
              params.panel_id === panel.id
            )
          })
          .sort((a, b) => (b.updated_at ?? b.created_at) - (a.updated_at ?? a.created_at))[0]
        if (!task) continue

        if (task.status === 'completed' && typeof task.result === 'string' && task.result.trim()) {
          const signature = `completed:${task.updated_at ?? task.created_at}:${task.result}`
          if (syncedResearchTaskSignaturesRef.current.get(task.task_id) === signature) {
            continue
          }

          const taskSources = Array.isArray(task.params?.research_sources)
            ? task.params.research_sources
            : undefined
          const taskWorkflowNodes = Array.isArray(task.params?.research_workflow_nodes)
            ? task.params.research_workflow_nodes
            : undefined

          replaceAssistantMessageByAnswerGroup(panel.id, message.answerGroupId, {
            content: task.result,
            streaming: false,
            sources: taskSources as SourceItem[] | undefined,
            workflowNodes: taskWorkflowNodes as any,
            taskId: task.task_id,
            taskType: task.task_type,
          })
          if (taskWorkflowNodes && taskWorkflowNodes.length > 0) {
            useWorkflowStore.getState().hydrateWorkflow(panel.id, taskWorkflowNodes as any)
          }
          syncedResearchTaskSignaturesRef.current.set(task.task_id, signature)
          continue
        }

        if (task.status === 'failed' && typeof task.error === 'string' && task.error.trim()) {
          const failureContent = `联网研究任务失败：${task.error}`
          const signature = `failed:${task.updated_at ?? task.created_at}:${failureContent}`
          if (syncedResearchTaskSignaturesRef.current.get(task.task_id) === signature) {
            continue
          }

          replaceAssistantMessageByAnswerGroup(panel.id, message.answerGroupId, {
            content: failureContent,
            streaming: false,
            taskId: task.task_id,
            taskType: task.task_type,
          })
          syncedResearchTaskSignaturesRef.current.set(task.task_id, signature)
        }
      }
    }
  }, [currentSessionId, panels, replaceAssistantMessageByAnswerGroup, tasksMap])

  const resetComposer = () => {
    setInput('')
    clearAttachments()
    setPendingEditAnswerGroupId(null)
    setOmitHistoryForNextSend(false)
    closeSuggestions()
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
    if (imageInputRef.current) {
      imageInputRef.current.value = ''
    }
    if (attachmentInputRef.current) {
      attachmentInputRef.current.value = ''
    }
  }

  const {
    isLoading,
    handleSend,
    handleStop,
  } = useComposerSendSubmit({
    input,
    images,
    files,
    pendingEditAnswerGroupId,
    omitHistoryForNextSend,
    isInteractionLocked,
    textareaRef,
    adjustHeight,
    resetComposer,
    restoreAttachments,
    setInput,
    setPendingEditAnswerGroupId,
    setOmitHistoryForNextSend,
    ensureActiveSession,
    syncSessionMetaFromPanels,
    onStreamingChange,
    setActiveStreamControl,
  })

  const {
    isResearchStarting,
    handleStartResearch,
  } = useComposerResearchSubmit({
    input,
    images,
    files,
    pendingEditAnswerGroupId,
    isInteractionLocked,
    isSendLoading: isLoading,
    effectiveComposerResearchMode,
    researchModeLabel,
    researchSourceStrategyLabel,
    researchSourceStrategy,
    researchRequestConfig,
    ensureActiveSession,
    syncSessionMetaFromPanels,
    resetComposer,
  })

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (suggestions.length > 0) {
      if (event.key === 'ArrowDown') {
        event.preventDefault()
        setActiveSuggestionIndex((current) => (current + 1) % suggestions.length)
        return
      }
      if (event.key === 'ArrowUp') {
        event.preventDefault()
        setActiveSuggestionIndex((current) => (current - 1 + suggestions.length) % suggestions.length)
        return
      }
      if (event.key === 'Escape') {
        event.preventDefault()
        closeSuggestions()
        return
      }
      if ((event.key === 'Enter' && !event.shiftKey) || event.key === 'Tab') {
        event.preventDefault()
        const selected = suggestions[activeSuggestionIndex]
        if (selected) {
          applySuggestion(selected)
          return
        }
      }
    }

    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      void handleSend()
    }
  }

  const activeStopHandler = isLoading ? handleStop : activeStreamControl?.stop ?? null
  const stopButtonTitle =
    activeStreamControl?.mode === 'single_rerun'
      ? '停止重跑'
      : activeStreamControl?.mode === 'single_continue'
        ? '停止续写'
        : '停止生成'
  const lockedPlaceholder =
    activeStreamControl?.mode === 'single_rerun'
      ? '某个面板正在重新生成，可以停止它，或等待完成后再发送新消息。'
      : activeStreamControl?.mode === 'single_continue'
        ? '某个面板正在继续生成，可以停止它，或等待完成后再发送新消息。'
        : '正在生成回答，请等待完成后再发送新消息。'
  const composerLocked = isInteractionLocked && !isLoading
  const composerBusy = isLoading || isResearchStarting
  const canSend = input.trim().length > 0 || images.length > 0 || files.length > 0
  const composerDataFiles = files.filter(isWorkflowDataFile)
  const hasOnlyComposerDataFiles =
    composerDataFiles.length > 0 && composerDataFiles.length === files.length
  const canResearch =
    input.trim().length > 0 &&
    images.length === 0 &&
    (files.length === 0 || hasOnlyComposerDataFiles) &&
    !pendingEditAnswerGroupId &&
    !composerBusy &&
    !composerLocked
  const researchButtonLabel = hasOnlyComposerDataFiles
    ? '分析'
    : researchSourceStrategy === 'web_only'
      ? '研究'
      : researchSourceStrategyLabel
  const researchButtonTitle =
    pendingEditAnswerGroupId
      ? '编辑重发模式下暂不支持联网研究'
      : images.length > 0 || files.length > 0
        ? '联网研究暂不支持图片或文件附件'
        : effectiveComposerResearchMode === 'deep'
          ? '以 Deep 模式发起联网研究；若研究模型不可用会自动回退 Quick'
          : '以 Quick 模式发起联网研究；更快返回网页摘要与来源'
  const effectiveResearchButtonTitle = hasOnlyComposerDataFiles
    ? '用多 Agent 数据分析工作流处理 CSV/TSV/JSON/Excel 文件'
    : researchButtonTitle

  return (
    <div
      className="sticky bottom-0 z-10 shrink-0 border-t border-bg-border bg-bg-primary/95 px-4 py-3 pb-[calc(env(safe-area-inset-bottom)+0.75rem)] backdrop-blur-sm"
      data-testid="message-composer"
    >
      <div className="mx-auto max-w-4xl">
        {pendingEditAnswerGroupId && (
          <div className="mb-2 flex items-center justify-between rounded-xl border border-amber-400/25 bg-amber-400/10 px-3 py-2 text-xs text-amber-200">
            <span>编辑模式已开启：发送后会截断该消息之后的内容并重新生成。</span>
            <button
              type="button"
              onClick={() => setPendingEditAnswerGroupId(null)}
              className="rounded-md px-1.5 py-0.5 text-[11px] text-amber-100/80 transition-colors hover:bg-amber-300/20 hover:text-amber-100"
            >
              取消
            </button>
          </div>
        )}

        {images.length > 0 && (
          <div className="mb-2 flex flex-wrap gap-2">
            {images.map((image, index) => (
              <div
                key={`${image.name}-${index}`}
                className="group relative overflow-hidden rounded-xl border border-bg-border bg-bg-secondary"
              >
                <img
                  src={image.data_url}
                  alt={image.name}
                  className="h-20 w-20 object-cover"
                />
                <button
                  type="button"
                  onClick={() => handleRemoveImage(index)}
                  disabled={composerLocked}
                  className="absolute right-1 top-1 flex h-5 w-5 items-center justify-center rounded-full bg-black/60 text-white opacity-90 transition-opacity group-hover:opacity-100"
                  title="Remove image"
                >
                  <X size={12} />
                </button>
              </div>
            ))}
          </div>
        )}
        {files.length > 0 && (
          <div className="mb-2 flex flex-wrap gap-2">
            {files.map((file, index) => (
              <div
                key={`${file.name}-${index}`}
                className="group flex items-center gap-2 rounded-xl border border-bg-border bg-bg-secondary px-3 py-2 text-xs text-text-primary"
              >
                <Paperclip size={12} className="shrink-0 text-text-secondary" />
                <div className="flex min-w-0 flex-col">
                  <span className="max-w-[180px] truncate">{file.name}</span>
                  <span className="text-[10px] text-text-secondary">
                    {formatFileSize(file.size_bytes)}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => handleRemoveFile(index)}
                  disabled={composerLocked}
                  className="flex h-5 w-5 items-center justify-center rounded-full text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
                  title="Remove file"
                >
                  <X size={12} />
                </button>
              </div>
            ))}
          </div>
        )}

        <div className="rounded-2xl border border-bg-border bg-bg-secondary px-4 py-3 transition-colors focus-within:border-accent-blue/50">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="relative w-full flex-1">
              {suggestions.length > 0 && (
                <div className="absolute bottom-full left-0 right-0 z-20 mb-2 overflow-hidden rounded-xl border border-bg-border bg-bg-primary shadow-xl">
                  <div className="max-h-56 overflow-y-auto py-1">
                    {suggestions.map((suggestion, index) => (
                      <button
                        key={suggestion.id}
                        type="button"
                        className={`w-full px-3 py-2 text-left transition-colors ${
                          index === activeSuggestionIndex
                            ? 'bg-accent-blue/15'
                            : 'hover:bg-bg-hover'
                        }`}
                        onMouseDown={(event) => {
                          event.preventDefault()
                          applySuggestion(suggestion)
                        }}
                      >
                        <div className="flex items-center gap-2 text-xs font-medium text-text-primary">
                          <span className="rounded-md bg-bg-tertiary px-1.5 py-0.5 text-[10px] text-text-secondary">
                            {suggestion.trigger}
                          </span>
                          <span>{suggestion.label}</span>
                        </div>
                        <p className="mt-1 line-clamp-2 text-[11px] leading-4 text-text-secondary">
                          {suggestion.description}
                        </p>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <textarea
                ref={textareaRef}
                data-testid="composer-input"
                className="min-h-[24px] max-h-[180px] w-full resize-none bg-transparent text-sm leading-relaxed text-text-primary outline-none placeholder:text-text-secondary"
                placeholder={
                  composerLocked
                    ? lockedPlaceholder
                  : '输入消息，可上传文件或图片。Enter 发送，Shift+Enter 换行。'
                }
                value={input}
                onChange={(event) => {
                  const nextValue = event.target.value
                  setInput(nextValue)
                  updateSuggestions(nextValue, event.target.selectionStart)
                  adjustHeight()
                }}
                onClick={(event) => updateSuggestions(event.currentTarget.value, event.currentTarget.selectionStart)}
                onKeyUp={(event) => {
                  if (event.key === 'ArrowUp' || event.key === 'ArrowDown') return
                  updateSuggestions(event.currentTarget.value, event.currentTarget.selectionStart)
                }}
                onPaste={(event) => {
                  void handlePaste(event)
                }}
                onKeyDown={handleKeyDown}
                rows={1}
                disabled={composerBusy || composerLocked}
              />
            </div>

            <input
              ref={imageInputRef}
              type="file"
              accept="image/*"
              multiple
              data-testid="composer-image-input"
              className="hidden"
              onChange={(event) => {
                void handleSelectImages(event)
              }}
            />

            <input
              ref={attachmentInputRef}
              type="file"
              accept=".pdf,.doc,.docx,.txt,.md,.csv,.tsv,.json,.xls,.xlsx"
              multiple
              data-testid="composer-attachment-input"
              className="hidden"
              onChange={(event) => {
                void handleSelectFiles(event)
              }}
            />

            <div className="flex flex-wrap items-center justify-end gap-2 sm:pb-0.5">
              <div
                className="inline-flex items-center rounded-lg border border-bg-border bg-bg-primary/50 p-0.5"
                title="研究模式"
              >
                {(['quick', 'deep'] as const).map((mode) => {
                  const active = researchMode === mode
                  const label = mode === 'quick' ? 'Quick' : 'Deep'
                  return (
                    <button
                      key={mode}
                      type="button"
                      onClick={() => {
                        setResearchMode(mode)
                        if (mode === 'quick') {
                          setResearchSourceStrategy('web_only')
                        }
                      }}
                      disabled={composerBusy || composerLocked}
                      data-testid={`composer-research-mode-${mode}`}
                      className={`rounded-md px-2 py-1 text-[11px] transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
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
                title="Research source strategy"
              >
                {researchSourceStrategyOptions.map((option) => {
                  const active = researchSourceStrategy === option.value
                  const isCommunity = option.value === 'community_first'
                  const isStrict = option.value === 'evidence_strict'
                  return (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => {
                        setResearchSourceStrategy(option.value)
                        if (option.value !== 'web_only') {
                          setResearchMode('deep')
                        }
                      }}
                      disabled={composerBusy || composerLocked}
                      data-testid={`composer-research-source-${option.value}`}
                      className={`rounded-md px-2 py-1 text-[11px] transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
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
                onClick={() => setOmitHistoryForNextSend((current) => !current)}
                disabled={composerLocked}
                data-testid="composer-omit-history-toggle"
                className={`flex items-center gap-1 rounded-lg px-2 py-1.5 text-xs transition-colors ${
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
                onClick={() => setWebSearchEnabled(!webSearchEnabled)}
                disabled={composerLocked}
                data-testid="composer-web-search-toggle"
                className={`flex items-center gap-1 rounded-lg px-2 py-1.5 text-xs transition-colors ${
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
                onClick={() => setKnowledgeBaseEnabled(!knowledgeBaseEnabled)}
                disabled={composerLocked}
                data-testid="composer-knowledge-base-toggle"
                className={`flex items-center gap-1 rounded-lg px-2 py-1.5 text-xs transition-colors ${
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
                onClick={() => attachmentInputRef.current?.click()}
                disabled={composerBusy || composerLocked}
                data-testid="composer-attachment-button"
                className="flex items-center gap-1 rounded-lg px-2 py-1.5 text-xs text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-40"
                title="附加文件"
              >
                <Paperclip size={13} />
              </button>

              <button
                type="button"
                onClick={() => imageInputRef.current?.click()}
                disabled={composerBusy || composerLocked}
                className="flex items-center gap-1 rounded-lg px-2 py-1.5 text-xs text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-40"
                title="上传图片"
              >
                <ImagePlus size={13} />
              </button>

              <button
                type="button"
                onClick={() => {
                  void handleStartResearch()
                }}
                disabled={!canResearch}
                data-testid="composer-research"
                className={`flex items-center gap-1 rounded-lg px-2 py-1.5 text-xs transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
                  canResearch
                    ? effectiveComposerResearchMode === 'deep' || hasOnlyComposerDataFiles
                      ? 'bg-amber-400/15 text-amber-300 hover:bg-amber-400/20'
                      : 'bg-accent-blue/15 text-accent-blue hover:bg-accent-blue/20'
                    : 'text-text-secondary'
                }`}
                title={effectiveResearchButtonTitle}
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
                  className="flex h-8 w-8 items-center justify-center rounded-xl bg-accent-red/20 text-accent-red transition-colors hover:bg-accent-red/30"
                  title={stopButtonTitle}
                >
                  <Square size={13} fill="currentColor" />
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => {
                    void handleSend()
                  }}
                  disabled={!canSend || composerBusy || composerLocked}
                  data-testid="composer-send"
                  className="flex h-8 w-8 items-center justify-center rounded-xl bg-accent-blue text-white transition-colors hover:bg-accent-blue-hover disabled:cursor-not-allowed disabled:opacity-30"
                  title="发送"
                >
                  <Send size={13} />
                </button>
              )}
            </div>
          </div>
        </div>

        <div className="mt-2 flex items-center justify-center text-[10px] text-text-secondary/50">
          AI 可能出错，重要信息请自行核实。
        </div>
      </div>
    </div>
  )
}
