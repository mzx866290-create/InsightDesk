import { useCallback, useEffect, useState } from 'react'

import { getDeck } from '../../../api/client'
import type { DeckSpec, ModelConfig } from '../../../api/client'
import { createAndTrackTask, useTaskStore } from '../../../stores/taskStore'
import type { HeaderActionFeedbackSetter, HeaderDeckTheme } from './headerTypes'

export interface HeaderDeckGenerationPayload {
  panel_config: ModelConfig
  target_slide_count: number
  theme: HeaderDeckTheme
  template_id?: string
  template_options?: Record<string, unknown>
}

interface UseHeaderDeckActionsOptions {
  currentSessionId: string | null
  knowledgeBaseEnabled: boolean
  setActionFeedback: HeaderActionFeedbackSetter
}

export function useHeaderDeckActions({
  currentSessionId,
  knowledgeBaseEnabled,
  setActionFeedback,
}: UseHeaderDeckActionsOptions) {
  const [deckTaskId, setDeckTaskId] = useState<string | null>(null)
  const [handledDeckTaskId, setHandledDeckTaskId] = useState<string | null>(null)
  const deckTask = useTaskStore((state) => (deckTaskId ? state.tasks[deckTaskId] : undefined))
  const [deckConfigOpen, setDeckConfigOpen] = useState(false)
  const [deckOpen, setDeckOpen] = useState(false)
  const [deckData, setDeckData] = useState<DeckSpec | null>(null)
  const [generatingDeck, setGeneratingDeck] = useState(false)
  const isDeckTaskActive = deckTask?.status === 'pending' || deckTask?.status === 'running'

  useEffect(() => {
    if (!deckTaskId || !deckTask || handledDeckTaskId === deckTaskId) return

    if (deckTask.status === 'completed') {
      const nextDeckId =
        typeof deckTask.params?.deck_id === 'string' ? deckTask.params.deck_id : ''
      if (!nextDeckId) {
        setActionFeedback({
          tone: 'error',
          message: 'Deck 任务已完成，但没有返回可打开的 deck_id。',
        })
        setHandledDeckTaskId(deckTaskId)
        return
      }

      void getDeck(nextDeckId)
        .then((deck) => {
          setDeckData(deck)
          setDeckOpen(true)
          setActionFeedback(null)
          setHandledDeckTaskId(deckTaskId)
        })
        .catch((error) => {
          setActionFeedback({
            tone: 'error',
            message: `打开生成后的 Deck 失败：${(error as Error).message}`,
          })
          setHandledDeckTaskId(deckTaskId)
        })
      return
    }

    if (deckTask.status === 'failed') {
      setActionFeedback({
        tone: 'error',
        message: deckTask.error || '生成演示稿失败，请稍后重试。',
      })
      setHandledDeckTaskId(deckTaskId)
    }
  }, [deckTask, deckTaskId, handledDeckTaskId, setActionFeedback])

  const handleGenerateReport = useCallback(() => {
    if (!currentSessionId || generatingDeck || isDeckTaskActive) return
    setDeckConfigOpen(true)
  }, [currentSessionId, generatingDeck, isDeckTaskActive])

  const handleGenerateDeck = useCallback(async (payload: HeaderDeckGenerationPayload) => {
    if (!currentSessionId) return
    setGeneratingDeck(true)
    try {
      const task = await createAndTrackTask(
        'generate_deck',
        {
          panel_config: payload.panel_config,
          knowledge_base_enabled: knowledgeBaseEnabled,
          target_slide_count: payload.target_slide_count,
          theme: payload.theme,
          template_id: payload.template_id,
          template_options: payload.template_options,
        },
        currentSessionId,
      )
      setDeckTaskId(task.task_id)
      setHandledDeckTaskId(null)
      setActionFeedback({
        tone: 'success',
        message: '演示稿生成任务已加入任务中心，完成后会自动打开。',
      })
    } catch (error) {
      setActionFeedback({
        tone: 'error',
        message: `生成演示稿失败：${(error as Error).message}`,
      })
    } finally {
      setGeneratingDeck(false)
    }
  }, [currentSessionId, knowledgeBaseEnabled, setActionFeedback])

  return {
    deckTaskId,
    deckConfigOpen,
    setDeckConfigOpen,
    deckOpen,
    setDeckOpen,
    deckData,
    setDeckData,
    generatingDeck,
    isDeckTaskActive,
    handleGenerateReport,
    handleGenerateDeck,
  }
}
