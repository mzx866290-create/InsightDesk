import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import type { RetrievalDebugItem } from '../../api/client'
import { KbRetrievalDebugList } from './KbRetrievalDebugList'

const item = (patch: Partial<RetrievalDebugItem> = {}): RetrievalDebugItem => ({
  rank: 1,
  source: 'docs/intro.md',
  snippet: 'retrieval snippet',
  score: 0.8765,
  channel: 'semantic',
  matched_terms: ['retrieval', 'snippet'],
  ...patch,
})

describe('KbRetrievalDebugList', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders nothing for empty items', () => {
    const { container } = render(<KbRetrievalDebugList title="Top" items={[]} />)

    expect(container.firstChild).toBeNull()
  })

  it('renders ranked retrieval candidates with feedback and matched terms', () => {
    render(
      <KbRetrievalDebugList
        title="Top"
        items={[
          item({
            feedback_positive_count: 2,
            feedback_negative_count: 1,
            feedback_net: 1,
            feedback_boost: 0.1234,
          }),
        ]}
        tone="green"
      />,
    )

    expect(screen.getByText('Top')).toBeInTheDocument()
    expect(screen.getByText('#1')).toHaveClass('text-accent-green')
    expect(screen.getByText('docs/intro.md')).toBeInTheDocument()
    expect(screen.getByText('分数 0.876')).toBeInTheDocument()
    expect(screen.getByText('retrieval snippet')).toBeInTheDocument()
    expect(screen.getByText('retrieval')).toBeInTheDocument()
    expect(screen.getByText('反馈 +2/-1')).toBeInTheDocument()
    expect(screen.getByText('boost +0.123')).toBeInTheDocument()
  })
})
