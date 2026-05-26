import React, { useEffect, useRef, useState } from 'react'
import { useChatStore } from '../../stores/chatStore'
import type { ResearchMode, ResearchSourceStrategy } from '../../stores/chatStore'
import type { ActiveStreamControl } from './streamControl'
import { ComposerAttachmentTray } from './ComposerAttachmentTray'
import { ComposerSuggestionMenu } from './ComposerSuggestionMenu'
import { ComposerToolbar } from './ComposerToolbar'
import {
  RESEARCH_REQUEST_CONFIG,
  RESEARCH_SOURCE_STRATEGY_OPTIONS,
  getEffectiveComposerResearchMode,
  getResearchModeLabel,
  getResearchSourceStrategyLabel,
} from './composerResearchConfig'
import {
  isWorkflowDataFile,
  mergeComposerText,
} from './messageInputUtils'
import { useComposerAttachments } from './useComposerAttachments'
import { useComposerResearchSubmit } from './useComposerResearchSubmit'
import { useComposerSendSubmit } from './useComposerSendSubmit'
import { useComposerSession } from './useComposerSession'
import { useComposerSuggestions } from './useComposerSuggestions'
import { useComposerTaskSync } from './useComposerTaskSync'

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
    addSession,
    setCurrentSession,
    updateSession,
    composerSeed,
    adjustWorkspaceSessionCount,
  } = useChatStore()

  const effectiveComposerResearchMode = getEffectiveComposerResearchMode(
    researchMode,
    researchSourceStrategy,
  )
  const researchModeLabel = getResearchModeLabel(effectiveComposerResearchMode)
  const researchSourceStrategyLabel = getResearchSourceStrategyLabel(researchSourceStrategy)

  const [input, setInput] = useState('')
  const [pendingEditAnswerGroupId, setPendingEditAnswerGroupId] = useState<string | null>(null)
  const [omitHistoryForNextSend, setOmitHistoryForNextSend] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const imageInputRef = useRef<HTMLInputElement>(null)
  const attachmentInputRef = useRef<HTMLInputElement>(null)

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

  useComposerTaskSync()

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
    researchRequestConfig: RESEARCH_REQUEST_CONFIG,
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
          ? '以深研模式发起联网研究；若研究模型不可用会自动回退快研'
          : '以快研模式发起联网研究；更快返回网页摘要与来源'
  const effectiveResearchButtonTitle = hasOnlyComposerDataFiles
    ? '用多 Agent 数据分析工作流处理 CSV/TSV/JSON/Excel 文件'
    : researchButtonTitle

  const handleSelectResearchMode = (mode: ResearchMode) => {
    setResearchMode(mode)
    if (mode === 'quick') {
      setResearchSourceStrategy('web_only')
    }
  }

  const handleSelectResearchSourceStrategy = (strategy: ResearchSourceStrategy) => {
    setResearchSourceStrategy(strategy)
    if (strategy !== 'web_only') {
      setResearchMode('deep')
    }
  }

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

        <ComposerAttachmentTray
          images={images}
          files={files}
          disabled={composerLocked}
          onRemoveImage={handleRemoveImage}
          onRemoveFile={handleRemoveFile}
        />

        <div className="rounded-2xl border border-bg-border bg-bg-secondary px-4 py-3 transition-colors focus-within:border-accent-blue/50">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="relative w-full flex-1">
              <ComposerSuggestionMenu
                suggestions={suggestions}
                activeSuggestionIndex={activeSuggestionIndex}
                onApplySuggestion={applySuggestion}
              />

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

            <ComposerToolbar
              researchMode={researchMode}
              researchSourceStrategy={researchSourceStrategy}
              researchSourceStrategyOptions={RESEARCH_SOURCE_STRATEGY_OPTIONS}
              omitHistoryForNextSend={omitHistoryForNextSend}
              webSearchEnabled={webSearchEnabled}
              knowledgeBaseEnabled={knowledgeBaseEnabled}
              composerBusy={composerBusy}
              composerLocked={composerLocked}
              canResearch={canResearch}
              canSend={canSend}
              hasOnlyComposerDataFiles={hasOnlyComposerDataFiles}
              effectiveComposerResearchMode={effectiveComposerResearchMode}
              researchButtonLabel={researchButtonLabel}
              researchButtonTitle={effectiveResearchButtonTitle}
              isResearchStarting={isResearchStarting}
              activeStopHandler={activeStopHandler}
              stopButtonTitle={stopButtonTitle}
              onSelectResearchMode={handleSelectResearchMode}
              onSelectResearchSourceStrategy={handleSelectResearchSourceStrategy}
              onToggleOmitHistory={() => setOmitHistoryForNextSend((current) => !current)}
              onToggleWebSearch={() => setWebSearchEnabled(!webSearchEnabled)}
              onToggleKnowledgeBase={() => setKnowledgeBaseEnabled(!knowledgeBaseEnabled)}
              onChooseAttachment={() => attachmentInputRef.current?.click()}
              onChooseImage={() => imageInputRef.current?.click()}
              onStartResearch={() => {
                void handleStartResearch()
              }}
              onSend={() => {
                void handleSend()
              }}
            />
          </div>
        </div>

        <div className="mt-2 flex items-center justify-center text-[10px] text-text-secondary/50">
          AI 可能出错，重要信息请自行核实。
        </div>
      </div>
    </div>
  )
}
