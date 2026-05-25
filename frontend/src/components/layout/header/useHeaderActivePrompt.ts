import { useEffect, useState } from 'react'

import { getSystemPrompts, type SystemPrompt } from '../../../api/client'

export function useHeaderActivePrompt(activePromptId: string | null) {
  const [activePrompt, setActivePrompt] = useState<SystemPrompt | null>(null)

  useEffect(() => {
    getSystemPrompts()
      .then((list) => {
        const active = list.find((prompt) => prompt.is_active) ?? list[0] ?? null
        setActivePrompt(active)
      })
      .catch(() => {})
  }, [activePromptId])

  return activePrompt
}
