import { useCallback, useEffect, useState } from 'react'

import {
  getSecurityAuditSummary,
  getSecurityStatus,
  type SecurityAuditSummary,
  type SecurityAuditSummaryCategory,
  type SecurityStatusResponse,
} from '../../api/client'
import { normalizeError } from './securityAuditSummaryModel'

interface UseSecurityAuditSummaryDataOptions {
  category: SecurityAuditSummaryCategory
  limit: number
}

interface SecurityAuditSummaryData {
  summary: SecurityAuditSummary | null
  loading: boolean
  summaryError: string | null
  securityStatus: SecurityStatusResponse | null
  securityStatusError: string | null
  loadSummary: () => Promise<void>
  loadSecurityStatus: () => Promise<void>
  refreshSummaryAndStatus: () => void
}

export function useSecurityAuditSummaryData({
  category,
  limit,
}: UseSecurityAuditSummaryDataOptions): SecurityAuditSummaryData {
  const [summary, setSummary] = useState<SecurityAuditSummary | null>(null)
  const [loading, setLoading] = useState(false)
  const [summaryError, setSummaryError] = useState<string | null>(null)
  const [securityStatus, setSecurityStatus] = useState<SecurityStatusResponse | null>(null)
  const [securityStatusError, setSecurityStatusError] = useState<string | null>(null)

  const loadSecurityStatus = useCallback(async () => {
    setSecurityStatusError(null)
    try {
      const payload = await getSecurityStatus()
      setSecurityStatus(payload)
    } catch (err) {
      setSecurityStatus(null)
      setSecurityStatusError(normalizeError(err, 'Failed to load security status'))
    }
  }, [])

  const loadSummary = useCallback(async () => {
    setLoading(true)
    setSummaryError(null)
    try {
      const payload = await getSecurityAuditSummary(category, limit)
      setSummary(payload)
    } catch (err) {
      setSummaryError(normalizeError(err))
    } finally {
      setLoading(false)
    }
  }, [category, limit])

  useEffect(() => {
    void loadSummary()
  }, [loadSummary])

  useEffect(() => {
    void loadSecurityStatus()
  }, [loadSecurityStatus])

  const refreshSummaryAndStatus = useCallback(() => {
    void loadSecurityStatus()
    void loadSummary()
  }, [loadSecurityStatus, loadSummary])

  return {
    summary,
    loading,
    summaryError,
    securityStatus,
    securityStatusError,
    loadSummary,
    loadSecurityStatus,
    refreshSummaryAndStatus,
  }
}
