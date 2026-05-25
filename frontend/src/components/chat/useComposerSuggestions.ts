import { useEffect, useState } from 'react'
import type { Dispatch, RefObject, SetStateAction } from 'react'
import { getSystemPrompts } from '../../api/client'
import type { SystemPrompt } from '../../api/client'
import {
  SLASH_TEMPLATES,
  type ComposerSuggestion,
  type TriggerRange,
} from './messageInputUtils'

interface UseComposerSuggestionsOptions {
  input: string
  setInput: Dispatch<SetStateAction<string>>
  textareaRef: RefObject<HTMLTextAreaElement>
  adjustHeight: () => void
}

export const useComposerSuggestions = ({
  input,
  setInput,
  textareaRef,
  adjustHeight,
}: UseComposerSuggestionsOptions) => {
  const [systemPrompts, setSystemPrompts] = useState<SystemPrompt[]>([])
  const [suggestions, setSuggestions] = useState<ComposerSuggestion[]>([])
  const [activeSuggestionIndex, setActiveSuggestionIndex] = useState(0)
  const [triggerRange, setTriggerRange] = useState<TriggerRange | null>(null)

  useEffect(() => {
    let disposed = false
    getSystemPrompts()
      .then((list) => {
        if (!disposed) setSystemPrompts(list)
      })
      .catch(() => {
        if (!disposed) setSystemPrompts([])
      })
    return () => {
      disposed = true
    }
  }, [])

  const closeSuggestions = () => {
    setSuggestions([])
    setActiveSuggestionIndex(0)
    setTriggerRange(null)
  }

  const updateSuggestions = (nextInput: string, caretPosition: number | null) => {
    if (caretPosition === null) {
      closeSuggestions()
      return
    }

    const textBeforeCaret = nextInput.slice(0, caretPosition)
    const triggerMatch = textBeforeCaret.match(/(?:^|\s)([@/][^\s@/]*)$/)
    if (!triggerMatch) {
      closeSuggestions()
      return
    }

    const triggerToken = triggerMatch[1]
    const trigger = triggerToken[0] as '/' | '@'
    const query = triggerToken.slice(1).trim().toLowerCase()
    const start = caretPosition - triggerToken.length

    let nextSuggestions: ComposerSuggestion[] = []
    if (trigger === '/') {
      nextSuggestions = SLASH_TEMPLATES
        .filter((item) =>
          query.length === 0 ||
          item.label.toLowerCase().includes(query) ||
          item.description.toLowerCase().includes(query),
        )
        .slice(0, 8)
    } else {
      nextSuggestions = systemPrompts
        .map((prompt) => {
          const normalizedContent = prompt.content.trim()
          return {
            id: `prompt-${prompt.id}`,
            trigger: '@' as const,
            label: prompt.name,
            description:
              normalizedContent.replace(/\s+/g, ' ').slice(0, 72) ||
              'System prompt template',
            insertText: normalizedContent ? `${normalizedContent}\n` : `@${prompt.name} `,
          }
        })
        .filter((item) =>
          query.length === 0 ||
          item.label.toLowerCase().includes(query) ||
          item.description.toLowerCase().includes(query),
        )
        .slice(0, 8)
    }

    if (nextSuggestions.length === 0) {
      closeSuggestions()
      return
    }

    setSuggestions(nextSuggestions)
    setActiveSuggestionIndex(0)
    setTriggerRange({ start, end: caretPosition })
  }

  const applySuggestion = (suggestion: ComposerSuggestion) => {
    if (!triggerRange) return

    const before = input.slice(0, triggerRange.start)
    const after = input.slice(triggerRange.end)
    const nextInput = `${before}${suggestion.insertText}${after}`
    const nextCaret = before.length + suggestion.insertText.length

    setInput(nextInput)
    closeSuggestions()

    window.requestAnimationFrame(() => {
      const textarea = textareaRef.current
      if (!textarea) return
      textarea.focus()
      textarea.setSelectionRange(nextCaret, nextCaret)
      adjustHeight()
    })
  }

  return {
    suggestions,
    activeSuggestionIndex,
    setActiveSuggestionIndex,
    closeSuggestions,
    updateSuggestions,
    applySuggestion,
  }
}
