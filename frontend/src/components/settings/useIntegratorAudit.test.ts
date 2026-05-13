import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { IntegratorAuditEvent, IntegratorAuditEventsResponse } from '../../api/client'
import { useIntegratorAudit } from './useIntegratorAudit'

const mocks = vi.hoisted(() => ({
  getIntegratorAuditEvents: vi.fn(),
}))

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client')
  return {
    ...actual,
    getIntegratorAuditEvents: mocks.getIntegratorAuditEvents,
  }
})

const auditEvent = (patch: Partial<IntegratorAuditEvent> = {}): IntegratorAuditEvent => ({
  timestamp: 1_715_000_000,
  action: 'connector.test',
  result: 'success',
  connector_id: 'connector-1',
  connector_type: 'webhook',
  actor: 'admin',
  request_id: 'request-1',
  details: {},
  ...patch,
})

const auditResponse = (events: IntegratorAuditEvent[]): IntegratorAuditEventsResponse => ({
  events,
  total: events.length,
  limit: 20,
})

describe('useIntegratorAudit', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  it('loads audit events successfully', async () => {
    const events = [
      auditEvent(),
      auditEvent({ action: 'connector.save', request_id: 'request-2' }),
    ]
    mocks.getIntegratorAuditEvents.mockResolvedValue(auditResponse(events))

    const { result } = renderHook(() => useIntegratorAudit())

    await act(async () => {
      await result.current.loadAuditEvents()
    })

    expect(mocks.getIntegratorAuditEvents).toHaveBeenCalledWith(20)
    expect(result.current.auditEvents).toEqual(events)
    expect(result.current.auditError).toBeNull()
    expect(result.current.auditLoading).toBe(false)
  })

  it('captures load failures', async () => {
    mocks.getIntegratorAuditEvents.mockRejectedValue(new Error('audit unavailable'))

    const { result } = renderHook(() => useIntegratorAudit())

    await act(async () => {
      await result.current.loadAuditEvents()
    })

    expect(result.current.auditError).toBe('audit unavailable')
    expect(result.current.auditEvents).toEqual([])
    expect(result.current.auditLoading).toBe(false)
  })

  it('restores loading after the load completes', async () => {
    let resolveAuditEvents: (payload: IntegratorAuditEventsResponse) => void = () => undefined
    const pendingAuditEvents = new Promise<IntegratorAuditEventsResponse>((resolve) => {
      resolveAuditEvents = resolve
    })
    mocks.getIntegratorAuditEvents.mockReturnValue(pendingAuditEvents)

    const { result } = renderHook(() => useIntegratorAudit())

    let loadPromise: Promise<void> = Promise.resolve()
    await act(async () => {
      loadPromise = result.current.loadAuditEvents()
    })

    expect(result.current.auditLoading).toBe(true)

    await act(async () => {
      resolveAuditEvents(auditResponse([auditEvent()]))
      await loadPromise
    })

    expect(result.current.auditLoading).toBe(false)
  })
})
