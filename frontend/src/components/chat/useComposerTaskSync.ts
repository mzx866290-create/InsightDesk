import { useEffect, useRef } from 'react'
import type { SourceItem, TaskRecord } from '../../api/client'
import { useChatStore } from '../../stores/chatStore'
import { useTaskStore } from '../../stores/taskStore'
import { useWorkflowStore } from '../../stores/workflowStore'
import type { WorkflowNode } from '../../stores/workflowStore'

const getLatestMatchingResearchTask = (
  taskRecords: TaskRecord[],
  sessionId: string | null,
  panelId: string,
  answerGroupId: string,
): TaskRecord | undefined =>
  taskRecords
    .filter((item) => {
      if (item.task_type !== 'web_research') return false
      if ((item.session_id ?? '') !== (sessionId ?? '')) return false
      const params = item.params ?? {}
      return (
        params.answer_group_id === answerGroupId &&
        params.panel_id === panelId
      )
    })
    .sort((a, b) => (b.updated_at ?? b.created_at) - (a.updated_at ?? a.created_at))[0]

const getArrayParam = <T,>(
  params: Record<string, unknown> | undefined,
  key: string,
): T[] | undefined => {
  const value = params?.[key]
  return Array.isArray(value) ? value as T[] : undefined
}

export const useComposerTaskSync = () => {
  const panels = useChatStore((state) => state.panels)
  const currentSessionId = useChatStore((state) => state.currentSessionId)
  const replaceAssistantMessageByAnswerGroup = useChatStore(
    (state) => state.replaceAssistantMessageByAnswerGroup,
  )
  const tasksMap = useTaskStore((state) => state.tasks)
  const syncedResearchTaskSignaturesRef = useRef<Map<string, string>>(new Map())

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

        const task = getLatestMatchingResearchTask(
          taskRecords,
          currentSessionId,
          panel.id,
          message.answerGroupId,
        )
        if (!task) continue

        if (task.status === 'completed' && typeof task.result === 'string' && task.result.trim()) {
          const signature = `completed:${task.updated_at ?? task.created_at}:${task.result}`
          if (syncedResearchTaskSignaturesRef.current.get(task.task_id) === signature) {
            continue
          }

          const taskSources = getArrayParam<SourceItem>(task.params, 'research_sources')
          const taskWorkflowNodes = getArrayParam<WorkflowNode>(
            task.params,
            'research_workflow_nodes',
          )

          replaceAssistantMessageByAnswerGroup(panel.id, message.answerGroupId, {
            content: task.result,
            streaming: false,
            sources: taskSources,
            workflowNodes: taskWorkflowNodes,
            taskId: task.task_id,
            taskType: task.task_type,
          })
          if (taskWorkflowNodes && taskWorkflowNodes.length > 0) {
            useWorkflowStore.getState().hydrateWorkflow(panel.id, taskWorkflowNodes)
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
}
