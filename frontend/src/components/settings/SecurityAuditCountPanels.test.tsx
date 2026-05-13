import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { SecurityAuditSummary } from '../../api/client'
import { SecurityAuditCountPanels } from './SecurityAuditCountPanels'

const securityAuditSummaryPayload: SecurityAuditSummary = {
  category: '',
  categories: ['auth', 'audit'],
  total: 12,
  recent_count: 5,
  window_limit: 200,
  action_counts: {
    remote_auth_guard: 3,
  },
  result_counts: {
    blocked: 2,
  },
  category_counts: {
    auth: 8,
    audit: 4,
  },
  unknown_action_count: 2,
}

describe('SecurityAuditCountPanels', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders the three count lists', () => {
    render(
      <SecurityAuditCountPanels
        summary={securityAuditSummaryPayload}
        selectedAction=""
        onSelectAction={vi.fn()}
      />,
    )

    expect(screen.getByTestId('settings-security-audit-actions')).toBeInTheDocument()
    expect(screen.getByTestId('settings-security-audit-results')).toBeInTheDocument()
    expect(screen.getByTestId('settings-security-audit-categories')).toBeInTheDocument()
  })

  it('forwards action selection clicks', () => {
    const onSelectAction = vi.fn()

    render(
      <SecurityAuditCountPanels
        summary={securityAuditSummaryPayload}
        selectedAction=""
        onSelectAction={onSelectAction}
      />,
    )

    fireEvent.click(screen.getByTestId('settings-security-audit-actions-row'))

    expect(onSelectAction).toHaveBeenCalledWith('remote_auth_guard')
  })

  it('does not render anything when summary is missing', () => {
    const { container } = render(
      <SecurityAuditCountPanels summary={null} selectedAction="" onSelectAction={vi.fn()} />,
    )

    expect(container).toBeEmptyDOMElement()
    expect(screen.queryByTestId('settings-security-audit-actions')).not.toBeInTheDocument()
  })
})
