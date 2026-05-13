import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  cleanupSecurityAuditEvents,
  getSecurityAuditEvents,
  type SecurityAuditEvent,
} from '../../api/client'
import {
  buildDraftAuditEventFilters,
  cleanupSecurityAuditEventsState,
  createSecurityAuditEventsPanelProps,
  loadSecurityAuditEventsState,
  normalizeAuditEventsCleanupError,
  normalizeAuditEventsLoadError,
} from './securityAuditEventsControllerModel'

vi.mock('../../api/client', () => ({
  cleanupSecurityAuditEvents: vi.fn(),
  getSecurityAuditEvents: vi.fn(),
}))

const auditEvent: SecurityAuditEvent = {
  timestamp: 1_715_000_000,
  action: 'remote_auth_guard',
  result: 'blocked',
  user_id: 'user-1',
  user_role: 'admin',
  auth_mode: 'token',
  auth_source: 'header',
  is_local: false,
  request_id: 'req-1',
  ip: '203.0.113.10',
  details: { reason: 'missing_token' },
}

describe('securityAuditEventsControllerModel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('builds compact event filters from draft form values', () => {
    expect(buildDraftAuditEventFilters({
      actionFilter: ' remote_auth_guard ',
      resultFilter: ' blocked ',
      categoryFilter: ' auth ',
      userFilter: ' user-1 ',
      sinceFilter: '2024-01-01T08:00',
      untilFilter: 'bad-date',
    })).toEqual({
      action: 'remote_auth_guard',
      result: 'blocked',
      category: 'auth',
      user_id: 'user-1',
      since: Math.floor(new Date('2024-01-01T08:00').getTime() / 1000),
      until: undefined,
    })
  })

  it('loads events with compact filters and exposes controller state shape', async () => {
    vi.mocked(getSecurityAuditEvents).mockResolvedValue({
      events: [auditEvent],
      total: 3,
      limit: 50,
    })

    await expect(loadSecurityAuditEventsState(50, {
      action: ' remote_auth_guard ',
      result: '',
      category: ' auth ',
      user_id: ' ',
      since: 12.9,
    })).resolves.toEqual({
      events: [auditEvent],
      total: 3,
      limit: 50,
    })

    expect(getSecurityAuditEvents).toHaveBeenCalledWith(50, {
      action: 'remote_auth_guard',
      result: '',
      category: 'auth',
      user_id: '',
      since: 12,
      until: undefined,
    })
  })

  it('runs retention cleanup before refreshing summary', async () => {
    const onSummaryRefresh = vi.fn().mockResolvedValue(undefined)
    vi.mocked(cleanupSecurityAuditEvents).mockResolvedValue({
      keep_latest: 200,
      deleted_count: 4,
      remaining_count: 200,
      dry_run: false,
    })

    await expect(cleanupSecurityAuditEventsState({
      keepLatest: 200,
      onSummaryRefresh,
    })).resolves.toEqual({
      keep_latest: 200,
      deleted_count: 4,
      remaining_count: 200,
      dry_run: false,
    })

    expect(cleanupSecurityAuditEvents).toHaveBeenCalledWith({ keep_latest: 200 })
    expect(onSummaryRefresh).toHaveBeenCalledTimes(1)
    expect(vi.mocked(cleanupSecurityAuditEvents).mock.invocationCallOrder[0]).toBeLessThan(
      onSummaryRefresh.mock.invocationCallOrder[0],
    )
  })

  it('normalizes load and cleanup errors with their specific fallback messages', () => {
    expect(normalizeAuditEventsLoadError(null)).toBe('Failed to load security audit events')
    expect(normalizeAuditEventsCleanupError(null)).toBe('Failed to cleanup security audit events')
    expect(normalizeAuditEventsLoadError(new Error('load failed'))).toBe('load failed')
  })

  it('maps events panel state and handlers without changing prop names', () => {
    const handlers = {
      onActionFilterChange: vi.fn(),
      onResultFilterChange: vi.fn(),
      onCategoryFilterChange: vi.fn(),
      onUserFilterChange: vi.fn(),
      onSinceFilterChange: vi.fn(),
      onUntilFilterChange: vi.fn(),
      onApplyFilters: vi.fn(),
      onResetFilters: vi.fn(),
      onRefresh: vi.fn(),
      onKeepLatestChange: vi.fn(),
      onPreviewRetention: vi.fn(),
      onCleanupRetention: vi.fn(),
    }

    const props = createSecurityAuditEventsPanelProps({
      events: [auditEvent],
      eventsTotal: 1,
      eventsLimit: 50,
      eventsLoading: false,
      eventsError: null,
      actionFilter: 'remote_auth_guard',
      resultFilter: 'blocked',
      categoryFilter: 'auth',
      userFilter: 'user-1',
      sinceFilter: '',
      untilFilter: '',
      resultOptions: ['blocked'],
      resetDisabled: false,
      retentionKeepLatest: '200',
      retentionLoading: null,
      retentionResult: null,
      retentionError: null,
    }, handlers)

    expect(props.events).toEqual([auditEvent])
    expect(props.actionFilter).toBe('remote_auth_guard')
    expect(props.onRefresh).toBe(handlers.onRefresh)
    expect(props.onCleanupRetention).toBe(handlers.onCleanupRetention)
  })
})
