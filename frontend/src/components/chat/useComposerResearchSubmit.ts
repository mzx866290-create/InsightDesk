import { useState } from 'react'
import type { ChatFile, ChatImage } from '../../api/client'
import { createAndTrackTask, createAndTrackWorkflowTask } from '../../stores/taskStore'
import { useChatStore } from '../../stores/chatStore'
import type { ResearchMode, ResearchSourceStrategy } from '../../stores/chatStore'
import {
  buildAnswerGroupId,
  buildDataWorkflowPlan,
  buildDeepResearchWorkflowPlan,
  isWorkflowDataFile,
} from './messageInputUtils'
import type { ResearchRequestConfig } from './messageInputUtils'

interface UseComposerResearchSubmitOptions {
  input: string
  images: ChatImage[]
  files: ChatFile[]
  pendingEditAnswerGroupId: string | null
  isInteractionLocked: boolean
  isSendLoading: boolean
  effectiveComposerResearchMode: ResearchMode
  researchModeLabel: string
  researchSourceStrategyLabel: string
  researchSourceStrategy: ResearchSourceStrategy
  researchRequestConfig: Record<ResearchMode, ResearchRequestConfig>
  ensureActiveSession: (sessionTitleSeed: string) => Promise<string | null>
  syncSessionMetaFromPanels: (sessionId: string) => void
  resetComposer: () => void
}

export const useComposerResearchSubmit = ({
  input,
  images,
  files,
  pendingEditAnswerGroupId,
  isInteractionLocked,
  isSendLoading,
  effectiveComposerResearchMode,
  researchModeLabel,
  researchSourceStrategyLabel,
  researchSourceStrategy,
  researchRequestConfig,
  ensureActiveSession,
  syncSessionMetaFromPanels,
  resetComposer,
}: UseComposerResearchSubmitOptions) => {
  const panels = useChatStore((state) => state.panels)
  const sessions = useChatStore((state) => state.sessions)
  const addUserMessage = useChatStore((state) => state.addUserMessage)
  const appendChunk = useChatStore((state) => state.appendChunk)
  const setAssistantMessage = useChatStore((state) => state.setAssistantMessage)
  const setTaskId = useChatStore((state) => state.setTaskId)
  const updateSessionTitle = useChatStore((state) => state.updateSessionTitle)

  const [isResearchStarting, setIsResearchStarting] = useState(false)

  const handleStartResearch = async () => {
    const query = input.trim()
    const requestConfig = researchRequestConfig[effectiveComposerResearchMode]
    const pendingImages = [...images]
    const pendingFiles = [...files]
    const pendingDataFiles = pendingFiles.filter(isWorkflowDataFile)
    const hasWorkflowDataFiles = pendingDataFiles.length > 0 && pendingDataFiles.length === pendingFiles.length
    const shouldUseWorkflow =
      effectiveComposerResearchMode === 'deep' || hasWorkflowDataFiles
    if (
      query.length === 0 ||
      pendingImages.length > 0 ||
      (pendingFiles.length > 0 && !hasWorkflowDataFiles) ||
      pendingEditAnswerGroupId ||
      isSendLoading ||
      isResearchStarting ||
      isInteractionLocked
    ) {
      return
    }

    setIsResearchStarting(true)
    const sessionTitleSeed = query
    const sessionId = await ensureActiveSession(sessionTitleSeed)
    if (!sessionId) {
      setIsResearchStarting(false)
      return
    }

    const currentSession = sessions.find((session) => session.session_id === sessionId)
    const answerGroupId = buildAnswerGroupId()
    const primaryPanelId = panels[0]?.id
    const assistantMessageId = `assistant-research-${Date.now()}`
    const researchModelId = shouldUseWorkflow ? 'multi_agent_workflow' : 'web_research'

    try {
      const task =
        shouldUseWorkflow
          ? await createAndTrackWorkflowTask({
              user_request: query,
              session_id: sessionId,
              panel_id: primaryPanelId ?? '',
              answer_group_id: answerGroupId,
              model_id: researchModelId,
              panel_config: panels[0]?.modelConfig,
              research_mode: effectiveComposerResearchMode,
              research_source_strategy: researchSourceStrategy,
              max_rounds: requestConfig.maxRounds,
              max_results_per_query: requestConfig.maxResultsPerQuery,
              context: hasWorkflowDataFiles
                ? {
                    workflow_origin: 'composer_data_files',
                    data_file_count: pendingDataFiles.length,
                  }
                : undefined,
              data_files: hasWorkflowDataFiles ? pendingDataFiles : undefined,
              plan: hasWorkflowDataFiles
                ? buildDataWorkflowPlan(query)
                : buildDeepResearchWorkflowPlan(query, requestConfig, researchSourceStrategy),
            })
          : await createAndTrackTask(
              'web_research',
              {
                query,
                research_mode: effectiveComposerResearchMode,
                research_source_strategy: researchSourceStrategy,
                search_depth: requestConfig.searchDepth,
                max_results: requestConfig.maxResults,
                max_results_per_query: requestConfig.maxResultsPerQuery,
                max_rounds: requestConfig.maxRounds,
                panel_config: panels[0]?.modelConfig,
                panel_id: primaryPanelId ?? '',
                answer_group_id: answerGroupId,
                model_id: researchModelId,
              },
              sessionId,
            )

      addUserMessage(query, [], hasWorkflowDataFiles ? pendingDataFiles : [], answerGroupId)

      if (primaryPanelId) {
        appendChunk(primaryPanelId, assistantMessageId, '', {
          answerGroupId,
          modelId: researchModelId,
        })
        setAssistantMessage(
          primaryPanelId,
          assistantMessageId,
          `已发起联网研究任务（${researchModeLabel}），系统会整理实时网页来源并在任务完成后显示摘要。`,
          false,
        )
        if (researchSourceStrategy !== 'web_only') {
          setAssistantMessage(
            primaryPanelId,
            assistantMessageId,
            `已启用 ${researchSourceStrategyLabel} 情报模式，系统会优先收集社区线索并要求独立来源复核。`,
            false,
          )
        }
        if (hasWorkflowDataFiles) {
          setAssistantMessage(
            primaryPanelId,
            assistantMessageId,
            `已发起数据分析工作流（${pendingDataFiles.length} 个文件），系统会先解析表格并生成摘要、图表和审核结果。`,
            false,
          )
        }
        setTaskId(primaryPanelId, assistantMessageId, task.task_id, task.task_type)
      }

      syncSessionMetaFromPanels(sessionId)

      if (currentSession && currentSession.message_count === 0 && sessionTitleSeed) {
        updateSessionTitle(sessionId, sessionTitleSeed.slice(0, 40))
      }

      resetComposer()
    } catch (error) {
      console.error('Failed to create web research task', error)
      window.alert((error as Error).message || '联网研究任务创建失败，请稍后重试。')
    } finally {
      setIsResearchStarting(false)
    }
  }

  return {
    isResearchStarting,
    handleStartResearch,
  }
}
