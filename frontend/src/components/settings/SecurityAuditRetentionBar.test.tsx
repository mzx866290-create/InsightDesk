import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { SecurityAuditRetentionBar } from './SecurityAuditRetentionBar'

describe('SecurityAuditRetentionBar', () => {
  afterEach(() => {
    cleanup()
  })

  it('keeps existing test ids and forwards input and button actions', () => {
    const onKeepLatestChange = vi.fn()
    const onPreview = vi.fn()
    const onCleanup = vi.fn()

    render(
      <SecurityAuditRetentionBar
        keepLatest="200"
        loading={null}
        result={null}
        error={null}
        onKeepLatestChange={onKeepLatestChange}
        onPreview={onPreview}
        onCleanup={onCleanup}
      />,
    )

    const input = screen.getByTestId('settings-security-audit-retention-keep-latest')
    expect(input).toHaveValue(200)

    fireEvent.change(input, { target: { value: '50' } })
    fireEvent.click(screen.getByTestId('settings-security-audit-retention-preview'))
    fireEvent.click(screen.getByTestId('settings-security-audit-retention-cleanup'))

    expect(onKeepLatestChange).toHaveBeenCalledWith('50')
    expect(onPreview).toHaveBeenCalledTimes(1)
    expect(onCleanup).toHaveBeenCalledTimes(1)
  })

  it('renders preview and cleanup result text', () => {
    const { rerender } = render(
      <SecurityAuditRetentionBar
        keepLatest="200"
        loading={null}
        result={{
          keep_latest: 200,
          would_delete_count: 25,
          remaining_count: 200,
          dry_run: true,
        }}
        error={null}
        onKeepLatestChange={vi.fn()}
        onPreview={vi.fn()}
        onCleanup={vi.fn()}
      />,
    )

    expect(screen.getByTestId('settings-security-audit-retention-result')).toHaveTextContent(
      'Would delete 25 events, remaining 200 with keep latest 200.',
    )

    rerender(
      <SecurityAuditRetentionBar
        keepLatest="200"
        loading={null}
        result={{
          keep_latest: 200,
          deleted_count: 10,
          remaining_count: 200,
          dry_run: false,
        }}
        error={null}
        onKeepLatestChange={vi.fn()}
        onPreview={vi.fn()}
        onCleanup={vi.fn()}
      />,
    )

    expect(screen.getByTestId('settings-security-audit-retention-result')).toHaveTextContent(
      'Deleted 10 events, remaining 200 with keep latest 200.',
    )
  })

  it('prioritizes error state over a retention result', () => {
    render(
      <SecurityAuditRetentionBar
        keepLatest="200"
        loading="cleanup"
        result={{
          keep_latest: 200,
          deleted_count: 10,
          remaining_count: 200,
          dry_run: false,
        }}
        error="Cleanup failed"
        onKeepLatestChange={vi.fn()}
        onPreview={vi.fn()}
        onCleanup={vi.fn()}
      />,
    )

    expect(screen.getByTestId('settings-security-audit-retention-error')).toHaveTextContent('Cleanup failed')
    expect(screen.queryByTestId('settings-security-audit-retention-result')).not.toBeInTheDocument()
    expect(screen.getByTestId('settings-security-audit-retention-cleanup')).toBeDisabled()
  })
})
