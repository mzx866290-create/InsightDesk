import { useCallback, useState } from 'react'

import { getIntegratorAuditEvents } from '../../api/client'
import type { IntegratorAuditEvent } from '../../api/client'

export interface UseIntegratorAuditResult {
  auditEvents: IntegratorAuditEvent[]
  auditLoading: boolean
  auditError: string | null
  loadAuditEvents: () => Promise<void>
}

export function useIntegratorAudit(): UseIntegratorAuditResult {
  const [auditEvents, setAuditEvents] = useState<IntegratorAuditEvent[]>([])
  const [auditLoading, setAuditLoading] = useState(false)
  const [auditError, setAuditError] = useState<string | null>(null)

  const loadAuditEvents = useCallback(async () => {
    setAuditLoading(true)
    setAuditError(null)
    try {
      const payload = await getIntegratorAuditEvents(20)
      setAuditEvents(payload.events)
    } catch (err) {
      setAuditError(err instanceof Error ? err.message : String(err || 'Failed to load integration audit records'))
    } finally {
      setAuditLoading(false)
    }
  }, [])

  return {
    auditEvents,
    auditLoading,
    auditError,
    loadAuditEvents,
  }
}
