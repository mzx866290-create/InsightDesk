import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { KbRetrievalControls, type KbRetrievalControlsProps } from './KbRetrievalControls'

function createProps(overrides: Partial<KbRetrievalControlsProps> = {}): KbRetrievalControlsProps {
  return {
    query: 'retrieval question',
    loading: false,
    mode: 'semantic',
    searchK: 5,
    fetchK: 10,
    useRerank: false,
    testIdPrefix: 'kb-test',
    onQueryChange: vi.fn(),
    onModeChange: vi.fn(),
    onSearchKChange: vi.fn(),
    onFetchKChange: vi.fn(),
    onUseRerankChange: vi.fn(),
    onTest: vi.fn(),
    ...overrides,
  }
}

describe('KbRetrievalControls', () => {
  afterEach(() => {
    cleanup()
  })

  it('forwards query, mode, rerank and run actions', () => {
    const props = createProps()

    render(<KbRetrievalControls {...props} />)

    fireEvent.change(screen.getByTestId('kb-test-query'), {
      target: { value: 'new query' },
    })
    fireEvent.change(screen.getByTestId('kb-test-mode'), {
      target: { value: 'hybrid' },
    })
    fireEvent.click(screen.getByTestId('kb-test-rerank'))
    fireEvent.click(screen.getByTestId('kb-test-run'))

    expect(props.onQueryChange).toHaveBeenCalledWith('new query')
    expect(props.onModeChange).toHaveBeenCalledWith('hybrid')
    expect(props.onUseRerankChange).toHaveBeenCalledWith(true)
    expect(props.onTest).toHaveBeenCalledTimes(1)
  })

  it('clamps numeric inputs and keeps diagnostic fetch K hidden until rerank is enabled', () => {
    const props = createProps()
    const { rerender } = render(<KbRetrievalControls {...props} />)

    expect(screen.queryByTestId('kb-test-fetch-k')).not.toBeInTheDocument()

    fireEvent.change(screen.getByTestId('kb-test-search-k'), {
      target: { value: '99' },
    })

    expect(props.onSearchKChange).toHaveBeenCalledWith(20)

    rerender(<KbRetrievalControls {...props} useRerank searchK={8} />)
    fireEvent.change(screen.getByTestId('kb-test-fetch-k'), {
      target: { value: '3' },
    })

    expect(props.onFetchKChange).toHaveBeenCalledWith(8)
  })

  it('keeps tab fetch K visible and disables run for empty queries', () => {
    render(
      <KbRetrievalControls
        {...createProps({
          variant: 'tab',
          query: '   ',
        })}
      />,
    )

    expect(screen.getByTestId('kb-test-fetch-k')).toBeInTheDocument()
    expect(screen.getByTestId('kb-test-run')).toBeDisabled()
  })
})
