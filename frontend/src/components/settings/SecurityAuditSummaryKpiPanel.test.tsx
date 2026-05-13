import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import type { SecurityAuditSummary } from '../../api/client'
import { SecurityAuditSummaryKpiPanel } from './SecurityAuditSummaryKpiPanel'

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

describe('SecurityAuditSummaryKpiPanel', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders summary KPI copy and unknown action warning tone', () => {
    render(
      <SecurityAuditSummaryKpiPanel
        activeCategoryCount={2}
        activeCategoryLabel="Auth"
        summary={securityAuditSummaryPayload}
      />,
    )

    expect(screen.getByText('Category')).toBeInTheDocument()
    expect(screen.getByText('Auth')).toBeInTheDocument()
    expect(screen.getByText('Total')).toBeInTheDocument()
    expect(screen.getByText('12')).toBeInTheDocument()
    expect(screen.getByText('Recent / window')).toBeInTheDocument()
    expect(screen.getByText('5 / 200')).toBeInTheDocument()
    expect(screen.getByText('Active categories')).toBeInTheDocument()
    expect(screen.getByText('Unknown actions')).toBeInTheDocument()
    expect(
      within(screen.getByText('Unknown actions').closest('div') as HTMLElement).getByText('2'),
    ).toHaveClass('text-accent-red')
  })

  it('renders empty placeholders when summary is missing', () => {
    render(
      <SecurityAuditSummaryKpiPanel
        activeCategoryCount={0}
        activeCategoryLabel="All"
        summary={null}
      />,
    )

    expect(screen.getByText('All')).toBeInTheDocument()
    expect(screen.getByText('Active categories')).toBeInTheDocument()
    expect(screen.getByText('0')).toBeInTheDocument()
    expect(within(screen.getByText('Total').closest('div') as HTMLElement).getByText('-')).toBeInTheDocument()
    expect(within(screen.getByText('Recent / window').closest('div') as HTMLElement).getByText('-')).toBeInTheDocument()
    expect(within(screen.getByText('Unknown actions').closest('div') as HTMLElement).getByText('-')).toBeInTheDocument()
  })
})
