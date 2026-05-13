import { describe, expect, it, vi } from 'vitest'

import type { SecurityAuditSummary } from '../../api/client'
import {
  activeSecurityAuditCategoryCount,
  activeSecurityAuditCategoryLabel,
  barClass,
  buildRetentionPreview,
  clampText,
  compactAuditEventFilters,
  formatCountName,
  formatDetailValue,
  formatDetails,
  formatRetentionCount,
  formatTimestamp,
  hasAuditEventFilters,
  normalizeError,
  parseDatetimeLocalSeconds,
  parseRetentionKeepLatest,
  resultBadgeClass,
  securityAuditResultOptions,
  sortedCountEntries,
  valueClass,
} from './securityAuditSummaryModel'

describe('securityAuditSummaryModel', () => {
  it('normalizes errors and falls back for non-error values', () => {
    expect(normalizeError(new Error('boom'))).toBe('boom')
    expect(normalizeError('', 'fallback')).toBe('fallback')
    expect(normalizeError(0, 'fallback')).toBe('fallback')
  })

  it('sorts count entries by descending count then name and filters invalid counts', () => {
    expect(sortedCountEntries({ c: 2, b: 2, a: 4, bad: 0, nope: Number.NaN })).toEqual([
      ['a', 4],
      ['b', 2],
      ['c', 2],
    ])
  })

  it('derives summary controller labels and options', () => {
    const summary: SecurityAuditSummary = {
      category: '',
      categories: ['auth'],
      total: 3,
      recent_count: 3,
      window_limit: 200,
      action_counts: {},
      result_counts: { blocked: 2, allowed: 1, ignored: 0 },
      category_counts: { auth: 2, audit: 1 },
      unknown_action_count: 0,
    }

    expect(activeSecurityAuditCategoryLabel('auth')).toBe('Auth')
    expect(activeSecurityAuditCategoryLabel('all')).toBe('All')
    expect(activeSecurityAuditCategoryCount(summary)).toBe(2)
    expect(activeSecurityAuditCategoryCount(null)).toBe(0)
    expect(securityAuditResultOptions(summary)).toEqual(['blocked', 'allowed'])
    expect(securityAuditResultOptions(null)).toEqual([])
  })

  it('formats names and text snippets', () => {
    expect(formatCountName('  hello  ')).toBe('hello')
    expect(formatCountName('   ')).toBe('unknown')
    expect(clampText('short', 10)).toBe('short')
    expect(clampText('abcdefghijklmnopqrstuvwxyz', 8)).toBe('abcdefg...')
  })

  it('formats timestamps and datetime-local values', () => {
    const toLocaleString = vi.spyOn(Date.prototype, 'toLocaleString').mockReturnValue('2024-01-01 08:00:00')

    expect(formatTimestamp(1_700_000_000)).toBe('2024-01-01 08:00:00')
    expect(formatTimestamp(Number.NaN)).toBe('-')
    expect(toLocaleString).toHaveBeenCalledWith('zh-CN', { hour12: false })

    toLocaleString.mockRestore()

    expect(parseDatetimeLocalSeconds('')).toBeUndefined()
    expect(parseDatetimeLocalSeconds('not-a-date')).toBeUndefined()
    expect(parseDatetimeLocalSeconds('2024-01-01T08:00')).toBe(
      Math.floor(new Date('2024-01-01T08:00').getTime() / 1000),
    )
  })

  it('formats retention counts, details, and detail values', () => {
    expect(formatRetentionCount(12)).toBe('12')
    expect(formatRetentionCount('12')).toBe('-')
    expect(formatDetailValue(null)).toBe('null')
    expect(formatDetailValue('  hi  ')).toBe('hi')
    expect(formatDetailValue(true)).toBe('true')
    expect(formatDetailValue({ a: 1 })).toBe('{"a":1}')
    expect(formatDetails('  note  ')).toBe('note')
    expect(formatDetails({})).toBe('-')
    expect(formatDetails({ reason: 'missing_token', count: 2 })).toBe('reason=missing_token | count=2')
  })

  it('parses retention keep latest values and builds previews', () => {
    expect(parseRetentionKeepLatest('200.9')).toBe(200)
    expect(parseRetentionKeepLatest('-1')).toBe(0)
    expect(parseRetentionKeepLatest('bad')).toBe(0)
    expect(buildRetentionPreview(250, 200)).toEqual({
      keep_latest: 200,
      would_delete_count: 50,
      remaining_count: 200,
      dry_run: true,
    })
    expect(buildRetentionPreview(50, 200)).toEqual({
      keep_latest: 200,
      would_delete_count: 0,
      remaining_count: 50,
      dry_run: true,
    })
  })

  it('derives badge and bar classes from audit result names', () => {
    expect(resultBadgeClass('success')).toContain('bg-accent-green')
    expect(resultBadgeClass('blocked')).toContain('bg-accent-red')
    expect(barClass('category', 'auth')).toBe('bg-amber-300')
    expect(valueClass('result', 'allowed')).toBe('text-accent-green')
  })

  it('compacts and detects audit event filters', () => {
    const compact = compactAuditEventFilters({
      action: '  read  ',
      result: ' ',
      category: ' audit ',
      user_id: '  user-1 ',
      since: 12.9,
      until: Number.POSITIVE_INFINITY,
    })

    expect(compact).toEqual({
      action: 'read',
      result: '',
      category: 'audit',
      user_id: 'user-1',
      since: 12,
      until: undefined,
    })
    expect(hasAuditEventFilters(compact)).toBe(true)
    expect(hasAuditEventFilters({})).toBe(false)
  })
})
