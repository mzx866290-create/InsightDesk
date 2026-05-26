import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { ComposerSuggestion } from './messageInputUtils'
import { ComposerSuggestionMenu } from './ComposerSuggestionMenu'

const suggestions: ComposerSuggestion[] = [
  {
    id: 'summary',
    trigger: '/',
    label: 'summary',
    description: '总结当前问题',
    insertText: '请总结',
  },
  {
    id: 'prompt-analyst',
    trigger: '@',
    label: 'Analyst',
    description: '分析师提示词',
    insertText: '你是分析师',
  },
]

describe('ComposerSuggestionMenu', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders suggestions and applies the selected item on mouse down', () => {
    const onApplySuggestion = vi.fn()

    render(
      <ComposerSuggestionMenu
        suggestions={suggestions}
        activeSuggestionIndex={1}
        onApplySuggestion={onApplySuggestion}
      />,
    )

    expect(screen.getByText('summary')).toBeInTheDocument()
    expect(screen.getByText('Analyst')).toBeInTheDocument()

    fireEvent.mouseDown(screen.getByText('Analyst'))

    expect(onApplySuggestion).toHaveBeenCalledWith(suggestions[1])
  })

  it('renders nothing when there are no suggestions', () => {
    const { container } = render(
      <ComposerSuggestionMenu
        suggestions={[]}
        activeSuggestionIndex={0}
        onApplySuggestion={vi.fn()}
      />,
    )

    expect(container).toBeEmptyDOMElement()
  })
})
