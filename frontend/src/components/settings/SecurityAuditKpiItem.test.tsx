import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { SecurityAuditKpiItem } from './SecurityAuditKpiItem'

describe('SecurityAuditKpiItem', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders label, value, and tone class', () => {
    render(<SecurityAuditKpiItem label="Share secret" value="Weak" tone="red" />)

    expect(screen.getByText('Share secret')).toBeInTheDocument()
    expect(screen.getByText('Weak')).toHaveClass('text-accent-red')
  })
})
