import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { TraceOperationsMessage } from './TraceOperationsMessage'

describe('TraceOperationsMessage', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders nothing without a message', () => {
    const { container } = render(<TraceOperationsMessage error={null} notice={null} />)

    expect(container.firstChild).toBeNull()
  })

  it('prefers errors over notices', () => {
    render(<TraceOperationsMessage error="Failed" notice="Trace cleared" />)

    const message = screen.getByTestId('settings-trace-message')
    expect(message).toHaveTextContent('Failed')
    expect(message).toHaveClass('text-accent-red')
  })

  it('renders notices with the success tone', () => {
    render(<TraceOperationsMessage error={null} notice="Trace cleared" />)

    const message = screen.getByTestId('settings-trace-message')
    expect(message).toHaveTextContent('Trace cleared')
    expect(message).toHaveClass('text-accent-green')
  })
})
